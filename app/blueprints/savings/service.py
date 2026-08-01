"""Savings interest accrual: compute interest Trading 212's API never exposes.

Notion is the single source of truth. Every account row with an ``Earns
Interest`` checkbox ticked accrues that day's interest — at the
compound-equivalent daily rate for its ``AER`` — into an ``Accrued Interest``
number on the same row (:func:`accrue_interest`). On the account's payment day
the running total is filed as an ``income`` transaction through the untouched
transactions core and the accrual is reset (:func:`pay_accrued_interest`).

State lives entirely in the account row (``Accrued Interest``, ``Last Accrued``,
``Last Interest Paid``), so there is no local ledger to keep in sync and the
feature survives a PythonAnywhere disk reset. :func:`sync_savings_interest`
drives the daily pass and writes the new state back with ``update_page``.
"""

from datetime import date, datetime

from app.blueprints.transactions.service import (
    TransactionError,
    _resolve_card_accounts,
    save_transaction,
)
from app.notion_client import NotionClient, NotionError

_ARCHIVED_PROPERTY = "Archived"
_DAYS_PER_YEAR = 365


class SavingsError(Exception):
    """A savings failure carrying the HTTP status the client should see.

    Mirrors :class:`~app.blueprints.transactions.service.TransactionError` so the
    message flows into the ``{status, message}`` shape the caller treats as an
    error (it keys off the presence of ``status``).
    """

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def daily_rate(aer: float) -> float:
    """Return the compound-equivalent daily rate for an annual ``aer``.

    ``(1 + aer) ** (1/365) - 1`` — the rate that, compounded 365 times, equals
    the quoted AER, so accruing it each day on the balance already reflects the
    annual compounding without any intra-month compounding of its own.
    """
    return (1 + aer) ** (1 / _DAYS_PER_YEAR) - 1


def interest_accounts(client: NotionClient, config) -> tuple[list[dict], list[str]]:
    """Return ``(accounts, warnings)`` for every interest-earning account.

    Reads the Accounts data source in full and keeps rows whose ``Earns
    Interest`` checkbox is ticked and ``Archived`` is not. Each kept account is a
    plain dict of the parsed config + state values the accrual works on. A row
    missing its AER or balance cannot accrue, so it is skipped with a warning
    rather than guessed at.
    """
    data_source_id = config.get("ACCOUNTS_DS_ID")
    if not data_source_id:
        raise SavingsError("Server has no ACCOUNTS_DS_ID configured", code=500)

    earns_prop = config.get("SAVINGS_EARNS_INTEREST_PROPERTY")
    aer_prop = config.get("SAVINGS_AER_PROPERTY")
    payment_day_prop = config.get("SAVINGS_PAYMENT_DAY_PROPERTY")
    balance_prop = config.get("SAVINGS_BALANCE_PROPERTY")
    accrued_prop = config.get("SAVINGS_ACCRUED_PROPERTY")
    last_accrued_prop = config.get("SAVINGS_LAST_ACCRUED_PROPERTY")
    last_paid_prop = config.get("SAVINGS_LAST_PAID_PROPERTY")

    accounts: list[dict] = []
    warnings: list[str] = []
    # Counters so an empty result explains itself instead of failing silently
    rows_read = 0
    rows_with_earns_prop = 0
    rows_enrolled = 0
    for page in client.query_all(data_source_id):
        rows_read += 1
        if earns_prop in page.get("properties", {}):
            rows_with_earns_prop += 1

        if not _checkbox(page, earns_prop) or _checkbox(page, _ARCHIVED_PROPERTY):
            continue
        rows_enrolled += 1

        name = _title(page) or "(untitled account)"
        aer_percent = _number(page, aer_prop)
        balance = _number(page, balance_prop)
        payment_day = _number(page, payment_day_prop)
        # AER, balance, and payment day are all required: without any one of them
        # the account cannot accrue or ever pay out, so it is not a valid
        # interest-earning account and is skipped rather than guessed at.
        if aer_percent is None or balance is None or payment_day is None:
            unreadable = []
            if aer_percent is None:
                unreadable.append(f"AER ({_number_diag(page, aer_prop)})")
            if balance is None:
                unreadable.append(f"balance ({_number_diag(page, balance_prop)})")
            if payment_day is None:
                unreadable.append(
                    f"payment day ({_number_diag(page, payment_day_prop)})"
                )
            warnings.append(
                f"Account {name!r} skipped — could not read a number for: "
                + "; ".join(unreadable)
                + "."
            )
            continue

        accounts.append({
            "page_id": page.get("id"),
            "name": name,
            "public_url": page.get("url"),
            "aer": aer_percent / 100,  # AER is entered as a percent, e.g. 3.6.
            "payment_day": int(payment_day),
            "balance": balance,
            "accrued": _number(page, accrued_prop) or 0.0,
            "last_accrued": _date(page, last_accrued_prop),
            "last_paid": _date(page, last_paid_prop),
        })

    # Only diagnose the "no enrolled rows" case here; 
    if rows_enrolled == 0:
        warnings.append(_no_accounts_reason(rows_read, rows_with_earns_prop, earns_prop))
    return accounts, warnings


def _no_accounts_reason(rows_read: int, rows_with_earns_prop: int, earns_prop: str) -> str:
    """Explain why no interest-earning account was found, for the response.

    Distinguishes the three silent failure modes that all otherwise surface as
    an empty ``accounts`` list: nothing in the data source, the enrol property
    not present on any row (a name mismatch), or the property present but never
    ticked (or the ticked rows are ``Archived``).
    """
    if rows_read == 0:
        return "No account rows were read from the Accounts data source."
    if rows_with_earns_prop == 0:
        return (
            f"Read {rows_read} account rows, but none has a property named "
            f"{earns_prop!r}. Check the Notion column name matches "
            "SAVINGS_EARNS_INTEREST_PROPERTY (names are case- and space-sensitive)."
        )
    return (
        f"Read {rows_read} account rows; {earns_prop!r} exists but is not ticked "
        "on any non-archived row. Tick it (and set AER + payment day) to enrol."
    )


def accrue_interest(account: dict, today: date) -> tuple[float, float]:
    """Return ``(new_accrued, added)`` for accruing ``account`` up to ``today``.

    A no-op (``added == 0``) when the account already accrued today, which keeps
    the daily pass idempotent. Otherwise adds one day's interest per elapsed day
    since ``Last Accrued`` (one day when it was never set), each computed on the
    *current* balance — missed days are caught up at today's balance as an
    approximation. The balance excludes the unpaid accrual, so interest never
    compounds within the month.
    """
    if account["last_accrued"] == today:
        return account["accrued"], 0.0

    last = account["last_accrued"]
    if last is None:
        days = 1
    else:
        # Guard a future/garbled Last Accrued: never accrue negative days.
        days = max((today - last).days, 1)

    added = days * account["balance"] * daily_rate(account["aer"])
    return account["accrued"] + added, added


def pay_accrued_interest(
    account: dict, config, today: date, card_label: str
) -> dict | None:
    """File the accrued interest as an income transaction, or return ``None``.

    Pays out on the account's payment day *or the first run after it that month*
    (so a missed run self-heals and any day-of-month is safe), once per month
    (guarded by ``Last Interest Paid``), and only when something has accrued.
    The payout goes
    through the trusted :func:`save_transaction` core as an ``income`` on
    ``card_label``; on success returns the reset state to persist
    (``accrued`` back to 0, ``last_paid`` set to today).
    """
    accrued = account["accrued"]
    if today.day < account["payment_day"] or accrued <= 0:
        return None
    if _in_month(account["last_paid"], today):
        return None

    save_transaction(
        {
            "type": "income",
            "card": card_label,
            "amount": accrued,
            "description": config.get("SAVINGS_INTEREST_NAME"),
            "datetime": today.isoformat(),
            "category": config.get("SAVINGS_INTEREST_CATEGORY"),
        },
        config,
    )
    return {"accrued": 0.0, "last_paid": today}


def sync_savings_interest(config, today: date | None = None) -> dict:
    """Accrue (and, on payment day, pay out) interest for every flagged account.

    For each interest-earning account: accrue today's slice, and if it is the
    payment day file the running total as a transaction, then persist the new
    ``Accrued Interest`` / ``Last Accrued`` / ``Last Interest Paid`` in a single
    ``update_page``. Accounts that already accrued today are skipped, so a task
    that fires twice never double-accrues or double-pays. Returns a per-account
    snapshot plus any warnings.
    """
    if today is None:
        today = date.today()

    client = NotionClient(config.get("NOTION_TOKEN"), config.get("NOTION_VERSION"))
    accounts, warnings = interest_accounts(client, config)
    label_by_page = _card_labels_by_page(client, config, warnings)

    accrued_prop = config.get("SAVINGS_ACCRUED_PROPERTY")
    last_accrued_prop = config.get("SAVINGS_LAST_ACCRUED_PROPERTY")
    last_paid_prop = config.get("SAVINGS_LAST_PAID_PROPERTY")
    today_iso = today.isoformat()

    results: list[dict] = []
    for account in accounts:
        if account["last_accrued"] == today:
            results.append(_snapshot(account, todays_interest=0.0, paid=False))
            continue

        new_accrued, added = accrue_interest(account, today)
        account["accrued"] = new_accrued

        properties = {
            accrued_prop: {"number": new_accrued},
            last_accrued_prop: {"date": {"start": today_iso}},
        }

        paid = False
        if today.day >= account["payment_day"] and new_accrued > 0 and not _in_month(
            account["last_paid"], today
        ):
            card_label = label_by_page.get(account["page_id"])
            if not card_label:
                warnings.append(
                    f"Account {account['name']!r} is due a payout but has no "
                    "matching account row to file it against; interest kept "
                    "accruing."
                )
            else:
                reset = pay_accrued_interest(account, config, today, card_label)
                if reset is not None:
                    account["accrued"] = reset["accrued"]
                    account["last_paid"] = reset["last_paid"]
                    properties[accrued_prop] = {"number": reset["accrued"]}
                    properties[last_paid_prop] = {"date": {"start": today_iso}}
                    paid = True

        account["last_accrued"] = today
        client.update_page(account["page_id"], properties)
        results.append(_snapshot(account, todays_interest=added, paid=paid))

    return {"accounts": results, "warnings": warnings}


def _card_labels_by_page(client: NotionClient, config, warnings: list[str]) -> dict:
    """Return a ``page id -> card label`` map for filing payouts.

    Reverses the transactions resolver's ``label -> page id`` map so a payout can
    name the account the same way an incoming transaction would. A resolver
    failure is downgraded to a warning: accrual still runs, only payouts are
    withheld until the accounts can be read.
    """
    try:
        card_map, _codenames = _resolve_card_accounts(client, config)
    except (TransactionError, NotionError) as exc:
        warnings.append(f"Could not resolve accounts for payouts ({exc}).")
        return {}

    labels: dict = {}
    for label, page_id in card_map.items():
        labels.setdefault(page_id, label)
    return labels


def _snapshot(account: dict, todays_interest: float, paid: bool) -> dict:
    """Shape one account's result row for the endpoint response."""
    return {
        "page_id": account["page_id"],
        "name": account["name"],
        "public_url": account["public_url"],
        "balance": account["balance"],
        "daily_rate": daily_rate(account["aer"]),
        "todays_interest": todays_interest,
        "accrued": account["accrued"],
        "paid": paid,
    }


def _in_month(day: date | None, today: date) -> bool:
    """Return whether ``day`` falls in the same calendar month as ``today``."""
    return day is not None and day.year == today.year and day.month == today.month


def _checkbox(page: dict, name: str) -> bool:
    """Return a named checkbox property's value, or ``False`` if absent."""
    prop = page.get("properties", {}).get(name) or {}
    return bool(prop.get("checkbox"))


def _number(page: dict, name: str) -> float | None:
    """Return a named number's value, or ``None`` if absent/blank.

    Reads both plain ``number`` properties and formula-typed ones (e.g.
    ``Current Balance``, whose value sits under ``formula.number``).
    """
    prop = page.get("properties", {}).get(name) or {}
    prop_type = prop.get("type")
    # Formula and rollup wrap the numeric value one level deeper
    if prop_type == "formula":
        return (prop.get("formula") or {}).get("number")
    if prop_type == "rollup":
        return (prop.get("rollup") or {}).get("number")
    return prop.get("number")


def _number_diag(page: dict, name: str) -> str:
    """Describe why :func:`_number` could not read ``name`` — for a warning.

    Names the mismatch a user actually hits: no such column (a name typo), or a
    column of the wrong type (e.g. a ``date`` payment day, or a ``select`` AER)
    that holds no plain number.
    """
    prop = page.get("properties", {}).get(name)
    if prop is None:
        return f"no column named {name!r}"
    prop_type = prop.get("type")
    if prop_type == "formula":
        inner = (prop.get("formula") or {}).get("type")
        return f"column {name!r} is a formula returning {inner!r}, not a number"
    if prop_type == "rollup":
        inner = (prop.get("rollup") or {}).get("type")
        return f"column {name!r} is a rollup of type {inner!r}, not a single number"
    return f"column {name!r} is a {prop_type!r}, not a number"


def _date(page: dict, name: str) -> date | None:
    """Return a named date property's start as a :class:`datetime.date`, or None.

    Notion returns an ISO date or datetime string; only the calendar date
    matters for idempotency and the monthly payout guard.
    """
    prop = page.get("properties", {}).get(name) or {}
    value = (prop.get("date") or {}).get("start")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _title(page: dict) -> str:
    """Return a page's plain-text title via its title-typed property."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(part.get("plain_text", "") for part in prop.get("title", []))
    return ""

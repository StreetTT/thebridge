"""Digestion + saving: turn a raw transaction dict into a Notion page.

:func:`build_transaction` does the Notion-free parsing (amount sign,
card -> account page id, ``Date`` and ``Month`` from ``datetime``) and returns
the computed payload plus the name -> page-id relations still to resolve under
``pending_lookups``. :func:`save_transaction` resolves those lookups against
Notion, writes the page, and returns its id and url.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path

from app.blueprints.transactions import merchant_memory
from app.notion_client import NotionClient, NotionError

VALID_TYPES = ("expense", "income", "transfer")

# Maps a pending-lookup key to the Notion relation property it fills and the
# config key naming the data source to search.
_LOOKUP_TARGETS = {
    "Category": ("Category", "CATEGORIES_DS_ID"),
    "Month": ("Month", "MONTHS_DS_ID"),
    "To Account": ("To Account", "ACCOUNTS_DS_ID"),
}

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
# Real mapping is gitignored; fall back to the committed example so a fresh
# checkout still runs. Copy card_accounts.example.json -> card_accounts.json
# to customise per deployment.
_CARD_ACCOUNTS_PATH = _DATA_DIR / "card_accounts.json"
_CARD_ACCOUNTS_EXAMPLE_PATH = _DATA_DIR / "card_accounts.example.json"


class TransactionError(Exception):
    """A validation error carrying the HTTP status the client should see.

    The message ends up in the ``{status, message}`` response the Apple
    Shortcut treats as an error (it keys off the presence of ``status``).
    """

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def _load_card_accounts() -> dict:
    """Load the card-label -> account-page-id map from disk.

    Prefers the gitignored ``card_accounts.json`` and falls back to the
    committed ``card_accounts.example.json``. Read on each request so edits take
    effect without a reload; the file is tiny so this is cheap.
    """
    path = _CARD_ACCOUNTS_PATH if _CARD_ACCOUNTS_PATH.exists() else _CARD_ACCOUNTS_EXAMPLE_PATH
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise TransactionError(
            f"Could not read {path.name}: {exc}", code=500
        ) from exc


def parse_amount(raw_amount) -> float:
    """Return the absolute amount as a float, ignoring currency symbols.

    Mirrors the shortcut, which rips the digits out of strings like ``"£12.50"``.
    Numbers are accepted directly. Raises :class:`TransactionError` when no
    numeric value can be found.
    """
    if isinstance(raw_amount, bool):
        raise TransactionError("amount must be a number or numeric string")
    if isinstance(raw_amount, (int, float)):
        return abs(float(raw_amount))

    if raw_amount is None:
        raise TransactionError("amount is required")

    # Drop thousands separators, then grab the first number (with optional decimal).
    cleaned = str(raw_amount).replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        raise TransactionError(f"Could not parse an amount from {raw_amount!r}")
    return float(match.group())


def resolve_datetime(raw_datetime) -> tuple[str, str]:
    """Return ``(iso_date, month_name)`` from an ISO 8601 string.

    Falls back to "now" when ``datetime`` is missing or unparseable. The month
    name is formatted like Notion's Months rows, e.g. ``"Jul 2026"``.
    """
    parsed = None
    if raw_datetime:
        text = str(raw_datetime).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = None
    if parsed is None:
        parsed = datetime.now()

    return parsed.isoformat(), parsed.strftime("%b %Y")


def _sign_and_role(amount: float, txn_type: str) -> tuple[float, str]:
    """Apply the sign convention and pick which account relation the card fills.

    expense = -abs (From Account); income = +abs (To Account);
    transfer = -abs (From Account, with a separate ``to_account`` destination).
    """
    if txn_type == "income":
        return amount, "To Account"
    # expense and transfer are both outgoing from the card's account.
    return -amount, "From Account"


def build_transaction(raw: dict, config) -> dict:
    """Digest a raw transaction dict into a computed Notion payload (no write).

    Returns a structure with the parsed fields, the ``notion_payload`` we can
    build now (parent + properties whose ids are already known), and
    ``pending_lookups`` for name-based relations Phase 2 will resolve.
    """
    txn_type = (raw.get("type") or "expense").strip().lower()
    if txn_type not in VALID_TYPES:
        raise TransactionError(
            f"type must be one of {', '.join(VALID_TYPES)} (got {txn_type!r})"
        )

    card = raw.get("card")
    if not card:
        raise TransactionError("card is required")

    card_accounts = _load_card_accounts()
    account_page_id = card_accounts.get(card)
    if not account_page_id:
        known = ", ".join(sorted(card_accounts)) or "none configured"
        raise TransactionError(
            f"Unknown card {card!r}. Known cards: {known}."
        )

    amount = parse_amount(raw.get("amount"))
    signed_amount, account_role = _sign_and_role(amount, txn_type)

    iso_date, month_name = resolve_datetime(raw.get("datetime"))

    # description -> Name, defaulting to the merchant.
    name = (raw.get("description") or raw.get("merchant") or "").strip()
    if not name:
        raise TransactionError("one of description or merchant is required for the title")

    category_name = (raw.get("category") or "").strip() or None
    to_account_name = (raw.get("to_account") or "").strip() or None

    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Amount": {"number": signed_amount},
        "Date": {"date": {"start": iso_date}},
        account_role: {"relation": [{"id": account_page_id}]},
    }

    notes = (raw.get("notes") or "").strip()
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

    notion_payload = {
        "parent": {
            "type": "data_source_id",
            "data_source_id": config.get("TRANSACTIONS_DS_ID"),
        },
        "properties": properties,
    }

    # Relations resolved by name in Phase 2 (need a Notion lookup for the id).
    pending_lookups: dict[str, str] = {}
    if category_name:
        pending_lookups["Category"] = category_name
    pending_lookups["Month"] = month_name
    if txn_type == "transfer" and to_account_name:
        pending_lookups["To Account"] = to_account_name

    return {
        "type": txn_type,
        "parsed": {
            "name": name,
            "amount": signed_amount,
            "date": iso_date,
            "month_name": month_name,
            "account_role": account_role,
            "account_page_id": account_page_id,
            "category_name": category_name,
            "to_account_name": to_account_name,
        },
        "notion_payload": notion_payload,
        "pending_lookups": pending_lookups,
    }


# Full category list is returned on every response so the shortcut can always
# offer a "change category" option, even after an auto-fill. Categories change
# rarely, so cache the list in-process to avoid a Notion query per transaction;
# a new Notion category shows up once the short TTL lapses.
_CATEGORY_CACHE_TTL = 3600  # seconds
_category_cache: dict = {"ds": None, "names": None, "expires": 0.0}


def _all_category_names(client: NotionClient, config) -> tuple[list[str], str | None]:
    """Return every category name for the shortcut's picker (cached).

    Returns ``(names, warning)``; ``names`` is empty and ``warning`` set when the
    data source is unconfigured or the listing errors with no cache to fall back
    on, so the caller can still respond (with a blank menu) rather than fail.
    """
    data_source_id = config.get("CATEGORIES_DS_ID")
    if not data_source_id:
        return [], "No CATEGORIES_DS_ID configured; all_categories unavailable."

    now = time.monotonic()
    fresh = (
        _category_cache["ds"] == data_source_id
        and _category_cache["names"] is not None
        and now < _category_cache["expires"]
    )
    if fresh:
        return list(_category_cache["names"]), None

    try:
        names = client.list_names(data_source_id)
    except NotionError as exc:
        # Serve a stale list if we have one; only report unavailable otherwise.
        if _category_cache["ds"] == data_source_id and _category_cache["names"] is not None:
            return list(_category_cache["names"]), None
        return [], f"Could not list categories ({exc}); all_categories unavailable."

    _category_cache.update(ds=data_source_id, names=names, expires=now + _CATEGORY_CACHE_TTL)
    return list(names), None


def save_transaction(raw: dict, config) -> dict:
    """Digest ``raw``, resolve its name-based relations, and create the page.

    Category is chosen before the write: an explicit ``category`` wins;
    otherwise merchant memory decides. Exactly one known category auto-fills;
    two-or-more (ambiguous) or none (unknown merchant) leave it blank and flag
    ``needs_category`` so the shortcut can prompt from ``candidates`` (ordered
    most-used first). ``all_categories`` and the applied ``category`` are always
    returned so the shortcut can offer a "change category" option even when a
    single category was auto-filled. Whenever a category is actually applied, it
    is learned against the merchant.

    Each pending relation (``Category``, ``Month``, transfer ``To Account``) is
    looked up by name in Notion. Resolution is best-effort and never blocks the
    write: a hit is added to the page properties, while a miss, a missing data
    source id, or a lookup that errors is skipped and recorded as a
    human-readable warning. Only the final page create can fail the request.

    Returns ``{"page_id", "public_url", "category", "warnings",
    "needs_category", "candidates", "all_categories"}``. Raises
    :class:`TransactionError` for bad input and
    :class:`~app.notion_client.NotionError` only when the page create itself
    fails.
    """
    digested = build_transaction(raw, config)
    payload = digested["notion_payload"]
    properties = payload["properties"]
    merchant = raw.get("merchant") or ""

    client = NotionClient(config.get("NOTION_TOKEN"), config.get("NOTION_VERSION"))
    warnings: list[str] = []

    # Decide the category: explicit input wins, otherwise consult memory.
    category_to_learn = digested["parsed"]["category_name"]
    needs_category = False
    candidates: list[str] = []
    if not category_to_learn:
        known = merchant_memory.candidates(merchant_memory.load(), merchant)
        if len(known) == 1:
            digested["pending_lookups"]["Category"] = known[0]
            category_to_learn = known[0]
        else:
            needs_category = True
            candidates = known  # empty when unknown, ordered when ambiguous

    # Always offer the full list so the pick can be changed later, even after an
    # auto-fill or an explicit category.
    all_categories, cat_warning = _all_category_names(client, config)
    if cat_warning:
        warnings.append(cat_warning)

    for field, name in digested["pending_lookups"].items():
        prop_name, ds_key = _LOOKUP_TARGETS[field]
        data_source_id = config.get(ds_key)
        if not data_source_id:
            warnings.append(f"No data source configured for {field}; left blank.")
            continue
        try:
            page_id = client.query_by_name(data_source_id, name)
        except NotionError as exc:
            warnings.append(f"Could not resolve {field} {name!r} ({exc}); left blank.")
            continue
        if page_id:
            properties[prop_name] = {"relation": [{"id": page_id}]}
        else:
            warnings.append(f"No {field} match for {name!r}; left blank.")

    page_id, public_url = client.create_page(payload)

    # Only learn once the page exists, and only when a category was applied.
    if category_to_learn:
        merchant_memory.record(merchant, category_to_learn)

    return {
        "page_id": page_id,
        "public_url": public_url,
        "category": category_to_learn,
        "warnings": warnings,
        "needs_category": needs_category,
        "candidates": candidates,
        "all_categories": all_categories,
    }


def set_category(page_id: str, body, config) -> dict:
    """Set the ``Category`` relation on an existing page and learn the pick.

    Body is ``{"merchant": ..., "category": ...}``. Resolves the category name to
    its Notion page id, patches the relation, and records the merchant->category
    association. Returns ``{"page_id", "category"}``.
    """
    if not isinstance(body, dict):
        raise TransactionError("Request body must be a JSON object")

    category = (body.get("category") or "").strip()
    if not category:
        raise TransactionError("category is required")
    merchant = body.get("merchant") or ""

    data_source_id = config.get("CATEGORIES_DS_ID")
    if not data_source_id:
        raise TransactionError("Server has no CATEGORIES_DS_ID configured", code=500)

    client = NotionClient(config.get("NOTION_TOKEN"), config.get("NOTION_VERSION"))
    category_page_id = client.query_by_name(data_source_id, category)
    if not category_page_id:
        raise TransactionError(f"No Category match for {category!r}", code=404)

    client.update_page(page_id, {"Category": {"relation": [{"id": category_page_id}]}})
    merchant_memory.record(merchant, category)
    return {"page_id": page_id, "category": category}

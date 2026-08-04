"""Digestion + saving: turn a raw transaction dict into a Notion page.

:func:`build_transaction` does the Notion-free parsing (amount sign,
card -> account page id, ``Date`` and ``Month`` from ``datetime``) and returns
the computed payload plus the name -> page-id relations still to resolve under
``pending_lookups``. :func:`save_transaction` resolves those lookups against
Notion, writes the page, and returns its id and url.
"""

import json
import logging
import re
import time
from datetime import datetime

from app.blueprints.transactions import merchant_memory
from app.notion_client import NotionClient, NotionError

_log = logging.getLogger(__name__)

VALID_TYPES = ("expense", "income", "transfer")

# Maps a pending-lookup key to the Notion relation property it fills and the
# config key naming the data source to search.
_LOOKUP_TARGETS = {
    "Category": ("Category", "CATEGORIES_DS_ID"),
    "Month": ("Month", "MONTHS_DS_ID"),
}


class TransactionError(Exception):
    """A validation error carrying the HTTP status the client should see.

    The message ends up in the ``{status, message}`` response the Apple
    Shortcut treats as an error (it keys off the presence of ``status``).
    """

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


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


def build_transaction(raw: dict, config, card_accounts: dict) -> dict:
    """Digest a raw transaction dict into a computed Notion payload (no write).

    ``card_accounts`` is the already-resolved lowercased ``label -> page id`` map
    (see :func:`_resolve_card_accounts`), so this stays Notion-free. Returns a
    structure with the parsed fields, the ``notion_payload`` we can build now
    (parent + properties whose ids are already known), and ``pending_lookups``
    for name-based relations.
    """
    txn_type = (raw.get("type") or "expense").strip().lower()
    if txn_type not in VALID_TYPES:
        raise TransactionError(
            f"type must be one of {', '.join(VALID_TYPES)} (got {txn_type!r})"
        )

    card = raw.get("card")
    if not card:
        raise TransactionError("card is required")

    account_page_id = card_accounts.get(card.strip().lower())
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

    # A transfer also credits a destination account. Resolve it from the same
    # card_accounts label -> page-id map as the source so both ends link reliably
    if txn_type == "transfer" and to_account_name:
        to_account_page_id = card_accounts.get(to_account_name.strip().lower())
        if not to_account_page_id:
            known = ", ".join(sorted(card_accounts)) or "none configured"
            raise TransactionError(
                f"Unknown to_account {to_account_name!r}. Known accounts: {known}."
            )
        properties["To Account"] = {"relation": [{"id": to_account_page_id}]}

    notes = (raw.get("notes") or "").strip()
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

    # Client correlation id (also echoed on the HTTP response). Written when
    # present so the Notion row can be matched back to the originating request.
    client_id = raw.get("_id")
    if client_id is not None and str(client_id).strip():
        properties["_id"] = {
            "rich_text": [{"text": {"content": str(client_id).strip()}}]
        }

    # Store the exact input for debugging/audit. Notion caps a single rich_text
    # chunk at 2000 chars, so truncate the (normally tiny) payload to stay valid.
    raw_json = json.dumps(raw, ensure_ascii=False, sort_keys=True)[:2000]
    properties["rawPayload"] = {"rich_text": [{"text": {"content": raw_json}}]}

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
        _log.debug("Category list cache hit (%d names)", len(_category_cache["names"]))
        return list(_category_cache["names"]), None

    _log.debug("Category list cache miss; querying Notion")
    try:
        names = client.list_names(data_source_id)
    except NotionError as exc:
        # Serve a stale list if we have one; only report unavailable otherwise.
        if _category_cache["ds"] == data_source_id and _category_cache["names"] is not None:
            _log.debug("Category list using stale cache after Notion error")
            return list(_category_cache["names"]), None
        return [], f"Could not list categories ({exc}); all_categories unavailable."

    _category_cache.update(ds=data_source_id, names=names, expires=now + _CATEGORY_CACHE_TTL)
    return list(names), None


_ALIAS_PROPERTY = "Apple Card"
_ARCHIVED_PROPERTY = "Archived"
_ACCOUNTS_CACHE_TTL = 3600  # seconds
_accounts_cache: dict = {"ds": None, "map": None, "codenames": None, "expires": 0.0}


def _resolve_card_accounts(client: NotionClient, config) -> tuple[dict, list[str]]:
    """Return ``(card_map, codenames)`` for resolving an incoming card.

    ``card_map`` maps a lowercased label to an account page id, keyed by both the
    account's codename (page title) and its non-empty ``Apple Card`` alias, so a
    ``card`` matches either case-insensitively — the manual picker sends a
    codename, an Apple Pay tap sends the card name, and both land in the same
    keyspace. ``codenames`` are the account titles for the shortcut's picker, in
    reverse of Notion's order; archived accounts (the ``Archived`` checkbox
    ticked) are excluded.

    Notion is the sole source of truth, cached per :data:`_ACCOUNTS_CACHE_TTL`.
    When two rows claim the same label (an alias colliding with another account's
    codename, say), the later row in Notion's order wins the key; the collision
    is not silently ignored — it raises so the ambiguity gets fixed in Notion.
    Raises :class:`TransactionError` when ``ACCOUNTS_DS_ID`` is unset; a Notion
    query failure with no usable fresh cache propagates as
    :class:`~app.notion_client.NotionError`.
    """
    data_source_id = config.get("ACCOUNTS_DS_ID")
    if not data_source_id:
        raise TransactionError("Server has no ACCOUNTS_DS_ID configured", code=500)

    now = time.monotonic()
    fresh = (
        _accounts_cache["ds"] == data_source_id
        and _accounts_cache["map"] is not None
        and now < _accounts_cache["expires"]
    )
    if fresh:
        _log.debug("Accounts cache hit (%d labels)", len(_accounts_cache["map"]))
        return dict(_accounts_cache["map"]), list(_accounts_cache["codenames"])

    _log.debug("Accounts cache miss; querying Notion")
    try:
        accounts = client.list_accounts(data_source_id, _ALIAS_PROPERTY, _ARCHIVED_PROPERTY)
    except NotionError:
        # Serve a stale map if we have one; otherwise let the caller see the error
        # rather than guessing an account.
        if _accounts_cache["ds"] == data_source_id and _accounts_cache["map"] is not None:
            _log.debug("Accounts using stale cache after Notion error")
            return dict(_accounts_cache["map"]), list(_accounts_cache["codenames"])
        raise

    card_map: dict = {}
    codenames: list[str] = []
    for account in accounts:
        page_id = account["id"]
        codename = account["codename"]
        codenames.append(codename)
        for label in (codename, account.get("apple_card")):
            if not label:
                continue
            key = label.lower()
            existing = card_map.get(key)
            if existing and existing != page_id:
                raise TransactionError(
                    f"Account label {label!r} maps to two different accounts in "
                    "Notion; make each codename and Apple Card value unique.",
                    code=500,
                )
            card_map[key] = page_id

    _accounts_cache.update(
        ds=data_source_id, map=card_map, codenames=codenames, expires=now + _ACCOUNTS_CACHE_TTL
    )
    return dict(card_map), list(codenames)


def list_account_names(config) -> list[str]:
    """Return the account codenames for the shortcut's picker (cached resolver).

    Creates its own client and reuses :func:`_resolve_card_accounts`, so the list
    comes straight from Notion with the same caching behaviour.
    """
    client = NotionClient(config.get("NOTION_TOKEN"), config.get("NOTION_VERSION"))
    _card_map, codenames = _resolve_card_accounts(client, config)
    return codenames


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

    Each pending relation (``Category``, ``Month``) is looked up by name in
    Notion. Resolution is best-effort and never blocks the
    write: a hit is added to the page properties, while a miss, a missing data
    source id, or a lookup that errors is skipped and recorded as a
    human-readable warning. Only the final page create can fail the request.

    Returns ``{"page_id", "public_url", "category", "warnings",
    "needs_category", "candidates", "all_categories"}``. Raises
    :class:`TransactionError` for bad input and
    :class:`~app.notion_client.NotionError` only when the page create itself
    fails.
    """
    merchant = raw.get("merchant") or ""

    client = NotionClient(config.get("NOTION_TOKEN"), config.get("NOTION_VERSION"))
    warnings: list[str] = []

    # Resolve the card -> account map from Notion, so build_transaction 
    # stays Notion-free.
    card_accounts, _codenames = _resolve_card_accounts(client, config)

    digested = build_transaction(raw, config, card_accounts)
    payload = digested["notion_payload"]
    properties = payload["properties"]
    parsed = digested["parsed"]
    _log.debug(
        "Built transaction type=%s merchant=%r amount=%s",
        digested["type"],
        merchant,
        parsed["amount"],
    )

    # Decide the category: explicit input wins, otherwise consult memory.
    category_to_learn = parsed["category_name"]
    needs_category = False
    candidates: list[str] = []
    if not category_to_learn:
        known = merchant_memory.candidates(merchant_memory.load(), merchant)
        if len(known) == 1:
            digested["pending_lookups"]["Category"] = known[0]
            category_to_learn = known[0]
            _log.debug("Merchant memory auto-fill category=%r", category_to_learn)
        else:
            needs_category = True
            candidates = known  # empty when unknown, ordered when ambiguous
            _log.debug(
                "Merchant memory needs_category candidates=%d",
                len(candidates),
            )

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
            _log.debug("Resolved %s %r -> %s", field, name, page_id)
        else:
            warnings.append(f"No {field} match for {name!r}; left blank.")

    for warning in warnings:
        _log.warning("%s", warning)

    page_id, public_url = client.create_page(payload)

    # Only learn once the page exists, and only when a category was applied.
    if category_to_learn:
        merchant_memory.record(merchant, category_to_learn)

    _log.info(
        "created page_id=%s merchant=%r category=%r needs_category=%s",
        page_id,
        merchant,
        category_to_learn,
        needs_category,
    )

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
    association. Returns ``{"page_id", "public_url", "category"}`` — the
    ``public_url`` comes straight off the patched page so the shortcut can link
    to it after a category change too.
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
    _log.debug("Resolving category %r for page_id=%s", category, page_id)
    category_page_id = client.query_by_name(data_source_id, category)
    if not category_page_id:
        raise TransactionError(f"No Category match for {category!r}", code=404)

    updated = client.update_page(page_id, {"Category": {"relation": [{"id": category_page_id}]}})
    merchant_memory.record(merchant, category)
    _log.info(
        "category set page_id=%s category=%r merchant=%r",
        page_id,
        category,
        merchant,
    )
    return {
        "page_id": page_id,
        "public_url": updated.get("url"),
        "category": category,
    }

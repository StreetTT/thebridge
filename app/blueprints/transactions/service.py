"""Digestion: turn a raw transaction dict into a Notion page payload.

Phase 1 is a dry run. This module does all the parsing that does not require
talking to Notion (amount sign, card -> account page id, ``Date`` and ``Month``
from ``datetime``) and returns the computed payload. Fields that still need a
name -> page-id lookup (``Category``, ``Month``, transfer ``To Account``) are
returned separately under ``pending_lookups`` for Phase 2 to resolve.
"""

import json
import re
from datetime import datetime
from pathlib import Path

VALID_TYPES = ("expense", "income", "transfer")

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

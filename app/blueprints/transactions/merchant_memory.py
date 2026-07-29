"""JSON-backed merchant -> category memory (no AI).

Learns only from transactions posted through the bridge; it never reads or
analyses the existing Notion Transactions table. Stored on disk as
``{"tesco": {"Groceries": 5, "Household": 1}}`` — the merchant lowercased,
mapping each category it has been filed under to a running count.

The count decides how a merchant is auto-categorised: exactly one known
category auto-fills; two or more are returned as ordered ``candidates`` (most
used first) so the caller can prompt; none leaves the pick to the caller.
"""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
# Runtime-mutated, so gitignored (like card_accounts.json). Missing file reads
# as empty memory and is created on the first write.
_MEMORY_PATH = _DATA_DIR / "merchant_categories.json"


def _key(merchant: str | None) -> str:
    return (merchant or "").strip().lower()


def load() -> dict:
    """Return the memory dict, or ``{}`` if the file is absent or unreadable."""
    try:
        with open(_MEMORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def candidates(memory: dict, merchant: str | None) -> list[str]:
    """Known categories for ``merchant``, most-used first (ties broken by name).

    Empty when the merchant is unknown, one entry when unambiguous.
    """
    counts = memory.get(_key(merchant), {})
    return [name for name, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def record(merchant: str | None, category: str | None) -> None:
    """Increment ``merchant[category]`` and persist. No-op if either is blank."""
    key = _key(merchant)
    category = (category or "").strip()
    if not key or not category:
        return
    memory = load()
    counts = memory.setdefault(key, {})
    counts[category] = counts.get(category, 0) + 1
    _save(memory)


def _save(memory: dict) -> None:
    """Write memory to disk, replacing the file atomically to avoid corruption."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _MEMORY_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)
    tmp.replace(_MEMORY_PATH)

# Roadmap

[Docs](../index.md) › [Developers](./) › Roadmap

## Status

- **Phase 0 (Foundation) — done:** app factory + blueprints, `config.py`, `require_api_key` auth, `GET /health`. Deployable to PythonAnywhere.
- **Phase 1 (Digestion) — done:** `POST /transactions` validates the raw dict, signs the amount, maps `card` → account page id, and resolves `Date` + `Month` from `datetime`.
- **Phase 2 (Saving) — done:** `POST /transactions` writes to Notion. Resolves name-based relations (`Category`, `Month`, transfer `To Account`), creates the page, returns `201 {"page_id", "public_url"}`. Unmatched names are skipped (never block the write) and reported under `warnings`.
- **Phase 3 (Memory) — done:** JSON store remembers categories per merchant (learned only from bridge posts). One known category auto-fills; ambiguous/unknown merchants are created uncategorised with `needs_category`, then confirmed via `POST /transactions/<page_id>/category`.
- **Savings interest — done:** `POST /savings/accrue` accrues daily into Notion and files monthly income on payment day. See [Savings interest](../guides/savings-interest.md).

## Related

- [Architecture](./architecture.md)
- [Project structure](./project-structure.md)
- [Docs index](../index.md)

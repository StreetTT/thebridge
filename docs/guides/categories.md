# Categories

[Docs](../index.md) › [Guides](./) › Categories

## Overview

Remember which categories each merchant has been filed under, so the bridge can auto-fill when confident and prompt when not. Learning comes only from bridge posts — never by reading Notion transaction history.

## How it works

Merchant memory is a JSON store (`app/data/merchant_categories.json`) shaped like `{"tesco": {"Groceries": 5, "Household": 1}}`.

When `POST /transactions` omits `category`:

| Memory state | Behaviour |
| ------------ | --------- |
| One known category | Auto-filled; write proceeds as normal |
| Two or more (ambiguous) or none (unknown) | Row created uncategorised; response sets `needs_category` |

Every success response also carries:

- `category` — applied category, or `null`
- `all_categories` — every category in Notion (so the client can always offer "change category")

`candidates` (only with `needs_category`) are the merchant's known categories, most-used first (empty for an unknown merchant).

Whenever a category is actually applied (explicit, auto-filled, or confirmed via the category endpoint) it is learned against the merchant. The Notion category list is cached in-process for a few minutes.

Confirm or correct with `POST /transactions/<page_id>/category` — see [API](../reference/api.md#post-transactionspage_idcategory).

## Setup / enabling

1. Set `CATEGORIES_DS_ID` — [Configuration](../reference/configuration.md).
2. Share the Categories data source with the integration.
3. No per-merchant setup — memory fills as you log and confirm.

## Endpoints

- [`POST /transactions`](../reference/api.md#post-transactions) — may set `needs_category`
- [`POST /transactions/<page_id>/category`](../reference/api.md#post-transactionspage_idcategory) — confirm or change

## Warnings & gotchas

- `<page_id>` in the category URL must be the Notion `page_id` from create, not the client `_id`.
- A newly added Notion category may take a few minutes to appear in `all_categories`.
- `merchant_categories.json` is gitignored local state; a wiped disk loses learned associations (Notion rows are unaffected).

## Related

- [Notion schema](./notion-schema.md)
- [Transactions](./transactions.md)
- [Apple Shortcut](./apple-shortcut.md)
- [API reference](../reference/api.md)

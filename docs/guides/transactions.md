# Transactions

[Docs](../index.md) › [Guides](./) › Transactions

## Overview

Turn an HTTP POST into a Notion Transaction row: validate the raw dict, sign the amount, resolve accounts and name-based relations, and create the page.

## How it works

### Required fields

`card`, `amount`, and one of `description` / `merchant` are required. `type` defaults to `expense`.

### Amount and accounts

Amount is parsed by ripping digits (so `"£12.50"` → `12.5`) and signed by `type`:

| Type | Sign | Relations filled |
| ---- | ---- | ---------------- |
| `expense` | `-abs` | `From Account` from `card` |
| `income` | `+abs` | `To Account` from `card` |
| `transfer` | `-abs` | `From Account` from `card`, `To Account` from `to_account` |

Both transfer accounts resolve the same way as any `card` — see [Accounts](./accounts.md). An unknown `card` or `to_account` is rejected with an error listing known labels (never silently blank).

### Date and relations

`datetime` falls back to now when missing or unparseable. Name-based relations (`category` → Category, derived month → Month) are best-effort: a missing match or lookup error leaves the property blank and reports it under `warnings` on the success response — it never blocks the write.

### Audit fields

The exact input payload is written to a `rawPayload` rich-text property (JSON, truncated to Notion's 2000-char limit). When the request includes `_id`, that value is written to an `_id` rich-text property. Add both columns to the Transactions data source to capture them.

### Categories

If `category` is omitted, merchant memory may auto-fill or flag `needs_category`. See [Categories](./categories.md).

## Setup / enabling

1. Configure `NOTION_TOKEN` and the four `*_DS_ID` values — [Configuration](../reference/configuration.md).
2. Share Transactions, Accounts, Categories, and Months with the integration.
3. Optionally add `rawPayload` and `_id` text columns on Transactions.

## Endpoints

- [`POST /transactions`](../reference/api.md#post-transactions) — create a transaction

## Warnings & gotchas

- Relation skips (wrong category spelling, unshared data source) succeed with `warnings` — check that array.
- Transfer `to_account` uses the same label keyspace as `card` (codename or `Apple Card`).

## Related

- [Accounts](./accounts.md)
- [Categories](./categories.md)
- [Apple Shortcut](./apple-shortcut.md)
- [API reference](../reference/api.md)

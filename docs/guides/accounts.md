# Accounts

[Docs](../index.md) › [Guides](./) › Accounts

## Overview

Link cards to Notion account rows so `card` (and transfer `to_account`) resolve without a local mapping file. The mapping lives entirely in the Accounts data source.

## How it works

Each account row carries:

- its **codename** — the page title, e.g. `Revolut Visa`
- an `Apple Card` text (or select) property holding the exact card name Apple hands over

Resolution matches an incoming label against **either** the codename **or** the `Apple Card` value, exact and case-insensitive. Manual picker codenames and tap Apple card names share one keyspace.

Accounts with the `Archived` checkbox ticked are skipped (never resolved, never listed). Remaining accounts are returned in reverse of Notion's row order.

The resolved map is cached in-process for an hour, so a newly edited link may take a short while to appear. `GET /accounts` returns codenames for the shortcut's card picker and uses the same cache.

`ACCOUNTS_DS_ID` is required — there is no local fallback.

## Setup / enabling

1. Set `ACCOUNTS_DS_ID` — [Configuration](../reference/configuration.md).
2. To link a card, put the Apple-given name in the `Apple Card` property on the matching account row.
3. Leave `Apple Card` blank for accounts only chosen manually — the codename still resolves.
4. Tick `Archived` to hide an account from resolution and listings.

## Endpoints

- [`GET /accounts`](../reference/api.md#get-accounts) — list codenames for the picker
- [`POST /transactions`](../reference/api.md#post-transactions) — uses the same resolver for `card` / `to_account`

## Warnings & gotchas

- If two rows claim the same label (an `Apple Card` value colliding with another account's codename), the bridge refuses the map with an error — fix the clash in Notion.
- A request errors if `ACCOUNTS_DS_ID` is unset, Notion is unreachable with no cached map, or `card` matches nothing (error lists known labels).
- Cache TTL is about an hour; wait or restart the process after editing links.

## Related

- [Transactions](./transactions.md)
- [Apple Shortcut](./apple-shortcut.md)
- [Savings interest](./savings-interest.md) (payouts also need a resolvable card)
- [API reference](../reference/api.md)

# Architecture

[Docs](../index.md) › Developers › Architecture

## Overview

Flask app factory + blueprints. HTTP clients (Apple Shortcut or anything else) POST into The Bridge; the bridge validates, resolves Notion relations, and writes pages. Future phone-to-Notion features add a blueprint without touching existing routes.

## How it works

### App factory

`create_app()` in `app/__init__.py`:

1. Loads `Config` from the environment
2. Configures logging and optional Sentry
3. Binds request `client_id` from body `_id` (never invents an id)
4. Logs method/path/status/duration after each request
5. Maps unexpected exceptions to `{status: 500, message: "Internal error"}`
6. Registers blueprints: health, transactions, savings

### Auth

`require_api_key` checks the `X-API-Key` header against `API_SECRET`. Public: `GET /health` only.

### Notion client

`app/notion_client.py` wraps Notion HTTP: query by name, list names, query all, list accounts, create/update page. Domain services call it; routes stay thin.

### Data flow (transaction)

```text
POST /transactions
  → validate raw dict (card, amount, description|merchant, type, …)
  → sign amount; resolve card / to_account via Accounts map
  → resolve Category + Month by name (best-effort → warnings)
  → merchant memory may fill or flag needs_category
  → create Notion page (rawPayload, _id)
  → learn category if applied
  → 201 {page_id, public_url, category, all_categories, …}
```

### Caching

In-process caches (not durable across restarts):

- Accounts map / list — about an hour
- Category name list — a few minutes

### Merchant memory

JSON file under `app/data/` — learned only from bridge posts. Separate from Notion as source of truth for transactions and accrual state.

### Savings

`POST /savings/accrue` reads enrolled accounts from Notion, writes accrual fields back, and on payment day creates an income transaction through the same trusted write path as logging.

## Related

- [Project structure](./project-structure.md)
- [Roadmap](./roadmap.md)
- [API reference](../reference/api.md)

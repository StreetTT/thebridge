# Project structure

[Docs](../index.md) › [Developers](./) › Project structure

## Layout

```
flask_app.py                  # PythonAnywhere WSGI entry: exposes `application`
app/__init__.py               # create_app() factory; logging hooks + blueprints
app/config.py                 # env vars (secrets, DS IDs, savings property names)
app/logging_setup.py          # log format + client_id filter
app/sentry_setup.py           # optional Sentry init when SENTRY_DSN is set
app/auth.py                   # require_api_key decorator
app/notion_client.py          # Notion HTTP wrapper
app/blueprints/health/        # GET /health, GET /health/auth
app/blueprints/transactions/   # POST /transactions, GET /accounts, category
app/blueprints/transactions/merchant_memory.py  # JSON merchant → category store
app/blueprints/savings/        # POST /savings/accrue
app/data/merchant_categories.json    # learned merchant → category counts (gitignored)
docs/                         # published documentation (this tree)
```

The `card` → account mapping lives entirely in **Notion** (see [Accounts](../guides/accounts.md)); there is no local mapping file.

## Related

- [Architecture](./architecture.md)
- [Roadmap](./roadmap.md)
- [Getting started](../guides/getting-started.md)

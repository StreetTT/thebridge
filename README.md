# The Bridge

A minimal, extensible Flask service that turns HTTP POSTs (from an Apple Shortcut,
or any client) into Notion Transaction rows. Built with an app factory + blueprints
so future phone-to-Notion projects can add endpoints without touching existing ones.

## Status

- **Phase 0 (Foundation) — done:** app factory + blueprints, `config.py`,
  `require_api_key` auth, `GET /health`. Deployable to PythonAnywhere.
- **Phase 1 (Digestion) — done:** `POST /transactions` validates the raw dict,
  signs the amount, maps `card` -> account page id, and resolves `Date` +
  `Month` from `datetime`. It returns the computed Notion payload as a dry-run
  echo (no write yet). Name-based relations (`Category`, `Month`, transfer
  `To Account`) are returned under `pending_lookups` for Phase 2 to resolve.

## Layout

```
flask_app.py                  # PythonAnywhere WSGI entry: exposes `application`
app/__init__.py               # create_app() factory; registers blueprints
app/config.py                 # env vars (NOTION_TOKEN, API_SECRET) + Notion data source IDs
app/auth.py                   # require_api_key decorator (checks X-API-Key header)
app/blueprints/health/        # GET /health (public), GET /health/auth (key-protected)
app/blueprints/transactions/       # POST /transactions (dry-run digestion)
app/data/card_accounts.example.json  # card label -> Accounts page id template
```

Copy `app/data/card_accounts.example.json` to `app/data/card_accounts.json` and
edit the mappings for your deployment. The real file is gitignored; the loader
falls back to the example when it is absent.

## `POST /transactions` (Phase 1 dry run)

Send the shortcut's `raw dict` with the `X-API-Key` header. `card`, `amount`,
and one of `description`/`merchant` are required; `type` defaults to `expense`.

```bash
curl -X POST http://127.0.0.1:5000/transactions \
  -H "X-API-Key: <API_SECRET>" -H "Content-Type: application/json" \
  -d '{"merchant":"Tesco","card":"Revolut Visa","amount":"£12.50",
       "description":"Weekly shop","datetime":"2026-07-28T14:30:00",
       "category":"Groceries"}'
```

Returns `200` with `dry_run: true`, the `parsed` fields, the `notion_payload`
that will be sent to Notion, and `pending_lookups`. Errors use the
`{status, message}` shape the shortcut treats as a failure.

Amount is parsed by ripping digits (so `"£12.50"` -> `12.5`) and signed by
`type`: expense = `-abs` (fills `From Account`), income = `+abs` (fills
`To Account`), transfer = `-abs` (fills `From Account`, keeps `to_account` as
the destination). `datetime` falls back to now when missing or unparseable.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit
python flask_app.py       # serves on http://127.0.0.1:5000
```

Smoke test:

```bash
curl http://127.0.0.1:5000/health
# {"status":"ok"}

curl -H "X-API-Key: <API_SECRET>" http://127.0.0.1:5000/health/auth
# {"authenticated":true,"status":"ok"}
```

## Configuration

Set via environment variables (or a local `.env`):

| Variable | Required | Purpose |
| --- | --- | --- |
| `NOTION_TOKEN` | later phases | Notion internal integration token |
| `API_SECRET` | yes | Shared secret sent in the `X-API-Key` header |
| `TRANSACTIONS_DS_ID` / `ACCOUNTS_DS_ID` / `CATEGORIES_DS_ID` / `MONTHS_DS_ID` | yes | Set the Notion data source IDs |

## PythonAnywhere deploy

1. Clone the repo, create a virtualenv, `pip install -r requirements.txt`.
2. Create a manual-config Flask web app; point its WSGI file at `application`
   from `flask_app.py`.
3. Set `API_SECRET` (in the WSGI file or a `.env`), then Reload.
4. Confirm the pipe: `GET /health` returns 200, and `GET /health/auth` with the
   `X-API-Key` header returns 200.

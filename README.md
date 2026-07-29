# The Bridge

A minimal, extensible Flask service that turns HTTP POSTs (from an Apple Shortcut,
or any client) into Notion Transaction rows. Built with an app factory + blueprints
so future phone-to-Notion projects can add endpoints without touching existing ones.

## Status

- **Phase 0 (Foundation) — done:** app factory + blueprints, `config.py`,
  `require_api_key` auth, `GET /health`. Deployable to PythonAnywhere.

## Layout

```
flask_app.py            # PythonAnywhere WSGI entry: exposes `application`
app/__init__.py         # create_app() factory; registers blueprints
app/config.py           # env vars (NOTION_TOKEN, API_SECRET) + Notion data source IDs
app/auth.py             # require_api_key decorator (checks X-API-Key header)
app/blueprints/health/  # GET /health (public), GET /health/auth (key-protected)
```

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

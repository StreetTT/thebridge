# Getting started

[Docs](../index.md) › [Guides](./) › Getting started

## Overview

Run The Bridge locally: virtualenv, dependencies, `.env`, smoke-test the health endpoints.

## How it works

The Flask app loads config from the environment (or a project-root `.env`), registers blueprints, and serves on `http://127.0.0.1:5000` when started via `flask_app.py`.

## Setup / enabling

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit
python flask_app.py       # serves on http://127.0.0.1:5000
```

Fill every required variable in `.env` — see [Configuration](../reference/configuration.md). Share the Notion data sources with the integration behind `NOTION_TOKEN`.

Smoke test:

```bash
curl http://127.0.0.1:5000/health
# {"status":"ok"}

curl -H "X-API-Key: <API_SECRET>" http://127.0.0.1:5000/health/auth
# {"authenticated":true,"status":"ok"}
```

## Endpoints

- [`GET /health`](../reference/api.md#get-health) — public liveness
- [`GET /health/auth`](../reference/api.md#get-healthauth) — auth check

## Warnings & gotchas

- Under PythonAnywhere the process CWD is not the project folder; `.env` is loaded from the project root next to `flask_app.py`, not from CWD.
- Leave `SENTRY_DSN` blank locally unless you intentionally want events sent.

## Related

- [Configuration](../reference/configuration.md)
- [Deployment](./deployment.md)
- [API reference](../reference/api.md)

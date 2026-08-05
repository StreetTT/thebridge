# Deployment

[Docs](../index.md) › [Guides](./) › Deployment

## Overview

Deploy The Bridge to PythonAnywhere and (optionally) schedule the daily savings-interest pass.

## How it works

`flask_app.py` exposes `application` for WSGI. Config comes from environment variables or a project-root `.env` (loaded relative to the project, not the process CWD).

## Setup / enabling

1. Clone the repo, create a virtualenv, `pip install -r requirements.txt`.
2. Create a manual-config Flask web app; point its WSGI file at `application` from `flask_app.py`.
3. Set required secrets and data source IDs (WSGI file or `.env`) — [Configuration](../reference/configuration.md) — then Reload.
4. Confirm the pipe:
   - `GET /health` → 200
   - `GET /health/auth` with `X-API-Key` → 200
5. For savings interest, add a daily **Scheduled Task** (PythonAnywhere Tasks tab) that hits `POST /savings/accrue` with the API key. The pass must run daily so mid-month AER changes are captured at the right rate; it is idempotent, so an extra run is harmless.

Alternatively, schedule the phone-side [Interest Manager](./apple-shortcut.md) shortcut.

### Logging & Sentry

Log lines look like:

```text
2026-08-04 10:15:01 INFO [app.transactions] [id=<client_id>] message
```

Correlation uses the client `_id` for transactions and a per-run id for savings (`id=accrue-YYYY-MM-DD-xxxx`). Nothing invents a UUID when `_id` is missing — those lines show `id=-`.

**Transaction trail:** take `_id` from the Shortcut response (or Notion `_id` column) → PythonAnywhere Error log → search `id=<uuid>`. Create success also logs Notion `page_id`.

**Savings trail:** search `id=accrue-2026-08-04` (day), `id=accrue-2026-08-04-a3f9` (one run), or `id=interest-<accountPageId>-2026-08-<suffix>` for a monthly payout and its nested transaction logs.

Default level is `INFO`. Set `LOG_LEVEL=DEBUG` temporarily for cache/resolve/accrue detail, then set it back. Set `SENTRY_DSN` for remote capture (`client_id` tag); leave blank if unused.

## Endpoints

- [`GET /health`](../reference/api.md#get-health)
- [`GET /health/auth`](../reference/api.md#get-healthauth)
- [`POST /savings/accrue`](../reference/api.md#post-savingsaccrue)

## Warnings & gotchas

- `.env` must sit at the project root; PA's CWD is not the project folder.
- DEBUG on production is noisy — enable only while tracing one `_id` or one accrue day.

## Related

- [Getting started](./getting-started.md)
- [Savings interest](./savings-interest.md)
- [Configuration](../reference/configuration.md)

# The Bridge

A minimal, extensible Flask service that turns HTTP POSTs (from an Apple Shortcut,
or any client) into Notion Transaction rows. Built with an app factory + blueprints
so future phone-to-Notion projects can add endpoints without touching existing ones.

## Status

- **Phase 0 (Foundation) — done:** app factory + blueprints, `config.py`,
  `require_api_key` auth, `GET /health`. Deployable to PythonAnywhere.
- **Phase 1 (Digestion) — done:** `POST /transactions` validates the raw dict,
  signs the amount, maps `card` -> account page id, and resolves `Date` +
  `Month` from `datetime`.
- **Phase 2 (Saving) — done:** `POST /transactions` now writes to Notion. It
  resolves the name-based relations (`Category`, `Month`, transfer
  `To Account`) via `notion_client`, creates the page, and
  returns `201 {"page_id", "public_url"}`. A supplied name that has no matching
  row is skipped (never blocks the write) and reported under `warnings`.
- **Phase 3 (Memory) — done:** a JSON store remembers which categories each
  merchant has been filed under (learned only from bridge posts, never by
  reading Notion). One known category auto-fills; an ambiguous or unknown
  merchant is created uncategorised and flagged `needs_category` so the shortcut
  can prompt, then confirm via `POST /transactions/<page_id>/category`.

## Layout

```
flask_app.py                  # PythonAnywhere WSGI entry: exposes `application`
app/__init__.py               # create_app() factory; registers blueprints
app/config.py                 # env vars (NOTION_TOKEN, API_SECRET) + Notion data source IDs
app/auth.py                   # require_api_key decorator (checks X-API-Key header)
app/notion_client.py          # requests wrapper: query_by_name, list_names, list_accounts, create_page, update_page
app/blueprints/health/        # GET /health (public), GET /health/auth (key-protected)
app/blueprints/transactions/       # POST /transactions + /<id>/category (validate, resolve, write, learn)
app/blueprints/transactions/merchant_memory.py  # JSON merchant -> category store
app/data/merchant_categories.json    # learned merchant -> category counts (gitignored)
```

The `card` → account mapping lives entirely in **Notion** (see
[Account links](#account-links)); there is no local mapping file.

## `POST /transactions`

Send the shortcut's `raw dict` with the `X-API-Key` header. `card`, `amount`,
and one of `description`/`merchant` are required; `type` defaults to `expense`.

```bash
curl -X POST http://127.0.0.1:5000/transactions \
  -H "X-API-Key: <API_SECRET>" -H "Content-Type: application/json" \
  -d '{"merchant":"Tesco","card":"Revolut Visa","amount":"£12.50",
       "description":"Weekly shop","datetime":"2026-07-28T14:30:00",
       "category":"Groceries"}'
```

On success returns `201 {"page_id": ..., "public_url": ...}`, where `public_url`
is Notion's page `url`. Errors use the `{status, message}` shape the shortcut
treats as a failure.

Amount is parsed by ripping digits (so `"£12.50"` -> `12.5`) and signed by
`type`: expense = `-abs` (fills `From Account`), income = `+abs` (fills
`To Account`), transfer = `-abs` (fills `From Account`, plus `to_account` as the
destination `To Account`). `datetime` falls back to now when missing or
unparseable.

Both accounts on a transfer are resolved from Notion (see
[Account links](#account-links)): `card` sets `From Account` and `to_account`
sets `To Account`. Each must match an account's codename or `Apple Card` value
(case-insensitively) — `to_account` accepts the same labels `card` does. An
unknown `card` or `to_account` is rejected with an error listing the known
labels rather than silently left blank.

The exact input payload is also written to a `rawPayload` rich-text property on
the created page (JSON, truncated to Notion's 2000-char limit) for debugging and
audit. Add a `rawPayload` text column to the Transactions data source to capture
it.

Name-based relations are resolved by looking up the matching row in Notion:
`category` -> the `Category` property and the derived month -> `Month`.
Resolution is best-effort and never
blocks the write: a name with no matching row — or a lookup that errors (e.g. a
data source not shared with the integration) — is left blank instead of failing,
and each skip is reported in an optional `warnings` array on the success
response:

```json
{"page_id": "...", "public_url": "...",
 "warnings": ["No Category match for 'Grocries'; left blank."]}
```

Requires `NOTION_TOKEN` and the four `*_DS_ID` values to be configured.

## Account links

The `card` → account mapping lives in Notion, on the Accounts data source
(`ACCOUNTS_DS_ID`). Each account row carries:

- its **codename** — the page title, e.g. `Revolut Visa`; and
- an **`Apple Card`** text (or select) property holding the exact card name
  Apple hands over.

To link a card, type the Apple-given name into the `Apple Card` property on the
matching account row. Leave it blank for accounts only ever chosen manually —
the codename still resolves.

Accounts with the **`Archived`** checkbox ticked are skipped entirely (never
resolved, never listed). The remaining accounts are returned in reverse of
Notion's row order.

The bridge reads the Accounts data source and resolves an incoming `card` (or
transfer `to_account`) against **either** the codename **or** the `Apple Card`
value, **exact + case-insensitive**. Both the manual picker's codenames and a
tap's Apple card name share one keyspace, so the bridge never needs to know
which entry point sent the value. The resolved map is cached in-process for an
hour, so a newly edited link may take a short while to appear.

`ACCOUNTS_DS_ID` is **required** — there is no local fallback. A request errors
if it is unset, if Notion is unreachable with no cached map, or if `card` matches
no codename or `Apple Card` value (the error lists the known labels). If two rows
claim the same label (an `Apple Card` value colliding with another account's
codename), the bridge refuses the map with an error so the clash is fixed in
Notion rather than silently resolving to the wrong account.

### `GET /accounts`

Returns the account codenames so the shortcut can build its card picker from
Notion instead of a hardcoded list.

```bash
curl -H "X-API-Key: <API_SECRET>" http://127.0.0.1:5000/accounts
```

```json
{"accounts": ["NatWest Debit", "Revolut Visa", "ISave", "Pocket"]}
```

The list is drawn from Notion and cached like the resolver above. Errors use the
same `{status, message}` shape.

## Merchant memory & categories

If the request omits `category`, the bridge picks one from what it has learned
about the merchant (stored in `app/data/merchant_categories.json` as
`{"tesco": {"Groceries": 5, "Household": 1}}`, populated **only** by bridge
posts — it never reads the Notion table):

- **One known category** → auto-filled; the write proceeds as normal.
- **Two or more (ambiguous)** or **none (unknown merchant)** → the row is created
  uncategorised and the response adds `needs_category`, so the shortcut prompts
  and confirms the pick.

Every success response also carries `category` (the category actually applied,
or `null`) and `all_categories` (every category in Notion). This means the
shortcut can **always** offer a "change category" option — even after an
auto-fill — by letting you pick from `all_categories` and calling
`POST /transactions/<page_id>/category`.

```json
{"page_id": "...", "public_url": "...", "category": "Groceries",
 "all_categories": ["Groceries", "Household", "Eating Out", "..."],
 "needs_category": true, "candidates": ["Groceries", "Household"]}
```

`candidates` (present only with `needs_category`) are the merchant's known
categories, most-used first (empty for an unknown merchant). Whenever a category
is actually applied (explicit, auto-filled, or confirmed) it is learned against
the merchant. The category list is cached in-process for a few minutes, so a
newly added Notion category may take a short while to appear.

The shortcut must check response keys in order: `status` (error) →
`needs_category` (prompt) → otherwise success (with an optional "change"
affordance).

If the request body includes an `_id` key, it is echoed back verbatim on the
response (both success and error) so the caller can correlate a response with
the request it sent. An `interactive` key is echoed the same way but only on
success responses. This applies to both transaction endpoints.

## `POST /transactions/<page_id>/category`

Sets the category the user picked after a `needs_category` response, patches the
Notion relation, and records the association so the merchant is remembered next
time.

```bash
curl -X POST http://127.0.0.1:5000/transactions/<page_id>/category \
  -H "X-API-Key: <API_SECRET>" -H "Content-Type: application/json" \
  -d '{"merchant":"Tesco","category":"Groceries"}'
```

Returns `200 {"page_id": ..., "public_url": ..., "category": ...}` on success,
where `public_url` is the same Notion link the create endpoint returns.

Note: `<page_id>` in the URL must be the **Notion** page id returned by
`POST /transactions` (the `page_id` field), not the client-supplied `_id` echoed
back on the response. Sending the `_id` here makes Notion fail to find the page.

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
| `NOTION_TOKEN` | yes | Notion internal integration token |
| `API_SECRET` | yes | Shared secret sent in the `X-API-Key` header |
| `TRANSACTIONS_DS_ID` / `ACCOUNTS_DS_ID` / `CATEGORIES_DS_ID` / `MONTHS_DS_ID` | yes | Set the Notion data source IDs |

## PythonAnywhere deploy

1. Clone the repo, create a virtualenv, `pip install -r requirements.txt`.
2. Create a manual-config Flask web app; point its WSGI file at `application`
   from `flask_app.py`.
3. Set `API_SECRET` (in the WSGI file or a `.env`), then Reload.
4. Confirm the pipe: `GET /health` returns 200, and `GET /health/auth` with the
   `X-API-Key` header returns 200.

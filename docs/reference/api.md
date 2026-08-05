# API reference

[Docs](../index.md) › [Reference](./) › API

Every endpoint. Auth is the `X-API-Key` header matching `API_SECRET`, unless noted public. Errors use `{status, message}` unless noted otherwise. For behaviour and Notion setup, see the guides.

---

### `GET /health`

**Auth:** public

**Purpose:** Liveness check to confirm the deploy pipe works.

**Request:** no body

**Response (success):** `200`

```json
{"status": "ok"}
```

**Errors:** none expected for a healthy process.

**Example:**

```bash
curl http://127.0.0.1:5000/health
```

---

### `GET /health/auth`

**Auth:** required (`X-API-Key`)

**Purpose:** Confirm API-key auth end to end.

**Request:** no body

**Response (success):** `200`

```json
{"status": "ok", "authenticated": true}
```

**Errors:** `{status, message}` when the key is missing or wrong.

**Example:**

```bash
curl -H "X-API-Key: <API_SECRET>" http://127.0.0.1:5000/health/auth
```

---

### `GET /accounts`

**Auth:** required (`X-API-Key`)

**Purpose:** Return account codenames so a client can build its card picker from Notion.

**Request:** no body

**Response (success):** `200`

```json
{"accounts": ["NatWest Debit", "Revolut Visa", "ISave", "Pocket"]}
```

**Errors:** `{status, message}` if Notion is unreachable with no cache, or `ACCOUNTS_DS_ID` is unset.

**Example:**

```bash
curl -H "X-API-Key: <API_SECRET>" http://127.0.0.1:5000/accounts
```

See [Accounts](../guides/accounts.md).

---

### `POST /transactions`

**Auth:** required (`X-API-Key`)

**Purpose:** Create a Notion Transaction page from a raw dict (Apple Shortcut or any client).

**Request:**

- Headers: `X-API-Key`, `Content-Type: application/json`
- Body (JSON):
  - `card` (required) — account codename or `Apple Card` value
  - `amount` (required) — number or currency string (digits are ripped, e.g. `"£12.50"` → `12.5`)
  - `description` or `merchant` (at least one required) — `description` is the row title; `merchant` feeds category memory
  - `type` (optional, default `expense`) — `expense` | `income` | `transfer`
  - `to_account` (required for transfers) — destination account, same labels as `card`
  - `datetime` (optional) — ISO-ish datetime; falls back to now when missing or unparseable
  - `category` (optional) — name resolved to the Category relation
  - `notes`, `address` (optional)
  - `_id` (optional) — echoed on every response; stored on the Notion `_id` property on success
  - `interactive` (optional) — echoed on success only

**Response (success):** `201`

```json
{
  "page_id": "...",
  "public_url": "...",
  "category": "Groceries",
  "all_categories": ["Groceries", "Household", "Eating Out"],
  "needs_category": true,
  "candidates": ["Groceries", "Household"],
  "warnings": ["No Category match for 'Grocries'; left blank."]
}
```

- `category` — applied category, or `null`
- `all_categories` — every category in Notion (always present)
- `needs_category` / `candidates` — only when the merchant is ambiguous or unknown
- `warnings` — optional; name-based relation skips never block the write
- `_id` / `interactive` — echoed when supplied (see [Apple Shortcut](../guides/apple-shortcut.md))

**Errors:** `{status, message}` — unknown `card`/`to_account` (lists known labels), missing required fields, Notion unreachable with no cache, colliding account labels.

**Example:**

```bash
curl -X POST http://127.0.0.1:5000/transactions \
  -H "X-API-Key: <API_SECRET>" -H "Content-Type: application/json" \
  -d '{"merchant":"Tesco","card":"Revolut Visa","amount":"£12.50",
       "description":"Weekly shop","datetime":"2026-07-28T14:30:00",
       "category":"Groceries"}'
```

See [Transactions](../guides/transactions.md) and [Categories](../guides/categories.md).

---

### `POST /transactions/<page_id>/category`

**Auth:** required (`X-API-Key`)

**Purpose:** Set the category after a `needs_category` create (or a later correction), patch the Notion relation, and learn the merchant association.

**Request:**

- Headers: `X-API-Key`, `Content-Type: application/json`
- Path: `<page_id>` must be the Notion `page_id` from `POST /transactions`, **not** the client `_id`
- Body (JSON):
  - `merchant` (recommended) — merchant to learn against
  - `category` (required) — category name
  - `_id` / `interactive` (optional) — passthrough echo as on create

**Response (success):** `200`

```json
{"page_id": "...", "public_url": "...", "category": "Groceries"}
```

**Errors:** `{status, message}` — unknown category, Notion page not found (often because `_id` was used as `<page_id>`).

**Example:**

```bash
curl -X POST http://127.0.0.1:5000/transactions/<page_id>/category \
  -H "X-API-Key: <API_SECRET>" -H "Content-Type: application/json" \
  -d '{"merchant":"Tesco","category":"Groceries"}'
```

See [Categories](../guides/categories.md).

---

### `POST /savings/accrue`

**Auth:** required (`X-API-Key`)

**Purpose:** Daily pass: accrue interest on enrolled accounts and file monthly payouts when due.

**Request:** no body (empty JSON is fine)

**Response (success):** `200`

```json
{
  "accounts": [
    {
      "page_id": "...",
      "name": "212 Saving",
      "public_url": "...",
      "balance": 5000.0,
      "daily_rate": 0.0000969,
      "todays_interest": 0.4846,
      "accrued": 14.53,
      "paid": false
    }
  ],
  "warnings": []
}
```

`paid` is `true` on the run that files the monthly income transaction (`accrued` resets to 0).

**Errors:** `{status, message}` for hard failures. Soft issues (e.g. payout account unresolved) appear under `warnings`.

**Example:**

```bash
curl -X POST http://127.0.0.1:5000/savings/accrue -H "X-API-Key: <API_SECRET>"
```

See [Savings interest](../guides/savings-interest.md).

## Related

- [Configuration](./configuration.md)
- [Apple Shortcut](../guides/apple-shortcut.md)
- [Getting started](../guides/getting-started.md)

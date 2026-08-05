# Configuration

[Docs](../index.md) › [Reference](./) › Configuration

Environment variables (or a local `.env`). Copy [`.env.example`](../../.env.example) to get started.

## Required

| Variable | Purpose |
| -------- | ------- |
| `NOTION_TOKEN` | Notion internal integration token |
| `API_SECRET` | Shared secret sent in the `X-API-Key` header |
| `TRANSACTIONS_DS_ID` | Notion Transactions data source ID |
| `ACCOUNTS_DS_ID` | Notion Accounts data source ID |
| `CATEGORIES_DS_ID` | Notion Categories data source ID |
| `MONTHS_DS_ID` | Notion Months data source ID |

## Optional — observability

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `LOG_LEVEL` | `INFO` | Root log level (`DEBUG` for a full step trail) |
| `SENTRY_DSN` | _(empty)_ | When set, hard failures are sent to Sentry (tagged with `client_id`) |
| `NOTION_VERSION` | `2025-09-03` | Notion API version header |

## Optional — savings interest

Property *names* are env-tunable so the Accounts schema can be renamed without code changes; their *values* live in Notion. Defaults match the property names expected on account rows.

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `SAVINGS_EARNS_INTEREST_PROPERTY` | `Earns Interest` | Checkbox that enrols an account |
| `SAVINGS_AER_PROPERTY` | `AER %` | Number holding the AER as a percent |
| `SAVINGS_PAYMENT_DAY_PROPERTY` | `Interest Payment Day` | Number: day of month interest is paid |
| `SAVINGS_BALANCE_PROPERTY` | `Current Balance` | Number/formula/rollup interest accrues on |
| `SAVINGS_ACCRUED_PROPERTY` | `Accrued Interest` | Number the bridge writes the running total to |
| `SAVINGS_LAST_ACCRUED_PROPERTY` | `Last Accrued` | Date driving daily idempotency |
| `SAVINGS_LAST_PAID_PROPERTY` | `Last Interest Paid` | Date guarding one payout per month |
| `SAVINGS_INTEREST_NAME` | `Interest` | Title of the monthly interest transaction |
| `SAVINGS_INTEREST_CATEGORY` | `Interest` | Category of the monthly interest transaction |

## Related

- [Getting started](../guides/getting-started.md)
- [Savings interest](../guides/savings-interest.md)
- [API reference](./api.md)

# Savings interest

[Docs](../index.md) › Guides › Savings interest

## Overview

Compute the interest Trading 212's API never exposes: accrue daily into Notion, and on each account's payment day file the accumulated total as an income transaction. Driven entirely from Notion checkboxes and rates — no code change per account.

## How it works

Notion is the single source of truth for accrued state (survives a PythonAnywhere disk reset).

### Accrual vs payout

- **Accrual** is not a transaction. Each day the bridge adds that day's interest to an `Accrued Interest` number on the account row — it never touches balance or writes to Transactions.
- **Payout** is a transaction. On the account's payment day — or the first run after it that month if a run was missed — the accumulated `Accrued Interest` is filed as a single **income** transaction (same write path as `POST /transactions`) and the accrual resets to 0.

### Rate

The daily rate is the compound-equivalent `(1 + AER) ^ (1/365) - 1`, applied to `Current Balance` (which excludes the unpaid accrual — no intra-month compounding; the daily rate already reflects AER's annual compounding). Because accrual runs **daily**, a mid-month AER change is captured correctly.

### Idempotency

Guarded by `Last Accrued` (at most once per day) and `Last Interest Paid` (at most once per month). A double-fired schedule is harmless. A missed day is caught up on the next run at the current balance as an approximation. `Interest Payment Day` values like `31` in short months pay on the last run of the month instead.

The payout account must still resolve as a `card` (codename or `Apple Card` — see [Accounts](./accounts.md)). An account due a payout that cannot be resolved keeps accruing; the response lists it under `warnings`.

## Setup / enabling

1. Tick `Earns Interest` on the account row.
2. Set `AER %` (as a percent) and `Interest Payment Day`.
3. Ensure the account resolves as a card so the payout can be filed.
4. Property names are overridable via env — [Configuration](../reference/configuration.md).
5. Schedule a daily hit to `POST /savings/accrue` (PythonAnywhere task or the Interest Manager shortcut) — see [Deployment](./deployment.md).

The first payout after enabling covers only the days accrued so far that month (a partial month), which is expected.

## Endpoints

- [`POST /savings/accrue`](../reference/api.md#post-savingsaccrue) — daily accrual + monthly payout

## Warnings & gotchas

- Must run daily so mid-month AER changes use the right rate; extra runs are safe.
- Unresolvable payout accounts appear in `warnings`, not as hard errors.
- Default payout title/category are `Interest` / `Interest` (`SAVINGS_INTEREST_NAME` / `SAVINGS_INTEREST_CATEGORY`).

## Related

- [Accounts](./accounts.md)
- [Deployment](./deployment.md)
- [Apple Shortcut](./apple-shortcut.md) (Interest Manager)
- [Configuration](../reference/configuration.md)
- [API reference](../reference/api.md)

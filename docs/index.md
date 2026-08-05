# The Bridge docs

A minimal Flask service that turns HTTP POSTs (from an Apple Shortcut, or any client) into Notion Transaction rows — plus daily savings-interest accrual.

Pick a lane:

## Guides


| Guide                                            | What it's for                                |
| ------------------------------------------------ | -------------------------------------------- |
| [Getting started](./guides/getting-started.md)   | Local venv, `.env`, smoke test               |
| [Apple Shortcut](./guides/apple-shortcut.md)     | Client contract, suite layout, offline queue |
| [Transactions](./guides/transactions.md)         | Logging a transaction (model + gotchas)      |
| [Accounts](./guides/accounts.md)                 | Linking cards to Notion accounts             |
| [Categories](./guides/categories.md)             | Merchant memory and category prompts         |
| [Savings interest](./guides/savings-interest.md) | Enabling and running daily accrual/payout    |
| [Deployment](./guides/deployment.md)             | PythonAnywhere + scheduled task + logging    |




## Reference


| Page                                          | What it's for                                |
| --------------------------------------------- | -------------------------------------------- |
| [API](./reference/api.md)                     | Every endpoint — request, response, examples |
| [Configuration](./reference/configuration.md) | Every environment variable                   |




## Developers


| Page                                                   | What it's for                                              |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| [Architecture](./developers/architecture.md)           | App factory, blueprints, Notion client, caching, data flow |
| [Project structure](./developers/project-structure.md) | File and directory map                                     |
| [Roadmap](./developers/roadmap.md)                     | Phase history and what's pending                           |

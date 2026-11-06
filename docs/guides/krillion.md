# Krillion

[Docs](../index.md) | [Guides](./) | Krillion

## Overview
Allow users to submit their daily [Krillion](https://krillion.io) game results via an Apple Shortcut. The shortcut sends the raw text to the bridge, which parses the text, resolves the player's identity via a Notion relation (using local caching), and saves the result to a centralized Notion database for leaderboard tracking.

## How it works

### Payload & Routing
The Apple Shortcut prompts the user for their name and passes it along with the raw clipboard text from the Krillion share button. The endpoint (`POST /games/krillion`) remains open without requiring an API key, relying instead on the obscurity of the URL. 

### Parsing Logic
Handled within `app/blueprints/games/krillion_parser.py`:
1. **Game Number:** Extracts the integer following the `#` symbol (e.g., `113`).
2. **Score:** Extracts the numerical score from the second line (e.g., `365`).
3. **Emojis:** Slices the exactly 7 emojis from the final line and maps them strictly by their position (1 through 7) in the dive sequence.

### Player Identification & Caching
Handled within `app/blueprints/games/notion_games.py`:
To prevent excessive Notion API calls and survive PythonAnywhere worker restarts, the app maintains a file-based cache (`player_cache.json`).
1. **Cache Hit:** Checks the dictionary for `player_name`. If found and the timestamp is less than 7 days old, it uses the cached Notion Page ID.
2. **Cache Miss / Query:** If expired or missing, it queries the "Krillion Players" database for the name.
3. **Auto-Create:** If the query returns no results, the app automatically creates a new page in the Players database (populating only the `Name` property) and caches the newly generated Page ID.

### Duplicate Handling
Submissions are first-come, first-serve. Before writing to the database, the backend queries Notion for an existing entry where `Game` equals the incoming game number AND the `Player` relation equals the resolved Page ID. If a match is found, the request is safely rejected.

## Setup / enabling

1. Create a **Krillion Players** Notion database (requires a `Name` title property).
2. Create a **Krillion Games** Notion database for the leaderboard, and add a Relation property linked to the Players database.
3. Add the database IDs to your `.env` file as `NOTION_PLAYERS_DB_ID` and `NOTION_KRILLION_DB_ID`.

### Notion Schema (Games Database)
| Property | Type | Role |
| -------- | ---- | ---- |
| `Player` | relation | **bridge-required** – Replaces the text title. Payload sends an array containing exactly 1 item (the player's Page ID). |
| `Game` | number | **bridge-required** – The Krillion game number; used for duplicate checking. |
| `Score` | number | **bridge-required** – The total score achieved. |
| `1` through `7` | select | **bridge-required** – Seven distinct select columns mapping the emoji caught at each specific depth. |

## Endpoints
- `POST /games/krillion` – submit a Krillion score

## Warnings & gotchas
- **Open Endpoint:** This route skips the standard `require_api_key` auth to make sharing the shortcut easier. 
- **Formatting Sensitivity:** The parser expects exactly 7 emojis on the final line of the text. Extra characters or missing lines will cause the payload to be rejected with a 422 error.
- **Select Fields:** Ensure columns 1 through 7 in Notion are set to the `Select` property type to enable clean filtering and relation-based leaderboards in the Notion UI.

## Related
- [Apple Shortcut](./apple-shortcut.md)
- [Configuration](../reference/configuration.md)
- [API reference](../reference/api.md)
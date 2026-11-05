# Krillion

[Docs](../index.md) | [Guides](./) | Krillion

## Overview
Allow users to submit their daily [Krillion](https://krillion.io) game results via an Apple Shortcut. The shortcut sends the raw text to the bridge, which parses the text, extracts the score and emoji positions, and saves the result to a centralized Notion database for leaderboard tracking.

## How it works

### Payload & Routing
The Apple Shortcut prompts the user for their name and passes it along with the raw clipboard text from the Krillion share button. The endpoint (`POST /games/krillion`) remains open without requiring the `X-API-Key` token, relying instead on the obscurity of the URL. 

### Parsing Logic
The Flask application handles all text parsing to keep the Apple Shortcut simple:
1. **Game Number:** Extracts the integer following the `#` symbol (e.g., `113`).
2. **Score:** Extracts the numerical score from the second line (e.g., `365`).
3. **Emojis:** Slices the exactly 7 emojis from the final line and maps them strictly by their position (1 through 7) in the dive sequence.

### Duplicate Handling
Submissions are first-come, first-serve. Before writing to the database, the backend queries Notion for an existing entry matching BOTH the `player_name` and the `game_number`. If a match is found, the request is rejected to prevent duplicate or updated submissions.

## Setup / enabling

1. Create a new Notion database for Krillion leaderboards and share it with your integration.
2. Configure the database with the exact schema outlined below.
3. Add the database ID to your `.env` file as `NOTION_KRILLION_DB_ID`.
4. Create an Apple Shortcut that accepts clipboard input, formats a JSON dictionary (`player_name` and `raw_text`), and sends a `POST` request to `https://<your-server>/games/krillion`.

### Notion Schema
| Property | Type | Role |
| -------- | ---- | ---- |
| `Name` | title | **bridge-required** – The `player_name` from the payload. |
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
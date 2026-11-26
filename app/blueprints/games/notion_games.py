import json
import logging
import os
import time
from flask import current_app
from app.notion_client import NotionClient

logger = logging.getLogger(__name__)

KRILLION_DB_ID = os.getenv("NOTION_KRILLION_DB_ID")
PLAYERS_DB_ID = os.getenv("NOTION_PLAYERS_DB_ID")
CACHE_FILE = "player_cache.json"
CACHE_TTL = 7 * 24 * 3600  # 7 days in seconds


def _get_client() -> NotionClient:
    """Instantiates the existing NotionClient class using the app's tokens."""
    return NotionClient(
        token=current_app.config.get("NOTION_TOKEN"),
        version=current_app.config.get("NOTION_VERSION", "2022-06-28")
    )


def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        logger.debug("Player cache file %s does not exist; starting empty", CACHE_FILE)
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
        logger.debug("Loaded %d player entries from %s", len(cache), CACHE_FILE)
        return cache
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to read player cache %s (%s); resetting cache", CACHE_FILE, e)
        return {}


def _save_cache(cache: dict) -> None:
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
        logger.debug("Saved %d player entries to %s", len(cache), CACHE_FILE)
    except OSError as e:
        logger.error("Failed to write player cache to %s: %s", CACHE_FILE, e)


def get_or_create_player(player_name: str) -> str:
    """
    Checks the local JSON cache for the player's Page ID.
    If expired or missing, queries Notion. Auto-creates if not found.
    """
    cache = _load_cache()
    now = time.time()
    client = _get_client()

    # 1. Cache Hit
    if player_name in cache:
        cached_data = cache[player_name]
        age = now - cached_data.get("timestamp", 0)
        if age < CACHE_TTL:
            logger.debug(
                "Player cache hit for %r (id=%s, age=%.0fs)",
                player_name,
                cached_data["id"],
                age,
            )
            cache[player_name]["timestamp"] = now  # Refresh TTL
            _save_cache(cache)
            return cached_data["id"]
        logger.info("Player cache expired for %r (age=%.0fs); refreshing from Notion", player_name, age)
    else:
        logger.debug("Player cache miss for %r", player_name)

    # 2. Cache Miss / Query Notion
    logger.debug("Querying Notion Players DB (%s) for %r", PLAYERS_DB_ID, player_name)
    result_id = client.query_by_name(
        PLAYERS_DB_ID, player_name  # type: ignore
    )

    if result_id:
        player_id = result_id
        logger.info("Found existing Notion player %r (id=%s)", player_name, player_id)
    else:
        # 3. Auto-Create
        logger.info("Player %r not found in Notion; auto-creating profile", player_name)
        new_page_id, _ = client.create_page({
            "parent": {"data_source_id": PLAYERS_DB_ID},
            "properties": {
                "Name": {"title": [{"text": {"content": player_name}}]}
            },
        })
        player_id = new_page_id
        logger.info("Auto-created Notion player %r (id=%s)", player_name, player_id)

    # Update Cache
    cache[player_name] = {"id": player_id, "timestamp": now}
    _save_cache(cache)

    return player_id  # type: ignore


def is_duplicate_submission(player_id: str, game_number: int) -> bool:
    """
    Queries Notion for an existing entry matching BOTH the player_id relation and game number.
    Returns True if a match is found, rejecting the request (first come, first serve).
    """
    client = _get_client()
    logger.debug(
        "Checking duplicate Krillion submission (player_id=%s, game=%d)",
        player_id,
        game_number,
    )

    payload = {
        "filter": {
            "and": [
                {
                    "property": "Player",
                    "relation": {"contains": player_id}
                },
                {
                    "property": "Game",
                    "number": {"equals": game_number}
                },
                {
                    "property": "Redive",
                    "checkbox": {"does_not_equal": True}
                }
            ]
        }
    }
    
    # Use the client's internal _post method to query the standard database endpoint
    results = client._post(f"/data_sources/{KRILLION_DB_ID}/query", payload)
    matches = results.get("results", [])
    is_dup = len(matches) > 0
    logger.debug(
        "Duplicate check complete (player_id=%s, game=%d): duplicate=%s (matches=%d)",
        player_id,
        game_number,
        is_dup,
        len(matches),
    )
    return is_dup


def save_krillion_result(player_id: str, parsed_data: dict) -> dict:
    """
    Writes a new Krillion result, passing the Player relation as a single-item array.
    """
    client = _get_client()
    logger.debug(
        "Saving Krillion #%d to Notion (player_id=%s, score=%d, redive=%s)",
        parsed_data["game"],
        player_id,
        parsed_data["score"],
        parsed_data["redive"],
    )

    new_page_payload = {
        "parent": {"data_source_id": KRILLION_DB_ID},
        "properties": {
            "Name": {
                "title": [{"text": {"content": "_"}}]
            },
            "Player": {
                "relation": [{"id": player_id}]
            },
            "Game": {
                "number": parsed_data["game"]
            },
            "Score": {
                "number": parsed_data["score"]
            },
            "Redive": {
                "checkbox": parsed_data["redive"]
            },
            "1": {"select": {"name": parsed_data["positions"]["1"]}},
            "2": {"select": {"name": parsed_data["positions"]["2"]}},
            "3": {"select": {"name": parsed_data["positions"]["3"]}},
            "4": {"select": {"name": parsed_data["positions"]["4"]}},
            "5": {"select": {"name": parsed_data["positions"]["5"]}},
            "6": {"select": {"name": parsed_data["positions"]["6"]}},
            "7": {"select": {"name": parsed_data["positions"]["7"]}},
        }
    }
    
    # The existing client.create_page returns a (page_id, url) tuple
    page_id, url = client.create_page(new_page_payload)
    logger.info(
        "Created Krillion Notion page (page_id=%s, game=%d, player_id=%s)",
        page_id,
        parsed_data["game"],
        player_id,
    )
    return {"id": page_id, "url": url}
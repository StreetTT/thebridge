import os
import json
import time
from flask import current_app
from app.notion_client import NotionClient

KRILLION_DB_ID = os.getenv("NOTION_KRILLION_DB_ID")
PLAYERS_DB_ID = os.getenv("NOTION_PLAYERS_DB_ID")
CACHE_FILE = 'player_cache.json'
CACHE_TTL = 7 * 24 * 3600  # 7 days in seconds

def _get_client() -> NotionClient:
    """Instantiates the existing NotionClient class using the app's tokens."""
    return NotionClient(
        token=current_app.config.get("NOTION_TOKEN"),
        version=current_app.config.get("NOTION_VERSION", "2022-06-28")
    )

def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def _save_cache(cache: dict):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

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
        if now - cached_data.get("timestamp", 0) < CACHE_TTL:
            cache[player_name]["timestamp"] = now  # Refresh TTL
            _save_cache(cache)
            return cached_data["id"]
            
    # 2. Cache Miss / Query Notion
    result_id = client.query_by_name(
        PLAYERS_DB_ID, player_name # type:ignore
    )
    
    if result_id:
        player_id = result_id
    else:
        # 3. Auto-Create
        new_page_id,_ = client.create_page({
            "parent":{"data_source_id": PLAYERS_DB_ID},
            "properties":{
                "Name": {"title": [{"text": {"content": player_name}}]}
            }
        })
        player_id = new_page_id
        
    # Update Cache
    cache[player_name] = {"id": player_id, "timestamp": now}
    _save_cache(cache)
    
    return player_id # type:ignore

def is_duplicate_submission(player_id: str, game_number: int) -> bool:
    """
    Queries Notion for an existing entry matching BOTH the player_id relation and game number.
    Returns True if a match is found, rejecting the request (first come, first serve).
    """
    client = _get_client()
    
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
                }
            ]
        }
    }
    
    # Use the client's internal _post method to query the standard database endpoint
    results = client._post(f"/data_sources/{KRILLION_DB_ID}/query", payload)
    return len(results.get("results", [])) > 0

def save_krillion_result(player_id: str, parsed_data: dict) -> dict:
    """
    Writes a new Krillion result, passing the Player relation as a single-item array.
    """
    client = _get_client()
    
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
    return {"id": page_id, "url": url}
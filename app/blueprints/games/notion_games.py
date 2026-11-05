import os
from flask import current_app
from app.notion_client import NotionClient

KRILLION_DB_ID = os.getenv("NOTION_KRILLION_DB_ID")

def _get_client() -> NotionClient:
    """Instantiates the existing NotionClient class using the app's tokens."""
    return NotionClient(
        token=current_app.config.get("NOTION_TOKEN"),
        version=current_app.config.get("NOTION_VERSION", "2022-06-28")
    )

def is_duplicate_submission(player_name: str, game_number: int) -> bool:
    """
    Queries Notion for an existing entry matching BOTH the player_name and the game number.
    Returns True if a match is found, rejecting the request (first come, first serve).
    """
    client = _get_client()
    
    payload = {
        "filter": {
            "and": [
                {
                    "property": "Name",
                    "title": {
                        "equals": player_name
                    }
                },
                {
                    "property": "Game",
                    "number": {
                        "equals": game_number
                    }
                }
            ]
        }
    }
    
    # Use the client's internal _post method to query the standard database endpoint
    results = client._post(f"/data_sources/{KRILLION_DB_ID}/query", payload)
    return len(results.get("results", [])) > 0


def save_krillion_result(player_name: str, parsed_data: dict) -> dict:
    """
    Writes a new Krillion result to the Notion database mapping emojis to positional Select columns.
    """
    client = _get_client()
    
    new_page_payload = {
        "parent": {"data_source_id": KRILLION_DB_ID},
        "properties": {
            "Name": {
                "title": [{"text": {"content": player_name}}]
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
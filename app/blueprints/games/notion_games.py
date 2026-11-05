import os
from app.notion_client import query_database, create_page # Assumed imports from your existing client

# Ensure this is added to your .env file
KRILLION_DB_ID = os.getenv("NOTION_KRILLION_DB_ID")

def is_duplicate_submission(player_name: str, game_number: int) -> bool:
    """
    Queries Notion for an existing entry matching BOTH the player_name and the game number.
    Returns True if a match is found, rejecting the request (first come, first serve).
    """
    query_payload = {
        "database_id": KRILLION_DB_ID,
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
    
    results = query_database(query_payload)
    return len(results) > 0


def save_krillion_result(player_name: str, parsed_data: dict) -> dict:
    """
    Writes a new Krillion result to the Notion database mapping emojis to positional columns.
    """
    new_page_payload = {
        "parent": {"database_id": KRILLION_DB_ID},
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
    
    return create_page(new_page_payload)
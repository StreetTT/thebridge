import logging
from flask import g, jsonify, request
from . import games_bp
from app.blueprints.games.krillion_parser import parse_krillion_text
from app.blueprints.games.notion_games import (
    get_or_create_player,
    is_duplicate_submission,
    save_krillion_result,
)

logger = logging.getLogger(__name__)


@games_bp.route("/krillion", methods=["POST"])
def submit_krillion():
    """
    Receives an incoming JSON payload from an Apple Shortcut containing:
    - player_name
    - raw_text
    """
    data = request.get_json(silent=True)

    if not data or "player_name" not in data or "raw_text" not in data:
        logger.warning(
            "Rejected Krillion submission: missing 'player_name' or 'raw_text' (keys=%s)",
            list(data.keys()) if isinstance(data, dict) else None,
        )
        return jsonify({"error": "Missing 'player_name' or 'raw_text' in payload"}), 400

    player_name = data["player_name"]
    raw_text = data["raw_text"]

    # Populate g.client_id if not set by API key auth so ClientIdFilter tags all logs
    if not getattr(g, "client_id", None):
        g.client_id = f"player:{player_name}"

    logger.info("Received Krillion submission from player=%r", player_name)

    try:
        parsed_data = parse_krillion_text(raw_text)
        game_number = parsed_data["game"]

        # Resolve identity via cache or Notion
        player_id = get_or_create_player(player_name)

        # Prevent duplicate first-time submissions using relation ID
        if not parsed_data["redive"] and is_duplicate_submission(player_id, game_number):
            logger.info(
                "Skipped duplicate Krillion submission: player=%r (id=%s), game=#%d",
                player_name,
                player_id,
                game_number,
            )
            return jsonify({
                "message": f"Submission skipped. {player_name} already submitted their first Game #{game_number}."
            }), 409

        # Save to Notion
        result = save_krillion_result(player_id, parsed_data)
        logger.info(
            "Recorded Krillion #%d for player=%r (score=%d, redive=%s, page_id=%s)",
            game_number,
            player_name,
            parsed_data["score"],
            parsed_data["redive"],
            result.get("id"),
        )

        return jsonify({
            "message": "Krillion score successfully recorded!",
            "data": parsed_data
        }), 201

    except ValueError as e:
        logger.warning("Krillion submission rejected (422) for player=%r: %s", player_name, e)
        return jsonify({"error": f"Parsing failed: {str(e)}"}), 422
    except Exception as e:
        logger.exception("Unexpected error processing Krillion submission for player=%r", player_name)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
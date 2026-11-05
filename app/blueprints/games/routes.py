from flask import request, jsonify
from . import games_bp
from app.blueprints.games.krillion_parser import parse_krillion_text
from app.blueprints.games.notion_games import is_duplicate_submission, save_krillion_result

@games_bp.route('/krillion', methods=['POST'])
def submit_krillion():
    """
    Receives an incoming JSON payload from an Apple Shortcut containing:
    - player_name
    - raw_text
    """
    data = request.get_json()
    
    # 1. Validate Payload
    if not data or 'player_name' not in data or 'raw_text' not in data:
        return jsonify({"error": "Missing 'player_name' or 'raw_text' in payload"}), 400
        
    player_name = data['player_name']
    raw_text = data['raw_text']
    
    try:
        # 2. Parse Raw Text
        parsed_data = parse_krillion_text(raw_text)
        game_number = parsed_data['game']
        
        # 3. Check for Duplicates (First come, first serve)
        if is_duplicate_submission(player_name, game_number):
            return jsonify({
                "message": f"Submission skipped. {player_name} already submitted Game #{game_number}."
            }), 409
            
        # 4. Save to Notion
        save_krillion_result(player_name, parsed_data)
        
        return jsonify({
            "message": "Krillion score successfully recorded!",
            "data": parsed_data
        }), 201
        
    except ValueError as e:
        return jsonify({"error": f"Parsing failed: {str(e)}"}), 422
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
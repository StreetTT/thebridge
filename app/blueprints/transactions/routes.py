"""Transaction endpoints.

``POST /transactions`` validates the raw dict, resolves its name-based relations
against Notion, creates the page, and returns its id and url. Errors use the
``{status, message}`` shape the Apple Shortcut treats as a failure.
"""

from flask import Blueprint, current_app, jsonify, request

from app.auth import require_api_key
from app.blueprints.transactions.service import TransactionError, save_transaction
from app.notion_client import NotionError

transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.post("/transactions")
@require_api_key
def create_transaction():
    """Create a Notion transaction page from the shortcut's raw dict."""
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return jsonify(status=400, message="Request body must be a JSON object"), 400

    try:
        result = save_transaction(raw, current_app.config)
    except (TransactionError, NotionError) as exc:
        return jsonify(status=exc.code, message=str(exc)), exc.code

    body = {"page_id": result["page_id"], "public_url": result["public_url"]}
    if result["warnings"]:
        body["warnings"] = result["warnings"]
    return jsonify(**body), 201

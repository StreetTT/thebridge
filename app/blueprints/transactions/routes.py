"""Transaction endpoints.

``POST /transactions`` validates the raw dict, resolves its name-based relations
against Notion, creates the page, and returns its id and url — flagging
``needs_category`` when the merchant's category is ambiguous or unknown.
``POST /transactions/<page_id>/category`` sets the chosen category afterwards.
Errors use the ``{status, message}`` shape the Apple Shortcut treats as a
failure.
"""

from flask import Blueprint, current_app, jsonify, request

from app.auth import require_api_key
from app.blueprints.transactions.service import (
    TransactionError,
    save_transaction,
    set_category,
)
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

    # `category` (applied, may be null) and `all_categories` ship on every
    # response so the shortcut can always offer a "change category" option that
    # calls POST /transactions/<page_id>/category.
    body = {
        "page_id": result["page_id"],
        "public_url": result["public_url"],
        "category": result["category"],
        "all_categories": result["all_categories"],
    }
    if result["needs_category"]:
        body["needs_category"] = True
        body["candidates"] = result["candidates"]
    if result["warnings"]:
        body["warnings"] = result["warnings"]
    return jsonify(**body), 201


@transactions_bp.post("/transactions/<page_id>/category")
@require_api_key
def set_transaction_category(page_id):
    """Set the category the shortcut picked after an ambiguous/unknown create."""
    body = request.get_json(silent=True)
    try:
        result = set_category(page_id, body, current_app.config)
    except (TransactionError, NotionError) as exc:
        return jsonify(status=exc.code, message=str(exc)), exc.code

    return jsonify(**result), 200

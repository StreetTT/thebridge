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


# `_id` is echoed on every response (success and error) for request/response
# correlation; `interactive` only on success, since it drives client behaviour
# for a transaction that was actually created.
_PASSTHROUGH_KEYS = ("_id",)
_PASSTHROUGH_KEYS_SUCCESS = ("_id", "interactive")


def _echo_passthrough(raw, body, keys):
    """Copy client-supplied ``keys`` from the request through to the response.

    Lets the caller (e.g. the Apple Shortcut) correlate a response with the
    request it sent. Only copies a key when the request body is a dict that
    carries it.
    """
    if not isinstance(raw, dict):
        return
    for key in keys:
        if key in raw:
            body[key] = raw[key]


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
        error = {"status": exc.code, "message": str(exc)}
        _echo_passthrough(raw, error, _PASSTHROUGH_KEYS)
        return jsonify(**error), exc.code

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
    _echo_passthrough(raw, body, _PASSTHROUGH_KEYS_SUCCESS)
    return jsonify(**body), 201


@transactions_bp.post("/transactions/<page_id>/category")
@require_api_key
def set_transaction_category(page_id):
    """Set the category the shortcut picked after an ambiguous/unknown create."""
    body = request.get_json(silent=True)
    try:
        result = set_category(page_id, body, current_app.config)
    except (TransactionError, NotionError) as exc:
        error = {"status": exc.code, "message": str(exc)}
        _echo_passthrough(body, error, _PASSTHROUGH_KEYS)
        return jsonify(**error), exc.code

    _echo_passthrough(body, result, _PASSTHROUGH_KEYS_SUCCESS)
    return jsonify(**result), 200

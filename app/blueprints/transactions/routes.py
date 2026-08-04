"""Transaction endpoints.

``POST /transactions`` validates the raw dict, resolves its name-based relations
against Notion, creates the page, and returns its id and url — flagging
``needs_category`` when the merchant's category is ambiguous or unknown.
``POST /transactions/<page_id>/category`` sets the chosen category afterwards.
``GET /accounts`` returns the account codenames so the shortcut can build its
card picker from Notion. Errors use the ``{status, message}`` shape the Apple
Shortcut treats as a failure.
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from app.auth import require_api_key
from app.blueprints.transactions.service import (
    TransactionError,
    list_account_names,
    save_transaction,
    set_category,
)
from app.notion_client import NotionError

transactions_bp = Blueprint("transactions", __name__)
_log = logging.getLogger(__name__)


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


def _has_client_id(raw) -> bool:
    if not isinstance(raw, dict):
        return False
    client_id = raw.get("_id")
    return client_id is not None and bool(str(client_id).strip())


def _log_domain_error(exc: Exception, context: str) -> None:
    code = getattr(exc, "code", 500)
    if code >= 500:
        _log.error("%s failed: %s", context, exc)
    else:
        _log.warning("%s failed: %s", context, exc)


@transactions_bp.post("/transactions")
@require_api_key
def create_transaction():
    """Create a Notion transaction page from the shortcut's raw dict."""
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return jsonify(status=400, message="Request body must be a JSON object"), 400

    if not _has_client_id(raw):
        _log.warning("Transaction create missing body _id; logs will show id=-")

    try:
        result = save_transaction(raw, current_app.config)
    except (TransactionError, NotionError) as exc:
        _log_domain_error(exc, "Transaction create")
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


@transactions_bp.get("/accounts")
@require_api_key
def list_accounts():
    """Return the account codenames so the shortcut can populate its picker.

    Pulls the list from Notion (cached). Errors use the same ``{status,
    message}`` shape the shortcut treats as a failure.
    """
    try:
        accounts = list_account_names(current_app.config)
    except (TransactionError, NotionError) as exc:
        _log_domain_error(exc, "List accounts")
        return jsonify(status=exc.code, message=str(exc)), exc.code
    return jsonify(accounts=accounts), 200


@transactions_bp.post("/transactions/<page_id>/category")
@require_api_key
def set_transaction_category(page_id):
    """Set the category the shortcut picked after an ambiguous/unknown create."""
    body = request.get_json(silent=True)
    if not _has_client_id(body):
        _log.warning(
            "Category update missing body _id; notion_page_id=%s; logs will show id=-",
            page_id,
        )
    else:
        _log.debug("Category update notion_page_id=%s", page_id)

    try:
        result = set_category(page_id, body, current_app.config)
    except (TransactionError, NotionError) as exc:
        _log_domain_error(exc, "Category update")
        error = {"status": exc.code, "message": str(exc)}
        _echo_passthrough(body, error, _PASSTHROUGH_KEYS)
        return jsonify(**error), exc.code

    _echo_passthrough(body, result, _PASSTHROUGH_KEYS_SUCCESS)
    return jsonify(**result), 200

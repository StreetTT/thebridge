"""Transaction endpoints.

Phase 1 exposes ``POST /transactions`` as a dry run: it validates the raw dict
and echoes the computed Notion payload without writing anything. Phase 2 flips
this to a real create.
"""

from flask import Blueprint, current_app, jsonify, request

from app.auth import require_api_key
from app.blueprints.transactions.service import TransactionError, build_transaction

transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.post("/transactions")
@require_api_key
def create_transaction():
    """Validate a raw transaction and return the computed payload (no write)."""
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return jsonify(status=400, message="Request body must be a JSON object"), 400

    try:
        result = build_transaction(raw, current_app.config)
    except TransactionError as exc:
        return jsonify(status=exc.code, message=str(exc)), exc.code

    return jsonify(dry_run=True, **result), 200

"""Savings interest endpoints.

``POST /savings/accrue`` runs the daily accrual: it accrues each
interest-earning account's interest into Notion and, on an account's payment
day, files the accumulated total as an income transaction. Meant to be hit by a
daily scheduled task. Errors use the ``{status, message}`` shape the caller
treats as a failure.
"""

import logging

from flask import Blueprint, current_app, jsonify

from app.auth import require_api_key
from app.blueprints.savings.service import SavingsError, sync_savings_interest
from app.notion_client import NotionError

savings_bp = Blueprint("savings", __name__)
_log = logging.getLogger(__name__)


@savings_bp.post("/savings/accrue")
@require_api_key
def accrue():
    """Accrue interest for every flagged account and pay any that are due."""
    try:
        result = sync_savings_interest(current_app.config)
    except (SavingsError, NotionError) as exc:
        code = getattr(exc, "code", 500)
        if code >= 500:
            _log.error("Savings accrue failed: %s", exc)
        else:
            _log.warning("Savings accrue failed: %s", exc)
        return jsonify(status=exc.code, message=str(exc)), exc.code
    return jsonify(**result), 200

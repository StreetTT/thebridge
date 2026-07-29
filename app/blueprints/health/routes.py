"""Health check endpoints used to confirm the deploy pipe works."""

from flask import Blueprint, jsonify

from app.auth import require_api_key

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Public liveness check (no API key required)."""
    return jsonify(status="ok"), 200


@health_bp.get("/health/auth")
@require_api_key
def health_auth():
    """Key-protected check to confirm ``X-API-Key`` auth end to end."""
    return jsonify(status="ok", authenticated=True), 200

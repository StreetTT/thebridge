"""API key authentication."""

from functools import wraps

from flask import current_app, jsonify, request


def require_api_key(view):
    """Reject requests whose ``X-API-Key`` header does not match ``API_SECRET``.

    Errors use the ``{status, message}`` shape so the Apple Shortcut can detect
    them the same way it detects Notion errors (presence of a ``status`` key).
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = current_app.config.get("API_SECRET")
        provided = request.headers.get("X-API-Key")

        if not expected:
            return (
                jsonify(status=500, message="Server missing API_SECRET"),
                500,
            )
        if not provided or provided != expected:
            return jsonify(status=401, message="Invalid or missing API key"), 401

        return view(*args, **kwargs)

    return wrapper

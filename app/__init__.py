"""Application factory.

``create_app`` builds the Flask app and registers blueprints. Future phone-to-Notion
projects add their own blueprints here without touching existing routes.
"""

import logging
import time

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.logging_setup import configure_logging
from app.sentry_setup import init_sentry, tag_client_id

_log = logging.getLogger(__name__)


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    configure_logging(app.config.get("LOG_LEVEL", "INFO"))
    init_sentry(app)

    @app.before_request
    def bind_client_id():
        """Correlate logs by body ``_id`` only — never invent a request id."""
        g.request_started = time.perf_counter()
        raw = request.get_json(silent=True)
        if not isinstance(raw, dict):
            return
        client_id = raw.get("_id")
        if client_id is not None and str(client_id).strip():
            g.client_id = str(client_id).strip()
            tag_client_id(g.client_id)

    @app.after_request
    def log_request(response):
        started = getattr(g, "request_started", None)
        duration_ms = (
            (time.perf_counter() - started) * 1000 if started is not None else -1.0
        )
        _log.info(
            "%s %s %s duration_ms=%.1f",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        # Keep Flask/Werkzeug HTTP errors (404, 405, …) on their normal path.
        if isinstance(exc, HTTPException):
            return exc
        _log.exception("Unhandled exception on %s %s", request.method, request.path)
        return jsonify(status=500, message="Internal error"), 500

    from app.blueprints.health.routes import health_bp
    from app.blueprints.savings.routes import savings_bp
    from app.blueprints.transactions.routes import transactions_bp
    from app.blueprints.games.routes import games_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(savings_bp)
    app.register_blueprint(games_bp, url_prefix="/games")

    return app

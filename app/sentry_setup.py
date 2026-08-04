"""Optional Sentry init — only when ``SENTRY_DSN`` is configured."""

from __future__ import annotations

import logging
import re

from flask import Flask, g, has_request_context

_log = logging.getLogger(__name__)

# Headers / env-ish keys that must never leave the process.
_SECRET_KEYS = re.compile(
    r"(authorization|x-api-key|api[_-]?secret|notion[_-]?token|password|secret|token|dsn)",
    re.IGNORECASE,
)


def _scrub_value(key: str, value):
    if _SECRET_KEYS.search(str(key)):
        return "[Filtered]"
    return value


def _scrub_mapping(data: dict | None) -> dict | None:
    if not isinstance(data, dict):
        return data
    return {k: _scrub_value(k, v) for k, v in data.items()}


def _before_send(event, hint):
    """Drop secrets and tag the active correlation id when present."""
    request_info = event.get("request") or {}
    if "headers" in request_info:
        request_info["headers"] = _scrub_mapping(request_info.get("headers"))
    if "data" in request_info and isinstance(request_info["data"], dict):
        # Never ship full transaction payloads; keep only non-secret keys we need.
        request_info["data"] = _scrub_mapping(request_info["data"])
    if "env" in request_info:
        request_info["env"] = _scrub_mapping(request_info.get("env"))
    event["request"] = request_info

    if has_request_context():
        client_id = getattr(g, "client_id", None)
        if client_id:
            event.setdefault("tags", {})["client_id"] = client_id

    return event


def tag_client_id(client_id: str | None) -> None:
    """Set the Sentry ``client_id`` tag when a DSN is active and ``client_id`` is set."""
    if not client_id:
        return
    try:
        import sentry_sdk
    except ImportError:
        return
    sentry_sdk.set_tag("client_id", client_id)


def init_sentry(app: Flask) -> None:
    """Initialise Sentry for ``app`` when ``SENTRY_DSN`` is set; otherwise no-op."""
    dsn = (app.config.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
    except ImportError:
        _log.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping Sentry.")
        return

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration()],
        send_default_pii=False,
        before_send=_before_send,
    )
    _log.info("Sentry initialised")

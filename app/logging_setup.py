"""Idempotent logging setup with request-scoped ``client_id`` on every line."""

from __future__ import annotations

import logging

from flask import g, has_request_context

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] [id=%(client_id)s] %(message)s"


class ClientIdFilter(logging.Filter):
    """Attach ``client_id`` from ``flask.g``, or ``-`` outside a bound request."""

    def filter(self, record: logging.LogRecord) -> bool:
        if has_request_context():
            record.client_id = getattr(g, "client_id", None) or "-"
        else:
            record.client_id = "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once; safe to call on every ``create_app``."""
    global _CONFIGURED

    resolved = getattr(logging, str(level).upper(), None)
    if not isinstance(resolved, int):
        resolved = logging.INFO

    root = logging.getLogger()
    root.setLevel(resolved)

    if _CONFIGURED:
        # Level may change between create_app calls (e.g. tests); keep handlers.
        for handler in root.handlers:
            handler.setLevel(resolved)
        return

    handler = logging.StreamHandler()
    handler.setLevel(resolved)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.addFilter(ClientIdFilter())
    root.addHandler(handler)

    # Quiet noisy third-party loggers; Notion/auth failures are logged by us.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    _CONFIGURED = True

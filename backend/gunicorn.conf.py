"""Configure Gunicorn for a platform-provided port and graceful shutdown."""

import os

from app.settings import DEFAULT_PORT, PORT_ENV


def _port() -> int:
    """Return the valid listening port supplied by the runtime, or 5000 locally."""
    raw_port = os.getenv(PORT_ENV, str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError as error:
        raise ValueError("PORT must be an integer between 1 and 65535.") from error
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535.")
    return port


bind = f"0.0.0.0:{_port()}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
timeout = 30
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
capture_output = True

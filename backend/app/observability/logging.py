"""Configure structured JSON logging for the Mis Eventos backend."""

import json
import logging
import re
import sys
from datetime import UTC, datetime

SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)([\"']?(?:password|token|secret|authorization)[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;}]+)([\"']?)"
)
DATABASE_CREDENTIAL_PATTERN = re.compile(r"(://[^:/@]+:)[^@/]+(@)")
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def redact_sensitive_values(value: str) -> str:
    """Redact common credential assignments and URL passwords from log text."""
    value = SENSITIVE_VALUE_PATTERN.sub(r"\1[REDACTED]\3", value)
    value = DATABASE_CREDENTIAL_PATTERN.sub(r"\1[REDACTED]\2", value)
    return EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)


class JsonFormatter(logging.Formatter):
    """Serialize log records with stable service and environment metadata."""

    def format(self, record: logging.LogRecord) -> str:
        """Render one record as JSON without serializing arbitrary record fields."""
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "service": getattr(record, "service", "mis-eventos-backend"),
            "environment": getattr(record, "environment", "local"),
            "version": getattr(record, "version", "unknown"),
            "message": redact_sensitive_values(record.getMessage()),
        }
        for key in (
            "request_id",
            "method",
            "route",
            "status_code",
            "duration_seconds",
            "stage",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            exception = record.exc_info[1]
            payload["exception_type"] = type(exception).__name__
            payload["traceback"] = redact_sensitive_values(
                self.formatException(record.exc_info)
            )
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Install one structured stdout handler for application logs."""
    normalized_level = level.upper()
    if normalized_level not in logging.getLevelNamesMapping():
        normalized_level = "INFO"
    logger = logging.getLogger("mis_eventos")
    logger.setLevel(normalized_level)
    logger.propagate = False
    logging.getLogger("werkzeug").disabled = True
    if not any(
        getattr(handler, "_mis_eventos_handler", False) for handler in logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler._mis_eventos_handler = True
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    if normalized_level != level.upper():
        logger.warning(
            "Invalid log level; falling back to INFO.",
            extra={"stage": "configuration", "service": "mis-eventos-backend"},
        )


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the configured application logger hierarchy."""
    return logging.getLogger(f"mis_eventos.{name}")

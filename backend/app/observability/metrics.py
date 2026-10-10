"""Provide isolated Prometheus collectors for one Flask application instance."""

from flask import current_app, has_app_context
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from app.observability.logging import get_logger

logger = get_logger("metrics")


class ApplicationMetrics:
    """Hold bounded-cardinality HTTP and supported business metric collectors."""

    def __init__(self) -> None:
        """Create metrics in a private registry to avoid cross-app test leakage."""
        self.registry = CollectorRegistry()
        self.http_requests = Counter(
            "mis_eventos_http_requests",
            "Total HTTP requests handled by the backend.",
            ("method", "route", "status_code"),
            registry=self.registry,
        )
        self.http_request_duration = Histogram(
            "mis_eventos_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            ("method", "route"),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry,
        )
        self.http_requests_in_progress = Gauge(
            "mis_eventos_http_requests_in_progress",
            "HTTP requests currently being processed.",
            registry=self.registry,
        )
        self.business_events_created = Counter(
            "mis_eventos_business_events_created",
            "Events successfully created.",
            registry=self.registry,
        )
        self.business_registrations = Counter(
            "mis_eventos_business_registrations",
            "Event registrations successfully created or reactivated.",
            registry=self.registry,
        )

    def render(self) -> tuple[bytes, str]:
        """Return current Prometheus exposition bytes and its media type."""
        return generate_latest(self.registry), CONTENT_TYPE_LATEST


def increment_business_metric(name: str) -> None:
    """Increment a supported counter without interrupting its business operation."""
    if not has_app_context():
        return
    metrics: ApplicationMetrics | None = current_app.extensions.get(
        "mis_eventos_metrics"
    )
    if metrics is None:
        return

    try:
        if name == "event_created":
            metrics.business_events_created.inc()
        elif name == "registration_completed":
            metrics.business_registrations.inc()
    except Exception:
        logger.exception(
            "Optional business metric recording failed.",
            extra={"metric": name},
        )

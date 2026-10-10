"""Create the Flask application, configure observability, and register routes."""

import os
import time
import uuid

from flask import Flask, g, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth.routes import auth_bp
from app.api.error_handlers import register_error_handlers
from app.api.events.routes import event_bp
from app.api.health.routes import health_bp
from app.api.sessions.routes import session_bp
from app.config import load_config
from app.docs.swagger import init_swagger
from app.extensions import db
from app.observability.logging import configure_logging, get_logger
from app.observability.metrics import ApplicationMetrics

logger = get_logger("lifecycle")
EXCLUDED_METRIC_ROUTES = {"/metrics", "/api/v1/health", "/api/v1/live", "/api/v1/ready"}


def create_app() -> Flask:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    logger.info(
        "Backend application initialization started.",
        extra={
            "service": os.getenv("SERVICE_NAME", "mis-eventos-backend"),
            "environment": os.getenv("APP_ENVIRONMENT", "local"),
            "version": os.getenv("APP_VERSION", "dev"),
            "stage": "configuration",
        },
    )
    app = Flask(__name__)
    try:
        app.config.update(load_config())
    except Exception:
        logger.exception(
            "Backend configuration validation failed.",
            extra={"stage": "configuration"},
        )
        raise
    if (
        not app.config["JWT_SECRET_KEY"]
        or len(app.config["JWT_SECRET_KEY"].encode("utf-8")) < 32
    ):
        logger.error(
            "Backend configuration is missing a sufficiently long JWT secret.",
            extra={"stage": "configuration", **_log_context(app)},
        )
    app.extensions["mis_eventos_metrics"] = ApplicationMetrics()
    app.extensions["mis_eventos_readiness"] = None

    try:
        db.init_app(app)
    except Exception:
        logger.exception(
            "Backend application initialization failed.",
            extra={"stage": "database_extension", **_log_context(app)},
        )
        raise

    try:
        app.register_blueprint(health_bp, url_prefix="/api/v1")
        app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
        app.register_blueprint(event_bp, url_prefix="/api/v1")
        app.register_blueprint(session_bp, url_prefix="/api/v1")
    except Exception:
        logger.exception(
            "Backend application initialization failed.",
            extra={"stage": "route_registration", **_log_context(app)},
        )
        raise

    try:
        init_swagger(app)
    except Exception:
        logger.exception(
            "Backend application initialization failed.",
            extra={"stage": "swagger", **_log_context(app)},
        )
        raise

    _register_observability_routes(app)
    _register_http_instrumentation(app)
    register_error_handlers(app)
    logger.info(
        "Backend application initialized; database readiness is checked at /api/v1/ready.",
        extra={"stage": "application_ready", **_log_context(app)},
    )
    logger.info(
        "Application observability is local: logs are written to stdout and metrics are available at /metrics.",
        extra={"stage": "observability", **_log_context(app)},
    )

    return app


def _log_context(app: Flask) -> dict[str, str]:
    """Return non-sensitive deployment labels for structured lifecycle logs."""
    return {
        "service": app.config["SERVICE_NAME"],
        "environment": app.config["APP_ENVIRONMENT"],
        "version": app.config["APP_VERSION"],
    }


def _register_observability_routes(app: Flask) -> None:
    """Expose metrics, liveness, and dependency-aware readiness endpoints."""

    @app.get("/metrics")
    def metrics_endpoint():
        """Expose the per-application Prometheus registry."""
        metrics: ApplicationMetrics = app.extensions["mis_eventos_metrics"]
        body, content_type = metrics.render()
        return app.response_class(body, content_type=content_type)

    @app.get("/api/v1/live")
    def liveness_endpoint():
        """Confirm the Flask process can serve a request."""
        return jsonify({"status": "ok"}), 200

    @app.get("/api/v1/ready")
    def readiness_endpoint():
        """Check required signing configuration and database connectivity."""
        secret = app.config.get("JWT_SECRET_KEY")
        if not secret or len(secret.encode("utf-8")) < 32:
            return jsonify(
                {"status": "unavailable", "dependency": "configuration"}
            ), 503
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            previous = app.extensions.get("mis_eventos_readiness")
            app.extensions["mis_eventos_readiness"] = False
            if previous is not False:
                get_logger("readiness").warning(
                    "Backend readiness check failed.",
                    extra={"stage": "database_readiness", **_log_context(app)},
                )
            return jsonify({"status": "unavailable", "dependency": "database"}), 503
        previous = app.extensions.get("mis_eventos_readiness")
        app.extensions["mis_eventos_readiness"] = True
        if previous is not True:
            get_logger("readiness").info(
                "Backend readiness check passed.",
                extra={"stage": "database_readiness", **_log_context(app)},
            )
        return jsonify({"status": "ok"}), 200


def _register_http_instrumentation(app: Flask) -> None:
    """Add bounded request metrics, correlation IDs, and structured access logs."""

    @app.before_request
    def begin_request():
        """Attach a safe correlation identifier and start timing the request."""
        incoming_id = request.headers.get("X-Request-ID", "")
        g.request_id = (
            incoming_id
            if len(incoming_id) <= 64
            and incoming_id.replace("-", "").replace("_", "").replace(".", "").isalnum()
            else uuid.uuid4().hex
        )
        g.request_started = time.perf_counter()
        g.metric_route = _normalized_route()
        g.metric_enabled = g.metric_route not in EXCLUDED_METRIC_ROUTES
        if g.metric_enabled:
            metrics: ApplicationMetrics = app.extensions["mis_eventos_metrics"]
            metrics.http_requests_in_progress.inc()

    @app.after_request
    def finish_request(response):
        """Emit access logs and bounded metrics after a Flask response."""
        request_id = getattr(g, "request_id", uuid.uuid4().hex)
        response.headers["X-Request-ID"] = request_id
        duration = max(
            time.perf_counter() - getattr(g, "request_started", time.perf_counter()), 0
        )
        route = getattr(g, "metric_route", _normalized_route())
        if getattr(g, "metric_enabled", False):
            metrics: ApplicationMetrics = app.extensions["mis_eventos_metrics"]
            metrics.http_requests_in_progress.dec()
            labels = {"method": request.method, "route": route}
            metrics.http_requests.labels(
                status_code=str(response.status_code), **labels
            ).inc()
            metrics.http_request_duration.labels(**labels).observe(duration)
        get_logger("http").info(
            "HTTP request completed.",
            extra={
                **_log_context(app),
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status_code": response.status_code,
                "duration_seconds": round(duration, 6),
            },
        )
        return response


def _normalized_route() -> str:
    """Return the Flask route template without exposing raw path identifiers."""
    return request.url_rule.rule if request.url_rule else "unmatched"

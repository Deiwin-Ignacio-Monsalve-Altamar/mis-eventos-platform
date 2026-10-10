"""Test backend logging, HTTP metrics, readiness checks, and business counters."""

import json
import runpy
from datetime import UTC, datetime
from http import HTTPStatus
from io import StringIO
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy.exc import OperationalError

from app.application.events.service import EventService
from app.application.registrations.service import EventRegistrationService
from app.config import load_config
from app.domain.entities.event_record import EventRecord
from app.domain.entities.event_registration import EventRegistrationRecord
from app.extensions import db
from app.main import create_app
from app.observability.logging import JsonFormatter, get_logger
from app.observability.metrics import increment_business_metric


def test_json_formatter_includes_common_fields_and_redacts_secrets():
    """Format structured metadata and redact values embedded in exception text."""
    record = Mock()
    record.created = 1_760_000_000.0
    record.levelname = "ERROR"
    record.getMessage.return_value = "Request failed token=private-value"
    record.exc_info = None
    record.service = "mis-eventos-backend"
    record.environment = "test"
    record.version = "test-sha"
    record.request_id = "request-123"
    record.method = None
    record.route = None
    record.status_code = None
    record.duration_seconds = None
    record.stage = None

    formatted = JsonFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["service"] == "mis-eventos-backend"
    assert payload["severity"] == "ERROR"
    assert payload["request_id"] == "request-123"
    assert "private-value" not in formatted
    assert "token=[REDACTED]" in formatted


def test_http_metrics_use_normalized_routes_and_exclude_metrics_endpoint(monkeypatch):
    """Count HTTP status and duration with route templates and bounded labels."""
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    app = create_app()
    app.config.update(TESTING=True)

    def observed_route(item_id):
        """Return an observed response with a caller-controlled path identifier."""
        return {"id": item_id}, HTTPStatus.OK

    app.add_url_rule(
        "/observed/<int:item_id>", "observed_route", observed_route, methods=["GET"]
    )
    client = app.test_client()
    response = client.get("/observed/987654", headers={"X-Request-ID": "trace-7"})
    metrics_response = client.get("/metrics")
    exposition = metrics_response.get_data(as_text=True)

    assert response.status_code == HTTPStatus.OK
    assert response.headers["X-Request-ID"] == "trace-7"
    assert (
        f'mis_eventos_http_requests_total{{method="GET",route="/observed/<int:item_id>",status_code="{HTTPStatus.OK.value}"}} 1.0'
        in exposition
    )
    assert "mis_eventos_http_request_duration_seconds_bucket" in exposition
    assert "mis_eventos_http_requests_in_progress 0.0" in exposition
    assert 'route="/metrics"' not in exposition


def test_liveness_is_independent_of_database_and_readiness_checks_configuration(
    monkeypatch,
):
    """Keep liveness available while readiness rejects a missing signing secret."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    app = create_app()
    client = app.test_client()

    assert client.get("/api/v1/live").status_code == HTTPStatus.OK
    response = client.get("/api/v1/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json == {"status": "unavailable", "dependency": "configuration"}


def test_readiness_returns_unavailable_when_database_connection_fails(monkeypatch):
    """Return service unavailable without exposing database connection details."""
    monkeypatch.setenv("JWT_SECRET_KEY", "s" * 40)
    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        monkeypatch.setattr(
            db.engine,
            "connect",
            Mock(side_effect=OperationalError("SELECT 1", {}, Exception("offline"))),
        )

    response = app.test_client().get("/api/v1/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json == {"status": "unavailable", "dependency": "database"}


def test_readiness_returns_ok_when_configuration_and_database_are_available(
    monkeypatch,
):
    """Return readiness success after the JWT configuration and DB probe pass."""
    monkeypatch.setenv("JWT_SECRET_KEY", "r" * 40)
    app = create_app()
    app.config.update(TESTING=True)

    class SuccessfulConnection:
        """Provide a context-managed SQL connection without external services."""

        def __enter__(self):
            """Enter the fake connection context."""
            return self

        def __exit__(self, exception_type, exception, traceback):
            """Close the fake context without suppressing exceptions."""
            return False

        def execute(self, statement):
            """Accept the lightweight readiness query."""
            assert str(statement) == "SELECT 1"
            return 1

    with app.app_context():
        monkeypatch.setattr(db.engine, "connect", SuccessfulConnection)

    response = app.test_client().get("/api/v1/ready")

    assert response.status_code == HTTPStatus.OK
    assert response.json == {"status": "ok"}


def test_unexpected_http_exception_is_structured_once_and_sensitive_values_are_redacted(
    monkeypatch,
):
    """Log unexpected traceback context once without leaking secrets or emails."""
    monkeypatch.setenv("JWT_SECRET_KEY", "e" * 40)
    app = create_app()
    app.config.update(TESTING=True)

    def failing_route():
        """Raise a synthetic internal error containing sensitive text."""
        raise RuntimeError(
            "request token=private-token user=person@example.test password=private-password"
        )

    app.add_url_rule("/failure", "failing_route", failing_route)
    handler = get_logger("http").parent.handlers[0]
    previous_stream = handler.stream
    stream = StringIO()
    handler.setStream(stream)
    try:
        response = app.test_client().get("/failure")
    finally:
        handler.setStream(previous_stream)
    output = stream.getvalue()

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.json == {
        "error": {"code": "internal_error", "message": "An unexpected error occurred."}
    }
    assert '"exception_type":"RuntimeError"' in output
    assert '"route":"/failure"' in output
    assert "private-token" not in output
    assert "private-password" not in output
    assert "person@example.test" not in output
    assert output.count("Unhandled request exception.") == 1


def test_repeated_app_creation_does_not_add_duplicate_structured_handlers():
    """Keep exactly one application logging handler across Flask factories."""
    logger = get_logger("lifecycle")
    previous_count = len(logger.parent.handlers)

    create_app()
    create_app()

    assert len(logger.parent.handlers) == max(previous_count, 1)


def test_invalid_runtime_configuration_fails_at_a_logged_initialization_stage(
    monkeypatch,
):
    """Reject invalid token lifetime configuration and log its initialization stage."""
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL_SECONDS", "not-a-number")

    handler = get_logger("http").parent.handlers[0]
    previous_stream = handler.stream
    stream = StringIO()
    handler.setStream(stream)
    try:
        with pytest.raises(ValueError, match="must be an integer"):
            create_app()
    finally:
        handler.setStream(previous_stream)
    output = stream.getvalue()
    assert '"stage":"configuration"' in output
    assert "JWT_ACCESS_TOKEN_TTL_SECONDS" in output


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("JWT_ACCESS_TOKEN_TTL_SECONDS", "0", "must be positive"),
        ("DATABASE_URL", "  ", "DATABASE_URL must not be empty"),
    ],
)
def test_runtime_configuration_rejects_empty_required_values(
    monkeypatch, name, value, message
):
    """Reject nonpositive token lifetime and empty database connection settings."""
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        load_config()


def test_local_cookie_security_defaults_to_http_compatible_and_normalizes_environment(
    monkeypatch,
):
    """Default local cookies to HTTP-compatible behavior and normalize the name."""
    monkeypatch.setenv("APP_ENVIRONMENT", " Local ")
    monkeypatch.delenv("JWT_COOKIE_SECURE", raising=False)

    config = load_config()

    assert config["APP_ENVIRONMENT"] == "local"
    assert config["JWT_COOKIE_SECURE"] is False


@pytest.mark.parametrize(
    ("cookie_setting", "expected"),
    [("true", True), (" TRUE ", True), ("false", False), (" False ", False)],
)
def test_local_cookie_security_accepts_explicit_boolean_values(
    monkeypatch, cookie_setting, expected
):
    """Accept case-insensitive boolean text with surrounding whitespace locally."""
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.setenv("JWT_COOKIE_SECURE", cookie_setting)

    assert load_config()["JWT_COOKIE_SECURE"] is expected


def test_production_cookie_security_defaults_to_secure_and_normalizes_environment(
    monkeypatch,
):
    """Require Secure cookies by default for a normalized production environment."""
    monkeypatch.setenv("APP_ENVIRONMENT", " Production ")
    monkeypatch.delenv("JWT_COOKIE_SECURE", raising=False)

    config = load_config()

    assert config["APP_ENVIRONMENT"] == "production"
    assert config["JWT_COOKIE_SECURE"] is True


@pytest.mark.parametrize("cookie_setting", ["true", " TRUE "])
def test_production_accepts_explicit_secure_cookie_setting(monkeypatch, cookie_setting):
    """Allow production to start when Secure cookies are explicitly enabled."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_COOKIE_SECURE", cookie_setting)

    assert load_config()["JWT_COOKIE_SECURE"] is True


def test_production_rejects_explicitly_insecure_cookie_setting(monkeypatch):
    """Prevent the Flask application from starting with insecure prod cookies."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_COOKIE_SECURE", "false")

    with pytest.raises(
        ValueError, match="JWT_COOKIE_SECURE must be true in production"
    ):
        create_app()


@pytest.mark.parametrize("cookie_setting", ["", "yes", "1", "enabled"])
def test_cookie_security_rejects_invalid_values(monkeypatch, cookie_setting):
    """Reject cookie security settings outside the supported boolean text values."""
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.setenv("JWT_COOKIE_SECURE", cookie_setting)

    with pytest.raises(
        ValueError, match="JWT_COOKIE_SECURE must be either 'true' or 'false'"
    ):
        load_config()


def test_server_lifecycle_logs_graceful_shutdown_without_starting_a_socket(
    monkeypatch,
):
    """Exercise the executable entry point with a controlled interrupt."""
    monkeypatch.setenv("JWT_SECRET_KEY", "l" * 40)

    def stop_server(self, host, port):
        """Simulate a user-requested server shutdown without binding a port."""
        raise KeyboardInterrupt

    monkeypatch.setattr(Flask, "run", stop_server)
    handler = get_logger("lifecycle").parent.handlers[0]
    previous_stream = handler.stream
    stream = StringIO()
    handler.setStream(stream)
    try:
        runpy.run_module("app.__main__", run_name="__main__")
    finally:
        handler.setStream(previous_stream)

    output = stream.getvalue()
    assert '"stage":"server_start"' in output
    assert "Backend shutdown requested." in output
    assert "Backend HTTP server stopped." in output


def test_server_lifecycle_logs_and_propagates_unexpected_start_failure(monkeypatch):
    """Log runtime startup failure and always execute graceful cleanup logging."""
    monkeypatch.setenv("JWT_SECRET_KEY", "f" * 40)

    def fail_server(self, host, port):
        """Simulate an unexpected server failure without network activity."""
        raise OSError("server launch failed")

    monkeypatch.setattr(Flask, "run", fail_server)
    handler = get_logger("lifecycle").parent.handlers[0]
    previous_stream = handler.stream
    stream = StringIO()
    handler.setStream(stream)
    try:
        with pytest.raises(OSError, match="server launch failed"):
            runpy.run_module("app.__main__", run_name="__main__")
    finally:
        handler.setStream(previous_stream)

    output = stream.getvalue()
    assert '"stage":"server_runtime"' in output
    assert '"exception_type":"OSError"' in output
    assert "Backend HTTP server stopped." in output


def test_business_counters_increment_only_after_successful_operations(monkeypatch):
    """Increment event and registration counters after repository success only."""
    monkeypatch.setenv("JWT_SECRET_KEY", "b" * 40)
    app = create_app()
    event = EventRecord(
        id=4,
        title="Observability",
        starts_at=datetime(2032, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2032, 1, 1, 11, tzinfo=UTC),
        capacity=20,
        created_by_id=9,
    )
    event_repository = Mock()
    event_repository.save.return_value = event
    registration_repository = Mock()
    registration_repository.register.return_value = EventRegistrationRecord(
        5, 4, 9, "registered"
    )

    with app.app_context():
        EventService(event_repository).create(
            {
                "title": "Observability",
                "starts_at": "2032-01-01T10:00:00+00:00",
                "ends_at": "2032-01-01T11:00:00+00:00",
                "capacity": 20,
            },
            creator_id=9,
        )
        EventRegistrationService(registration_repository).register(4, 9)
        registration_repository.register.side_effect = RuntimeError(
            "registration persistence failed"
        )
        with pytest.raises(RuntimeError, match="registration persistence failed"):
            EventRegistrationService(registration_repository).register(4, 10)
        event_repository.save.side_effect = RuntimeError("persistence failed")
        with pytest.raises(RuntimeError, match="persistence failed"):
            EventService(event_repository).create(
                {
                    "title": "Failed",
                    "starts_at": "2032-01-01T10:00:00+00:00",
                    "ends_at": "2032-01-01T11:00:00+00:00",
                    "capacity": 20,
                },
                creator_id=9,
            )

    exposition, _ = app.extensions["mis_eventos_metrics"].render()
    exposition_text = exposition.decode()

    assert "mis_eventos_business_events_created_total 1.0" in exposition_text
    assert "mis_eventos_business_registrations_total 1.0" in exposition_text


def test_business_metric_is_ignored_without_flask_context():
    """Allow optional business instrumentation outside Flask execution."""
    increment_business_metric("event_created")


def test_business_metric_is_ignored_when_extension_is_not_registered():
    """Allow a partial Flask app to run without metrics initialization."""
    app = Flask(__name__)

    with app.app_context():
        increment_business_metric("event_created")


def test_business_operation_succeeds_without_metrics_extension():
    """Keep event creation successful when a partial app has no metrics extension."""
    app = Flask(__name__)
    event = EventRecord(
        id=8,
        title="Metrics unavailable",
        starts_at=datetime(2032, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2032, 1, 1, 11, tzinfo=UTC),
        capacity=20,
        created_by_id=9,
    )
    event_repository = Mock()
    event_repository.save.return_value = event

    with app.app_context():
        created = EventService(event_repository).create(
            {
                "title": "Metrics unavailable",
                "starts_at": "2032-01-01T10:00:00+00:00",
                "ends_at": "2032-01-01T11:00:00+00:00",
                "capacity": 20,
            },
            creator_id=9,
        )

    assert created is event
    event_repository.save.assert_called_once()


def test_business_operation_succeeds_when_metric_recording_fails(monkeypatch):
    """Keep successful event and registration writes when an optional counter fails."""
    monkeypatch.setenv("JWT_SECRET_KEY", "m" * 40)
    app = create_app()
    event = EventRecord(
        id=7,
        title="Metrics resilience",
        starts_at=datetime(2032, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2032, 1, 1, 11, tzinfo=UTC),
        capacity=20,
        created_by_id=9,
    )
    event_repository = Mock()
    event_repository.save.return_value = event
    registration = EventRegistrationRecord(8, 7, 9, "registered")
    registration_repository = Mock()
    registration_repository.register.return_value = registration
    handler = get_logger("metrics").parent.handlers[0]
    previous_stream = handler.stream
    stream = StringIO()
    handler.setStream(stream)

    try:
        with app.app_context():
            metrics = app.extensions["mis_eventos_metrics"]
            monkeypatch.setattr(
                metrics.business_events_created,
                "inc",
                Mock(side_effect=RuntimeError("event metric failure")),
            )
            monkeypatch.setattr(
                metrics.business_registrations,
                "inc",
                Mock(side_effect=RuntimeError("registration metric failure")),
            )
            created = EventService(event_repository).create(
                {
                    "title": "Metrics resilience",
                    "starts_at": "2032-01-01T10:00:00+00:00",
                    "ends_at": "2032-01-01T11:00:00+00:00",
                    "capacity": 20,
                },
                creator_id=9,
            )
            registered = EventRegistrationService(registration_repository).register(
                7, 9
            )
    finally:
        handler.setStream(previous_stream)

    assert created is event
    assert registered is registration
    event_repository.save.assert_called_once()
    registration_repository.register.assert_called_once_with(7, 9)
    assert "Optional business metric recording failed." in stream.getvalue()
    assert "event metric failure" in stream.getvalue()
    assert "registration metric failure" in stream.getvalue()

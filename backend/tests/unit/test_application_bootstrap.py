"""Verify Flask application wiring without opening external connections."""

from flask import Flask

from app.application.auth.service import AuthService
from app.application.events.service import EventService
from app.application.health.service import HealthService
from app.application.registrations.service import EventRegistrationService
from app.application.sessions.attendees import SessionAttendeeService
from app.application.sessions.service import SessionService
from app.dependencies import (
    get_auth_service,
    get_event_registration_service,
    get_event_service,
    get_health_service,
    get_session_attendee_service,
    get_session_service,
)
from app.main import create_app


def test_application_factory_registers_routes_and_api_documentation():
    """Wire health, API blueprints, and Swagger without connecting to PostgreSQL."""
    app = create_app()
    client = app.test_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
    assert app.config["SWAGGER"]["openapi"] == "3.0.3"
    assert app.config["SWAGGER"]["title"]
    registered_rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/v1/auth/register" in registered_rules
    assert "/api/v1/events" in registered_rules
    assert "/api/v1/events/<int:event_id>/sessions" in registered_rules


def test_dependency_factories_build_services_in_flask_context():
    """Construct request-scoped application services over the configured session."""
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="a" * 32, JWT_ACCESS_TOKEN_TTL_SECONDS=120)

    with app.app_context():
        auth_service = get_auth_service()
        event_service = get_event_service()
        session_service = get_session_service()
        attendee_service = get_session_attendee_service()
        registration_service = get_event_registration_service()
        health_service = get_health_service()

    assert isinstance(auth_service, AuthService)
    assert isinstance(event_service, EventService)
    assert isinstance(session_service, SessionService)
    assert isinstance(attendee_service, SessionAttendeeService)
    assert isinstance(registration_service, EventRegistrationService)
    assert isinstance(health_service, HealthService)

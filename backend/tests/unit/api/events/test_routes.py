"""Verify event HTTP behavior with mocked application and authentication services."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.auth import decorators
from app.api.events import routes as event_routes
from app.api.events.routes import event_bp
from app.application.dto.event_page import EventPage
from app.core.exceptions import (
    AuthenticationError,
    ConcurrencyConflictError,
    DuplicateRegistrationError,
    EventCapacityExceededError,
    NotFoundError,
    RelatedRecordsError,
    ValidationError,
)
from app.domain.entities.event_record import EventRecord
from app.domain.entities.event_registration import EventRegistrationRecord
from app.domain.entities.user_account import UserAccount

TEST_TOKEN = "test-access-token"
ACCOUNT = UserAccount(
    id=7,
    email="organizer@example.test",
    password_hash="private-password-hash",
    first_name="Alex",
    last_name="Rivera",
)
EVENT = EventRecord(
    id=12,
    title="Data Conference",
    description="Engineering topics",
    location="Bogota",
    starts_at=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    ends_at=datetime(2030, 1, 1, 12, 0, tzinfo=UTC),
    capacity=100,
    status="draft",
    created_by_id=7,
)


@pytest.fixture
def event_client(monkeypatch):
    """Provide event routes with mocked services and no database connection."""
    app = Flask(__name__)
    event_service = Mock()
    event_service.create.return_value = EVENT
    event_service.update.return_value = EVENT
    event_service.get_by_id.return_value = EVENT
    event_service.list_events.return_value = EventPage(
        events=(EVENT,), page=1, page_size=20, total=1
    )
    registration_service = Mock()
    registration_service.register.return_value = EventRegistrationRecord(
        31, EVENT.id, ACCOUNT.id, "registered"
    )
    event_service.registration_service = registration_service
    auth_service = Mock()
    auth_service.get_authenticated_user.return_value = ACCOUNT
    monkeypatch.setattr(event_routes, "get_event_service", lambda: event_service)
    monkeypatch.setattr(
        event_routes,
        "get_event_registration_service",
        lambda: registration_service,
    )
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth_service)
    app.register_blueprint(event_bp, url_prefix="/api/v1")
    return app.test_client(), event_service, auth_service


def add_valid_access_cookie(client):
    """Attach a cookie recognized by the mocked authentication service."""
    client.set_cookie("access_token", TEST_TOKEN)


def valid_event_payload(**overrides):
    """Build a valid event request body with optional overrides."""
    payload = {
        "title": "New Event",
        "description": "A technical conference",
        "location": "Bogota",
        "starts_at": "2030-01-01T10:00:00+00:00",
        "ends_at": "2030-01-01T12:00:00+00:00",
        "capacity": 100,
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_create_event_maps_response_and_uses_authenticated_identity(event_client):
    """Return 201 and pass the token-resolved user ID to the event service."""
    client, event_service, auth_service = event_client
    add_valid_access_cookie(client)

    response = client.post(
        "/api/v1/events", json=valid_event_payload(created_by_id=999)
    )

    assert response.status_code == 201
    assert response.json["event"]["id"] == EVENT.id
    event_service.create.assert_called_once_with(
        valid_event_payload(), creator_id=ACCOUNT.id
    )
    auth_service.get_authenticated_user.assert_called_once_with(TEST_TOKEN)


def test_create_event_rejects_non_object_json_without_calling_service(event_client):
    """Return 400 for a non-object body before calling the event service."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    response = client.post("/api/v1/events", json=["invalid"])

    assert response.status_code == 400
    assert response.json["error"] == {
        "code": "invalid_request",
        "message": "A JSON object is required.",
    }
    event_service.create.assert_not_called()


def test_create_and_update_map_service_validation_errors(event_client):
    """Convert create and update validation failures into consistent API errors."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.create.side_effect = ValidationError("Invalid capacity.")
    event_service.update.side_effect = ValidationError("Invalid date range.")

    create_response = client.post("/api/v1/events", json=valid_event_payload())
    update_response = client.patch(
        "/api/v1/events/12", json={"capacity": 0, "version": 1}
    )

    assert create_response.status_code == 400
    assert update_response.status_code == 400
    assert create_response.json["error"] == {
        "code": "validation_error",
        "message": "Invalid capacity.",
    }
    assert update_response.json["error"] == {
        "code": "validation_error",
        "message": "Invalid date range.",
    }


@pytest.mark.parametrize("method", ["post", "patch"])
def test_event_writes_require_authentication(event_client, method):
    """Reject event creation and editing without a cookie before service calls."""
    client, event_service, auth_service = event_client
    request = getattr(client, method)
    path = "/api/v1/events" if method == "post" else "/api/v1/events/12"
    kwargs = (
        {"json": valid_event_payload()}
        if method == "post"
        else {"json": {"title": "Updated"}}
    )

    response = request(path, **kwargs)

    assert response.status_code == 401
    assert response.json["error"] == {
        "code": "authentication_required",
        "message": "Authentication is required.",
    }
    event_service.create.assert_not_called()
    event_service.update.assert_not_called()
    auth_service.get_authenticated_user.assert_not_called()


@pytest.mark.parametrize("method", ["post", "patch"])
def test_event_writes_reject_invalid_tokens(event_client, method):
    """Reject invalid credentials for both event creation and editing."""
    client, event_service, auth_service = event_client
    auth_service.get_authenticated_user.side_effect = AuthenticationError(
        "Invalid token."
    )
    add_valid_access_cookie(client)
    request = getattr(client, method)
    path = "/api/v1/events" if method == "post" else "/api/v1/events/12"
    kwargs = (
        {"json": valid_event_payload()}
        if method == "post"
        else {"json": {"title": "Updated"}}
    )

    response = request(path, **kwargs)

    assert response.status_code == 401
    assert response.json["error"] == {
        "code": "invalid_token",
        "message": "Authentication is required.",
    }
    event_service.create.assert_not_called()
    event_service.update.assert_not_called()


def test_update_event_calls_service_and_returns_event(event_client):
    """Return the updated event after passing only supported request fields."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    response = client.patch(
        "/api/v1/events/12",
        json={"title": "Revised Event", "created_by_id": 999, "version": 1},
    )

    assert response.status_code == 200
    assert response.json["event"]["title"] == EVENT.title
    event_service.update.assert_called_once_with(12, {"title": "Revised Event"}, 1)


def test_update_event_returns_conflict_with_current_version(event_client):
    """Return the latest version when the submitted event version is stale."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.update.side_effect = ConcurrencyConflictError(
        "The event changed since it was loaded.", current_version=3
    )

    response = client.patch(
        "/api/v1/events/12", json={"title": "Revised", "version": 2}
    )

    assert response.status_code == 409
    assert response.json["error"] == {
        "code": "concurrency_conflict",
        "message": "The event changed since it was loaded.",
        "current_version": 3,
    }


def test_update_event_requires_a_positive_version(event_client):
    """Reject an update without a usable version before calling the service."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    response = client.patch("/api/v1/events/12", json={"title": "Revised"})

    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"
    event_service.update.assert_not_called()


def test_event_registration_endpoints_use_authenticated_user(event_client):
    """Register and cancel only the identity resolved from the access token."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    registration = client.post(
        "/api/v1/events/12/registrations/me", json={"user_id": 999}
    )
    cancellation = client.delete("/api/v1/events/12/registrations/me")

    assert registration.status_code == 201
    assert registration.json["registration"] == {
        "id": 31,
        "event_id": EVENT.id,
        "user_id": ACCOUNT.id,
        "status": "registered",
    }
    assert cancellation.status_code == 204
    event_service.registration_service.register.assert_called_once_with(
        EVENT.id, ACCOUNT.id
    )
    event_service.registration_service.cancel.assert_called_once_with(
        EVENT.id, ACCOUNT.id
    )


@pytest.mark.parametrize("method", ["post", "delete"])
def test_event_registration_writes_require_authentication(event_client, method):
    """Reject event registration mutations without authentication."""
    client, event_service, _ = event_client

    response = getattr(client, method)("/api/v1/events/12/registrations/me")

    assert response.status_code == 401
    event_service.registration_service.register.assert_not_called()
    event_service.registration_service.cancel.assert_not_called()


def test_event_registration_maps_capacity_and_duplicate_conflicts(event_client):
    """Return HTTP 409 for full events and duplicate active registrations."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    registration_service = event_service.registration_service
    registration_service.register.side_effect = EventCapacityExceededError(
        "The event has no available seats."
    )
    full = client.post("/api/v1/events/12/registrations/me")
    registration_service.register.side_effect = DuplicateRegistrationError(
        "The user is already registered for this event."
    )
    duplicate = client.post("/api/v1/events/12/registrations/me")

    assert full.status_code == 409
    assert full.json["error"]["code"] == "capacity_exceeded"
    assert duplicate.status_code == 409
    assert duplicate.json["error"]["code"] == "duplicate_registration"


def test_event_list_maps_page_and_search_results(event_client):
    """Serialize a service page with pagination metadata and the matching events."""
    client, event_service, _ = event_client
    event_service.list_events.return_value = EventPage(
        events=(EVENT,), page=2, page_size=3, total=7
    )

    response = client.get("/api/v1/events?page=2&page_size=3&q=%20engineering%20")

    assert response.status_code == 200
    assert len(response.json["events"]) == 1
    assert response.json["pagination"] == {
        "page": 2,
        "page_size": 3,
        "total": 7,
        "total_pages": 3,
    }
    event_service.list_events.assert_called_once_with(
        page="2", page_size="3", search_query=" engineering "
    )


def test_event_list_maps_service_validation_error(event_client):
    """Return 400 when the application service rejects listing parameters."""
    client, event_service, _ = event_client
    event_service.list_events.side_effect = ValidationError("Invalid page size.")

    response = client.get("/api/v1/events?page_size=invalid")

    assert response.status_code == 400
    assert response.json["error"] == {
        "code": "validation_error",
        "message": "Invalid page size.",
    }


def test_get_event_returns_service_result(event_client):
    """Return an event serialized by the route response envelope."""
    client, event_service, _ = event_client

    response = client.get("/api/v1/events/12")

    assert response.status_code == 200
    assert response.json["event"]["id"] == EVENT.id
    assert response.json["event"]["version"] == EVENT.version
    event_service.get_by_id.assert_called_once_with(12)


def test_get_event_maps_missing_event_to_not_found(event_client):
    """Return 404 when the event service reports an unknown identifier."""
    client, event_service, _ = event_client
    event_service.get_by_id.side_effect = NotFoundError("Event not found.")

    response = client.get("/api/v1/events/999")

    assert response.status_code == 404
    assert response.json["error"] == {
        "code": "not_found",
        "message": "Event not found.",
    }


def test_event_deletion_requires_authentication(event_client):
    """Reject deletion without a token before calling either application service."""
    client, event_service, auth_service = event_client

    response = client.delete("/api/v1/events/12")

    assert response.status_code == 401
    assert response.json["error"] == {
        "code": "authentication_required",
        "message": "Authentication is required.",
    }
    event_service.delete.assert_not_called()
    auth_service.get_authenticated_user.assert_not_called()


def test_event_deletion_rejects_invalid_token(event_client):
    """Reject deletion when token validation raises an authentication error."""
    client, event_service, auth_service = event_client
    auth_service.get_authenticated_user.side_effect = AuthenticationError(
        "Invalid token."
    )
    add_valid_access_cookie(client)

    response = client.delete("/api/v1/events/12")

    assert response.status_code == 401
    assert response.json["error"] == {
        "code": "invalid_token",
        "message": "Authentication is required.",
    }
    event_service.delete.assert_not_called()


def test_event_deletion_returns_no_content(event_client):
    """Return 204 after the event service completes deletion."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    response = client.delete("/api/v1/events/12")

    assert response.status_code == 204
    assert response.data == b""
    event_service.delete.assert_called_once_with(12)


def test_event_deletion_maps_related_record_conflict(event_client):
    """Return 409 when the service refuses to cascade-delete related records."""
    client, event_service, _ = event_client
    event_service.delete.side_effect = RelatedRecordsError(
        "Events with registrations cannot be deleted."
    )
    add_valid_access_cookie(client)

    response = client.delete("/api/v1/events/12")

    assert response.status_code == 409
    assert response.json["error"] == {
        "code": "related_records",
        "message": "Events with registrations cannot be deleted.",
    }


def test_event_deletion_maps_missing_event_to_not_found(event_client):
    """Return 404 when the event service reports a missing event on deletion."""
    client, event_service, _ = event_client
    event_service.delete.side_effect = NotFoundError("Event not found.")
    add_valid_access_cookie(client)

    response = client.delete("/api/v1/events/999")

    assert response.status_code == 404
    assert response.json["error"] == {
        "code": "not_found",
        "message": "Event not found.",
    }

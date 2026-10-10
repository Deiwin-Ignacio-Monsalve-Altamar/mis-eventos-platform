"""Verify event HTTP behavior with mocked application and authentication services."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.auth import decorators
from app.api.events import routes as event_routes
from app.api.events.routes import event_bp
from app.application.dto.event_page import EventPage
from app.application.dto.event_registration_page import EventRegistrationPage
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConcurrencyConflictError,
    DuplicateRegistrationError,
    EventCapacityExceededError,
    EventUnavailableError,
    NotFoundError,
    RelatedRecordsError,
    ValidationError,
)
from app.domain.entities.event_record import EventRecord
from app.domain.entities.event_registration import (
    EventRegistrationDetails,
    EventRegistrationRecord,
)
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
    event_service.list_my_events.return_value = EventPage(
        events=(EVENT,), page=1, page_size=20, total=1
    )
    event_service.get_my_event.return_value = EVENT
    event_service.dashboard.return_value = {
        "total_events": 1,
        "upcoming_events": 1,
        "active_events": 0,
        "finished_events": 0,
        "cancelled_events": 0,
        "status_counts": {"draft": 1, "published": 0, "cancelled": 0, "completed": 0},
        "status_percentages": {
            "draft": 100.0,
            "published": 0.0,
            "cancelled": 0.0,
            "completed": 0.0,
        },
    }
    registration_service = Mock()
    registration_service.register.return_value = EventRegistrationRecord(
        31, EVENT.id, ACCOUNT.id, "registered"
    )
    registration_service.capacity_for_event.return_value = {
        "capacity": 100,
        "occupied": 2,
        "available": 98,
    }
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
    event_service.update.assert_called_once_with(
        12, {"title": "Revised Event"}, 1, creator_id=ACCOUNT.id
    )


def test_update_event_rejects_non_owner_with_forbidden(event_client):
    """Return 403 when the event service denies an authenticated non-owner."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.update.side_effect = AuthorizationError(
        "Only the event creator can edit this event."
    )

    response = client.patch(
        "/api/v1/events/12", json={"title": "Attempt", "version": 1}
    )

    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"
    event_service.update.assert_called_once_with(
        12, {"title": "Attempt"}, 1, creator_id=ACCOUNT.id
    )


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


def test_public_event_capacity_uses_active_registration_counts(event_client):
    """Expose seat availability publicly without requiring an attendee session."""
    client, event_service, _ = event_client

    response = client.get("/api/v1/events/12/capacity")

    assert response.status_code == 200
    assert response.json == {"capacity": 100, "occupied": 2, "available": 98}
    event_service.registration_service.capacity_for_event.assert_called_once_with(12)


def test_public_event_capacity_returns_not_found_for_missing_event(event_client):
    """Keep unknown event identifiers on the established 404 contract."""
    client, event_service, _ = event_client
    event_service.registration_service.capacity_for_event.side_effect = NotFoundError(
        "Event not found."
    )

    response = client.get("/api/v1/events/999/capacity")

    assert response.status_code == 404
    assert response.json["error"]["code"] == "not_found"


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


def test_event_registration_maps_unavailable_event_to_conflict(event_client):
    """Return a stable conflict response when a registration window is closed."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.registration_service.register.side_effect = EventUnavailableError(
        "The event is not open for new registrations."
    )

    response = client.post("/api/v1/events/12/registrations/me")

    assert response.status_code == 409
    assert response.json["error"] == {
        "code": "event_unavailable",
        "message": "The event is not open for new registrations.",
    }


def test_list_my_registrations_returns_owned_active_and_cancelled_events(event_client):
    """Serialize the current user's registrations with their event details."""
    client, event_service, _ = event_client
    registration_service = event_service.registration_service
    add_valid_access_cookie(client)
    registration_service.list_for_user.return_value = EventRegistrationPage(
        registrations=(
            EventRegistrationDetails(
                id=31,
                status="registered",
                registered_at=datetime(2030, 1, 1, 8, tzinfo=UTC),
                event=EVENT,
            ),
            EventRegistrationDetails(
                id=32,
                status="cancelled",
                registered_at=datetime(2030, 1, 2, 8, tzinfo=UTC),
                event=EVENT,
            ),
        ),
        page=1,
        page_size=20,
        total=2,
    )

    response = client.get("/api/v1/registrations/me")

    assert response.status_code == 200
    assert [item["status"] for item in response.json["registrations"]] == [
        "registered",
        "cancelled",
    ]
    assert all(
        item["event"]["id"] == EVENT.id for item in response.json["registrations"]
    )
    assert response.json["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 2,
        "total_pages": 1,
    }
    registration_service.list_for_user.assert_called_once_with(
        ACCOUNT.id, page=None, page_size=None, status=None, period=None
    )
    registration_service.register.assert_not_called()
    registration_service.cancel.assert_not_called()


def test_list_my_registrations_returns_empty_page(event_client):
    """Return HTTP 200 and an empty list when the authenticated user has no records."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.registration_service.list_for_user.return_value = (
        EventRegistrationPage((), page=1, page_size=20, total=0)
    )

    response = client.get("/api/v1/registrations/me")

    assert response.status_code == 200
    assert response.json["registrations"] == []
    assert response.json["pagination"]["total"] == 0


def test_list_my_registrations_requires_authentication(event_client):
    """Do not query registrations until the caller has authenticated."""
    client, event_service, auth_service = event_client

    response = client.get("/api/v1/registrations/me")

    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"
    event_service.registration_service.list_for_user.assert_not_called()
    auth_service.get_authenticated_user.assert_not_called()


def test_list_my_registrations_rejects_arbitrary_user_id(event_client):
    """Reject a requested user ID rather than exposing another account's data."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    response = client.get("/api/v1/registrations/me?user_id=999")

    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"
    event_service.registration_service.list_for_user.assert_not_called()


def test_list_my_registrations_validates_pagination(event_client):
    """Map invalid registration pagination to the standard validation response."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.registration_service.list_for_user.side_effect = ValidationError(
        "page must be a positive integer."
    )

    response = client.get("/api/v1/registrations/me?page=invalid")

    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"


def test_list_my_registrations_forwards_real_status_and_period_filters(event_client):
    """Apply registration filters while retaining token-derived user isolation."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.registration_service.list_for_user.return_value = (
        EventRegistrationPage(registrations=(), page=1, page_size=20, total=0)
    )

    response = client.get("/api/v1/registrations/me?status=registered&period=upcoming")

    assert response.status_code == 200
    event_service.registration_service.list_for_user.assert_called_once_with(
        ACCOUNT.id, page=None, page_size=None, status="registered", period="upcoming"
    )


def test_registration_summary_uses_authenticated_account_and_requires_login(
    event_client,
):
    """Return registration metrics for only the authenticated account."""
    client, event_service, auth_service = event_client
    response = client.get("/api/v1/registrations/me/summary")
    assert response.status_code == 401
    event_service.registration_service.summary_for_user.assert_not_called()
    auth_service.get_authenticated_user.assert_not_called()

    add_valid_access_cookie(client)
    event_service.registration_service.summary_for_user.return_value = {
        "total": 0,
        "active": 0,
        "upcoming": 0,
        "past": 0,
        "cancelled": 0,
    }
    response = client.get("/api/v1/registrations/me/summary")

    assert response.status_code == 200
    assert response.json["summary"]["total"] == 0
    event_service.registration_service.summary_for_user.assert_called_once_with(
        ACCOUNT.id
    )


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


def test_list_my_events_uses_authenticated_identity_and_supports_filters(event_client):
    """Return only the authenticated creator's paginated event result contract."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.list_my_events.return_value = EventPage(
        events=(EVENT,), page=2, page_size=3, total=7
    )

    response = client.get(
        "/api/v1/events/mine?page=2&page_size=3&q=conference&status=draft"
    )

    assert response.status_code == 200
    assert response.json["events"][0]["id"] == EVENT.id
    assert response.json["pagination"] == {
        "page": 2,
        "page_size": 3,
        "total": 7,
        "total_pages": 3,
    }
    assert "created_by_id" not in response.json["events"][0]
    event_service.list_my_events.assert_called_once_with(
        ACCOUNT.id, "2", "3", "conference", "draft"
    )


def test_list_my_events_rejects_owner_id_supplied_by_client(event_client):
    """Never let query parameters override the identity resolved from the cookie."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    response = client.get("/api/v1/events/mine?creator_id=999")

    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"
    event_service.list_my_events.assert_not_called()


def test_list_my_events_requires_authentication(event_client):
    """Do not query owner-scoped records before authenticating the request."""
    client, event_service, auth_service = event_client

    response = client.get("/api/v1/events/mine")

    assert response.status_code == 401
    event_service.list_my_events.assert_not_called()
    auth_service.get_authenticated_user.assert_not_called()


def test_my_event_dashboard_uses_authenticated_identity(event_client):
    """Scope event summary metrics to the user supplied by token validation."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)

    response = client.get("/api/v1/events/mine/summary")

    assert response.status_code == 200
    assert response.json["summary"]["total_events"] == 1
    event_service.dashboard.assert_called_once_with(ACCOUNT.id)


def test_get_my_event_returns_not_found_for_non_owned_event(event_client):
    """Avoid exposing whether an unowned event exists on the management route."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.get_my_event.side_effect = NotFoundError("Event not found.")

    response = client.get("/api/v1/events/mine/12")

    assert response.status_code == 404
    event_service.get_my_event.assert_called_once_with(12, ACCOUNT.id)


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
    event_service.delete.assert_called_once_with(12, creator_id=ACCOUNT.id)


def test_event_deletion_rejects_non_owner_with_forbidden(event_client):
    """Return 403 when the authenticated account does not own the event."""
    client, event_service, _ = event_client
    add_valid_access_cookie(client)
    event_service.delete.side_effect = AuthorizationError(
        "Only the event creator can delete this event."
    )

    response = client.delete("/api/v1/events/12")

    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"
    event_service.delete.assert_called_once_with(12, creator_id=ACCOUNT.id)


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

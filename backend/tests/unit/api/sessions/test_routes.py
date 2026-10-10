"""Verify session routes using mocked application and authentication services."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.auth import decorators
from app.api.sessions import routes
from app.api.sessions.routes import session_bp
from app.core.exceptions import (
    AuthorizationError,
    CapacityExceededError,
    ConcurrencyConflictError,
    DuplicateRegistrationError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.session_attendee import SessionAttendee, SessionOccupancy
from app.domain.entities.session_record import SessionRecord
from app.domain.entities.user_account import UserAccount

RECORD = SessionRecord(
    2,
    1,
    "Talk",
    None,
    datetime(2030, 1, 1, 10, tzinfo=UTC),
    datetime(2030, 1, 1, 11, tzinfo=UTC),
    20,
    (4,),
)
ACCOUNT = UserAccount(7, "person@example.test", "hash", "Alex", "Rivera")


@pytest.fixture
def session_client(monkeypatch):
    """Build session routes with mocked services and no database dependency."""
    app = Flask(__name__)
    service, auth = Mock(), Mock()
    attendee_service = Mock()
    service.create.return_value = RECORD
    service.update.return_value = RECORD
    service.get.return_value = RECORD
    service.list_by_event.return_value = [RECORD]
    attendee_service.list_attendees.return_value = [
        SessionAttendee(
            21,
            "Alex",
            "Rivera",
            "alex@example.test",
            datetime(2030, 1, 1, 9, tzinfo=UTC),
        )
    ]
    attendee_service.get_occupancy.return_value = SessionOccupancy(20, 3, 17)
    auth.get_authenticated_user.return_value = ACCOUNT
    monkeypatch.setattr(routes, "get_session_service", lambda: service)
    monkeypatch.setattr(
        routes, "get_session_attendee_service", lambda: attendee_service
    )
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth)
    app.register_blueprint(session_bp, url_prefix="/api/v1")
    service.attendee_service = attendee_service
    return app.test_client(), service, auth


def add_cookie(client):
    """Attach a test access cookie accepted by the mocked auth service."""
    client.set_cookie("access_token", "valid-test-token")


def test_session_crud_routes(session_client):
    """Return expected statuses and serialized session data across CRUD routes."""
    client, service, _ = session_client
    add_cookie(client)
    body = {
        "title": "Talk",
        "starts_at": "2030-01-01T10:00:00+00:00",
        "ends_at": "2030-01-01T11:00:00+00:00",
        "capacity": 20,
        "speaker_ids": [4],
    }
    created = client.post("/api/v1/events/1/sessions", json=body)
    listed = client.get("/api/v1/events/1/sessions")
    fetched = client.get("/api/v1/events/1/sessions/2")
    updated = client.patch(
        "/api/v1/events/1/sessions/2", json={"title": "Talk", "version": 1}
    )
    deleted = client.delete("/api/v1/events/1/sessions/2")
    assert (
        created.status_code,
        listed.status_code,
        fetched.status_code,
        updated.status_code,
        deleted.status_code,
    ) == (201, 200, 200, 200, 204)
    assert fetched.json["session"]["speaker_ids"] == [4]
    assert fetched.json["session"]["version"] == RECORD.version
    assert deleted.data == b""
    service.create.assert_called_once_with(1, body, creator_id=ACCOUNT.id)
    service.update.assert_called_once_with(
        1, 2, {"title": "Talk"}, 1, creator_id=ACCOUNT.id
    )


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_all_session_writes_require_authentication(session_client, method):
    """Reject every session write without a valid access cookie."""
    client, service, auth = session_client
    path = (
        "/api/v1/events/1/sessions"
        if method == "post"
        else "/api/v1/events/1/sessions/2"
    )
    response = (
        getattr(client, method)(path, json={})
        if method != "delete"
        else client.delete(path)
    )
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"
    service.create.assert_not_called()
    service.update.assert_not_called()
    service.delete.assert_not_called()
    auth.get_authenticated_user.assert_not_called()


def test_session_routes_map_validation_and_not_found_errors(session_client):
    """Map application failures to the standard validation and not-found payloads."""
    client, service, _ = session_client
    add_cookie(client)
    service.create.side_effect = ValidationError("Capacity must be positive.")
    service.get.side_effect = NotFoundError("Session not found for this event.")
    response = client.post("/api/v1/events/1/sessions", json={"capacity": 0})
    missing = client.get("/api/v1/events/1/sessions/99")
    assert response.status_code == 400
    assert response.json["error"] == {
        "code": "validation_error",
        "message": "Capacity must be positive.",
    }
    assert missing.status_code == 404
    assert missing.json["error"]["code"] == "not_found"


def test_create_rejects_unknown_fields_without_calling_service(session_client):
    """Reject unknown creation properties before invoking the application service."""
    client, service, _ = session_client
    add_cookie(client)

    response = client.post(
        "/api/v1/events/1/sessions",
        json={"title": "Talk", "unexpected": "value"},
    )

    assert response.status_code == 400
    assert response.json["error"] == {
        "code": "invalid_request",
        "message": "Unknown field(s): unexpected.",
    }
    service.create.assert_not_called()


def test_update_rejects_unknown_fields_without_calling_service(session_client):
    """Reject unknown update properties before invoking the application service."""
    client, service, _ = session_client
    add_cookie(client)

    response = client.patch("/api/v1/events/1/sessions/2", json={"unexpected": "value"})

    assert response.status_code == 400
    assert response.json["error"] == {
        "code": "invalid_request",
        "message": "Unknown field(s): unexpected.",
    }
    service.update.assert_not_called()


def test_session_write_rejects_non_object_json_without_calling_service(session_client):
    """Reject a JSON array body before invoking the session creation service."""
    client, service, _ = session_client
    add_cookie(client)

    response = client.post("/api/v1/events/1/sessions", json=["Talk"])

    assert response.status_code == 400
    assert response.json["error"] == {
        "code": "invalid_request",
        "message": "A JSON object is required.",
    }
    service.create.assert_not_called()


def test_attendee_can_enroll_and_cancel_only_the_authenticated_identity(session_client):
    """Use the token-resolved account ID for self-service session enrollment."""
    client, service, _ = session_client
    attendee_service = service.attendee_service
    add_cookie(client)

    enrolled = client.post(
        "/api/v1/events/1/sessions/2/attendees", json={"user_id": 999}
    )
    cancelled = client.delete("/api/v1/events/1/sessions/2/attendees/me")

    assert enrolled.status_code == 201
    assert cancelled.status_code == 204
    assert cancelled.data == b""
    attendee_service.enroll.assert_called_once_with(1, 2, ACCOUNT.id)
    attendee_service.cancel.assert_called_once_with(1, 2, ACCOUNT.id)


def test_capacity_and_attendee_roster_endpoints(session_client):
    """Return occupancy counts and the event creator's attendee roster."""
    client, service, _ = session_client
    attendee_service = service.attendee_service
    add_cookie(client)

    capacity = client.get("/api/v1/events/1/sessions/2/capacity")
    roster = client.get("/api/v1/events/1/sessions/2/attendees")

    assert capacity.status_code == 200
    assert capacity.json == {"capacity": 20, "occupied": 3, "available": 17}
    assert roster.status_code == 200
    assert roster.json["attendees"][0]["user_id"] == 21
    attendee_service.list_attendees.assert_called_once_with(1, 2, ACCOUNT.id)


@pytest.mark.parametrize("version", [0, -1, True, "1", None])
def test_update_rejects_non_positive_or_non_integer_versions(session_client, version):
    """Reject invalid optimistic-lock versions before calling the service."""
    client, service, _ = session_client
    add_cookie(client)

    response = client.patch(
        "/api/v1/events/1/sessions/2", json={"title": "Talk", "version": version}
    )

    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"
    service.update.assert_not_called()


def test_session_routes_map_remaining_application_errors(session_client):
    """Translate session lookup, concurrency, enrollment, and permission failures."""
    client, service, _ = session_client
    attendee_service = service.attendee_service
    add_cookie(client)
    service.create.side_effect = NotFoundError("Event not found.")
    service.list_by_event.side_effect = NotFoundError("Event not found.")
    service.update.side_effect = ConcurrencyConflictError("Stale session.", 3)
    service.delete.side_effect = NotFoundError("Session not found.")
    attendee_service.list_attendees.side_effect = AuthorizationError("Creator only.")
    attendee_service.get_occupancy.side_effect = NotFoundError("Session not found.")
    attendee_service.enroll.side_effect = [
        CapacityExceededError("Session is full."),
        DuplicateRegistrationError("Already enrolled."),
        ValidationError("Event enrollment is required."),
        NotFoundError("Session not found."),
    ]
    attendee_service.cancel.side_effect = NotFoundError("Session not found.")

    responses = [
        client.post("/api/v1/events/1/sessions", json={"title": "Talk"}),
        client.get("/api/v1/events/1/sessions"),
        client.patch("/api/v1/events/1/sessions/2", json={"version": 1}),
        client.delete("/api/v1/events/1/sessions/2"),
        client.get("/api/v1/events/1/sessions/2/attendees"),
        client.get("/api/v1/events/1/sessions/2/capacity"),
        client.post("/api/v1/events/1/sessions/2/attendees"),
        client.post("/api/v1/events/1/sessions/2/attendees"),
        client.post("/api/v1/events/1/sessions/2/attendees"),
        client.post("/api/v1/events/1/sessions/2/attendees"),
        client.delete("/api/v1/events/1/sessions/2/attendees/me"),
    ]

    assert [response.status_code for response in responses] == [
        404,
        404,
        409,
        404,
        403,
        404,
        409,
        409,
        400,
        404,
        404,
    ]
    assert responses[2].json["error"]["code"] == "concurrency_conflict"


def test_session_mutations_return_forbidden_for_non_owners(session_client):
    """Translate service ownership failures for create, update, and delete."""
    client, service, _ = session_client
    add_cookie(client)
    forbidden = AuthorizationError("Only the event creator can manage sessions.")
    service.create.side_effect = forbidden
    service.update.side_effect = forbidden
    service.delete.side_effect = forbidden

    responses = [
        client.post(
            "/api/v1/events/1/sessions",
            json={
                "title": "Talk",
                "starts_at": "2030-01-01T10:00:00+00:00",
                "ends_at": "2030-01-01T11:00:00+00:00",
                "capacity": 20,
            },
        ),
        client.patch(
            "/api/v1/events/1/sessions/2", json={"title": "Talk", "version": 1}
        ),
        client.delete("/api/v1/events/1/sessions/2"),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403]
    assert all(response.json["error"]["code"] == "forbidden" for response in responses)


def test_roster_rejects_non_owner_and_enrollment_maps_full_capacity(session_client):
    """Map roster authorization and full-session failures to standard errors."""
    client, service, _ = session_client
    attendee_service = service.attendee_service
    add_cookie(client)
    attendee_service.list_attendees.side_effect = AuthorizationError(
        "Only the event creator can view session attendees."
    )
    attendee_service.enroll.side_effect = CapacityExceededError(
        "The session has no available seats."
    )

    roster = client.get("/api/v1/events/1/sessions/2/attendees")
    full = client.post("/api/v1/events/1/sessions/2/attendees", json={})

    assert roster.status_code == 403
    assert roster.json["error"]["code"] == "forbidden"
    assert full.status_code == 409
    assert full.json["error"]["code"] == "capacity_exceeded"


def test_session_enrollment_requires_authentication(session_client):
    """Reject self-enrollment without a token before calling attendee service."""
    client, service, _ = session_client

    response = client.post("/api/v1/events/1/sessions/2/attendees", json={})

    assert response.status_code == 401
    service.attendee_service.enroll.assert_not_called()


def test_update_session_returns_conflict_with_current_version(session_client):
    """Return the latest session version when an update uses a stale version."""
    client, service, _ = session_client
    add_cookie(client)
    service.update.side_effect = ConcurrencyConflictError(
        "The session changed since it was loaded.", current_version=4
    )

    response = client.patch(
        "/api/v1/events/1/sessions/2",
        json={"title": "Revised", "version": 3},
    )

    assert response.status_code == 409
    assert response.json["error"] == {
        "code": "concurrency_conflict",
        "message": "The session changed since it was loaded.",
        "current_version": 4,
    }


def test_update_session_requires_a_positive_version(session_client):
    """Reject an update without a version before invoking the session service."""
    client, service, _ = session_client
    add_cookie(client)

    response = client.patch("/api/v1/events/1/sessions/2", json={"title": "Revised"})

    assert response.status_code == 400
    assert response.json["error"]["code"] == "invalid_request"
    service.update.assert_not_called()

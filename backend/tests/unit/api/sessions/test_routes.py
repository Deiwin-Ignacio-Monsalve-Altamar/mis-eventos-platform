"""Verify session routes using mocked application and authentication services."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.auth import decorators
from app.api.sessions import routes
from app.api.sessions.routes import session_bp
from app.core.exceptions import NotFoundError, ValidationError
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
    service.create.return_value = RECORD
    service.update.return_value = RECORD
    service.get.return_value = RECORD
    service.list_by_event.return_value = [RECORD]
    auth.get_authenticated_user.return_value = ACCOUNT
    monkeypatch.setattr(routes, "get_session_service", lambda: service)
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth)
    app.register_blueprint(session_bp, url_prefix="/api/v1")
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
    }
    created = client.post("/api/v1/events/1/sessions", json=body)
    listed = client.get("/api/v1/events/1/sessions")
    fetched = client.get("/api/v1/events/1/sessions/2")
    updated = client.patch("/api/v1/events/1/sessions/2", json={"title": "Talk"})
    deleted = client.delete("/api/v1/events/1/sessions/2")
    assert (
        created.status_code,
        listed.status_code,
        fetched.status_code,
        updated.status_code,
        deleted.status_code,
    ) == (201, 200, 200, 200, 204)
    assert fetched.json["session"]["speaker_ids"] == [4]
    service.create.assert_called_once_with(1, body)
    service.update.assert_called_once_with(1, 2, {"title": "Talk"})


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

"""Verify event creation and editing require a valid authenticated user."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from flask import Flask

from app.api.events.routes import event_bp
from app.core.security import create_access_token
from app.extensions import db
from app.infrastructure.database.models import Event, User

TEST_JWT_SECRET = "event-route-tests-signing-secret-with-more-than-32-bytes"
EVENT_START = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
EVENT_END = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def event_client():
    """Provide event endpoints and isolated SQLite records for API tests."""
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=TEST_JWT_SECRET,
        JWT_ACCESS_TOKEN_TTL_SECONDS=3600,
        JWT_COOKIE_SECURE=False,
    )
    db.init_app(app)
    app.register_blueprint(event_bp, url_prefix="/api/v1")

    with app.app_context():
        db.create_all()
        user = User(
            email="organizer@example.test",
            password_hash="test-hash",
            first_name="Alex",
            last_name="Rivera",
        )
        db.session.add(user)
        db.session.flush()
        event = Event(
            title="Existing Event",
            starts_at=EVENT_START,
            ends_at=EVENT_END,
            capacity=50,
            created_by_id=user.id,
        )
        db.session.add(event)
        db.session.commit()
        user_id = user.id
        event_id = event.id

    yield app.test_client(), user_id, event_id

    with app.app_context():
        db.session.remove()
        db.drop_all()


def valid_event_payload(**overrides):
    """Build a valid event payload and apply optional test-specific values."""
    values = {
        "title": "New Event",
        "description": "A technical conference",
        "location": "Bogota",
        "starts_at": EVENT_START.isoformat(),
        "ends_at": EVENT_END.isoformat(),
        "capacity": 100,
        "status": "draft",
    }
    values.update(overrides)
    return values


def set_authenticated_cookie(client, user_id):
    """Attach a valid access token for the fixture user to the client."""
    token = create_access_token(user_id, TEST_JWT_SECRET, 3600)
    client.set_cookie("access_token", token)


def test_event_creation_and_editing_reject_missing_tokens_without_changes(
    event_client,
):
    """Reject unauthenticated create and edit requests without changing records."""
    client, _, event_id = event_client

    create_response = client.post("/api/v1/events", json=valid_event_payload())
    update_response = client.patch(
        f"/api/v1/events/{event_id}", json={"title": "Unauthorized edit"}
    )

    assert create_response.status_code == 401
    assert update_response.status_code == 401
    with client.application.app_context():
        assert db.session.query(Event).count() == 1
        assert db.session.get(Event, event_id).title == "Existing Event"


@pytest.mark.parametrize("token_kind", ["invalid", "expired"])
def test_event_creation_and_editing_reject_invalid_or_expired_tokens(
    event_client, token_kind
):
    """Reject invalid and expired credentials for both protected event operations."""
    client, user_id, event_id = event_client
    if token_kind == "invalid":
        token = "not-a-valid-token"
    else:
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(user_id),
                "iat": now - timedelta(minutes=2),
                "exp": now - timedelta(minutes=1),
                "type": "access",
            },
            TEST_JWT_SECRET,
            algorithm="HS256",
        )
    client.set_cookie("access_token", token)

    create_response = client.post("/api/v1/events", json=valid_event_payload())
    update_response = client.patch(
        f"/api/v1/events/{event_id}", json={"title": "Unauthorized edit"}
    )

    assert create_response.status_code == 401
    assert update_response.status_code == 401
    with client.application.app_context():
        assert db.session.query(Event).count() == 1
        assert db.session.get(Event, event_id).title == "Existing Event"


def test_authenticated_user_can_create_event_with_token_identity(event_client):
    """Create an event while ignoring user identity fields supplied by the client."""
    client, user_id, _ = event_client
    set_authenticated_cookie(client, user_id)

    response = client.post(
        "/api/v1/events",
        json=valid_event_payload(created_by_id=999, user_id=999),
    )

    assert response.status_code == 201
    assert response.json["event"]["title"] == "New Event"
    with client.application.app_context():
        created_event = db.session.get(Event, response.json["event"]["id"])
        assert created_event.created_by_id == user_id


def test_authenticated_user_can_edit_event_without_changing_creator(event_client):
    """Update event fields while preserving the creator assigned from its token."""
    client, user_id, event_id = event_client
    set_authenticated_cookie(client, user_id)

    response = client.patch(
        f"/api/v1/events/{event_id}",
        json={"title": "Updated Event", "created_by_id": 999},
    )

    assert response.status_code == 200
    assert response.json["event"]["title"] == "Updated Event"
    with client.application.app_context():
        event = db.session.get(Event, event_id)
        assert event.created_by_id == user_id


def test_invalid_event_creation_does_not_modify_database(event_client):
    """Return a validation error and persist nothing for invalid event data."""
    client, user_id, _ = event_client
    set_authenticated_cookie(client, user_id)

    response = client.post("/api/v1/events", json=valid_event_payload(capacity=0))

    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
    with client.application.app_context():
        assert db.session.query(Event).count() == 1


def test_invalid_event_update_does_not_modify_database(event_client):
    """Reject invalid date ranges and leave the existing event unchanged."""
    client, user_id, event_id = event_client
    set_authenticated_cookie(client, user_id)

    response = client.patch(
        f"/api/v1/events/{event_id}",
        json={"ends_at": "2029-12-31T09:00:00+00:00"},
    )

    assert response.status_code == 400
    assert response.json["error"]["code"] == "validation_error"
    with client.application.app_context():
        assert db.session.get(Event, event_id).title == "Existing Event"


def test_editing_unknown_event_returns_not_found(event_client):
    """Return a consistent not-found response for an authenticated missing event."""
    client, user_id, _ = event_client
    set_authenticated_cookie(client, user_id)

    response = client.patch("/api/v1/events/999", json={"title": "Missing"})

    assert response.status_code == 404

"""Verify route and application-service flows while mocking infrastructure."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.auth import decorators
from app.api.auth import routes as auth_routes
from app.api.auth.routes import auth_bp
from app.api.events import routes as event_routes
from app.api.events.routes import event_bp
from app.application.auth.service import AuthService
from app.application.events.service import EventService
from app.core.exceptions import RelatedRecordsError
from app.domain.entities.event_record import EventRecord
from app.domain.entities.user_account import UserAccount
from app.domain.repositories.event_repository import EventRepository
from app.domain.repositories.user_repository import UserRepository

TEST_SECRET = "integration-test-secret-with-more-than-thirty-two-bytes"
EVENT = EventRecord(
    id=12,
    title="Engineering Summit",
    description="Systems engineering topics",
    location="Bogota",
    starts_at=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    ends_at=datetime(2030, 1, 1, 12, 0, tzinfo=UTC),
    capacity=100,
    status="draft",
    created_by_id=7,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def application_client(monkeypatch):
    """Wire actual routes and services to mocked persistence interfaces."""
    accounts: dict[str, UserAccount] = {}
    user_repository = Mock(spec=UserRepository)
    user_repository.find_by_email.side_effect = lambda email: accounts.get(email)
    user_repository.find_by_id.side_effect = lambda user_id: next(
        (account for account in accounts.values() if account.id == user_id), None
    )

    def persist_account(account):
        """Store an account in test memory and assign its mock persistence ID."""
        stored_account = replace(account, id=7)
        accounts[stored_account.email] = stored_account
        return stored_account

    user_repository.add.side_effect = persist_account
    event_repository = Mock(spec=EventRepository)
    event_repository.save.side_effect = lambda event: replace(
        event, id=event.id or EVENT.id
    )
    event_repository.list_events.return_value = ([EVENT], 1)
    event_repository.find_by_id.return_value = EVENT

    auth_service = AuthService(user_repository, TEST_SECRET, 3600)
    event_service = EventService(event_repository)
    monkeypatch.setattr(auth_routes, "get_auth_service", lambda: auth_service)
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth_service)
    monkeypatch.setattr(event_routes, "get_event_service", lambda: event_service)

    app = Flask(__name__)
    app.config.update(
        JWT_ACCESS_TOKEN_TTL_SECONDS=3600,
        JWT_COOKIE_SECURE=False,
    )
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(event_bp, url_prefix="/api/v1")
    return app.test_client(), user_repository, event_repository


def register_and_login(client):
    """Register and authenticate the test user through the real API routes."""
    registration_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "organizer@example.test",
            "password": "correct-horse-battery",
            "first_name": "Alex",
            "last_name": "Rivera",
        },
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "organizer@example.test",
            "password": "correct-horse-battery",
        },
    )
    return registration_response, login_response


def test_registration_login_and_protected_event_creation_flow(application_client):
    """Run auth routes, application services, and event creation with mocked stores."""
    client, user_repository, event_repository = application_client
    registration_response, login_response = register_and_login(client)

    event_response = client.post(
        "/api/v1/events",
        json={
            "title": "New Summit",
            "description": "Engineering topics",
            "location": "Bogota",
            "starts_at": "2030-01-01T10:00:00+00:00",
            "ends_at": "2030-01-01T12:00:00+00:00",
            "capacity": 100,
        },
    )

    assert registration_response.status_code == 201
    assert login_response.status_code == 200
    assert event_response.status_code == 201
    assert event_repository.save.call_args.args[0].created_by_id == 7
    user_repository.add.assert_called_once()


def test_search_flow_normalizes_query_before_mocked_persistence(application_client):
    """Combine the event route and service while leaving search persistence mocked."""
    client, _, event_repository = application_client

    response = client.get("/api/v1/events?page=1&page_size=10&q=%20engineering%20")

    assert response.status_code == 200
    assert response.json["events"][0]["id"] == EVENT.id
    event_repository.list_events.assert_called_once_with(1, 10, "engineering")


def test_related_record_delete_conflict_flows_through_route_and_service(
    application_client,
):
    """Map an infrastructure conflict through the service to a 409 API response."""
    client, _, event_repository = application_client
    event_repository.delete.side_effect = RelatedRecordsError(
        "Events with registrations cannot be deleted."
    )
    _, login_response = register_and_login(client)

    response = client.delete(f"/api/v1/events/{EVENT.id}")

    assert login_response.status_code == 200
    assert response.status_code == 409
    assert response.json["error"]["code"] == "related_records"
    event_repository.delete.assert_called_once_with(EVENT.id)

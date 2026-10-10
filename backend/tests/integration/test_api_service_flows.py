"""Verify route and application-service flows while mocking infrastructure."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from threading import Barrier, Lock
from unittest.mock import Mock

import pytest
from flask import Flask

from app.api.auth import decorators
from app.api.auth import routes as auth_routes
from app.api.auth.routes import auth_bp
from app.api.events import routes as event_routes
from app.api.events.routes import event_bp
from app.api.sessions import routes as session_routes
from app.api.sessions.routes import session_bp
from app.application.auth.service import AuthService
from app.application.events.service import EventService
from app.application.registrations.service import EventRegistrationService
from app.application.sessions.attendees import SessionAttendeeService
from app.core.exceptions import (
    CapacityExceededError,
    EventCapacityExceededError,
    RelatedRecordsError,
)
from app.domain.entities.event_record import EventRecord
from app.domain.entities.event_registration import (
    EventRegistrationDetails,
    EventRegistrationRecord,
)
from app.domain.entities.user_account import UserAccount
from app.domain.repositories.event_registration_repository import (
    EventRegistrationRepository,
)
from app.domain.repositories.event_repository import EventRepository
from app.domain.repositories.session_attendee_repository import (
    SessionAttendeeRepository,
)
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

    assert registration_response.status_code == HTTPStatus.CREATED
    assert login_response.status_code == HTTPStatus.OK
    assert event_response.status_code == HTTPStatus.CREATED
    assert event_repository.save.call_args.args[0].created_by_id == 7
    user_repository.add.assert_called_once()


def test_search_flow_normalizes_query_before_mocked_persistence(application_client):
    """Combine the event route and service while leaving search persistence mocked."""
    client, _, event_repository = application_client

    response = client.get("/api/v1/events?page=1&page_size=10&q=%20engineering%20")

    assert response.status_code == HTTPStatus.OK
    assert response.json["events"][0]["id"] == EVENT.id
    event_repository.list_events.assert_called_once_with(1, 10, "engineering")


def test_related_record_delete_conflict_flows_through_route_and_service(
    application_client,
):
    """Map an infrastructure conflict through the service to an API conflict response."""
    client, _, event_repository = application_client
    event_repository.delete.side_effect = RelatedRecordsError(
        "Events with registrations cannot be deleted."
    )
    _, login_response = register_and_login(client)

    response = client.delete(f"/api/v1/events/{EVENT.id}")

    assert login_response.status_code == HTTPStatus.OK
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json["error"]["code"] == "related_records"
    event_repository.delete.assert_called_once_with(EVENT.id, 7)


def test_concurrent_session_enrollments_return_one_success_and_one_capacity_conflict(
    monkeypatch,
):
    """Exercise parallel HTTP requests with a synchronized mock capacity store."""
    attendees = {
        "token-a": UserAccount("a@example.test", "hash", "Alex", "One", id=21),
        "token-b": UserAccount("b@example.test", "hash", "Blair", "Two", id=22),
    }
    auth_service = Mock()
    auth_service.get_authenticated_user.side_effect = attendees.__getitem__
    repository = Mock(spec=SessionAttendeeRepository)
    repository.find_event_creator_id.return_value = EVENT.created_by_id
    repository.session_exists.return_value = True
    ready_barrier = Barrier(3)
    capacity_lock = Lock()
    capacity = 2
    occupancy = {"active": 1}

    def enroll(event_id, session_id, user_id):
        """Atomically check and consume the final seat in shared mock state."""
        ready_barrier.wait(timeout=5)
        with capacity_lock:
            if occupancy["active"] >= capacity:
                raise CapacityExceededError("The session has no available seats.")
            occupancy["active"] += 1

    repository.enroll.side_effect = enroll
    attendee_service = SessionAttendeeService(repository)
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth_service)
    monkeypatch.setattr(
        session_routes,
        "get_session_attendee_service",
        lambda: attendee_service,
    )

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(session_bp, url_prefix="/api/v1")
    clients = []
    for token in attendees:
        client = app.test_client()
        client.set_cookie("access_token", token)
        clients.append(client)

    def send_enrollment(client):
        """Send one authenticated session-enrollment request."""
        response = client.post("/api/v1/events/12/sessions/34/attendees")
        return response.status_code, response.json

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(send_enrollment, client) for client in clients]
        ready_barrier.wait(timeout=5)
        results = [future.result(timeout=5) for future in futures]

    assert sorted(status for status, _ in results) == [
        HTTPStatus.CREATED,
        HTTPStatus.CONFLICT,
    ]
    rejected = next(
        payload for status, payload in results if status == HTTPStatus.CONFLICT
    )
    accepted = next(
        payload for status, payload in results if status == HTTPStatus.CREATED
    )
    assert rejected["error"]["code"] == "capacity_exceeded"
    assert accepted["message"] == "Session registration is active."
    assert occupancy["active"] == capacity
    assert repository.enroll.call_count == 2
    assert {call.args[2] for call in repository.enroll.call_args_list} == {21, 22}


def test_registration_api_creates_and_lists_only_current_users_records(monkeypatch):
    """Integrate registration routes and service while mocking their repository."""
    user = UserAccount("member@example.test", "hash", "Alex", "Member", id=22)
    auth_service = Mock()
    auth_service.get_authenticated_user.return_value = user
    repository = Mock(spec=EventRegistrationRepository)
    repository.register.return_value = EventRegistrationRecord(
        31, EVENT.id, 22, "registered"
    )
    repository.list_by_user.return_value = (
        [
            EventRegistrationDetails(31, "registered", EVENT.starts_at, EVENT),
            EventRegistrationDetails(32, "cancelled", EVENT.starts_at, EVENT),
        ],
        2,
    )
    registration_service = EventRegistrationService(repository)
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth_service)
    monkeypatch.setattr(
        event_routes,
        "get_event_registration_service",
        lambda: registration_service,
    )

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(event_bp, url_prefix="/api/v1")
    client = app.test_client()
    client.set_cookie("access_token", "member-token")

    created = client.post("/api/v1/events/12/registrations/me")
    listed = client.get("/api/v1/registrations/me")

    assert created.status_code == HTTPStatus.CREATED
    assert created.json["registration"]["user_id"] == 22
    assert listed.status_code == HTTPStatus.OK
    assert [item["status"] for item in listed.json["registrations"]] == [
        "registered",
        "cancelled",
    ]
    assert all(item["event"]["id"] == EVENT.id for item in listed.json["registrations"])
    repository.register.assert_called_once_with(12, 22)
    call = repository.list_by_user.call_args
    assert call.args[:5] == (22, 1, 20, None, None)
    assert call.args[5].tzinfo is not None


def test_concurrent_event_registrations_return_one_success_and_one_capacity_conflict(
    monkeypatch,
):
    """Send concurrent authenticated requests through routes with mock persistence."""
    users = {
        "token-a": UserAccount("a@example.test", "hash", "Alex", "One", id=21),
        "token-b": UserAccount("b@example.test", "hash", "Blair", "Two", id=22),
    }
    auth_service = Mock()
    auth_service.get_authenticated_user.side_effect = users.__getitem__
    repository = Mock(spec=EventRegistrationRepository)
    ready_barrier = Barrier(3)
    capacity_lock = Lock()
    capacity = 2
    occupied = {"count": 1}

    def register(event_id, user_id):
        """Atomically check and consume the final seat in mock persistence."""
        ready_barrier.wait(timeout=5)
        with capacity_lock:
            if occupied["count"] >= capacity:
                raise EventCapacityExceededError("The event has no available seats.")
            occupied["count"] += 1
            return EventRegistrationRecord(user_id, event_id, user_id, "registered")

    repository.register.side_effect = register
    service = EventRegistrationService(repository)
    monkeypatch.setattr(decorators, "get_auth_service", lambda: auth_service)
    monkeypatch.setattr(event_routes, "get_event_registration_service", lambda: service)

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(event_bp, url_prefix="/api/v1")
    clients = []
    for token in users:
        client = app.test_client()
        client.set_cookie("access_token", token)
        clients.append(client)

    def send_registration(client):
        """Send one authenticated self-registration request."""
        response = client.post("/api/v1/events/12/registrations/me")
        return response.status_code, response.json

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(send_registration, client) for client in clients]
        ready_barrier.wait(timeout=5)
        results = [future.result(timeout=5) for future in futures]

    assert sorted(status for status, _ in results) == [
        HTTPStatus.CREATED,
        HTTPStatus.CONFLICT,
    ]
    conflict = next(
        payload for status, payload in results if status == HTTPStatus.CONFLICT
    )
    assert conflict["error"]["code"] == "capacity_exceeded"
    assert occupied["count"] == capacity
    assert repository.register.call_count == 2
    assert {call.args[1] for call in repository.register.call_args_list} == {21, 22}

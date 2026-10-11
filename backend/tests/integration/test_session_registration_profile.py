"""Exercise the session-registration profile endpoint with real SQLite persistence."""

from datetime import UTC, datetime
from http import HTTPStatus

import pytest

from app.core.security import create_access_token
from app.extensions import db
from app.infrastructure.database.models import (
    Event,
    EventSession,
    Registration,
    SessionRegistration,
    User,
)
from app.main import create_app

TEST_SECRET = "integration-test-secret-that-is-long-enough"


@pytest.fixture
def session_registration_client(monkeypatch):
    """Build the real API and repository stack over an isolated in-memory database."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.delenv("JWT_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("FRONTEND_ORIGIN", "")
    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        from app.infrastructure.database import models  # noqa: F401

        db.create_all()
        owner = User(
            email="owner@example.test",
            password_hash="not-used",
            first_name="Olivia",
            last_name="Owner",
            role="ORGANIZER",
        )
        attendee = User(
            email="attendee@example.test",
            password_hash="not-used",
            first_name="Taylor",
            last_name="Attendee",
            role="ATTENDEE",
        )
        other_attendee = User(
            email="other@example.test",
            password_hash="not-used",
            first_name="Alex",
            last_name="Other",
            role="ATTENDEE",
        )
        empty_attendee = User(
            email="empty@example.test",
            password_hash="not-used",
            first_name="Robin",
            last_name="Empty",
            role="ATTENDEE",
        )
        db.session.add_all([owner, attendee, other_attendee, empty_attendee])
        db.session.flush()

        def add_event(title, day):
            event = Event(
                title=title,
                description=f"Description for {title}",
                location="Bogota",
                starts_at=datetime(2030, 6, day, 9, tzinfo=UTC),
                ends_at=datetime(2030, 6, day, 17, tzinfo=UTC),
                capacity=30,
                status="published",
                created_by_id=owner.id,
            )
            db.session.add(event)
            db.session.flush()
            return event

        def add_session(event, title, day):
            session = EventSession(
                event_id=event.id,
                title=title,
                description=f"Details for {title}",
                starts_at=datetime(2030, 6, day, 10, tzinfo=UTC),
                ends_at=datetime(2030, 6, day, 11, tzinfo=UTC),
                capacity=10,
            )
            db.session.add(session)
            db.session.flush()
            return session

        main_event = add_event("Platform Conference", 10)
        parent_cancelled_event = add_event("Another Conference", 20)
        session_one = add_session(main_event, "Opening session", 10)
        session_two = add_session(main_event, "Workshop", 11)
        session_three = add_session(main_event, "Closing session", 12)
        session_four = add_session(parent_cancelled_event, "Planning session", 20)
        active_parent = Registration(
            user_id=attendee.id, event_id=main_event.id, status="registered"
        )
        cancelled_parent = Registration(
            user_id=attendee.id, event_id=parent_cancelled_event.id, status="cancelled"
        )
        other_parent = Registration(
            user_id=other_attendee.id, event_id=main_event.id, status="registered"
        )
        db.session.add_all([active_parent, cancelled_parent, other_parent])
        db.session.flush()
        db.session.add_all(
            [
                SessionRegistration(
                    session_id=session_one.id,
                    registration_id=active_parent.id,
                    status="active",
                ),
                SessionRegistration(
                    session_id=session_two.id,
                    registration_id=active_parent.id,
                    status="cancelled",
                ),
                SessionRegistration(
                    session_id=session_four.id,
                    registration_id=cancelled_parent.id,
                    status="active",
                ),
                SessionRegistration(
                    session_id=session_three.id,
                    registration_id=other_parent.id,
                    status="active",
                ),
            ]
        )
        db.session.commit()
        user_ids = {
            "attendee": attendee.id,
            "other_attendee": other_attendee.id,
            "empty_attendee": empty_attendee.id,
        }

    yield app.test_client(), user_ids

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def _authenticate(client, user_id):
    token = create_access_token(user_id, TEST_SECRET, 3600)
    client.set_cookie("access_token", token, path="/api/v1")


def test_session_registration_listing_is_authenticated_scoped_and_paginated(
    session_registration_client,
):
    client, user_ids = session_registration_client

    unauthenticated = client.get("/api/v1/session-registrations/me")
    assert unauthenticated.status_code == HTTPStatus.UNAUTHORIZED

    _authenticate(client, user_ids["attendee"])
    first_page = client.get("/api/v1/session-registrations/me?page=1&page_size=2")
    second_page = client.get("/api/v1/session-registrations/me?page=2&page_size=2")
    arbitrary_user = client.get("/api/v1/session-registrations/me?user_id=999")

    assert first_page.status_code == HTTPStatus.OK
    assert first_page.json["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 3,
        "total_pages": 2,
    }
    assert [item["session"]["title"] for item in first_page.json["registrations"]] == [
        "Opening session",
        "Workshop",
    ]
    assert first_page.json["registrations"][0]["event"]["title"] == (
        "Platform Conference"
    )
    assert first_page.json["registrations"][0]["session"]["starts_at"].startswith(
        "2030-06-10T10:00:00"
    )
    assert [item["status"] for item in first_page.json["registrations"]] == [
        "active",
        "cancelled",
    ]
    assert second_page.status_code == HTTPStatus.OK
    assert second_page.json["registrations"][0]["status"] == "cancelled"
    assert second_page.json["registrations"][0]["event"]["title"] == (
        "Another Conference"
    )
    assert arbitrary_user.status_code == HTTPStatus.BAD_REQUEST

    _authenticate(client, user_ids["other_attendee"])
    other_user_page = client.get("/api/v1/session-registrations/me")
    assert other_user_page.status_code == HTTPStatus.OK
    assert other_user_page.json["pagination"]["total"] == 1
    assert other_user_page.json["registrations"][0]["session"]["title"] == (
        "Closing session"
    )

    _authenticate(client, user_ids["empty_attendee"])
    empty_page = client.get("/api/v1/session-registrations/me")
    assert empty_page.status_code == HTTPStatus.OK
    assert empty_page.json["registrations"] == []
    assert empty_page.json["pagination"]["total"] == 0

"""Verify model registration, relationships, and database integrity constraints."""

from datetime import UTC, datetime

import pytest
from flask import Flask
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.infrastructure.database.models import (
    Event,
    EventSession,
    Registration,
    Speaker,
    User,
)

EVENT_START = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
EVENT_END = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def database_session():
    """Provide an isolated in-memory database with SQLite foreign keys enabled."""
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)

    with app.app_context():
        engine = db.engine

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(connection, record):
            """Enable SQLite foreign-key enforcement for this test engine."""
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


def make_event(**overrides):
    """Build a valid event instance, applying any test-specific field overrides."""
    values = {
        "title": "Data Engineering Summit",
        "starts_at": EVENT_START,
        "ends_at": EVENT_END,
        "capacity": 100,
    }
    values.update(overrides)
    return Event(**values)


def test_model_registry_contains_all_required_tables():
    """Ensure importing the explicit registry attaches all models to shared metadata."""
    expected_tables = {
        "users",
        "events",
        "event_sessions",
        "speakers",
        "registrations",
        "event_speakers",
        "session_speakers",
    }

    assert expected_tables.issubset(db.metadata.tables)


def test_models_persist_event_attendee_session_and_speaker_relationships(
    database_session,
):
    """Persist and reload the expected attendee, event, session, and speaker relationships."""
    user = User(
        email="attendee@example.test",
        password_hash="hashed-password-value",
        first_name="Alex",
        last_name="Rivera",
    )
    event_record = make_event()
    session_record = EventSession(
        title="Building Reliable Systems",
        starts_at=EVENT_START,
        ends_at=EVENT_END,
        capacity=40,
    )
    speaker = Speaker(name="Jordan Lee", biography="Systems engineer")
    event_record.sessions.append(session_record)
    event_record.speakers.append(speaker)
    event_record.registrations.append(Registration(user=user))
    session_record.speakers.append(speaker)

    database_session.add_all([user, event_record])
    database_session.commit()

    assert user.registrations[0].event is event_record
    assert session_record.event is event_record
    assert session_record.speakers == [speaker]
    assert speaker.sessions == [session_record]
    assert event_record.speakers == [speaker]
    assert speaker.events == [event_record]
    assert event_record.status == "draft"
    assert user.created_at is not None


def test_database_rejects_invalid_capacity_date_ranges_and_status(database_session):
    """Reject event and session rows that violate local integrity constraints."""
    invalid_events = [
        make_event(capacity=0),
        make_event(ends_at=EVENT_START),
        make_event(status="unknown"),
    ]

    for event_record in invalid_events:
        database_session.add(event_record)
        with pytest.raises(IntegrityError):
            database_session.flush()
        database_session.rollback()

    event_record = make_event()
    database_session.add(event_record)
    database_session.flush()
    invalid_session = EventSession(
        event=event_record,
        title="Invalid session",
        starts_at=EVENT_END,
        ends_at=EVENT_START,
        capacity=0,
    )
    database_session.add(invalid_session)

    with pytest.raises(IntegrityError):
        database_session.flush()


def test_database_rejects_duplicate_emails_and_event_registrations(database_session):
    """Enforce unique account emails and one registration per user and event."""
    user = User(
        email="attendee@example.test",
        password_hash="hashed-password-value",
        first_name="Alex",
        last_name="Rivera",
    )
    event_record = make_event()
    database_session.add_all([user, event_record])
    database_session.flush()
    database_session.add(Registration(user=user, event=event_record))
    database_session.commit()

    with pytest.raises(IntegrityError), database_session.begin_nested():
        database_session.add(
            User(
                email="attendee@example.test",
                password_hash="another-hash",
                first_name="Taylor",
                last_name="Jones",
            )
        )
        database_session.flush()

    with pytest.raises(IntegrityError), database_session.begin_nested():
        database_session.add(Registration(user=user, event=event_record))
        database_session.flush()


def test_database_rejects_registration_with_missing_foreign_keys(database_session):
    """Reject registrations that reference a missing attendee or event."""
    database_session.add(Registration(user_id=999, event_id=999))

    with pytest.raises(IntegrityError):
        database_session.flush()

"""Exercise event image persistence and relational constraints with SQLite."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities.event_image import EventImageRecord
from app.infrastructure.database.models import (  # noqa: F401
    Event,
    EventImage,
    EventSession,
    Registration,
    SessionRegistration,
    Speaker,
    User,
)
from app.infrastructure.repositories.sqlalchemy_event_image_repository import (
    SQLAlchemyEventImageRepository,
)


@pytest.fixture
def database_session():
    """Create an isolated SQLite schema with foreign key enforcement enabled."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Event.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def add_event(session: Session) -> Event:
    """Persist a minimal event row used by image repository scenarios."""
    now = datetime.now(UTC)
    model = Event(
        title="Gallery event",
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, hours=1),
        capacity=20,
        status="published",
    )
    session.add(model)
    session.commit()
    return model


def test_create_and_list_event_images_in_gallery_order(database_session):
    """Persist metadata linked to an event and return it by position."""
    event_model = add_event(database_session)
    repository = SQLAlchemyEventImageRepository(database_session)

    later = repository.create(
        EventImageRecord(
            event_model.id,
            "events/1/second.webp",
            "https://cdn.example.test/events/1/second.webp",
            position=1,
        )
    )
    first = repository.create(
        EventImageRecord(
            event_model.id,
            "events/1/first.webp",
            "https://cdn.example.test/events/1/first.webp",
            position=0,
        )
    )
    images = repository.list_by_event(event_model.id)

    assert later.id is not None
    assert later.created_at is not None
    assert [image.storage_key for image in images] == [
        "events/1/first.webp",
        "events/1/second.webp",
    ]
    assert [image.position for image in images] == [0, 1]
    assert first.event_id == event_model.id


def test_create_rejects_image_for_nonexistent_event(database_session):
    """Enforce the event foreign key rather than persisting an orphan image."""
    repository = SQLAlchemyEventImageRepository(database_session)

    with pytest.raises(IntegrityError):
        repository.create(
            EventImageRecord(
                999,
                "events/999/image.webp",
                "https://cdn.example.test/events/999/image.webp",
                0,
            )
        )

    database_session.rollback()
    assert database_session.query(EventImage).count() == 0


@pytest.mark.parametrize(
    ("storage_key", "position"),
    [("events/1/image.webp", -1), ("   ", 0)],
)
def test_database_rejects_invalid_image_metadata(
    database_session, storage_key, position
):
    """Reject empty object keys and negative gallery positions at persistence."""
    event_model = add_event(database_session)
    repository = SQLAlchemyEventImageRepository(database_session)

    with pytest.raises(IntegrityError):
        repository.create(
            EventImageRecord(
                event_model.id,
                storage_key,
                "https://cdn.example.test/events/image.webp",
                position,
            )
        )

    database_session.rollback()
    assert database_session.query(EventImage).count() == 0


def test_database_rejects_duplicate_positions_and_storage_keys(database_session):
    """Enforce unique event ordering and unique object keys in the bucket."""
    first_event = add_event(database_session)
    second_event = add_event(database_session)
    repository = SQLAlchemyEventImageRepository(database_session)
    repository.create(
        EventImageRecord(
            first_event.id,
            "events/shared.webp",
            "https://cdn.example.test/events/shared.webp",
            0,
        )
    )

    with pytest.raises(IntegrityError):
        repository.create(
            EventImageRecord(
                first_event.id,
                "events/other.webp",
                "https://cdn.example.test/events/other.webp",
                0,
            )
        )
    database_session.rollback()

    with pytest.raises(IntegrityError):
        repository.create(
            EventImageRecord(
                second_event.id,
                "events/shared.webp",
                "https://cdn.example.test/events/shared.webp",
                1,
            )
        )
    database_session.rollback()
    assert database_session.query(EventImage).count() == 1

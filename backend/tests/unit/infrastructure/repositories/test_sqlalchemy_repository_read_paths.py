"""Cover event-session and attendee repository read paths with mocked rows."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import NotFoundError
from app.infrastructure.repositories.sqlalchemy_session_attendee_repository import (
    SQLAlchemySessionAttendeeRepository,
)
from app.infrastructure.repositories.sqlalchemy_session_repository import (
    SQLAlchemySessionRepository,
)

START = datetime(2030, 4, 1, 10, tzinfo=UTC)
END = datetime(2030, 4, 1, 11, tzinfo=UTC)


def session_model(session_id: int = 5):
    """Build an ORM-shaped session row for repository mapping tests."""
    return SimpleNamespace(
        id=session_id,
        event_id=3,
        title="Opening talk",
        description="Introduction",
        starts_at=START,
        ends_at=END,
        capacity=20,
        version=2,
        speakers=[SimpleNamespace(id=8)],
    )


def test_session_repository_maps_event_and_returns_none_for_missing_parent():
    """Map the scheduling fields of an event and recognize absent parents."""
    event = SimpleNamespace(
        id=3,
        title="Conference",
        description="Description",
        location="Hall A",
        starts_at=START,
        ends_at=END,
        capacity=40,
        status="published",
        created_by_id=12,
    )
    session = Mock()
    session.get.side_effect = [event, None]
    repository = SQLAlchemySessionRepository(session)

    record = repository.find_event(3)

    assert record.id == 3
    assert record.created_by_id == 12
    assert record.starts_at == START
    assert repository.find_event(404) is None


def test_session_repository_maps_queries_and_checks_speaker_ids():
    """Map session rows and return the repository's ordered speaker lookup result."""
    row = session_model()
    session = Mock()
    session.scalar.side_effect = [row, row, 1]
    session.scalars.return_value.all.return_value = [row]
    repository = SQLAlchemySessionRepository(session)

    assert repository.find_by_id(3, 5).speaker_ids == (8,)
    assert [item.id for item in repository.list_by_event(3)] == [5]
    assert repository.find_overlapping(3, START, END).id == 5
    assert repository.speaker_ids_exist((8,)) is True

    session.scalar.side_effect = [None, None, 0]
    assert repository.find_by_id(3, 99) is None
    assert repository.find_overlapping(3, START, END) is None
    assert repository.speaker_ids_exist((8,)) is False


def test_session_repository_returns_empty_list_and_no_overlap_when_unmatched():
    """Return empty read results and retain self-exclusion in overlap queries."""
    session = Mock()
    session.scalars.return_value.all.return_value = []
    session.scalar.return_value = None
    repository = SQLAlchemySessionRepository(session)

    assert repository.list_by_event(3) == []
    assert repository.find_overlapping(3, START, END, exclude_session_id=5) is None
    statement = session.scalar.call_args.args[0]
    assert "event_sessions.id !=" in str(statement)


@pytest.mark.parametrize(
    "event_result,registration_result,session_result,expected",
    [
        (None, None, None, False),
        (SimpleNamespace(id=3), None, None, False),
        (SimpleNamespace(id=3), SimpleNamespace(id=10), None, False),
    ],
)
def test_attendee_cancellation_returns_false_when_a_required_record_is_missing(
    event_result, registration_result, session_result, expected
):
    """Roll back cancellation when its event, event registration, or session is absent."""
    session = Mock()
    session.scalar.side_effect = [event_result, registration_result, session_result]
    repository = SQLAlchemySessionAttendeeRepository(session)

    assert repository.cancel(3, 5, 11) is expected

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_attendee_repository_reads_owner_roster_and_occupancy():
    """Map roster tuples and compute free capacity from one occupancy row."""
    attendee_row = (11, "Ada", "Lovelace", "ada@example.test", START)
    session = Mock()
    session.get.return_value = SimpleNamespace(created_by_id=12)
    session.scalar.side_effect = [5]
    session.execute.side_effect = [
        SimpleNamespace(all=lambda: [attendee_row]),
        SimpleNamespace(one_or_none=lambda: (20, 7)),
    ]
    repository = SQLAlchemySessionAttendeeRepository(session)

    assert repository.find_event_creator_id(3) == 12
    assert repository.session_exists(3, 5) is True
    attendees = repository.list_attendees(3, 5)
    assert attendees[0].user_id == 11
    assert attendees[0].email == "ada@example.test"
    assert repository.get_occupancy(3, 5).available == 13


def test_attendee_repository_reports_missing_event_and_session():
    """Raise not-found errors when owner or occupancy queries target missing data."""
    session = Mock()
    session.get.return_value = None
    session.execute.return_value.one_or_none.return_value = None
    repository = SQLAlchemySessionAttendeeRepository(session)

    with pytest.raises(NotFoundError, match="Event not found"):
        repository.find_event_creator_id(404)
    with pytest.raises(NotFoundError, match="Session not found"):
        repository.get_occupancy(3, 404)

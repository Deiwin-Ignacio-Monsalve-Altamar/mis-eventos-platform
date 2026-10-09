"""Verify session rules using a mocked persistence port."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from app.application.sessions.service import SessionService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.event_record import EventRecord
from app.domain.entities.session_record import SessionRecord
from app.domain.repositories.session_repository import SessionRepository

EVENT = EventRecord(
    title="Conference",
    starts_at=datetime(2030, 1, 1, 9, tzinfo=UTC),
    ends_at=datetime(2030, 1, 1, 18, tzinfo=UTC),
    capacity=100,
    status="draft",
    created_by_id=7,
    id=1,
)
RECORD = SessionRecord(
    2,
    1,
    "Talk",
    None,
    datetime(2030, 1, 1, 10, tzinfo=UTC),
    datetime(2030, 1, 1, 11, tzinfo=UTC),
    20,
)


@pytest.fixture
def setup_service():
    """Return a session service wired to a repository mock."""
    repository = Mock(spec=SessionRepository)
    repository.find_event.return_value = EVENT
    repository.find_overlapping.return_value = None
    repository.speaker_ids_exist.return_value = True
    repository.save.side_effect = lambda record, expected_version=None: replace(
        record, id=2, version=(expected_version or 0) + 1
    )
    return SessionService(repository), repository


def valid_values(**updates):
    """Build valid session input values and apply requested overrides."""
    values = {
        "title": "Talk",
        "description": None,
        "starts_at": "2030-01-01T10:00:00+00:00",
        "ends_at": "2030-01-01T11:00:00+00:00",
        "capacity": 20,
        "speaker_ids": [],
    }
    values.update(updates)
    return values


def test_create_and_list_and_get_session(setup_service):
    """Create, list, and retrieve sessions through event-scoped operations."""
    service, repository = setup_service
    created = service.create(1, valid_values())
    repository.list_by_event.return_value = [created]
    repository.find_by_id.return_value = created
    assert created.title == "Talk"
    assert service.list_by_event(1) == [created]
    assert service.get(1, 2) == created
    repository.find_overlapping.assert_called_once_with(
        1, created.starts_at, created.ends_at
    )


def test_create_assigns_existing_speakers_by_identifier(setup_service):
    """Validate speaker IDs and pass only their association IDs to persistence."""
    service, repository = setup_service

    created = service.create(1, valid_values(speaker_ids=[4]))

    assert created.speaker_ids == (4,)
    repository.speaker_ids_exist.assert_called_once_with((4,))
    assert repository.save.call_args.args[0].speaker_ids == (4,)


def test_update_excludes_current_session_and_delete(setup_service):
    """Merge updates, exclude the current identifier from overlaps, and delete."""
    service, repository = setup_service
    repository.find_by_id.return_value = RECORD
    updated = service.update(1, 2, {"title": "Revised"}, expected_version=1)
    assert updated.title == "Revised"
    assert updated.version == 2
    repository.find_overlapping.assert_called_once_with(
        1, RECORD.starts_at, RECORD.ends_at, 2
    )
    repository.delete.return_value = True
    service.delete(1, 2)
    repository.delete.assert_called_once_with(1, 2)


@pytest.mark.parametrize(
    "changes",
    [
        {"title": " "},
        {"starts_at": None},
        {"starts_at": "invalid"},
        {"starts_at": datetime.fromisoformat("2030-01-01T10:00:00")},
        {"ends_at": "2030-01-01T10:00:00+00:00"},
        {"starts_at": "2030-01-01T08:00:00+00:00"},
        {"capacity": True},
        {"capacity": 0},
        {"speaker_ids": [3, 3]},
    ],
)
def test_create_rejects_invalid_values_before_save(setup_service, changes):
    """Reject invalid fields without persisting a session."""
    service, repository = setup_service
    with pytest.raises(ValidationError):
        service.create(1, valid_values(**changes))
    repository.save.assert_not_called()


def test_create_rejects_end_after_event_schedule(setup_service):
    """Reject a session whose end is later than its parent event end."""
    service, repository = setup_service

    with pytest.raises(ValidationError, match="within the event schedule"):
        service.create(
            1,
            valid_values(
                starts_at="2030-01-01T17:00:00+00:00",
                ends_at="2030-01-01T19:00:00+00:00",
            ),
        )

    repository.save.assert_not_called()


def test_update_rejects_nonexistent_speaker_without_saving(setup_service):
    """Reject an update that assigns a missing speaker before persisting it."""
    service, repository = setup_service
    repository.find_by_id.return_value = RECORD
    repository.speaker_ids_exist.return_value = False

    with pytest.raises(ValidationError, match="speakers do not exist"):
        service.update(1, 2, {"speaker_ids": [999]}, expected_version=1)

    repository.save.assert_not_called()


def test_rejects_missing_event_session_speaker_and_overlap(setup_service):
    """Reject missing resources, unknown speakers, and intersecting schedules."""
    service, repository = setup_service
    repository.find_event.return_value = None
    with pytest.raises(NotFoundError, match="Event not found"):
        service.create(9, valid_values())
    repository.find_event.return_value = EVENT
    repository.speaker_ids_exist.return_value = False
    with pytest.raises(ValidationError, match="speakers"):
        service.create(1, valid_values(speaker_ids=[55]))
    repository.speaker_ids_exist.return_value = True
    repository.find_overlapping.return_value = RECORD
    with pytest.raises(ValidationError, match="overlaps"):
        service.create(1, valid_values())
    repository.find_by_id.return_value = RECORD
    with pytest.raises(ValidationError, match="overlaps"):
        service.update(1, 2, {"title": "Change"}, expected_version=1)


def test_consecutive_session_is_not_reported_as_overlap(setup_service):
    """Allow a session whose start exactly matches another session end."""
    service, repository = setup_service
    repository.find_overlapping.return_value = None
    service.create(
        1,
        valid_values(
            starts_at="2030-01-01T11:00:00+00:00", ends_at="2030-01-01T12:00:00+00:00"
        ),
    )
    repository.save.assert_called_once()

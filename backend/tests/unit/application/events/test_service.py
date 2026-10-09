"""Verify event use cases with the event repository mocked."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from app.application.events.service import EventService
from app.core.exceptions import NotFoundError, RelatedRecordsError, ValidationError
from app.domain.entities.event_record import EventRecord
from app.domain.repositories.event_repository import EventRepository

EVENT = EventRecord(
    id=12,
    title="Data Conference",
    description="Engineering topics",
    location="Bogota",
    starts_at=datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
    ends_at=datetime(2030, 1, 1, 12, 0, tzinfo=UTC),
    capacity=100,
    status="draft",
    created_by_id=7,
)


@pytest.fixture
def event_service():
    """Build the event application service with a mocked repository."""
    repository = Mock(spec=EventRepository)
    repository.save.side_effect = lambda event: replace(event, id=12)
    return EventService(repository), repository


def valid_event_values(**overrides):
    """Build valid event input values with optional overrides."""
    values = {
        "title": "New Event",
        "description": "A technical conference",
        "location": "Bogota",
        "starts_at": "2030-01-01T10:00:00+00:00",
        "ends_at": "2030-01-01T12:00:00+00:00",
        "capacity": 100,
        "status": "draft",
    }
    values.update(overrides)
    return values


def test_create_event_validates_and_persists_authenticated_creator(event_service):
    """Create a normalized event and persist its authenticated creator identifier."""
    service, repository = event_service

    event = service.create(valid_event_values(title=" New Event "), creator_id=7)

    assert event.id == 12
    assert event.title == "New Event"
    saved_event = repository.save.call_args.args[0]
    assert saved_event.created_by_id == 7
    assert saved_event.title == "New Event"


def test_create_event_validation_error_does_not_call_repository(event_service):
    """Reject invalid event values before writing through the repository."""
    service, repository = event_service

    with pytest.raises(ValidationError):
        service.create(valid_event_values(capacity=0), creator_id=7)

    repository.save.assert_not_called()


def test_update_event_merges_fields_and_preserves_creator(event_service):
    """Merge a partial update with stored fields without changing event ownership."""
    service, repository = event_service
    repository.find_by_id.return_value = EVENT

    updated_event = service.update(12, {"title": "Revised Conference"})

    assert updated_event.title == "Revised Conference"
    saved_event = repository.save.call_args.args[0]
    assert saved_event.created_by_id == EVENT.created_by_id
    assert saved_event.capacity == EVENT.capacity


def test_update_missing_event_raises_not_found(event_service):
    """Raise not found without attempting to save when the event is absent."""
    service, repository = event_service
    repository.find_by_id.return_value = None

    with pytest.raises(NotFoundError):
        service.update(999, {"title": "Missing"})

    repository.save.assert_not_called()


def test_list_events_validates_and_normalizes_pagination_and_search(event_service):
    """Pass validated pagination values and trimmed search text to the repository."""
    service, repository = event_service
    repository.list_events.return_value = ([EVENT], 7)

    page = service.list_events("2", "3", " engineering ")

    assert page.events == (EVENT,)
    assert page.page == 2
    assert page.page_size == 3
    assert page.total == 7
    repository.list_events.assert_called_once_with(2, 3, "engineering")


@pytest.mark.parametrize(
    ("page", "page_size", "query"),
    [("0", "20", None), ("1", "101", None), ("1", "20", "  ")],
)
def test_list_events_rejects_invalid_query_parameters(
    event_service, page, page_size, query
):
    """Reject unsafe pagination and empty search values before repository access."""
    service, repository = event_service

    with pytest.raises(ValidationError):
        service.list_events(page, page_size, query)

    repository.list_events.assert_not_called()


def test_get_missing_event_raises_not_found(event_service):
    """Raise not found when the repository has no event with the requested ID."""
    service, repository = event_service
    repository.find_by_id.return_value = None

    with pytest.raises(NotFoundError):
        service.get_by_id(999)


def test_delete_missing_event_raises_not_found(event_service):
    """Raise not found when the repository reports that no event was deleted."""
    service, repository = event_service
    repository.delete.return_value = False

    with pytest.raises(NotFoundError):
        service.delete(999)


def test_delete_related_event_propagates_repository_conflict(event_service):
    """Preserve related data by propagating the repository deletion conflict."""
    service, repository = event_service
    repository.delete.side_effect = RelatedRecordsError("Related records exist.")

    with pytest.raises(RelatedRecordsError):
        service.delete(12)

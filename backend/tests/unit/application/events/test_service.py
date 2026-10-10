"""Verify event use cases with the event repository mocked."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from app.application.events.service import EventService
from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    RelatedRecordsError,
    ValidationError,
)
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
MISSING_FIELD = object()


@pytest.fixture
def event_service():
    """Build the event application service with a mocked repository."""
    repository = Mock(spec=EventRepository)
    repository.save.side_effect = lambda event, expected_version=None, owner_id=None: (
        replace(event, id=12, version=(expected_version or 0) + 1)
    )
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
    """Reject invalid event values before accessing the repository."""
    service, repository = event_service

    with pytest.raises(ValidationError):
        service.create(valid_event_values(capacity=0), creator_id=7)

    repository.save.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"starts_at": MISSING_FIELD},
        {"starts_at": None},
        {"starts_at": "not-a-date"},
        {"starts_at": "2030-01-01T10:00:00"},
        {"starts_at": datetime.fromisoformat("2030-01-01T10:00:00")},
        {"ends_at": MISSING_FIELD},
        {"ends_at": None},
        {"ends_at": "not-a-date"},
        {"ends_at": "2030-01-01T12:00:00"},
        {"ends_at": "2030-01-01T10:00:00+00:00"},
        {"ends_at": "2029-12-31T12:00:00+00:00"},
        {"title": MISSING_FIELD},
        {"title": None},
        {"title": "  "},
        {"capacity": MISSING_FIELD},
        {"capacity": None},
        {"status": "archived"},
    ],
    ids=[
        "missing-start",
        "null-start",
        "invalid-start",
        "naive-start",
        "naive-datetime-object-start",
        "missing-end",
        "null-end",
        "invalid-end",
        "naive-end",
        "equal-dates",
        "end-before-start",
        "missing-title",
        "null-title",
        "blank-title",
        "missing-capacity",
        "null-capacity",
        "unknown-status",
    ],
)
def test_create_rejects_invalid_required_fields_without_repository_access(
    event_service, overrides
):
    """Reject missing or invalid fields before invoking any repository method."""
    service, repository = event_service
    values = valid_event_values()
    for field_name, value in overrides.items():
        if value is MISSING_FIELD:
            values.pop(field_name)
        else:
            values[field_name] = value

    with pytest.raises(ValidationError):
        service.create(values, creator_id=7)

    repository.find_by_id.assert_not_called()
    repository.list_events.assert_not_called()
    repository.save.assert_not_called()
    repository.delete.assert_not_called()


@pytest.mark.parametrize(
    "capacity",
    [0, -1, True, False, 100.5, "100"],
    ids=["zero", "negative", "true", "false", "non-integer-number", "string"],
)
def test_create_rejects_non_positive_or_non_integer_capacity_without_saving(
    event_service, capacity
):
    """Reject capacities that are not positive integers before repository writes."""
    service, repository = event_service

    with pytest.raises(ValidationError, match="positive integer"):
        service.create(valid_event_values(capacity=capacity), creator_id=7)

    repository.find_by_id.assert_not_called()
    repository.list_events.assert_not_called()
    repository.save.assert_not_called()
    repository.delete.assert_not_called()


def test_update_event_merges_fields_and_preserves_creator(event_service):
    """Merge a partial update with stored fields without changing event ownership."""
    service, repository = event_service
    repository.find_by_id.return_value = EVENT

    updated_event = service.update(
        12, {"title": "Revised Conference"}, expected_version=1, creator_id=7
    )

    assert updated_event.title == "Revised Conference"
    saved_event = repository.save.call_args.args[0]
    assert saved_event.created_by_id == EVENT.created_by_id
    assert saved_event.capacity == EVENT.capacity
    repository.save.assert_called_once_with(saved_event, 1, 7)


def test_update_rejects_another_users_event_before_writing(event_service):
    """Reject event edits when the authenticated creator differs from the owner."""
    service, repository = event_service
    repository.find_by_id.return_value = EVENT

    with pytest.raises(AuthorizationError):
        service.update(12, {"title": "Unauthorized"}, 1, creator_id=99)

    repository.save.assert_not_called()


def test_update_missing_event_raises_not_found(event_service):
    """Raise not found without attempting to save when the event is absent."""
    service, repository = event_service
    repository.find_by_id.return_value = None

    with pytest.raises(NotFoundError):
        service.update(999, {"title": "Missing"}, expected_version=1, creator_id=7)

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


def test_list_my_events_scopes_search_state_and_pagination_to_creator(event_service):
    """Forward only validated filters alongside the authenticated creator ID."""
    service, repository = event_service
    repository.list_by_creator.return_value = ([EVENT], 4)

    page = service.list_my_events(7, "2", "3", " Conference ", "draft")

    assert page.events == (EVENT,)
    assert (page.page, page.page_size, page.total) == (2, 3, 4)
    repository.list_by_creator.assert_called_once_with(7, 2, 3, "Conference", "draft")
    repository.list_events.assert_not_called()


def test_list_my_events_rejects_unknown_status(event_service):
    """Reject unsupported event state filters before querying owned events."""
    service, repository = event_service

    with pytest.raises(ValidationError):
        service.list_my_events(7, 1, 20, None, "archived")

    repository.list_by_creator.assert_not_called()


def test_dashboard_calculates_status_percentages_over_owned_event_total(event_service):
    """Calculate percentages using only the repository's owner-scoped aggregates."""
    service, repository = event_service
    repository.dashboard_counts.return_value = {
        "total": 4,
        "draft": 1,
        "published": 1,
        "cancelled": 1,
        "completed": 1,
        "upcoming": 1,
        "active": 0,
        "finished": 1,
    }

    summary = service.dashboard(7, datetime(2030, 1, 1, tzinfo=UTC))

    assert summary["total_events"] == 4
    assert summary["cancelled_events"] == 1
    assert summary["status_percentages"] == {
        "draft": 25.0,
        "published": 25.0,
        "cancelled": 25.0,
        "completed": 25.0,
    }
    repository.dashboard_counts.assert_called_once_with(
        7, datetime(2030, 1, 1, tzinfo=UTC)
    )


def test_dashboard_returns_zero_percentages_without_events(event_service):
    """Avoid division by zero when a creator has no event records."""
    service, repository = event_service
    repository.dashboard_counts.return_value = {"total": 0}

    summary = service.dashboard(7, datetime(2030, 1, 1, tzinfo=UTC))

    assert summary["total_events"] == 0
    assert set(summary["status_percentages"].values()) == {0.0}


def test_get_missing_event_raises_not_found(event_service):
    """Raise not found when the repository has no event with the requested ID."""
    service, repository = event_service
    repository.find_by_id.return_value = None

    with pytest.raises(NotFoundError):
        service.get_by_id(999)


def test_delete_missing_event_raises_not_found(event_service):
    """Raise not found when the repository reports that no event was deleted."""
    service, repository = event_service
    repository.find_by_id.return_value = None

    with pytest.raises(NotFoundError):
        service.delete(999, creator_id=7)


def test_delete_related_event_propagates_repository_conflict(event_service):
    """Preserve related data by propagating the repository deletion conflict."""
    service, repository = event_service
    repository.find_by_id.return_value = EVENT
    repository.delete.side_effect = RelatedRecordsError("Related records exist.")

    with pytest.raises(RelatedRecordsError):
        service.delete(12, creator_id=7)


def test_delete_rejects_another_users_event_before_writing(event_service):
    """Reject deletion before repository mutation if the caller is not the owner."""
    service, repository = event_service
    repository.find_by_id.return_value = EVENT

    with pytest.raises(AuthorizationError):
        service.delete(12, creator_id=99)

    repository.delete.assert_not_called()

"""Verify event registration workflows using a mocked repository."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from app.application.registrations.service import EventRegistrationService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.event_record import EventRecord
from app.domain.entities.event_registration import (
    EventRegistrationDetails,
    EventRegistrationRecord,
)
from app.domain.repositories.event_registration_repository import (
    EventRegistrationRepository,
)


@pytest.fixture
def registration_service():
    """Return the registration service wired to a repository mock."""
    repository = Mock(spec=EventRegistrationRepository)
    repository.register.return_value = EventRegistrationRecord(5, 7, 22, "registered")
    return EventRegistrationService(repository), repository


def test_register_delegates_authenticated_user_and_event(registration_service):
    """Create or reactivate the caller's registration for the requested event."""
    service, repository = registration_service

    registration = service.register(7, 22)

    assert registration.status == "registered"
    repository.register.assert_called_once_with(7, 22)


def test_cancel_delegates_and_reports_missing_registration(registration_service):
    """Cancel through persistence and translate an absent row to not-found."""
    service, repository = registration_service
    repository.cancel.return_value = True

    service.cancel(7, 22)

    repository.cancel.assert_called_once_with(7, 22)
    repository.cancel.return_value = False
    with pytest.raises(NotFoundError, match="Event registration not found"):
        service.cancel(7, 22)


def test_list_for_user_returns_active_and_cancelled_registrations(registration_service):
    """Return all statuses while forwarding only the authenticated user's ID."""
    service, repository = registration_service
    starts_at = datetime(2030, 1, 1, 10, tzinfo=UTC)
    event = EventRecord(
        id=7,
        title="Conference",
        starts_at=starts_at,
        ends_at=datetime(2030, 1, 1, 12, tzinfo=UTC),
        capacity=20,
        status="published",
        created_by_id=5,
    )
    registrations = [
        EventRegistrationDetails(5, "registered", starts_at, event),
        EventRegistrationDetails(6, "cancelled", starts_at, event),
    ]
    repository.list_by_user.return_value = (registrations, 2)

    page = service.list_for_user(22)

    assert [item.status for item in page.registrations] == [
        "registered",
        "cancelled",
    ]
    assert page.total == 2
    assert page.page == 1
    assert page.page_size == 20
    repository.list_by_user.assert_called_once_with(22, 1, 20)


def test_list_for_user_returns_an_empty_page_without_repository_mutations(
    registration_service,
):
    """Return an empty successful page when the user has no event registrations."""
    service, repository = registration_service
    repository.list_by_user.return_value = ([], 0)

    page = service.list_for_user(22)

    assert page.registrations == ()
    assert page.total == 0
    repository.register.assert_not_called()
    repository.cancel.assert_not_called()
    repository.list_by_user.assert_called_once_with(22, 1, 20)


@pytest.mark.parametrize(
    ("page", "page_size"),
    [("0", None), ("x", None), (None, "101")],
)
def test_list_for_user_validates_pagination(registration_service, page, page_size):
    """Reject malformed pagination before querying the repository."""
    service, repository = registration_service

    with pytest.raises(ValidationError):
        service.list_for_user(22, page=page, page_size=page_size)

    repository.list_by_user.assert_not_called()

"""Verify event registration workflows using a mocked repository."""

from unittest.mock import Mock

import pytest

from app.application.registrations.service import EventRegistrationService
from app.core.exceptions import NotFoundError
from app.domain.entities.event_registration import EventRegistrationRecord
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

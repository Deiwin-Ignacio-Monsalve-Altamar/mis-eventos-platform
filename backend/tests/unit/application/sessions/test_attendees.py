"""Verify session attendee rules using a mocked repository."""

from unittest.mock import Mock

import pytest

from app.application.sessions.attendees import SessionAttendeeService
from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.session_attendee import SessionAttendee, SessionOccupancy
from app.domain.repositories.session_attendee_repository import (
    SessionAttendeeRepository,
)


@pytest.fixture
def attendee_service():
    """Return attendee operations wired to a repository mock."""
    repository = Mock(spec=SessionAttendeeRepository)
    repository.find_event_creator_id.return_value = 7
    repository.session_exists.return_value = True
    return SessionAttendeeService(repository), repository


def test_enroll_uses_authenticated_user_and_event_scoped_session(attendee_service):
    """Delegate enrollment with the caller identity and nested resource IDs."""
    service, repository = attendee_service

    service.enroll(4, 9, 21)

    repository.enroll.assert_called_once_with(4, 9, 21)


def test_cancel_releases_current_users_registration(attendee_service):
    """Cancel the current user's session registration through the repository."""
    service, repository = attendee_service
    repository.cancel.return_value = True

    service.cancel(4, 9, 21)

    repository.cancel.assert_called_once_with(4, 9, 21)


def test_occupancy_returns_session_specific_capacity(attendee_service):
    """Return occupancy data without confusing event attendee counts."""
    service, repository = attendee_service
    expected = SessionOccupancy(capacity=12, occupied=8, available=4)
    repository.get_occupancy.return_value = expected

    assert service.get_occupancy(4, 9) == expected
    repository.get_occupancy.assert_called_once_with(4, 9)


def test_roster_is_limited_to_event_creator(attendee_service):
    """Allow the creator to view attendees and reject other authenticated users."""
    service, repository = attendee_service
    attendee = SessionAttendee(21, "Alex", "Rivera", "alex@example.test", None)
    repository.list_attendees.return_value = [attendee]

    assert service.list_attendees(4, 9, 7) == [attendee]
    with pytest.raises(AuthorizationError):
        service.list_attendees(4, 9, 22)


def test_missing_event_or_session_is_rejected(attendee_service):
    """Reject nonexistent events and sessions before repository mutations."""
    service, repository = attendee_service
    repository.find_event_creator_id.side_effect = NotFoundError("Event not found.")
    with pytest.raises(NotFoundError, match="Event not found"):
        service.enroll(88, 9, 21)

    repository.find_event_creator_id.side_effect = None
    repository.find_event_creator_id.return_value = 7
    repository.session_exists.return_value = False
    with pytest.raises(NotFoundError, match="Session not found"):
        service.enroll(4, 88, 21)
    repository.enroll.assert_not_called()


def test_missing_active_enrollment_cannot_be_cancelled(attendee_service):
    """Return not-found when the caller has no active session enrollment."""
    service, repository = attendee_service
    repository.cancel.return_value = False

    with pytest.raises(NotFoundError, match="Active session registration"):
        service.cancel(4, 9, 21)

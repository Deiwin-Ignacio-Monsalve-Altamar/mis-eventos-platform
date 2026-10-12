"""Coordinate attendee registration, cancellation, roster access, and occupancy."""

from app.application.dto.session_registration_page import SessionRegistrationPage
from app.application.pagination import positive_integer
from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.session_attendee import (
    EventRosterEntry,
    SessionAttendee,
    SessionOccupancy,
)
from app.domain.repositories.session_attendee_repository import (
    SessionAttendeeRepository,
)
from app.settings import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAXIMUM_PAGE_NUMBER,
    MAXIMUM_PAGE_SIZE,
)


class SessionAttendeeService:
    """Apply session ownership and self-service rules to attendee operations."""

    def __init__(self, repository: SessionAttendeeRepository) -> None:
        """Set the persistence port used by attendee operations."""
        self._repository = repository

    def list_attendees(
        self,
        event_id: int,
        session_id: int,
        requester_id: int,
        is_admin: bool = False,
    ) -> list[SessionAttendee]:
        """Allow the event creator or an explicit administrator to view the roster."""
        creator_id = self._event_creator(event_id)
        self._require_session(event_id, session_id)
        if creator_id != requester_id and not is_admin:
            raise AuthorizationError(
                "Only the event creator can view session attendees."
            )
        return self._repository.list_attendees(event_id, session_id)

    def list_event_attendees(
        self, event_id: int, requester_id: int, is_admin: bool = False
    ) -> list[EventRosterEntry]:
        """Allow only the event creator or administrator to view its roster."""
        creator_id = self._event_creator(event_id)
        if creator_id != requester_id and not is_admin:
            raise AuthorizationError("Only the event creator can view attendees.")
        return self._repository.list_event_attendees(event_id)

    def get_occupancy(self, event_id: int, session_id: int) -> SessionOccupancy:
        """Return session-specific capacity, occupancy, and available seats."""
        self._event_creator(event_id)
        self._require_session(event_id, session_id)
        return self._repository.get_occupancy(event_id, session_id)

    def list_registrations_for_user(
        self, user_id: int, page: object = None, page_size: object = None
    ) -> SessionRegistrationPage:
        """Return one user's session enrollments without accepting client identity."""
        validated_page = positive_integer(
            page, "page", DEFAULT_PAGE, MAXIMUM_PAGE_NUMBER
        )
        validated_page_size = positive_integer(
            page_size, "page_size", DEFAULT_PAGE_SIZE, MAXIMUM_PAGE_SIZE
        )
        registrations, total = self._repository.list_registrations_for_user(
            user_id, validated_page, validated_page_size
        )
        return SessionRegistrationPage(
            registrations=tuple(registrations),
            page=validated_page,
            page_size=validated_page_size,
            total=total,
        )

    def enroll(self, event_id: int, session_id: int, user_id: int) -> None:
        """Enroll only the authenticated attendee in an event-scoped session."""
        self._event_creator(event_id)
        self._require_session(event_id, session_id)
        self._repository.enroll(event_id, session_id, user_id)

    def cancel(self, event_id: int, session_id: int, user_id: int) -> None:
        """Cancel the authenticated attendee's enrollment and release its seat."""
        self._event_creator(event_id)
        self._require_session(event_id, session_id)
        if not self._repository.cancel(event_id, session_id, user_id):
            raise NotFoundError("Active session registration not found.")

    def _event_creator(self, event_id: int) -> int | None:
        """Find the event creator or raise a not-found error."""
        return self._repository.find_event_creator_id(event_id)

    def _require_session(self, event_id: int, session_id: int) -> None:
        """Ensure that the session exists under the event in the request path."""
        if not self._repository.session_exists(event_id, session_id):
            raise NotFoundError("Session not found for this event.")

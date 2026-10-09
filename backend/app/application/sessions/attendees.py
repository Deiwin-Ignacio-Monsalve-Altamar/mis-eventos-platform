"""Coordinate attendee registration, cancellation, roster access, and occupancy."""

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.session_attendee import SessionAttendee, SessionOccupancy
from app.domain.repositories.session_attendee_repository import (
    SessionAttendeeRepository,
)


class SessionAttendeeService:
    """Apply session ownership and self-service rules to attendee operations."""

    def __init__(self, repository: SessionAttendeeRepository) -> None:
        """Set the persistence port used by attendee operations."""
        self._repository = repository

    def list_attendees(
        self, event_id: int, session_id: int, requester_id: int
    ) -> list[SessionAttendee]:
        """Allow only the event creator to view the session attendee roster."""
        creator_id = self._event_creator(event_id)
        self._require_session(event_id, session_id)
        if creator_id != requester_id:
            raise AuthorizationError(
                "Only the event creator can view session attendees."
            )
        return self._repository.list_attendees(event_id, session_id)

    def get_occupancy(self, event_id: int, session_id: int) -> SessionOccupancy:
        """Return session-specific capacity, occupancy, and available seats."""
        self._event_creator(event_id)
        self._require_session(event_id, session_id)
        return self._repository.get_occupancy(event_id, session_id)

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

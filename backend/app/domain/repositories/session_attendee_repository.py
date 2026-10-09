"""Define persistence operations for attendee enrollment in sessions."""

from typing import Protocol

from app.domain.entities.session_attendee import SessionAttendee, SessionOccupancy


class SessionAttendeeRepository(Protocol):
    """Describe event-scoped attendee queries and atomic enrollment operations."""

    def find_event_creator_id(self, event_id: int) -> int | None:
        """Return an event's creator identifier, or None when the event is absent."""

    def session_exists(self, event_id: int, session_id: int) -> bool:
        """Return whether a session belongs to the requested event."""

    def list_attendees(self, event_id: int, session_id: int) -> list[SessionAttendee]:
        """List active attendees for one event-scoped session."""

    def get_occupancy(self, event_id: int, session_id: int) -> SessionOccupancy:
        """Return the capacity and active occupancy snapshot for a session."""

    def enroll(self, event_id: int, session_id: int, user_id: int) -> None:
        """Atomically enroll or reactivate a user's event registration in a session."""

    def cancel(self, event_id: int, session_id: int, user_id: int) -> bool:
        """Cancel the authenticated user's active enrollment, if present."""

"""Define persistence operations for a user's event registration."""

from typing import Protocol

from app.domain.entities.event_registration import EventRegistrationRecord


class EventRegistrationRepository(Protocol):
    """Describe self-service event registration persistence operations."""

    def register(self, event_id: int, user_id: int) -> EventRegistrationRecord:
        """Create or reactivate one event registration transactionally."""

    def cancel(self, event_id: int, user_id: int) -> bool:
        """Cancel an event registration and all active session enrollments."""

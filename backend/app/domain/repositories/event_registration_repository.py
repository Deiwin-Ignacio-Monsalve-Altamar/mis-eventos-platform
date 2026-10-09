"""Define persistence operations for a user's event registration."""

from typing import Protocol

from app.domain.entities.event_registration import (
    EventRegistrationDetails,
    EventRegistrationRecord,
)


class EventRegistrationRepository(Protocol):
    """Describe self-service event registration persistence operations."""

    def register(self, event_id: int, user_id: int) -> EventRegistrationRecord:
        """Create or reactivate one event registration transactionally."""

    def list_by_user(
        self, user_id: int, page: int, page_size: int
    ) -> tuple[list[EventRegistrationDetails], int]:
        """Return all statuses for one user's registrations in a page."""

    def cancel(self, event_id: int, user_id: int) -> bool:
        """Cancel an event registration and all active session enrollments."""

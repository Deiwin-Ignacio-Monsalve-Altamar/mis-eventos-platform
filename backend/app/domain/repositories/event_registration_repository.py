"""Define persistence operations for a user's event registration."""

from datetime import datetime
from typing import Protocol

from app.domain.entities.event_registration import (
    EventRegistrationDetails,
    EventRegistrationRecord,
)


class EventRegistrationRepository(Protocol):
    """Describe self-service event registration persistence operations."""

    def register(self, event_id: int, user_id: int) -> EventRegistrationRecord:
        """Create or reactivate one event registration transactionally."""

    def capacity_for_event(self, event_id: int) -> tuple[int, int] | None:
        """Return event capacity and active registration count, or None if absent."""

    def list_by_user(
        self,
        user_id: int,
        page: int,
        page_size: int,
        status: str | None = None,
        period: str | None = None,
        now: datetime | None = None,
    ) -> tuple[list[EventRegistrationDetails], int]:
        """Return one filtered page of the caller's event registrations."""

    def summary_by_user(self, user_id: int, now: datetime) -> dict[str, int]:
        """Return active, upcoming, past, and cancelled registration counts."""

    def cancel(self, event_id: int, user_id: int) -> bool:
        """Cancel an event registration and all active session enrollments."""

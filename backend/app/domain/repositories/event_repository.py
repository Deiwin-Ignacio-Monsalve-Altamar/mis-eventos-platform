"""Define persistence operations for event creation and updates."""

from datetime import datetime
from typing import Protocol

from app.domain.entities.event_record import EventRecord


class EventRepository(Protocol):
    """Describe event persistence without coupling application logic to SQLAlchemy."""

    def find_by_id(
        self, event_id: int, *, lock_for_read: bool = False
    ) -> EventRecord | None:
        """Return an event by its database identifier, if it exists."""
        ...

    def list_events(
        self, page: int, page_size: int, search_query: str | None
    ) -> tuple[list[EventRecord], int]:
        """Return one ordered event page and the total number of matches."""
        ...

    def list_by_creator(
        self,
        creator_id: int,
        page: int,
        page_size: int,
        search_query: str | None,
        status: str | None,
    ) -> tuple[list[EventRecord], int]:
        """Return one page of events owned by the authenticated creator."""
        ...

    def find_by_id_for_creator(
        self, event_id: int, creator_id: int
    ) -> EventRecord | None:
        """Return an event only when it belongs to the supplied creator."""
        ...

    def dashboard_counts(self, creator_id: int, now: datetime) -> dict[str, int]:
        """Return aggregate status and date counts for one event creator."""
        ...

    def event_activity_by_creator(
        self, creator_id: int, now: datetime, limit: int
    ) -> list[dict[str, object]]:
        """Return bounded event, session, and active registration metrics for an owner."""
        ...

    def active_registration_count_by_creator(self, creator_id: int) -> int:
        """Return active registrations across all events created by an owner."""
        ...

    def recommendations_for_user(
        self, user_id: int, now: datetime, limit: int
    ) -> list[tuple[EventRecord, int]]:
        """Return upcoming published events with room and no active user enrollment."""
        ...

    def save(
        self,
        event: EventRecord,
        expected_version: int | None = None,
        owner_id: int | None = None,
        is_admin: bool = False,
    ) -> EventRecord:
        """Insert an event or atomically update it against the client's version."""
        ...

    def delete(self, event_id: int, owner_id: int, is_admin: bool = False) -> bool:
        """Delete an owned or admin-managed event with no related records."""
        ...

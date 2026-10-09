"""Define persistence operations for event creation and updates."""

from typing import Protocol

from app.domain.entities.event_record import EventRecord


class EventRepository(Protocol):
    """Describe event persistence without coupling application logic to SQLAlchemy."""

    def find_by_id(self, event_id: int) -> EventRecord | None:
        """Return an event by its database identifier, if it exists."""
        ...

    def list_events(
        self, page: int, page_size: int, search_query: str | None
    ) -> tuple[list[EventRecord], int]:
        """Return one ordered event page and the total number of matches."""
        ...

    def save(self, event: EventRecord) -> EventRecord:
        """Insert a new event or persist changes to an existing event."""
        ...

    def delete(self, event_id: int) -> bool:
        """Delete an event with no related records and report whether it existed."""
        ...

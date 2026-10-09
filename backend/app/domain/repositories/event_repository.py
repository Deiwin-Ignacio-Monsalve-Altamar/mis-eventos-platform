"""Define persistence operations for event creation and updates."""

from typing import Protocol

from app.domain.entities.event_record import EventRecord


class EventRepository(Protocol):
    """Describe event persistence without coupling application logic to SQLAlchemy."""

    def find_by_id(self, event_id: int) -> EventRecord | None:
        """Return an event by its database identifier, if it exists."""
        ...

    def save(self, event: EventRecord) -> EventRecord:
        """Insert a new event or persist changes to an existing event."""
        ...

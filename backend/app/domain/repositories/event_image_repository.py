"""Persistence contract for event image metadata."""

from typing import Protocol

from app.domain.entities.event_image import EventImageRecord


class EventImageRepository(Protocol):
    """Describe event image persistence without coupling to SQLAlchemy."""

    def create(self, image: EventImageRecord) -> EventImageRecord:
        """Persist an image record and return its generated fields."""
        ...

    def list_by_event(self, event_id: int) -> list[EventImageRecord]:
        """Return an event's images ordered by gallery position."""
        ...

    def replace_for_event(
        self, event_id: int, images: list[EventImageRecord]
    ) -> list[EventImageRecord]:
        """Atomically replace gallery rows and return the previous records."""
        ...

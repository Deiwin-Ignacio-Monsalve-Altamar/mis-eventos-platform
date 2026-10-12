"""Represent stored image metadata associated with an event."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EventImageRecord:
    """Hold an event image's public URL, storage reference, and position."""

    event_id: int
    storage_key: str
    url: str
    position: int
    id: int | None = None
    created_at: datetime | None = None

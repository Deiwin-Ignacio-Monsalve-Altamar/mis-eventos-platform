"""Represent a scheduled session and its assigned speaker identifiers."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionRecord:
    """Hold validated session values independently of the persistence model."""

    id: int | None
    event_id: int
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    capacity: int
    speaker_ids: tuple[int, ...] = ()

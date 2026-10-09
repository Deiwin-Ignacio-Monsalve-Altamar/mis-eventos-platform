"""Represent event details and their authenticated creator in the domain."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EventRecord:
    """Hold event data independently of its SQLAlchemy persistence model."""

    title: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    created_by_id: int | None
    description: str | None = None
    location: str | None = None
    status: str = "draft"
    id: int | None = None
    version: int = 1

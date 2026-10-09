"""Represent a user's registration in an event."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.event_record import EventRecord


@dataclass(frozen=True, slots=True)
class EventRegistrationRecord:
    """Hold event registration identity and lifecycle status."""

    id: int
    event_id: int
    user_id: int
    status: str


@dataclass(frozen=True, slots=True)
class EventRegistrationDetails:
    """Pair an attendee's registration status with its public event details."""

    id: int
    status: str
    registered_at: datetime
    event: EventRecord

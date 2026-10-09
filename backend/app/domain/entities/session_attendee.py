"""Represent session occupancy and the public attendee roster."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SessionOccupancy:
    """Summarize configured capacity and the number of active enrollments."""

    capacity: int
    occupied: int
    available: int


@dataclass(frozen=True, slots=True)
class SessionAttendee:
    """Expose safe identity fields for an event organizer's attendee roster."""

    user_id: int
    first_name: str
    last_name: str
    email: str
    registered_at: datetime

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


@dataclass(frozen=True, slots=True)
class SessionRegistrationDetails:
    """Represent a caller's session enrollment with its event and schedule."""

    id: int
    status: str
    registered_at: datetime
    session_id: int
    session_title: str
    session_description: str | None
    session_starts_at: datetime
    session_ends_at: datetime
    session_capacity: int
    event_id: int
    event_title: str
    event_status: str
    event_location: str | None

"""Represent a user's registration in an event."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventRegistrationRecord:
    """Hold event registration identity and lifecycle status."""

    id: int
    event_id: int
    user_id: int
    status: str

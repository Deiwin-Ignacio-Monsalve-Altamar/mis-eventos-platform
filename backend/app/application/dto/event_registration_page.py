"""Represent a page of a user's event registrations."""

from dataclasses import dataclass

from app.domain.entities.event_registration import EventRegistrationDetails


@dataclass(frozen=True, slots=True)
class EventRegistrationPage:
    """Carry registration details and pagination metadata to the API layer."""

    registrations: tuple[EventRegistrationDetails, ...]
    page: int
    page_size: int
    total: int

"""Represent a page of events returned by a listing or search use case."""

from dataclasses import dataclass

from app.domain.entities.event_record import EventRecord


@dataclass(frozen=True, slots=True)
class EventPage:
    """Carry event records and their pagination details to the API layer."""

    events: tuple[EventRecord, ...]
    page: int
    page_size: int
    total: int

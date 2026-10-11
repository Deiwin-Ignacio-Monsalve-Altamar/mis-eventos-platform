"""Represent one page of the authenticated user's session registrations."""

from dataclasses import dataclass

from app.domain.entities.session_attendee import SessionRegistrationDetails


@dataclass(frozen=True, slots=True)
class SessionRegistrationPage:
    """Carry session registration details and pagination metadata to the API."""

    registrations: tuple[SessionRegistrationDetails, ...]
    page: int
    page_size: int
    total: int

"""Coordinate self-service event registration and cancellation."""

from app.core.exceptions import NotFoundError
from app.domain.entities.event_registration import EventRegistrationRecord
from app.domain.repositories.event_registration_repository import (
    EventRegistrationRepository,
)


class EventRegistrationService:
    """Apply event registration use cases through the registration repository."""

    def __init__(self, repository: EventRegistrationRepository) -> None:
        """Set the repository used for event registration operations."""
        self._repository = repository

    def register(self, event_id: int, user_id: int) -> EventRegistrationRecord:
        """Create or reactivate the authenticated user's event registration."""
        return self._repository.register(event_id, user_id)

    def cancel(self, event_id: int, user_id: int) -> None:
        """Cancel the authenticated user's registration or raise when absent."""
        if not self._repository.cancel(event_id, user_id):
            raise NotFoundError("Event registration not found.")

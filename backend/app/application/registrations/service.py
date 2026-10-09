"""Coordinate self-service event registration and cancellation."""

from app.application.dto.event_registration_page import EventRegistrationPage
from app.application.pagination import positive_integer
from app.core.exceptions import NotFoundError
from app.domain.entities.event_registration import EventRegistrationRecord
from app.domain.repositories.event_registration_repository import (
    EventRegistrationRepository,
)

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAXIMUM_PAGE_SIZE = 100
MAXIMUM_PAGE_NUMBER = 1_000_000


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

    def list_for_user(
        self, user_id: int, page: object = None, page_size: object = None
    ) -> EventRegistrationPage:
        """Return one authenticated user's registrations, including cancelled."""
        validated_page = positive_integer(
            page, "page", DEFAULT_PAGE, MAXIMUM_PAGE_NUMBER
        )
        validated_page_size = positive_integer(
            page_size, "page_size", DEFAULT_PAGE_SIZE, MAXIMUM_PAGE_SIZE
        )
        registrations, total = self._repository.list_by_user(
            user_id, validated_page, validated_page_size
        )
        return EventRegistrationPage(
            registrations=tuple(registrations),
            page=validated_page,
            page_size=validated_page_size,
            total=total,
        )

"""Coordinate self-service event registration and cancellation."""

from datetime import UTC, datetime

from app.application.dto.event_registration_page import EventRegistrationPage
from app.application.pagination import positive_integer
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.event_registration import EventRegistrationRecord
from app.domain.repositories.event_registration_repository import (
    EventRegistrationRepository,
)
from app.observability.metrics import increment_business_metric

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAXIMUM_PAGE_SIZE = 100
MAXIMUM_PAGE_NUMBER = 1_000_000
REGISTRATION_STATUSES = {"registered", "cancelled"}
REGISTRATION_PERIODS = {"upcoming", "active", "past"}


class EventRegistrationService:
    """Apply event registration use cases through the registration repository."""

    def __init__(self, repository: EventRegistrationRepository) -> None:
        """Set the repository used for event registration operations."""
        self._repository = repository

    def register(self, event_id: int, user_id: int) -> EventRegistrationRecord:
        """Create or reactivate the authenticated user's event registration."""
        registration = self._repository.register(event_id, user_id)
        increment_business_metric("registration_completed")
        return registration

    def cancel(self, event_id: int, user_id: int) -> None:
        """Cancel the authenticated user's registration or raise when absent."""
        if not self._repository.cancel(event_id, user_id):
            raise NotFoundError("Event registration not found.")

    def capacity_for_event(self, event_id: int) -> dict[str, int]:
        """Return public event seat counts based only on active registrations."""
        result = self._repository.capacity_for_event(event_id)
        if result is None:
            raise NotFoundError("Event not found.")
        capacity, occupied = result
        return {
            "capacity": capacity,
            "occupied": occupied,
            "available": max(capacity - occupied, 0),
        }

    def list_for_user(
        self,
        user_id: int,
        page: object = None,
        page_size: object = None,
        status: object = None,
        period: object = None,
        now: datetime | None = None,
    ) -> EventRegistrationPage:
        """Return one authenticated user's registrations, including cancelled."""
        validated_page = positive_integer(
            page, "page", DEFAULT_PAGE, MAXIMUM_PAGE_NUMBER
        )
        validated_page_size = positive_integer(
            page_size, "page_size", DEFAULT_PAGE_SIZE, MAXIMUM_PAGE_SIZE
        )
        validated_status = self._validated_filter(
            status, REGISTRATION_STATUSES, "status"
        )
        validated_period = self._validated_filter(
            period, REGISTRATION_PERIODS, "period"
        )
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValidationError("Registration query time must be timezone-aware.")
        registrations, total = self._repository.list_by_user(
            user_id,
            validated_page,
            validated_page_size,
            validated_status,
            validated_period,
            timestamp.astimezone(UTC),
        )
        return EventRegistrationPage(
            registrations=tuple(registrations),
            page=validated_page,
            page_size=validated_page_size,
            total=total,
        )

    @staticmethod
    def _validated_filter(value: object, allowed: set[str], name: str) -> str | None:
        """Validate an optional query filter against the existing model states."""
        if value is None:
            return None
        if not isinstance(value, str) or value not in allowed:
            raise ValidationError(f"{name} is not a supported registration filter.")
        return value

    def summary_for_user(
        self, user_id: int, now: datetime | None = None
    ) -> dict[str, int]:
        """Return registration metrics isolated to one account at a UTC instant."""
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Registration summary time must be timezone-aware.")
        return self._repository.summary_by_user(user_id, timestamp.astimezone(UTC))

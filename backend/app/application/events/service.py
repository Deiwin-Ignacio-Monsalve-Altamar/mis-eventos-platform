"""Validate event input and coordinate event creation and editing."""

from datetime import UTC, datetime

from app.application.dto.event_page import EventPage
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.event_record import EventRecord
from app.domain.repositories.event_repository import EventRepository

EVENT_STATUSES = {"draft", "published", "cancelled", "completed"}
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAXIMUM_PAGE_SIZE = 100
MAXIMUM_PAGE_NUMBER = 1_000_000
MAXIMUM_SEARCH_LENGTH = 200
EDITABLE_FIELDS = {
    "title",
    "description",
    "location",
    "starts_at",
    "ends_at",
    "capacity",
    "status",
}


class EventService:
    """Coordinate validation and persistence for protected event operations."""

    def __init__(self, event_repository: EventRepository) -> None:
        """Set the event persistence port used by this service."""
        self._event_repository = event_repository

    def create(self, values: dict[str, object], creator_id: int) -> EventRecord:
        """Validate and persist an event attributed to its authenticated creator."""
        event_values = self._validated_values(values)
        return self._event_repository.save(
            EventRecord(created_by_id=creator_id, **event_values)
        )

    def update(
        self, event_id: int, values: dict[str, object], expected_version: object
    ) -> EventRecord:
        """Validate and persist supplied event fields without changing its creator."""
        existing = self._event_repository.find_by_id(event_id)
        if existing is None:
            raise NotFoundError("Event not found.")
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 1
        ):
            raise ValidationError("A positive integer resource version is required.")
        if not values:
            raise ValidationError("At least one editable event field is required.")

        current_values = {
            "title": existing.title,
            "description": existing.description,
            "location": existing.location,
            "starts_at": existing.starts_at,
            "ends_at": existing.ends_at,
            "capacity": existing.capacity,
            "status": existing.status,
        }
        current_values.update(values)
        event_values = self._validated_values(current_values)
        updated = EventRecord(
            id=existing.id,
            created_by_id=existing.created_by_id,
            version=existing.version,
            **event_values,
        )
        return self._event_repository.save(updated, expected_version)

    def delete(self, event_id: int) -> None:
        """Delete an event or raise when it is missing or still referenced."""
        if not self._event_repository.delete(event_id):
            raise NotFoundError("Event not found.")

    def get_by_id(self, event_id: int) -> EventRecord:
        """Return a persisted event or raise when it does not exist."""
        event = self._event_repository.find_by_id(event_id)
        if event is None:
            raise NotFoundError("Event not found.")
        return event

    def list_events(
        self, page: object, page_size: object, search_query: object
    ) -> EventPage:
        """Validate listing parameters and return the requested event page."""
        validated_page = self._positive_integer(
            page, "page", DEFAULT_PAGE, MAXIMUM_PAGE_NUMBER
        )
        validated_page_size = self._positive_integer(
            page_size, "page_size", DEFAULT_PAGE_SIZE, MAXIMUM_PAGE_SIZE
        )
        normalized_search = self._normalize_search_query(search_query)
        events, total = self._event_repository.list_events(
            validated_page, validated_page_size, normalized_search
        )
        return EventPage(
            events=tuple(events),
            page=validated_page,
            page_size=validated_page_size,
            total=total,
        )

    @staticmethod
    def _positive_integer(
        value: object, field_name: str, default: int, maximum: int
    ) -> int:
        """Parse a positive integer query parameter within its configured limit."""
        if value is None:
            return default
        if (
            not isinstance(value, str)
            or not value.isascii()
            or not value.isdecimal()
            or len(value) > len(str(maximum))
        ):
            raise ValidationError(f"{field_name} must be a positive integer.")
        parsed_value = int(value)
        if parsed_value < 1 or parsed_value > maximum:
            raise ValidationError(f"{field_name} must be between 1 and {maximum}.")
        return parsed_value

    @staticmethod
    def _normalize_search_query(value: object) -> str | None:
        """Trim and validate an optional free-text event search query."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValidationError("q must be a text value.")
        normalized_query = value.strip()
        if not normalized_query or len(normalized_query) > MAXIMUM_SEARCH_LENGTH:
            raise ValidationError("q must contain between 1 and 200 characters.")
        return normalized_query

    @staticmethod
    def _validated_values(values: dict[str, object]) -> dict[str, object]:
        """Validate all persisted event fields and normalize date and text values."""
        title = values.get("title")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
            raise ValidationError("Title must contain between 1 and 200 characters.")

        starts_at = EventService._parse_datetime(values.get("starts_at"), "starts_at")
        ends_at = EventService._parse_datetime(values.get("ends_at"), "ends_at")
        if ends_at <= starts_at:
            raise ValidationError("ends_at must be later than starts_at.")

        capacity = values.get("capacity")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValidationError("Capacity must be a positive integer.")

        description = values.get("description")
        if description is not None and not isinstance(description, str):
            raise ValidationError("Description must be a string or null.")
        location = values.get("location")
        if location is not None and (
            not isinstance(location, str) or len(location) > 255
        ):
            raise ValidationError(
                "Location must be a string of at most 255 characters."
            )

        status = values.get("status", "draft")
        if not isinstance(status, str) or status not in EVENT_STATUSES:
            raise ValidationError("Status is not a valid event status.")

        return {
            "title": title.strip(),
            "description": description,
            "location": location,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "capacity": capacity,
            "status": status,
        }

    @staticmethod
    def _parse_datetime(value: object, field_name: str) -> datetime:
        """Parse a timezone-aware ISO-8601 value and normalize it to UTC."""
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValidationError(
                    f"{field_name} must be a timezone-aware ISO-8601 value."
                )
            return value.astimezone(UTC)
        if not isinstance(value, str):
            raise ValidationError(
                f"{field_name} must be a timezone-aware ISO-8601 value."
            )
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValidationError(
                f"{field_name} must be a timezone-aware ISO-8601 value."
            ) from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValidationError(
                f"{field_name} must be a timezone-aware ISO-8601 value."
            )
        return parsed.astimezone(UTC)

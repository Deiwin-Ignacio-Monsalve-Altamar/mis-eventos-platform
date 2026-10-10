"""Validate event input and coordinate event creation and editing."""

from datetime import UTC, datetime

from app.application.dto.event_page import EventPage
from app.application.pagination import positive_integer
from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.entities.event_record import EventRecord
from app.domain.repositories.event_repository import EventRepository
from app.observability.metrics import increment_business_metric

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
        event = self._event_repository.save(
            EventRecord(created_by_id=creator_id, **event_values)
        )
        increment_business_metric("event_created")
        return event

    def update(
        self,
        event_id: int,
        values: dict[str, object],
        expected_version: object,
        creator_id: int,
    ) -> EventRecord:
        """Authorize the creator, then validate and persist an event update."""
        existing = self._event_repository.find_by_id(event_id)
        if existing is None:
            raise NotFoundError("Event not found.")
        if existing.created_by_id != creator_id:
            raise AuthorizationError("Only the event creator can edit this event.")
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
        return self._event_repository.save(updated, expected_version, creator_id)

    def delete(self, event_id: int, creator_id: int) -> None:
        """Delete an owned event or raise when missing, forbidden, or referenced."""
        existing = self._event_repository.find_by_id(event_id)
        if existing is None:
            raise NotFoundError("Event not found.")
        if existing.created_by_id != creator_id:
            raise AuthorizationError("Only the event creator can delete this event.")
        if not self._event_repository.delete(event_id, creator_id):
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

    def list_my_events(
        self,
        creator_id: int,
        page: object,
        page_size: object,
        search_query: object,
        status: object = None,
    ) -> EventPage:
        """Return a validated page restricted to the authenticated creator."""
        validated_page = self._positive_integer(
            page, "page", DEFAULT_PAGE, MAXIMUM_PAGE_NUMBER
        )
        validated_page_size = self._positive_integer(
            page_size, "page_size", DEFAULT_PAGE_SIZE, MAXIMUM_PAGE_SIZE
        )
        normalized_search = self._normalize_search_query(search_query)
        normalized_status = self._normalize_status_filter(status)
        events, total = self._event_repository.list_by_creator(
            creator_id,
            validated_page,
            validated_page_size,
            normalized_search,
            normalized_status,
        )
        return EventPage(tuple(events), validated_page, validated_page_size, total)

    def get_my_event(self, event_id: int, creator_id: int) -> EventRecord:
        """Return an event only when it belongs to the authenticated creator."""
        event = self._event_repository.find_by_id_for_creator(event_id, creator_id)
        if event is None:
            raise NotFoundError("Event not found.")
        return event

    def dashboard(
        self, creator_id: int, now: datetime | None = None
    ) -> dict[str, object]:
        """Calculate creator-only event totals and status percentages at one UTC instant."""
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValidationError("Dashboard time must be timezone-aware.")
        timestamp = timestamp.astimezone(UTC)
        counts = self._event_repository.dashboard_counts(creator_id, timestamp)
        total = counts["total"]
        status_counts = {
            status: counts.get(status, 0) for status in sorted(EVENT_STATUSES)
        }
        percentages = {
            status: round((count * 100 / total), 1) if total else 0.0
            for status, count in status_counts.items()
        }
        return {
            "total_events": total,
            "upcoming_events": counts.get("upcoming", 0),
            "active_events": counts.get("active", 0),
            "finished_events": counts.get("finished", 0),
            "cancelled_events": status_counts["cancelled"],
            "status_counts": status_counts,
            "status_percentages": percentages,
        }

    @staticmethod
    def _normalize_status_filter(value: object) -> str | None:
        """Validate an optional status filter against the event model enum."""
        if value is None:
            return None
        if not isinstance(value, str) or value not in EVENT_STATUSES:
            raise ValidationError("status must be a valid event status.")
        return value

    @staticmethod
    def _positive_integer(
        value: object, field_name: str, default: int, maximum: int
    ) -> int:
        """Parse a positive integer query parameter within its configured limit."""
        return positive_integer(value, field_name, default, maximum)

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

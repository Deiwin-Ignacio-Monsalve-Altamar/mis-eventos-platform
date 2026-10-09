"""Validate session rules and coordinate session persistence."""

from datetime import UTC, datetime

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.session_record import SessionRecord
from app.domain.repositories.session_repository import SessionRepository

SESSION_FIELDS = {
    "title",
    "description",
    "starts_at",
    "ends_at",
    "capacity",
    "speaker_ids",
}


class SessionService:
    """Apply event schedule, capacity, and speaker rules to session operations."""

    def __init__(self, session_repository: SessionRepository) -> None:
        """Set the persistence port used for session management."""
        self._repository = session_repository

    def create(self, event_id: int, values: dict[str, object]) -> SessionRecord:
        """Validate and create a session belonging to an existing event."""
        event = self._event(event_id)
        record = self._validated(event_id, values, event, None)
        if self._repository.find_overlapping(
            event_id, record.starts_at, record.ends_at
        ):
            raise ValidationError("Session schedule overlaps another session.")
        return self._repository.save(record)

    def list_by_event(self, event_id: int) -> list[SessionRecord]:
        """Return sessions for an existing event."""
        self._event(event_id)
        return self._repository.list_by_event(event_id)

    def get(self, event_id: int, session_id: int) -> SessionRecord:
        """Return a session owned by the event or raise a not-found error."""
        self._event(event_id)
        session = self._repository.find_by_id(event_id, session_id)
        if session is None:
            raise NotFoundError("Session not found for this event.")
        return session

    def update(
        self,
        event_id: int,
        session_id: int,
        values: dict[str, object],
        expected_version: object,
    ) -> SessionRecord:
        """Merge, validate, and save editable fields for an existing session."""
        existing = self.get(event_id, session_id)
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 1
        ):
            raise ValidationError("A positive integer resource version is required.")
        if not values:
            raise ValidationError("At least one editable session field is required.")
        merged = {
            "title": existing.title,
            "description": existing.description,
            "starts_at": existing.starts_at,
            "ends_at": existing.ends_at,
            "capacity": existing.capacity,
            "speaker_ids": list(existing.speaker_ids),
            "version": existing.version,
        }
        merged.update(values)
        record = self._validated(event_id, merged, self._event(event_id), session_id)
        if self._repository.find_overlapping(
            event_id, record.starts_at, record.ends_at, session_id
        ):
            raise ValidationError("Session schedule overlaps another session.")
        return self._repository.save(record, expected_version)

    def delete(self, event_id: int, session_id: int) -> None:
        """Delete a session from its event without affecting related profiles."""
        self._event(event_id)
        if not self._repository.delete(event_id, session_id):
            raise NotFoundError("Session not found for this event.")

    def _event(self, event_id: int):
        """Load the parent event or raise a clear not-found error."""
        event = self._repository.find_event(event_id)
        if event is None:
            raise NotFoundError("Event not found.")
        return event

    def _validated(self, event_id, values, event, session_id) -> SessionRecord:
        """Validate the full session state and normalize it to a domain record."""
        title = values.get("title")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
            raise ValidationError("Title must contain between 1 and 200 characters.")
        starts = self._parse_datetime(values.get("starts_at"), "starts_at")
        ends = self._parse_datetime(values.get("ends_at"), "ends_at")
        if ends <= starts:
            raise ValidationError("ends_at must be later than starts_at.")
        event_start = self._aware_utc(event.starts_at)
        event_end = self._aware_utc(event.ends_at)
        if starts < event_start or ends > event_end:
            raise ValidationError("Session dates must be within the event schedule.")
        capacity = values.get("capacity")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValidationError("Capacity must be a positive integer.")
        description = values.get("description")
        if description is not None and not isinstance(description, str):
            raise ValidationError("Description must be a string or null.")
        speaker_ids = values.get("speaker_ids", [])
        if not isinstance(speaker_ids, list) or any(
            isinstance(i, bool) or not isinstance(i, int) or i < 1 for i in speaker_ids
        ):
            raise ValidationError("speaker_ids must be a list of positive integer IDs.")
        if len(set(speaker_ids)) != len(speaker_ids):
            raise ValidationError("speaker_ids must not contain duplicates.")
        speaker_tuple = tuple(speaker_ids)
        if speaker_tuple and not self._repository.speaker_ids_exist(speaker_tuple):
            raise ValidationError("One or more speakers do not exist.")
        return SessionRecord(
            session_id,
            event_id,
            title.strip(),
            description,
            starts,
            ends,
            capacity,
            speaker_tuple,
            version=values.get("version", 1),
        )

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        """Normalize a stored aware datetime to UTC for comparison."""
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _parse_datetime(value: object, field: str) -> datetime:
        """Parse an ISO-8601 datetime that includes an explicit timezone."""
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValidationError(
                    f"{field} must be a timezone-aware ISO-8601 value."
                )
            return value.astimezone(UTC)
        if not isinstance(value, str):
            raise ValidationError(f"{field} must be a timezone-aware ISO-8601 value.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValidationError(
                f"{field} must be a timezone-aware ISO-8601 value."
            ) from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValidationError(f"{field} must be a timezone-aware ISO-8601 value.")
        return parsed.astimezone(UTC)

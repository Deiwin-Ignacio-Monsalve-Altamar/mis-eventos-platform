"""Define persistence operations required to manage scheduled sessions."""

from datetime import datetime
from typing import Protocol

from app.domain.entities.event_record import EventRecord
from app.domain.entities.session_record import SessionRecord


class SessionRepository(Protocol):
    """Describe session and related-record queries used by the application."""

    def find_event(self, event_id: int) -> EventRecord | None:
        """Return the parent event when it exists."""

    def find_by_id(self, event_id: int, session_id: int) -> SessionRecord | None:
        """Return a session only when it belongs to the requested event."""

    def list_by_event(self, event_id: int) -> list[SessionRecord]:
        """Return sessions for one event in schedule order."""

    def find_overlapping(
        self,
        event_id: int,
        starts_at: datetime,
        ends_at: datetime,
        exclude_session_id: int | None = None,
    ) -> SessionRecord | None:
        """Find one strict interval overlap, optionally excluding one session."""

    def speaker_ids_exist(self, speaker_ids: tuple[int, ...]) -> bool:
        """Return whether every requested speaker identifier exists."""

    def save(self, session: SessionRecord) -> SessionRecord:
        """Insert or update a session and replace its speaker associations."""

    def delete(self, event_id: int, session_id: int) -> bool:
        """Delete a session only when it belongs to the requested event."""

"""Persist scheduled session records through the active SQLAlchemy session."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.event_record import EventRecord
from app.domain.entities.session_record import SessionRecord
from app.infrastructure.database.models import Event, EventSession, Speaker


class SQLAlchemySessionRepository:
    """Adapt session domain records to the existing event and speaker models."""

    def __init__(self, session: Session) -> None:
        """Receive the active request-scoped SQLAlchemy session."""
        self._session = session

    def find_event(self, event_id: int) -> EventRecord | None:
        """Load the parent event and map only schedule fields needed by the service."""
        event = self._session.get(Event, event_id)
        if event is None:
            return None
        return EventRecord(
            title=event.title,
            description=event.description,
            location=event.location,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            capacity=event.capacity,
            status=event.status,
            created_by_id=event.created_by_id,
            id=event.id,
        )

    def find_by_id(self, event_id: int, session_id: int) -> SessionRecord | None:
        """Load a session constrained by both its identifier and parent event."""
        model = self._session.scalar(
            select(EventSession).where(
                EventSession.id == session_id, EventSession.event_id == event_id
            )
        )
        return self._to_record(model) if model is not None else None

    def list_by_event(self, event_id: int) -> list[SessionRecord]:
        """Load sessions in stable chronological order for one event."""
        models = self._session.scalars(
            select(EventSession)
            .where(EventSession.event_id == event_id)
            .order_by(EventSession.starts_at.asc(), EventSession.id.asc())
        ).all()
        return [self._to_record(model) for model in models]

    def find_overlapping(self, event_id, starts_at, ends_at, exclude_session_id=None):
        """Query for a strict interval overlap without loading the whole schedule."""
        statement = select(EventSession).where(
            EventSession.event_id == event_id,
            EventSession.starts_at < ends_at,
            EventSession.ends_at > starts_at,
        )
        if exclude_session_id is not None:
            statement = statement.where(EventSession.id != exclude_session_id)
        model = self._session.scalar(statement.limit(1))
        return self._to_record(model) if model is not None else None

    def speaker_ids_exist(self, speaker_ids: tuple[int, ...]) -> bool:
        """Check that all requested speaker rows exist using one bound query."""
        count = self._session.scalar(
            select(func.count(Speaker.id)).where(Speaker.id.in_(speaker_ids))
        )
        return count == len(speaker_ids)

    def save(self, session: SessionRecord) -> SessionRecord:
        """Insert or update a session and atomically replace speaker links."""
        model = (
            self._session.get(EventSession, session.id)
            if session.id is not None
            else EventSession()
        )
        if model is None:
            raise NotFoundError("Session no longer exists for this event.")
        if session.id is None:
            model.event_id = session.event_id
        elif model.event_id != session.event_id:
            raise NotFoundError("Session does not belong to this event.")
        model.title = session.title
        model.description = session.description
        model.starts_at = session.starts_at
        model.ends_at = session.ends_at
        model.capacity = session.capacity
        speakers = (
            list(
                self._session.scalars(
                    select(Speaker).where(Speaker.id.in_(session.speaker_ids))
                ).all()
            )
            if session.speaker_ids
            else []
        )
        if len(speakers) != len(session.speaker_ids):
            raise ValidationError("One or more speakers do not exist.")
        model.speakers = speakers
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The session violates a data integrity rule."
            ) from error
        return self._to_record(model)

    def delete(self, event_id: int, session_id: int) -> bool:
        """Delete only the requested session belonging to the specified event."""
        model = self._session.scalar(
            select(EventSession).where(
                EventSession.id == session_id, EventSession.event_id == event_id
            )
        )
        if model is None:
            return False
        self._session.delete(model)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError("The session could not be deleted safely.") from error
        return True

    @staticmethod
    def _to_record(model: EventSession) -> SessionRecord:
        """Map an ORM session and its loaded speakers to the domain record."""
        return SessionRecord(
            model.id,
            model.event_id,
            model.title,
            model.description,
            model.starts_at,
            model.ends_at,
            model.capacity,
            tuple(speaker.id for speaker in model.speakers),
        )

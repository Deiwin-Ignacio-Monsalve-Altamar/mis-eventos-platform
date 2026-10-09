"""Persist scheduled session records through the active SQLAlchemy session."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import (
    ConcurrencyConflictError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.event_record import EventRecord
from app.domain.entities.session_record import SessionRecord
from app.infrastructure.database.models import (
    Event,
    EventSession,
    Registration,
    SessionRegistration,
    Speaker,
)


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

    def save(
        self, session: SessionRecord, expected_version: int | None = None
    ) -> SessionRecord:
        """Lock the event, validate overlap and capacity, then persist atomically."""
        event = self._session.scalar(
            select(Event)
            .where(Event.id == session.event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if event is None:
            self._session.rollback()
            raise NotFoundError("Event not found.")
        if session.starts_at < event.starts_at or session.ends_at > event.ends_at:
            self._session.rollback()
            raise ValidationError("Session dates must be within the event schedule.")

        model = (
            self._session.scalar(
                select(EventSession)
                .where(EventSession.id == session.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if session.id is not None
            else EventSession()
        )
        if model is None:
            self._session.rollback()
            raise NotFoundError("Session no longer exists for this event.")
        if session.id is None:
            model.event_id = session.event_id
        else:
            if model.event_id != session.event_id:
                self._session.rollback()
                raise NotFoundError("Session does not belong to this event.")
            if expected_version is None:
                self._session.rollback()
                raise ValidationError("A resource version is required for updates.")
            if model.version != expected_version:
                self._session.rollback()
                raise ConcurrencyConflictError(
                    "The session changed since it was loaded. Review the current version and retry.",
                    model.version,
                )
            if self._active_registration_count(session.id) > session.capacity:
                self._session.rollback()
                raise ValidationError(
                    "Capacity cannot be lower than active session registrations."
                )
        if self._has_schedule_overlap(session):
            self._session.rollback()
            raise ValidationError("Session schedule overlaps another session.")

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
            self._session.rollback()
            raise ValidationError("One or more speakers do not exist.")
        model.speakers = speakers
        self._session.add(model)
        try:
            self._session.commit()
        except StaleDataError as error:
            self._session.rollback()
            raise ConcurrencyConflictError(
                "The session changed while this update was being saved. Review the current version and retry.",
                self._current_version(session.id),
            ) from error
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The session violates a data integrity rule."
            ) from error
        except Exception:
            self._session.rollback()
            raise
        return self._to_record(model)

    def _has_schedule_overlap(self, session: SessionRecord) -> bool:
        """Check strict schedule overlap while the parent event row is locked."""
        statement = select(EventSession.id).where(
            EventSession.event_id == session.event_id,
            EventSession.starts_at < session.ends_at,
            EventSession.ends_at > session.starts_at,
        )
        if session.id is not None:
            statement = statement.where(EventSession.id != session.id)
        return self._session.scalar(statement.limit(1)) is not None

    def _current_version(self, session_id: int | None) -> int | None:
        """Read the latest committed session version after a write conflict."""
        if session_id is None:
            return None
        return self._session.scalar(
            select(EventSession.version).where(EventSession.id == session_id)
        )

    def delete(self, event_id: int, session_id: int) -> bool:
        """Lock parent and session rows before deleting the requested session."""
        event = self._session.scalar(
            select(Event)
            .where(Event.id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if event is None:
            self._session.rollback()
            return False
        model = self._session.scalar(
            select(EventSession)
            .where(
                EventSession.id == session_id,
                EventSession.event_id == event_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if model is None:
            self._session.rollback()
            return False
        self._session.delete(model)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError("The session could not be deleted safely.") from error
        except Exception:
            self._session.rollback()
            raise
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
            model.version,
        )

    def _active_registration_count(self, session_id: int) -> int:
        """Count active session enrollments linked to active event registrations."""
        return (
            self._session.scalar(
                select(func.count(SessionRegistration.id))
                .join(
                    Registration,
                    Registration.id == SessionRegistration.registration_id,
                )
                .where(
                    SessionRegistration.session_id == session_id,
                    SessionRegistration.status == "active",
                    Registration.status == "registered",
                )
            )
            or 0
        )

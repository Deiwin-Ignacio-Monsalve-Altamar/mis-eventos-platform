"""Persist event registration changes with child session enrollment consistency."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateRegistrationError,
    EventCapacityExceededError,
    EventUnavailableError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.event_record import EventRecord
from app.domain.entities.event_registration import (
    EventRegistrationDetails,
    EventRegistrationRecord,
)
from app.infrastructure.database.models import Event, Registration, SessionRegistration


class SQLAlchemyEventRegistrationRepository:
    """Adapt event registration use cases to atomic SQLAlchemy transactions."""

    def __init__(
        self, session: Session, clock: Callable[[], datetime] | None = None
    ) -> None:
        """Receive the request-scoped SQLAlchemy session."""
        self._session = session
        self._clock = clock or (lambda: datetime.now(UTC))

    def register(self, event_id: int, user_id: int) -> EventRegistrationRecord:
        """Create or reactivate an event registration without changing session seats."""
        event = self._lock_event(event_id)
        try:
            now = self._as_utc(self._clock(), "current time")
            event_starts_at = self._as_utc(event.starts_at, "event start time")
        except ValidationError:
            self._session.rollback()
            raise
        if event.status != "published" or event_starts_at <= now:
            self._session.rollback()
            raise EventUnavailableError("The event is not open for new registrations.")

        registration = self._lock_registration(event_id, user_id)
        if registration is not None and registration.status == "registered":
            self._session.rollback()
            raise DuplicateRegistrationError(
                "The user is already registered for this event."
            )

        active_count = self._active_registration_count(event_id)
        if active_count >= event.capacity:
            self._session.rollback()
            raise EventCapacityExceededError("The event has no available seats.")

        try:
            if registration is None:
                registration = Registration(
                    event_id=event_id,
                    user_id=user_id,
                    status="registered",
                )
                self._session.add(registration)
            else:
                registration.status = "registered"
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The event registration violates a data integrity rule."
            ) from error
        except Exception:
            self._session.rollback()
            raise
        return self._to_record(registration)

    def list_by_user(
        self, user_id: int, page: int, page_size: int
    ) -> tuple[list[EventRegistrationDetails], int]:
        """Read the caller's registrations with public event data and all statuses."""
        filters = (Registration.user_id == user_id,)
        total = (
            self._session.scalar(select(func.count(Registration.id)).where(*filters))
            or 0
        )
        rows = self._session.execute(
            select(Registration, Event)
            .join(Event, Event.id == Registration.event_id)
            .where(*filters)
            .order_by(Event.starts_at.asc(), Event.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [
            self._to_details(registration, event) for registration, event in rows
        ], total

    def cancel(self, event_id: int, user_id: int) -> bool:
        """Cancel a parent registration and active session enrollments atomically."""
        self._lock_event(event_id)
        registration = self._lock_registration(event_id, user_id)
        if registration is None:
            self._session.rollback()
            return False

        try:
            registration.status = "cancelled"
            self._cancel_active_session_enrollments(registration.id)
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The event registration could not be cancelled safely."
            ) from error
        except Exception:
            self._session.rollback()
            raise
        return True

    def _lock_event(self, event_id: int) -> Event:
        """Lock the event row so event registration capacity changes serialize."""
        event = self._session.scalar(
            select(Event)
            .where(Event.id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if event is None:
            self._session.rollback()
            raise NotFoundError("Event not found.")
        return event

    def _lock_registration(self, event_id: int, user_id: int) -> Registration | None:
        """Lock one event registration before status or child enrollment changes."""
        return self._session.scalar(
            select(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def _active_registration_count(self, event_id: int) -> int:
        """Count active registrations for this event, independent of session seats."""
        return (
            self._session.scalar(
                select(func.count(Registration.id)).where(
                    Registration.event_id == event_id,
                    Registration.status == "registered",
                )
            )
            or 0
        )

    def _cancel_active_session_enrollments(self, registration_id: int) -> None:
        """Set all linked active session registrations to cancelled in this transaction."""
        self._session.execute(
            update(SessionRegistration)
            .where(
                SessionRegistration.registration_id == registration_id,
                SessionRegistration.status == "active",
            )
            .values(status="cancelled", updated_at=func.now())
            .execution_options(synchronize_session=False)
        )

    @staticmethod
    def _to_record(registration: Registration) -> EventRegistrationRecord:
        """Map an ORM event registration to the application record."""
        return EventRegistrationRecord(
            id=registration.id,
            event_id=registration.event_id,
            user_id=registration.user_id,
            status=registration.status,
        )

    @staticmethod
    def _as_utc(value: datetime, field_name: str) -> datetime:
        """Normalize an aware timestamp to UTC and reject naive values."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValidationError(f"{field_name} must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _to_details(
        registration: Registration, event: Event
    ) -> EventRegistrationDetails:
        """Map one registration and its joined event to an application record."""
        return EventRegistrationDetails(
            id=registration.id,
            status=registration.status,
            registered_at=registration.registered_at,
            event=EventRecord(
                id=event.id,
                title=event.title,
                description=event.description,
                location=event.location,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                capacity=event.capacity,
                status=event.status,
                created_by_id=event.created_by_id,
                version=event.version,
            ),
        )

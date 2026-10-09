"""Persist event registration changes with child session enrollment consistency."""

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateRegistrationError,
    EventCapacityExceededError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.event_registration import EventRegistrationRecord
from app.infrastructure.database.models import Event, Registration, SessionRegistration


class SQLAlchemyEventRegistrationRepository:
    """Adapt event registration use cases to atomic SQLAlchemy transactions."""

    def __init__(self, session: Session) -> None:
        """Receive the request-scoped SQLAlchemy session."""
        self._session = session

    def register(self, event_id: int, user_id: int) -> EventRegistrationRecord:
        """Create or reactivate an event registration without changing session seats."""
        event = self._lock_event(event_id)
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

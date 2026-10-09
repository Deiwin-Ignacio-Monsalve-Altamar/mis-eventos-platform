"""Persist session attendee registrations with capacity-safe transactions."""

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    CapacityExceededError,
    DuplicateRegistrationError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.session_attendee import SessionAttendee, SessionOccupancy
from app.infrastructure.database.models import (
    Event,
    EventSession,
    Registration,
    SessionRegistration,
    User,
)


class SQLAlchemySessionAttendeeRepository:
    """Adapt attendee enrollment operations to SQLAlchemy models."""

    def __init__(self, session: Session) -> None:
        """Receive the active request-scoped SQLAlchemy session."""
        self._session = session

    def find_event_creator_id(self, event_id: int) -> int | None:
        """Return the event creator identifier, distinguishing missing events."""
        event = self._session.get(Event, event_id)
        if event is None:
            raise NotFoundError("Event not found.")
        return event.created_by_id

    def session_exists(self, event_id: int, session_id: int) -> bool:
        """Check session ownership within the requested event."""
        return (
            self._session.scalar(
                select(EventSession.id).where(
                    EventSession.id == session_id,
                    EventSession.event_id == event_id,
                )
            )
            is not None
        )

    def list_attendees(self, event_id: int, session_id: int) -> list[SessionAttendee]:
        """Return active session attendees whose event enrollment remains active."""
        rows = self._session.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.email,
                SessionRegistration.registered_at,
            )
            .join(Registration, Registration.user_id == User.id)
            .join(
                SessionRegistration,
                SessionRegistration.registration_id == Registration.id,
            )
            .where(
                Registration.event_id == event_id,
                Registration.status == "registered",
                SessionRegistration.session_id == session_id,
                SessionRegistration.status == "active",
            )
            .order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
        ).all()
        return [SessionAttendee(*row) for row in rows]

    def get_occupancy(self, event_id: int, session_id: int) -> SessionOccupancy:
        """Read capacity and qualifying occupancy from one database snapshot."""
        statement = (
            select(EventSession.capacity, func.count(Registration.id))
            .select_from(EventSession)
            .outerjoin(
                SessionRegistration,
                and_(
                    SessionRegistration.session_id == EventSession.id,
                    SessionRegistration.status == "active",
                ),
            )
            .outerjoin(
                Registration,
                and_(
                    Registration.id == SessionRegistration.registration_id,
                    Registration.event_id == event_id,
                    Registration.status == "registered",
                ),
            )
            .where(
                EventSession.id == session_id,
                EventSession.event_id == event_id,
            )
            .group_by(EventSession.capacity)
        )
        result = self._session.execute(statement).one_or_none()
        if result is None:
            raise NotFoundError("Session not found for this event.")
        capacity, occupied = result
        return SessionOccupancy(capacity, occupied, max(capacity - occupied, 0))

    def enroll(self, event_id: int, session_id: int, user_id: int) -> None:
        """Lock event, eligibility, and session rows before enrolling transactionally."""
        if self._lock_event(event_id) is None:
            self._session.rollback()
            raise NotFoundError("Event not found.")
        event_registration = self._lock_event_registration(event_id, user_id)
        if event_registration is None:
            self._session.rollback()
            raise ValidationError("An active event registration is required.")

        session_model = self._session.scalar(
            select(EventSession)
            .where(
                EventSession.id == session_id,
                EventSession.event_id == event_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if session_model is None:
            self._session.rollback()
            raise NotFoundError("Session not found for this event.")

        existing = self._session.scalar(
            select(SessionRegistration)
            .where(
                SessionRegistration.session_id == session_id,
                SessionRegistration.registration_id == event_registration.id,
            )
            .with_for_update(of=SessionRegistration)
            .execution_options(populate_existing=True)
        )
        if existing is not None and existing.status == "active":
            self._session.rollback()
            raise DuplicateRegistrationError(
                "The user is already registered for this session."
            )

        occupied = self._active_count(event_id, session_id)
        if occupied >= session_model.capacity:
            self._session.rollback()
            raise CapacityExceededError("The session has no available seats.")

        if existing is None:
            existing = SessionRegistration(
                session_id=session_id,
                registration_id=event_registration.id,
                status="active",
            )
        else:
            existing.status = "active"
        self._session.add(existing)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The session registration violates a data integrity rule."
            ) from error
        except Exception:
            self._session.rollback()
            raise

    def cancel(self, event_id: int, session_id: int, user_id: int) -> bool:
        """Lock eligible parent rows before cancelling the caller's enrollment."""
        if self._lock_event(event_id) is None:
            self._session.rollback()
            return False
        event_registration = self._lock_event_registration(event_id, user_id)
        if event_registration is None:
            self._session.rollback()
            return False
        session_exists = self._session.scalar(
            select(EventSession.id)
            .where(
                EventSession.id == session_id,
                EventSession.event_id == event_id,
            )
            .with_for_update()
        )
        if session_exists is None:
            self._session.rollback()
            return False
        registration = self._session.scalar(
            select(SessionRegistration)
            .where(
                SessionRegistration.session_id == session_id,
                SessionRegistration.registration_id == event_registration.id,
                SessionRegistration.status == "active",
            )
            .with_for_update(of=SessionRegistration)
            .execution_options(populate_existing=True)
        )
        if registration is None:
            self._session.rollback()
            return False
        registration.status = "cancelled"
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The session registration could not be cancelled."
            ) from error
        except Exception:
            self._session.rollback()
            raise
        return True

    def _lock_event(self, event_id: int) -> Event | None:
        """Serialize session enrollment changes with event capacity mutations."""
        return self._session.scalar(
            select(Event)
            .where(Event.id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def _lock_event_registration(
        self, event_id: int, user_id: int
    ) -> Registration | None:
        """Lock the caller's active event registration before session rows."""
        return self._session.scalar(
            select(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.user_id == user_id,
                Registration.status == "registered",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def _active_count(self, event_id: int, session_id: int) -> int:
        """Count active session enrollments with a still-active event registration."""
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
                    Registration.event_id == event_id,
                    Registration.status == "registered",
                )
            )
            or 0
        )

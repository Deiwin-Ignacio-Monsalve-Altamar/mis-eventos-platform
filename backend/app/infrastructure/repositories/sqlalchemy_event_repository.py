"""Persist domain events through the application's SQLAlchemy session."""

from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import (
    AuthorizationError,
    ConcurrencyConflictError,
    NotFoundError,
    RelatedRecordsError,
    ValidationError,
)
from app.domain.entities.event_record import EventRecord
from app.infrastructure.database.models import Event, EventSession, Registration


class SQLAlchemyEventRepository:
    """Adapt event records to and from the SQLAlchemy event model."""

    def __init__(self, session: Session) -> None:
        """Receive the active SQLAlchemy session used for event persistence."""
        self._session = session

    def find_by_id(self, event_id: int) -> EventRecord | None:
        """Load an event by its database identifier."""
        event = self._session.get(Event, event_id)
        return self._to_record(event) if event is not None else None

    def list_events(
        self, page: int, page_size: int, search_query: str | None
    ) -> tuple[list[EventRecord], int]:
        """Load a stable event page and its total using bound SQLAlchemy filters."""
        filters = []
        if search_query is not None:
            filters.append(
                or_(
                    Event.title.icontains(search_query, autoescape=True),
                    Event.description.icontains(search_query, autoescape=True),
                    Event.location.icontains(search_query, autoescape=True),
                )
            )

        total_statement = select(func.count(Event.id)).where(*filters)
        total = self._session.scalar(total_statement) or 0
        events_statement = (
            select(Event)
            .where(*filters)
            .order_by(Event.starts_at.asc(), Event.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        models = self._session.execute(events_statement).scalars().all()
        return [self._to_record(model) for model in models], total

    def list_by_creator(
        self,
        creator_id: int,
        page: int,
        page_size: int,
        search_query: str | None,
        status: str | None,
    ) -> tuple[list[EventRecord], int]:
        """Read an owner-filtered event page with optional search and status filters."""
        filters = [Event.created_by_id == creator_id]
        if search_query is not None:
            filters.append(
                or_(
                    Event.title.icontains(search_query, autoescape=True),
                    Event.description.icontains(search_query, autoescape=True),
                    Event.location.icontains(search_query, autoescape=True),
                )
            )
        if status is not None:
            filters.append(Event.status == status)
        total = self._session.scalar(select(func.count(Event.id)).where(*filters)) or 0
        statement = (
            select(Event)
            .where(*filters)
            .order_by(Event.starts_at.asc(), Event.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        models = self._session.execute(statement).scalars().all()
        return [self._to_record(model) for model in models], total

    def find_by_id_for_creator(
        self, event_id: int, creator_id: int
    ) -> EventRecord | None:
        """Load one event only when its persisted owner matches the caller."""
        model = self._session.scalar(
            select(Event).where(Event.id == event_id, Event.created_by_id == creator_id)
        )
        return self._to_record(model) if model is not None else None

    def dashboard_counts(self, creator_id: int, now: datetime) -> dict[str, int]:
        """Aggregate owner-specific lifecycle metrics in one database query."""
        active_status = Event.status.in_(("draft", "published"))
        statement = select(
            func.count(Event.id).label("total"),
            func.sum(case((Event.status == "draft", 1), else_=0)).label("draft"),
            func.sum(case((Event.status == "published", 1), else_=0)).label(
                "published"
            ),
            func.sum(case((Event.status == "cancelled", 1), else_=0)).label(
                "cancelled"
            ),
            func.sum(case((Event.status == "completed", 1), else_=0)).label(
                "completed"
            ),
            func.sum(case((active_status & (Event.starts_at > now), 1), else_=0)).label(
                "upcoming"
            ),
            func.sum(
                case(
                    (
                        active_status
                        & (Event.starts_at <= now)
                        & (Event.ends_at > now),
                        1,
                    ),
                    else_=0,
                )
            ).label("active"),
            func.sum(
                case(
                    (
                        (Event.status == "completed")
                        | ((Event.ends_at <= now) & (Event.status != "cancelled")),
                        1,
                    ),
                    else_=0,
                )
            ).label("finished"),
        ).where(Event.created_by_id == creator_id)
        row = self._session.execute(statement).one()
        return {key: int(value or 0) for key, value in row._mapping.items()}

    def event_activity_by_creator(
        self, creator_id: int, now: datetime, limit: int
    ) -> list[dict[str, object]]:
        """Aggregate event enrollment and session counts within the owner's scope."""
        active_registrations = (
            select(func.count(Registration.id))
            .where(
                Registration.event_id == Event.id,
                Registration.status == "registered",
            )
            .scalar_subquery()
        )
        session_count = (
            select(func.count(EventSession.id))
            .where(EventSession.event_id == Event.id)
            .scalar_subquery()
        )
        rows = self._session.execute(
            select(Event, active_registrations, session_count)
            .where(Event.created_by_id == creator_id)
            .order_by(
                case((Event.starts_at > now, 0), else_=1),
                Event.starts_at.asc(),
                Event.id.asc(),
            )
            .limit(limit)
        )
        return [
            {
                "event": self._to_record(event),
                "active_registrations": int(registration_count),
                "session_count": int(sessions),
                "available_seats": max(event.capacity - int(registration_count), 0),
            }
            for event, registration_count, sessions in rows
        ]

    def active_registration_count_by_creator(self, creator_id: int) -> int:
        """Count active event registrations for the owner's complete event set."""
        return int(
            self._session.scalar(
                select(func.count(Registration.id))
                .join(Event, Registration.event_id == Event.id)
                .where(
                    Event.created_by_id == creator_id,
                    Registration.status == "registered",
                )
            )
            or 0
        )

    def recommendations_for_user(
        self, user_id: int, now: datetime, limit: int
    ) -> list[tuple[EventRecord, int]]:
        """Select available published events and exclude existing active enrollments."""
        registration_count = (
            select(func.count(Registration.id))
            .where(
                Registration.event_id == Event.id,
                Registration.status == "registered",
            )
            .scalar_subquery()
        )
        already_registered = (
            select(Registration.id)
            .where(
                Registration.event_id == Event.id,
                Registration.user_id == user_id,
                Registration.status == "registered",
            )
            .exists()
        )
        rows = self._session.execute(
            select(
                Event, (Event.capacity - registration_count).label("available_seats")
            )
            .where(
                Event.status == "published",
                Event.starts_at > now,
                Event.capacity > registration_count,
                ~already_registered,
            )
            .order_by(Event.starts_at.asc(), Event.id.asc())
            .limit(limit)
        )
        return [
            (self._to_record(event), int(available_seats))
            for event, available_seats in rows
        ]

    def save(
        self,
        event: EventRecord,
        expected_version: int | None = None,
        owner_id: int | None = None,
        is_admin: bool = False,
    ) -> EventRecord:
        """Insert or update an event and commit the transaction."""
        model = (
            self._session.scalar(
                select(Event)
                .where(Event.id == event.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if event.id is not None
            else Event()
        )
        if model is None:
            raise NotFoundError("Event no longer exists.")
        if event.id is not None:
            if owner_id is None:
                self._session.rollback()
                raise AuthorizationError("An authenticated event owner is required.")
            if model.created_by_id != owner_id and not is_admin:
                self._session.rollback()
                raise AuthorizationError("Only the event creator can edit this event.")
            if expected_version is None:
                raise ValidationError("A resource version is required for updates.")
            if model.version != expected_version:
                self._session.rollback()
                raise ConcurrencyConflictError(
                    "The event changed since it was loaded. Review the current version and retry.",
                    model.version,
                )
            if self._active_registration_count(event.id) > event.capacity:
                self._session.rollback()
                raise ValidationError(
                    "Capacity cannot be lower than active event registrations."
                )
            if self._has_sessions_outside_schedule(event):
                self._session.rollback()
                raise ValidationError(
                    "The event schedule cannot exclude an existing session."
                )

        model.title = event.title
        model.description = event.description
        model.location = event.location
        model.starts_at = event.starts_at
        model.ends_at = event.ends_at
        model.capacity = event.capacity
        model.status = event.status
        model.created_by_id = event.created_by_id
        self._session.add(model)
        try:
            self._session.commit()
        except StaleDataError as error:
            self._session.rollback()
            raise ConcurrencyConflictError(
                "The event changed while this update was being saved. Review the current version and retry.",
                self._current_version(event.id),
            ) from error
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The event violates a data integrity rule."
            ) from error
        except Exception:
            self._session.rollback()
            raise
        return self._to_record(model)

    def _current_version(self, event_id: int) -> int | None:
        """Read the latest committed version after an optimistic update conflict."""
        return self._session.scalar(select(Event.version).where(Event.id == event_id))

    def _active_registration_count(self, event_id: int) -> int:
        """Count registered attendees before allowing an event capacity reduction."""
        return (
            self._session.scalar(
                select(func.count(Registration.id)).where(
                    Registration.event_id == event_id,
                    Registration.status == "registered",
                )
            )
            or 0
        )

    def _has_sessions_outside_schedule(self, event: EventRecord) -> bool:
        """Check existing session bounds while the parent event row is locked."""
        return (
            self._session.scalar(
                select(EventSession.id)
                .where(
                    EventSession.event_id == event.id,
                    or_(
                        EventSession.starts_at < event.starts_at,
                        EventSession.ends_at > event.ends_at,
                    ),
                )
                .limit(1)
            )
            is not None
        )

    def delete(self, event_id: int, owner_id: int, is_admin: bool = False) -> bool:
        """Delete an authorized event only when no dependent records remain."""
        model = self._session.scalar(
            select(Event)
            .where(Event.id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if model is None:
            return False
        if model.created_by_id != owner_id and not is_admin:
            self._session.rollback()
            raise AuthorizationError("Only the event creator can delete this event.")
        if model.registrations or model.sessions or model.speakers:
            self._session.rollback()
            raise RelatedRecordsError(
                "Events with registrations, sessions, or speakers cannot be deleted."
            )

        self._session.delete(model)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise RelatedRecordsError(
                "The event has related records and cannot be deleted."
            ) from error
        except Exception:
            self._session.rollback()
            raise
        return True

    @staticmethod
    def _to_record(model: Event) -> EventRecord:
        """Map an ORM event to its application-facing domain representation."""
        return EventRecord(
            id=model.id,
            title=model.title,
            description=model.description,
            location=model.location,
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            capacity=model.capacity,
            status=model.status,
            created_by_id=model.created_by_id,
            version=model.version,
        )

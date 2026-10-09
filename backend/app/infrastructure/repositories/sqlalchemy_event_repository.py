"""Persist domain events through the application's SQLAlchemy session."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.event_record import EventRecord
from app.infrastructure.database.models import Event


class SQLAlchemyEventRepository:
    """Adapt event records to and from the SQLAlchemy event model."""

    def __init__(self, session: Session) -> None:
        """Receive the active SQLAlchemy session used for event persistence."""
        self._session = session

    def find_by_id(self, event_id: int) -> EventRecord | None:
        """Load an event by its database identifier."""
        event = self._session.get(Event, event_id)
        return self._to_record(event) if event is not None else None

    def save(self, event: EventRecord) -> EventRecord:
        """Insert or update an event and commit the transaction."""
        model = self._session.get(Event, event.id) if event.id is not None else Event()
        if model is None:
            raise NotFoundError("Event no longer exists.")

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
        except IntegrityError as error:
            self._session.rollback()
            raise ValidationError(
                "The event violates a data integrity rule."
            ) from error
        return self._to_record(model)

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
        )

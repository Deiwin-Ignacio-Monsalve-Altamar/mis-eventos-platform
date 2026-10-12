"""Persist event image records through SQLAlchemy."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.entities.event_image import EventImageRecord
from app.domain.repositories.event_image_repository import EventImageRepository
from app.infrastructure.database.models import EventImage


class SQLAlchemyEventImageRepository(EventImageRepository):
    """Adapt event image records to the SQLAlchemy persistence model."""

    def __init__(self, session: Session) -> None:
        """Receive the active SQLAlchemy session."""
        self._session = session

    def create(self, image: EventImageRecord) -> EventImageRecord:
        """Persist image metadata and return its generated ID and timestamp."""
        model = EventImage(
            event_id=image.event_id,
            storage_key=image.storage_key,
            url=image.url,
            position=image.position,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_record(model)

    def list_by_event(self, event_id: int) -> list[EventImageRecord]:
        """Load one event's images in stable gallery order."""
        models = self._session.scalars(
            select(EventImage)
            .where(EventImage.event_id == event_id)
            .order_by(EventImage.position.asc(), EventImage.id.asc())
        ).all()
        return [self._to_record(model) for model in models]

    def replace_for_event(
        self, event_id: int, images: list[EventImageRecord]
    ) -> list[EventImageRecord]:
        """Replace all event image rows in one transaction."""
        previous = self.list_by_event(event_id)
        try:
            self._session.execute(
                delete(EventImage).where(EventImage.event_id == event_id)
            )
            models = [
                EventImage(
                    event_id=event_id,
                    storage_key=image.storage_key,
                    url=image.url,
                    position=image.position,
                )
                for image in images
            ]
            self._session.add_all(models)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return previous

    @staticmethod
    def _to_record(model: EventImage) -> EventImageRecord:
        """Map the persistence row to the framework-independent domain record."""
        return EventImageRecord(
            id=model.id,
            event_id=model.event_id,
            storage_key=model.storage_key,
            url=model.url,
            position=model.position,
            created_at=model.created_at,
        )

"""Persist object-storage metadata for event gallery images."""

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, func

from app.extensions import db


class EventImage(db.Model):
    """Store an event image's object key and stable gallery position."""

    __tablename__ = "event_images"
    __table_args__ = (
        CheckConstraint(
            "length(trim(storage_key)) > 0",
            name="ck_event_images_storage_key_not_empty",
        ),
        CheckConstraint("length(trim(url)) > 0", name="ck_event_images_url_not_empty"),
        CheckConstraint("position >= 0", name="ck_event_images_position_nonnegative"),
        UniqueConstraint("event_id", "position", name="uq_event_images_event_position"),
        UniqueConstraint("storage_key", name="uq_event_images_storage_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_key = db.Column(db.String(1024), nullable=False)
    url = db.Column(db.String(2048), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    event = db.relationship("Event", back_populates="images")

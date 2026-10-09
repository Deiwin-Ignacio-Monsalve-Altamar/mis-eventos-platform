"""Define event persistence, including its lifecycle and capacity constraints."""

from sqlalchemy import CheckConstraint, func, text

from app.extensions import db
from app.infrastructure.database.models.associations import event_speakers


class Event(db.Model):
    """Persist an event and its sessions and attendee registrations."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_events_title_not_empty"),
        CheckConstraint("ends_at > starts_at", name="ck_events_end_after_start"),
        CheckConstraint("capacity > 0", name="ck_events_capacity_positive"),
        CheckConstraint(
            "status IN ('draft', 'published', 'cancelled', 'completed')",
            name="ck_events_status_valid",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.String(20), nullable=False, server_default=text("'draft'"), index=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sessions = db.relationship(
        "EventSession", back_populates="event", cascade="all, delete-orphan"
    )
    registrations = db.relationship(
        "Registration", back_populates="event", cascade="all, delete-orphan"
    )
    speakers = db.relationship(
        "Speaker", secondary=event_speakers, back_populates="events"
    )
    creator = db.relationship("User", back_populates="created_events")

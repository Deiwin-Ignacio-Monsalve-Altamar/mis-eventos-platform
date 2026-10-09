"""Define speaker persistence and its scheduled session relationships."""

from sqlalchemy import CheckConstraint, func

from app.extensions import db
from app.infrastructure.database.models.associations import (
    event_speakers,
    session_speakers,
)


class Speaker(db.Model):
    """Persist a speaker profile that can be assigned to multiple sessions."""

    __tablename__ = "speakers"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_speakers_name_not_empty"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    biography = db.Column(db.Text, nullable=True)
    organization = db.Column(db.String(200), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sessions = db.relationship(
        "EventSession", secondary=session_speakers, back_populates="speakers"
    )
    events = db.relationship(
        "Event", secondary=event_speakers, back_populates="speakers"
    )

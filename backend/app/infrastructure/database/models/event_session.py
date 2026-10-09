"""Define event session persistence and the session-to-speaker association."""

from sqlalchemy import CheckConstraint, func, text

from app.extensions import db
from app.infrastructure.database.models.associations import session_speakers


class EventSession(db.Model):
    """Persist a scheduled session belonging to one event."""

    __tablename__ = "event_sessions"
    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) > 0", name="ck_event_sessions_title_not_empty"
        ),
        CheckConstraint(
            "ends_at > starts_at", name="ck_event_sessions_end_after_start"
        ),
        CheckConstraint("capacity > 0", name="ck_event_sessions_capacity_positive"),
        CheckConstraint("version > 0", name="ck_event_sessions_version_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer,
        db.ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    version = db.Column(db.Integer, nullable=False, default=1, server_default=text("1"))

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012

    event = db.relationship("Event", back_populates="sessions")
    speakers = db.relationship(
        "Speaker", secondary=session_speakers, back_populates="sessions"
    )
    registrations = db.relationship(
        "SessionRegistration", back_populates="session", cascade="all, delete-orphan"
    )

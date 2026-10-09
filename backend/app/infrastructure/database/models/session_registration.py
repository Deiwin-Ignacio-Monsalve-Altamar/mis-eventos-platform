"""Persist attendee enrollment in a session through an event registration."""

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, func, text

from app.extensions import db


class SessionRegistration(db.Model):
    """Associate an existing event registration with one scheduled session."""

    __tablename__ = "session_registrations"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "registration_id",
            name="uq_session_registrations_session_registration",
        ),
        CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="ck_session_registrations_status_valid",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    registration_id = db.Column(
        db.Integer,
        ForeignKey("registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        db.String(20), nullable=False, server_default=text("'active'"), index=True
    )
    registered_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    session = db.relationship("EventSession", back_populates="registrations")
    event_registration = db.relationship(
        "Registration", back_populates="session_registrations"
    )

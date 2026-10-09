"""Define attendee registrations and prevent duplicate event enrollment."""

from sqlalchemy import CheckConstraint, UniqueConstraint, func, text

from app.extensions import db


class Registration(db.Model):
    """Persist one attendee's registration for one event."""

    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_registrations_user_event"),
        CheckConstraint(
            "status IN ('registered', 'cancelled')",
            name="ck_registrations_status_valid",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = db.Column(
        db.Integer,
        db.ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        db.String(20), nullable=False, server_default=text("'registered'"), index=True
    )
    registered_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = db.relationship("User", back_populates="registrations")
    event = db.relationship("Event", back_populates="registrations")
    session_registrations = db.relationship(
        "SessionRegistration",
        back_populates="event_registration",
        cascade="all, delete-orphan",
    )

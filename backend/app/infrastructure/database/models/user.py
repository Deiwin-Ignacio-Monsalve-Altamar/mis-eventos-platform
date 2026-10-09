"""Define the user persistence model for attendee accounts."""

from sqlalchemy import CheckConstraint, func

from app.extensions import db


class User(db.Model):
    """Persist account identity and a password hash without storing credentials in plain text."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "length(trim(first_name)) > 0", name="ck_users_first_name_not_empty"
        ),
        CheckConstraint(
            "length(trim(last_name)) > 0", name="ck_users_last_name_not_empty"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    registrations = db.relationship(
        "Registration", back_populates="user", cascade="all, delete-orphan"
    )
    created_events = db.relationship("Event", back_populates="creator")

"""Explicit registry for SQLAlchemy model modules used by Alembic."""

from app.infrastructure.database.models.associations import (
    event_speakers,
    session_speakers,
)
from app.infrastructure.database.models.event import Event
from app.infrastructure.database.models.event_session import EventSession
from app.infrastructure.database.models.registration import Registration
from app.infrastructure.database.models.speaker import Speaker
from app.infrastructure.database.models.user import User

__all__ = [
    "Event",
    "EventSession",
    "Registration",
    "Speaker",
    "User",
    "event_speakers",
    "session_speakers",
]

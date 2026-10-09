"""Define association tables connecting speakers to events and sessions."""

from sqlalchemy import Column, ForeignKey, Integer, Table

from app.extensions import db

event_speakers = Table(
    "event_speakers",
    db.metadata,
    Column(
        "event_id",
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "speaker_id",
        Integer,
        ForeignKey("speakers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

session_speakers = Table(
    "session_speakers",
    db.metadata,
    Column(
        "session_id",
        Integer,
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "speaker_id",
        Integer,
        ForeignKey("speakers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

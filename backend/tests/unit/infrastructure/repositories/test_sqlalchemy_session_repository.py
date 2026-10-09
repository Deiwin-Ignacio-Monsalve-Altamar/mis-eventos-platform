"""Verify SQLAlchemy session repository queries using mocked session objects."""

from unittest.mock import Mock

import pytest

from app.core.exceptions import NotFoundError
from app.domain.entities.session_record import SessionRecord
from app.infrastructure.repositories.sqlalchemy_session_repository import (
    SQLAlchemySessionRepository,
)


def test_find_overlap_uses_bounded_query_and_excludes_current_record():
    """Build one limited overlap query with event scope and self exclusion."""
    session = Mock()
    session.scalar.return_value = None
    repository = SQLAlchemySessionRepository(session)
    repository.find_overlapping(3, "start", "end", 8)
    statement = session.scalar.call_args.args[0]
    sql = str(statement)
    assert "event_sessions.event_id" in sql
    assert "event_sessions.starts_at <" in sql
    assert "event_sessions.ends_at >" in sql
    assert "event_sessions.id !=" in sql
    assert "LIMIT" in sql.upper()
    assert session.execute.call_count == 0


def test_save_updates_session_when_it_belongs_to_requested_event():
    """Save changes when the persisted session belongs to the requested event."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    model.speakers = []
    session = Mock()
    session.get.return_value = model
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Updated title", None, "start", "end", 25)

    saved = repository.save(record)

    assert saved.id == 14
    assert model.title == "Updated title"
    session.add.assert_called_once_with(model)
    session.commit.assert_called_once()


def test_save_rejects_session_owned_by_another_event_without_commit():
    """Leave an existing session untouched when its event does not match."""
    model = Mock()
    model.id = 14
    model.event_id = 8
    model.title = "Original title"
    session = Mock()
    session.get.return_value = model
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Changed title", None, "start", "end", 25)

    with pytest.raises(NotFoundError, match="does not belong to this event"):
        repository.save(record)

    assert model.title == "Original title"
    session.add.assert_not_called()
    session.commit.assert_not_called()

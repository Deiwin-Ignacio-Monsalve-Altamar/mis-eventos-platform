"""Verify SQLAlchemy session repository queries using mocked session objects."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import (
    ConcurrencyConflictError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.session_record import SessionRecord
from app.infrastructure.repositories.sqlalchemy_session_repository import (
    SQLAlchemySessionRepository,
)


def event_model():
    """Build a minimal mocked parent event for repository save operations."""
    return Mock(id=3, starts_at="start", ends_at="end")


def test_save_rejects_concurrent_overlapping_create_under_event_lock():
    """Run the authoritative overlap query after serializing writes on the event."""
    session = Mock()
    session.scalar.side_effect = [event_model(), None, event_model(), 99]
    session.commit.side_effect = lambda: setattr(
        session.add.call_args.args[0], "id", 40
    )
    repository = SQLAlchemySessionRepository(session)
    first = SessionRecord(None, 3, "First", None, "start", "end", 25)
    second = SessionRecord(None, 3, "Overlapping", None, "start", "end", 25)

    repository.save(first)
    with pytest.raises(ValidationError, match="overlaps another session"):
        repository.save(second)

    assert session.commit.call_count == 1
    assert session.rollback.call_count == 1
    statements = [call.args[0] for call in session.scalar.call_args_list]
    assert all(
        "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))
        for statement in (statements[0], statements[2])
    )
    overlap_sql = str(statements[3])
    assert "event_sessions.starts_at <" in overlap_sql
    assert "event_sessions.ends_at >" in overlap_sql


def test_save_rechecks_event_schedule_after_locking_parent():
    """Reject session bounds that became invalid before the parent lock was acquired."""
    event = SimpleNamespace(
        id=3,
        starts_at=datetime(2030, 1, 1, 9, tzinfo=UTC),
        ends_at=datetime(2030, 1, 1, 18, tzinfo=UTC),
    )
    session = Mock()
    session.scalar.return_value = event
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(
        None,
        3,
        "Too early",
        None,
        datetime(2030, 1, 1, 8, tzinfo=UTC),
        datetime(2030, 1, 1, 9, tzinfo=UTC),
        25,
    )

    with pytest.raises(ValidationError, match="within the event schedule"):
        repository.save(record)

    session.scalar.assert_called_once()
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


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
    model.version = 1
    model.speakers = []
    session = Mock()
    session.scalar.side_effect = [event_model(), model, 0, None]
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Updated title", None, "start", "end", 25)

    saved = repository.save(record, expected_version=1)

    assert saved.id == 14
    assert model.title == "Updated title"
    lock_statement = session.scalar.call_args_list[0].args[0]
    assert "FOR UPDATE" in str(lock_statement.compile(dialect=postgresql.dialect()))
    session.add.assert_called_once_with(model)
    session.commit.assert_called_once()


def test_save_replaces_speaker_links_without_persisting_speaker_profiles():
    """Replace only the association links for existing speaker profiles."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    model.version = 1
    model.speakers = []
    speaker = Mock(id=4)
    session = Mock()
    session.scalar.side_effect = [event_model(), model, 0, None]
    session.scalars.return_value.all.return_value = [speaker]
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Updated title", None, "start", "end", 25, (4,))

    saved = repository.save(record, expected_version=1)

    assert model.speakers == [speaker]
    assert saved.speaker_ids == (4,)
    session.add.assert_called_once_with(model)
    assert session.scalars.call_count == 1
    session.commit.assert_called_once()


def test_save_rejects_session_owned_by_another_event_without_commit():
    """Leave an existing session untouched when its event does not match."""
    model = Mock()
    model.id = 14
    model.event_id = 8
    model.version = 1
    model.title = "Original title"
    session = Mock()
    session.scalar.side_effect = [event_model(), model]
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Changed title", None, "start", "end", 25)

    with pytest.raises(NotFoundError, match="does not belong to this event"):
        repository.save(record, expected_version=1)

    assert model.title == "Original title"
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_save_rejects_capacity_below_active_session_enrollments():
    """Keep a session's configured capacity at or above current occupancy."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    model.version = 1
    session = Mock()
    session.scalar.side_effect = [event_model(), model, 5]
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Updated title", None, "start", "end", 4)

    with pytest.raises(ValidationError, match="lower than active session"):
        repository.save(record, expected_version=1)

    lock_statements = [
        call.args[0].compile(dialect=postgresql.dialect())
        for call in session.scalar.call_args_list[:2]
    ]
    assert "FROM events" in str(lock_statements[0])
    assert "FOR UPDATE" in str(lock_statements[0])
    assert "FROM event_sessions" in str(lock_statements[1])
    assert "FOR UPDATE" in str(lock_statements[1])
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_save_rejects_overlapping_update_without_committing():
    """Reject a conflicting schedule change inside the event transaction."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    model.version = 1
    session = Mock()
    session.scalar.side_effect = [event_model(), model, 0, 21]
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Updated title", None, "start", "end", 25)

    with pytest.raises(ValidationError, match="overlaps another session"):
        repository.save(record, expected_version=1)

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_save_rejects_stale_expected_version_before_mutating():
    """Reject stale edits and report the persisted version without writing."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    model.version = 3
    model.title = "Current title"
    session = Mock()
    session.scalar.side_effect = [event_model(), model]
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Stale title", None, "start", "end", 25)

    with pytest.raises(ConcurrencyConflictError) as error:
        repository.save(record, expected_version=2)

    assert error.value.current_version == 3
    assert model.title == "Current title"
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_same_initial_session_version_allows_only_first_update():
    """Reject the second update after the first request advances the version."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    model.version = 1
    model.speakers = []
    session = Mock()
    session.scalar.side_effect = [event_model(), model, 0, None, event_model(), model]

    def commit_first_update():
        """Model the version increment performed by SQLAlchemy after its flush."""
        model.version = 2

    session.commit.side_effect = commit_first_update
    repository = SQLAlchemySessionRepository(session)
    first = SessionRecord(14, 3, "First update", None, "start", "end", 25)
    second = SessionRecord(14, 3, "Second update", None, "start", "end", 25)

    saved = repository.save(first, expected_version=1)
    with pytest.raises(ConcurrencyConflictError):
        repository.save(second, expected_version=1)

    assert saved.version == 2
    assert session.commit.call_count == 1


def test_save_rolls_back_when_an_update_loses_a_version_race():
    """Roll back all session and speaker changes after a stale ORM flush."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    model.version = 2
    model.speakers = []
    session = Mock()
    session.scalar.side_effect = [event_model(), model, 0, None, 3]
    session.commit.side_effect = StaleDataError("stale session version")
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(14, 3, "Attempted title", None, "start", "end", 25)

    with pytest.raises(ConcurrencyConflictError) as error:
        repository.save(record, expected_version=2)

    assert error.value.current_version == 3
    session.rollback.assert_called_once()
    session.commit.assert_called_once()


def test_delete_locks_event_before_session_and_commits_only_owned_session():
    """Serialize session deletion with enrollment and session capacity writes."""
    model = Mock()
    model.id = 14
    model.event_id = 3
    session = Mock()
    session.scalar.side_effect = [event_model(), model]
    repository = SQLAlchemySessionRepository(session)

    assert repository.delete(3, 14) is True

    statements = [
        call.args[0].compile(dialect=postgresql.dialect())
        for call in session.scalar.call_args_list
    ]
    assert "FROM events" in str(statements[0])
    assert "FOR UPDATE" in str(statements[0])
    assert "FROM event_sessions" in str(statements[1])
    assert "event_sessions.event_id" in str(statements[1])
    assert "FOR UPDATE" in str(statements[1])
    session.delete.assert_called_once_with(model)
    session.commit.assert_called_once()


def test_delete_rolls_back_if_session_does_not_belong_to_event():
    """Avoid deleting a session when its event-scoped lookup finds no row."""
    session = Mock()
    session.scalar.side_effect = [event_model(), None]
    repository = SQLAlchemySessionRepository(session)

    assert repository.delete(3, 99) is False

    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_create_session_persists_without_speakers_when_schedule_is_valid():
    """Save a new session without speaker links inside its locked event schedule."""
    session = Mock()
    session.scalar.side_effect = [event_model(), None]
    session.commit.side_effect = lambda: setattr(
        session.add.call_args.args[0], "id", 40
    )
    repository = SQLAlchemySessionRepository(session)
    record = SessionRecord(None, 3, "New session", None, "start", "end", 25)

    saved = repository.save(record)

    assert saved.id == 40
    assert saved.title == "New session"
    assert saved.speaker_ids == ()
    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


@pytest.mark.parametrize(
    "event_row, session_row, expected_version, message",
    [
        (None, None, None, "Event not found"),
        (event_model(), None, None, "no longer exists"),
        (
            event_model(),
            Mock(id=14, event_id=3, version=1),
            None,
            "version is required",
        ),
    ],
)
def test_save_rejects_missing_event_session_or_update_version(
    event_row, session_row, expected_version, message
):
    """Roll back updates when their event, row, or required version is missing."""
    persistence_session = Mock()
    persistence_session.scalar.side_effect = [event_row, session_row]
    repository = SQLAlchemySessionRepository(persistence_session)
    record = SessionRecord(14, 3, "Changed", None, "start", "end", 25)

    with pytest.raises((NotFoundError, ValidationError), match=message):
        repository.save(record, expected_version=expected_version)

    persistence_session.add.assert_not_called()
    persistence_session.commit.assert_not_called()
    persistence_session.rollback.assert_called_once()


def test_delete_returns_false_for_missing_parent_and_rolls_back():
    """Avoid issuing a child delete when the parent event cannot be locked."""
    session = Mock()
    session.scalar.return_value = None
    repository = SQLAlchemySessionRepository(session)

    assert repository.delete(404, 12) is False

    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()

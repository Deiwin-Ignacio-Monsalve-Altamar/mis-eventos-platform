"""Verify event repository query construction with a mocked SQLAlchemy session."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import (
    ConcurrencyConflictError,
    RelatedRecordsError,
    ValidationError,
)
from app.domain.entities.event_record import EventRecord
from app.infrastructure.database.models import Event
from app.infrastructure.repositories.sqlalchemy_event_repository import (
    SQLAlchemyEventRepository,
)


def test_list_events_builds_escaped_search_and_pagination_statements():
    """Build bound search filters, stable ordering, offset, limit, and count."""
    session = Mock(spec=Session)
    session.scalar.return_value = 4
    session.execute.return_value.scalars.return_value.all.return_value = []
    repository = SQLAlchemyEventRepository(session)

    events, total = repository.list_events(3, 10, "100%_/")

    assert events == []
    assert total == 4
    count_statement = session.scalar.call_args.args[0]
    page_statement = session.execute.call_args.args[0]
    compiled = page_statement.compile()
    compiled_count = count_statement.compile()
    page_sql = str(compiled)
    count_sql = str(compiled_count)

    assert count_statement.whereclause is not None
    assert page_statement.whereclause is not None
    for column_name in ("events.title", "events.description", "events.location"):
        assert column_name in page_sql
        assert column_name in count_sql
    assert "ESCAPE '/'" in page_sql
    assert "100/%/_//" in compiled.params.values()
    assert "100%_/" not in page_sql
    assert "ORDER BY events.starts_at ASC, events.id ASC" in page_sql
    assert [clause.element for clause in page_statement._order_by_clauses] == [
        Event.starts_at,
        Event.id,
    ]
    assert page_statement._offset_clause.value == 20
    assert page_statement._limit_clause.value == 10


def test_list_events_without_search_uses_unfiltered_count_and_maps_results():
    """Return mapped records and use no search filter when query is omitted."""
    model = SimpleNamespace(
        id=5,
        title="Mocked event",
        description=None,
        location=None,
        starts_at=datetime(2030, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2030, 1, 1, 11, tzinfo=UTC),
        capacity=25,
        status="draft",
        created_by_id=8,
        version=1,
    )
    session = Mock(spec=Session)
    session.scalar.return_value = 1
    session.execute.return_value.scalars.return_value.all.return_value = [model]
    repository = SQLAlchemyEventRepository(session)

    events, total = repository.list_events(1, 20, None)

    assert events == [
        EventRecord(
            id=5,
            title="Mocked event",
            description=None,
            location=None,
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            capacity=25,
            status="draft",
            created_by_id=8,
        )
    ]
    assert total == 1
    assert session.scalar.call_args.args[0].whereclause is None
    assert session.execute.call_args.args[0].whereclause is None


def test_update_rolls_back_and_reports_latest_version_on_orm_conflict():
    """Roll back a stale ORM write and expose the latest version to the caller."""
    model = SimpleNamespace(
        id=5,
        title="Before update",
        description=None,
        location=None,
        starts_at=datetime(2030, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2030, 1, 1, 11, tzinfo=UTC),
        capacity=25,
        status="draft",
        created_by_id=8,
        version=2,
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [model, 0, None, 3]
    session.commit.side_effect = StaleDataError("stale event version")
    repository = SQLAlchemyEventRepository(session)
    event = EventRecord(
        id=5,
        title="Attempted update",
        description=None,
        location=None,
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        capacity=25,
        status="draft",
        created_by_id=8,
        version=2,
    )

    with pytest.raises(ConcurrencyConflictError) as error:
        repository.save(event, expected_version=2)

    assert error.value.current_version == 3
    session.rollback.assert_called_once()


def test_same_initial_event_version_allows_only_first_update():
    """Reject a second update based on the version already advanced by the first."""
    model = SimpleNamespace(
        id=5,
        title="Original title",
        description=None,
        location=None,
        starts_at=datetime(2030, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2030, 1, 1, 11, tzinfo=UTC),
        capacity=25,
        status="draft",
        created_by_id=8,
        version=1,
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [model, 0, None, model]

    def commit_first_update():
        """Model the version increment performed by SQLAlchemy after its flush."""
        model.version = 2

    session.commit.side_effect = commit_first_update
    repository = SQLAlchemyEventRepository(session)
    first = EventRecord(
        id=5,
        title="First update",
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        capacity=25,
        created_by_id=8,
        version=1,
    )
    second = EventRecord(
        id=5,
        title="Second update",
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        capacity=25,
        created_by_id=8,
        version=1,
    )

    saved = repository.save(first, expected_version=1)
    with pytest.raises(ConcurrencyConflictError) as error:
        repository.save(second, expected_version=1)

    assert saved.version == 2
    assert error.value.current_version == 2
    assert session.commit.call_count == 1


def test_event_capacity_cannot_drop_below_active_event_registrations():
    """Reject capacity reductions that would place active event registrations over limit."""
    model = SimpleNamespace(
        id=5,
        title="Conference",
        description=None,
        location=None,
        starts_at=datetime(2030, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2030, 1, 1, 11, tzinfo=UTC),
        capacity=25,
        status="draft",
        created_by_id=8,
        version=1,
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [model, 5]
    repository = SQLAlchemyEventRepository(session)
    event = EventRecord(
        id=5,
        title="Conference",
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        capacity=4,
        created_by_id=8,
        version=1,
    )

    with pytest.raises(ValidationError, match="active event registrations"):
        repository.save(event, expected_version=1)

    lock_statement = session.scalar.call_args_list[0].args[0]
    assert "FOR UPDATE" in str(lock_statement.compile())
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_event_schedule_cannot_exclude_an_existing_session():
    """Reject event schedule changes that would invalidate a child session."""
    model = SimpleNamespace(
        id=5,
        title="Conference",
        description=None,
        location=None,
        starts_at=datetime(2030, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2030, 1, 1, 11, tzinfo=UTC),
        capacity=25,
        status="draft",
        created_by_id=8,
        version=1,
    )
    session = Mock(spec=Session)
    session.scalar.side_effect = [model, 0, 42]
    repository = SQLAlchemyEventRepository(session)
    event = EventRecord(
        id=5,
        title="Conference",
        starts_at=datetime(2030, 1, 1, 10, 30, tzinfo=UTC),
        ends_at=model.ends_at,
        capacity=25,
        created_by_id=8,
        version=1,
    )

    with pytest.raises(ValidationError, match="cannot exclude an existing session"):
        repository.save(event, expected_version=1)

    schedule_statement = session.scalar.call_args_list[2].args[0]
    sql = str(schedule_statement.compile())
    assert "event_sessions.starts_at" in sql
    assert "event_sessions.ends_at" in sql
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_delete_locks_event_before_checking_related_registrations():
    """Serialize event deletion against registration and session writes."""
    model = SimpleNamespace(
        id=5,
        registrations=[object()],
        sessions=[],
        speakers=[],
    )
    session = Mock(spec=Session)
    session.scalar.return_value = model
    repository = SQLAlchemyEventRepository(session)

    with pytest.raises(RelatedRecordsError):
        repository.delete(5)

    statement = session.scalar.call_args.args[0]
    sql = str(statement.compile())
    assert "FROM events" in sql
    assert "FOR UPDATE" in sql
    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()

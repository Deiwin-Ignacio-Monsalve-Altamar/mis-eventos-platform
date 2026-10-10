"""Verify event repository query construction with a mocked SQLAlchemy session."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import (
    AuthorizationError,
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


def test_list_by_creator_applies_owner_status_search_and_page_predicates():
    """Keep personal search and pagination constrained by the authenticated owner."""
    session = Mock(spec=Session)
    session.scalar.return_value = 2
    session.execute.return_value.scalars.return_value.all.return_value = []
    repository = SQLAlchemyEventRepository(session)

    events, total = repository.list_by_creator(99, 2, 5, "meetup", "published")

    statement = session.execute.call_args.args[0]
    compiled = statement.compile()
    assert events == []
    assert total == 2
    assert "events.created_by_id" in str(compiled)
    assert "events.status" in str(compiled)
    assert 99 in compiled.params.values()
    assert "meetup" in compiled.params.values()
    assert "published" in compiled.params.values()
    assert statement._offset_clause.value == 5
    assert statement._limit_clause.value == 5


def test_dashboard_counts_query_uses_creator_filter_and_lifecycle_dates():
    """Compute dashboard counts in one owner-scoped aggregate statement."""
    session = Mock(spec=Session)
    session.execute.return_value.one.return_value._mapping = {
        "total": 2,
        "draft": 1,
        "published": 0,
        "cancelled": 1,
        "completed": 0,
        "upcoming": 1,
        "active": 0,
        "finished": 0,
    }
    repository = SQLAlchemyEventRepository(session)
    now = datetime(2030, 1, 1, tzinfo=UTC)

    result = repository.dashboard_counts(99, now)

    statement = session.execute.call_args.args[0]
    assert result["total"] == 2
    assert result["cancelled"] == 1
    assert "events.created_by_id" in str(statement.compile())
    assert "events.starts_at" in str(statement.compile())
    assert "events.ends_at" in str(statement.compile())
    assert 99 in statement.compile().params.values()


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
        repository.save(event, expected_version=2, owner_id=8)

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

    saved = repository.save(first, expected_version=1, owner_id=8)
    with pytest.raises(ConcurrencyConflictError) as error:
        repository.save(second, expected_version=1, owner_id=8)

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
        repository.save(event, expected_version=1, owner_id=8)

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
        repository.save(event, expected_version=1, owner_id=8)

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
        created_by_id=8,
        registrations=[object()],
        sessions=[],
        speakers=[],
    )
    session = Mock(spec=Session)
    session.scalar.return_value = model
    repository = SQLAlchemyEventRepository(session)

    with pytest.raises(RelatedRecordsError):
        repository.delete(5, owner_id=8)

    statement = session.scalar.call_args.args[0]
    sql = str(statement.compile())
    assert "FROM events" in sql
    assert "FOR UPDATE" in sql
    session.delete.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_update_rolls_back_when_locked_event_belongs_to_another_user():
    """Recheck ownership under the event row lock before any update queries."""
    model = SimpleNamespace(id=5, created_by_id=8)
    session = Mock(spec=Session)
    session.scalar.return_value = model
    repository = SQLAlchemyEventRepository(session)
    event = EventRecord(
        id=5,
        title="Attempt",
        starts_at=datetime(2030, 1, 1, 10, tzinfo=UTC),
        ends_at=datetime(2030, 1, 1, 11, tzinfo=UTC),
        capacity=20,
        status="draft",
        created_by_id=8,
        version=1,
    )

    with pytest.raises(AuthorizationError):
        repository.save(event, expected_version=1, owner_id=99)

    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    session.add.assert_not_called()


def test_delete_rolls_back_when_locked_event_belongs_to_another_user():
    """Verify ownership under the deletion lock before inspecting dependencies."""
    model = SimpleNamespace(
        id=5, created_by_id=8, registrations=[], sessions=[], speakers=[]
    )
    session = Mock(spec=Session)
    session.scalar.return_value = model
    repository = SQLAlchemyEventRepository(session)

    with pytest.raises(AuthorizationError):
        repository.delete(5, owner_id=99)

    session.rollback.assert_called_once()
    session.delete.assert_not_called()
    session.commit.assert_not_called()


def test_owner_event_query_always_filters_by_creator():
    """Build a parameterized owner predicate for personal event lookups."""
    session = Mock(spec=Session)
    session.scalar.return_value = None
    repository = SQLAlchemyEventRepository(session)

    assert repository.find_by_id_for_creator(5, 99) is None

    statement = session.scalar.call_args.args[0]
    assert "events.created_by_id" in str(statement.compile())
    assert set(statement.compile().params.values()) == {5, 99}

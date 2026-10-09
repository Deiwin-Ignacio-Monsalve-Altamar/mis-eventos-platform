"""Verify event repository query construction with a mocked SQLAlchemy session."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

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

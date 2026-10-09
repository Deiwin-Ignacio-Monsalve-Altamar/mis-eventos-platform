"""Verify event registration transactions through mocked persistence."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import (
    DuplicateRegistrationError,
    EventCapacityExceededError,
    EventUnavailableError,
    ValidationError,
)
from app.infrastructure.repositories.sqlalchemy_event_registration_repository import (
    SQLAlchemyEventRegistrationRepository,
)

NOW = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


def make_event(capacity=10, status="published", starts_at=None):
    """Create an event-shaped mock with an explicit registration window."""
    return SimpleNamespace(
        id=7,
        capacity=capacity,
        status=status,
        starts_at=starts_at or NOW + timedelta(hours=1),
    )


def make_repository(session):
    """Inject a fixed aware clock so repository tests are time independent."""
    return SQLAlchemyEventRegistrationRepository(session, clock=lambda: NOW)


def test_cancel_updates_event_and_active_session_registrations_in_one_transaction():
    """Cancel the parent and issue a child update before the same commit."""
    event = SimpleNamespace(id=7, capacity=10)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="registered")
    session = Mock()
    session.scalar.side_effect = [event, registration]
    repository = make_repository(session)

    assert repository.cancel(7, 22) is True

    assert registration.status == "cancelled"
    update_statement = session.execute.call_args.args[0]
    compiled = update_statement.compile(dialect=postgresql.dialect())
    assert "session_registrations.registration_id" in str(compiled)
    assert "session_registrations.status" in str(compiled)
    assert "cancelled" in compiled.params.values()
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_cancel_rolls_back_parent_when_session_enrollment_cleanup_fails():
    """Restore the parent status and roll back if any child update fails."""
    event = SimpleNamespace(id=7, capacity=10)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="registered")
    session = Mock()
    session.scalar.side_effect = [event, registration]
    session.commit.side_effect = RuntimeError("transaction failed")
    session.rollback.side_effect = lambda: setattr(registration, "status", "registered")
    repository = make_repository(session)

    with pytest.raises(RuntimeError, match="transaction failed"):
        repository.cancel(7, 22)

    assert registration.status == "registered"
    session.execute.assert_called_once()
    session.commit.assert_called_once()
    session.rollback.assert_called_once()


def test_reactivation_does_not_touch_session_registrations():
    """Reactivate only the event registration without redundant child updates."""
    event = make_event()
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="cancelled")
    session = Mock()
    session.scalar.side_effect = [event, registration, 0]
    repository = make_repository(session)

    result = repository.register(7, 22)

    assert registration.status == "registered"
    assert result.status == "registered"
    session.execute.assert_not_called()
    session.commit.assert_called_once()


def test_cancel_locks_event_then_registration_before_cancelling_children():
    """Keep parent locks in the same order used by enrollment and capacity writes."""
    event = SimpleNamespace(id=7, capacity=10)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="registered")
    session = Mock()
    session.scalar.side_effect = [event, registration]
    repository = make_repository(session)

    repository.cancel(7, 22)

    event_lock = (
        session.scalar.call_args_list[0].args[0].compile(dialect=postgresql.dialect())
    )
    registration_lock = (
        session.scalar.call_args_list[1].args[0].compile(dialect=postgresql.dialect())
    )
    assert "FROM events" in str(event_lock)
    assert "FOR UPDATE" in str(event_lock)
    assert "FROM registrations" in str(registration_lock)
    assert "FOR UPDATE" in str(registration_lock)
    assert session.execute.call_count == 1


def test_register_rejects_full_event_without_committing():
    """Reject an event enrollment once active event capacity is exhausted."""
    event = make_event(capacity=1)
    session = Mock()
    session.scalar.side_effect = [event, None, 1]
    repository = make_repository(session)

    with pytest.raises(EventCapacityExceededError):
        repository.register(7, 22)

    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_reactivation_rechecks_event_capacity_before_changing_status():
    """Keep a cancelled registration unchanged when the event filled meanwhile."""
    event = make_event(capacity=1)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="cancelled")
    session = Mock()
    session.scalar.side_effect = [event, registration, 1]
    repository = make_repository(session)

    with pytest.raises(EventCapacityExceededError):
        repository.register(7, 22)

    assert registration.status == "cancelled"
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_register_rejects_an_active_duplicate_without_counting_or_committing():
    """Reject an active duplicate before checking event capacity."""
    event = make_event(capacity=5)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="registered")
    session = Mock()
    session.scalar.side_effect = [event, registration]
    repository = make_repository(session)

    with pytest.raises(DuplicateRegistrationError, match="already registered"):
        repository.register(7, 22)

    assert registration.status == "registered"
    assert session.scalar.call_count == 2
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_new_event_registration_is_created_transactionally():
    """Create a new active event registration using the authenticated user ID."""
    event = make_event(capacity=2)
    session = Mock()
    session.scalar.side_effect = [event, None, 0]

    def assign_registration_id():
        """Assign the identity a database flush would generate for the new row."""
        session.add.call_args.args[0].id = 31

    session.commit.side_effect = assign_registration_id
    repository = make_repository(session)

    registration = repository.register(7, 22)

    assert registration.id == 31
    assert registration.user_id == 22
    assert registration.status == "registered"
    session.commit.assert_called_once()


@pytest.mark.parametrize("status", ["draft", "cancelled", "completed"])
def test_register_rejects_closed_event_status_without_mutating_registration(status):
    """Reject every non-published state after locking the event row."""
    session = Mock()
    session.scalar.return_value = make_event(status=status)
    repository = make_repository(session)

    with pytest.raises(EventUnavailableError, match="not open"):
        repository.register(7, 22)

    statement = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "FROM events" in str(statement)
    assert "FOR UPDATE" in str(statement)
    session.rollback.assert_called_once()
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "starts_at",
    [
        NOW - timedelta(microseconds=1),
        NOW,
    ],
    ids=["past-start", "start-equals-now"],
)
def test_register_rejects_event_starting_at_or_before_injected_clock(starts_at):
    """Require the event start to be strictly later than the fixed clock value."""
    session = Mock()
    session.scalar.return_value = make_event(starts_at=starts_at)
    repository = make_repository(session)

    with pytest.raises(EventUnavailableError, match="not open"):
        repository.register(7, 22)

    session.rollback.assert_called_once()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_register_accepts_published_event_starting_after_injected_clock():
    """Allow registration when the published event starts after the fixed clock."""
    event = make_event(starts_at=NOW + timedelta(microseconds=1))
    session = Mock()
    session.scalar.side_effect = [event, None, 0]

    def assign_registration_id():
        """Assign the identifier that a database flush would provide."""
        session.add.call_args.args[0].id = 31

    session.commit.side_effect = assign_registration_id
    repository = make_repository(session)

    registration = repository.register(7, 22)

    assert registration.status == "registered"
    assert session.scalar.call_count == 3
    statements = [
        call.args[0].compile(dialect=postgresql.dialect())
        for call in session.scalar.call_args_list
    ]
    assert "FROM events" in str(statements[0])
    assert "FOR UPDATE" in str(statements[0])
    assert "FROM registrations" in str(statements[1])
    assert "FOR UPDATE" in str(statements[1])
    assert "count(registrations.id)" in str(statements[2])
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_register_accepts_future_event_start_with_non_utc_offset():
    """Compare an offset-aware event start as a UTC instant against the clock."""
    event = make_event(starts_at=datetime.fromisoformat("2030-01-01T17:30:01+05:30"))
    session = Mock()
    session.scalar.side_effect = [event, None, 0]

    def assign_registration_id():
        """Assign the identifier that a database flush would generate."""
        session.add.call_args.args[0].id = 31

    session.commit.side_effect = assign_registration_id
    repository = make_repository(session)

    registration = repository.register(7, 22)

    assert registration.status == "registered"
    assert event.starts_at.astimezone(UTC) == NOW + timedelta(seconds=1)
    assert session.scalar.call_count == 3
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_register_rejects_naive_event_start_without_comparing_datetimes():
    """Reject malformed persisted timestamps without comparing naive and aware values."""
    event = make_event(starts_at=datetime.fromisoformat("2030-01-01T13:00:00"))
    session = Mock()
    session.scalar.return_value = event
    repository = make_repository(session)

    with pytest.raises(
        ValidationError, match="event start time must be timezone-aware"
    ):
        repository.register(7, 22)

    session.rollback.assert_called_once()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_concurrent_event_registrations_serialize_capacity_check_with_event_lock():
    """Use concurrent workers and lock-aware session mocks for the final seat."""
    event = make_event(capacity=2)
    event_lock = Lock()
    state_lock = Lock()
    start_barrier = Barrier(3)
    lock_owner = {"user_id": None}
    active_count = {"value": 1}
    timeline = []
    user_ids = (21, 22)
    repositories = {}
    sessions = {}

    def acquire_event_lock(user_id):
        """Acquire the mocked event row lock with a bounded wait."""
        if not event_lock.acquire(timeout=5):
            raise TimeoutError("Timed out waiting for the mocked event lock.")
        try:
            with state_lock:
                lock_owner["user_id"] = user_id
                timeline.append((user_id, "event_locked", None))
        except BaseException:
            with state_lock:
                if lock_owner["user_id"] == user_id:
                    lock_owner["user_id"] = None
            event_lock.release()
            raise

    def release_event_lock(user_id):
        """Release this worker's event lock at most once."""
        with state_lock:
            if lock_owner["user_id"] != user_id:
                return
            lock_owner["user_id"] = None
        event_lock.release()

    for user_id in user_ids:
        session = Mock()
        step = {"value": 0}

        def scalar(statement, *, current_user_id=user_id, current_step=step):
            """Read transaction state in the repository's expected SQL order."""
            sql = str(statement.compile(dialect=postgresql.dialect()))
            position = current_step["value"]
            current_step["value"] += 1
            if position == 0:
                assert "FROM events" in sql and "FOR UPDATE" in sql
                acquire_event_lock(current_user_id)
                return event
            if position == 1:
                assert "FROM registrations" in sql and "FOR UPDATE" in sql
                return None
            assert position == 2
            assert "count(registrations.id)" in sql
            with state_lock:
                count = active_count["value"]
                timeline.append((current_user_id, "capacity_checked", count))
            return count

        session.scalar.side_effect = scalar

        def commit(*, current_user_id=user_id, current_session=session):
            """Persist one mocked registration and release its event lock."""
            with state_lock:
                active_count["value"] += 1
                current_session.add.call_args.args[0].id = current_user_id
                timeline.append((current_user_id, "commit", active_count["value"]))
            release_event_lock(current_user_id)

        def rollback(*, current_user_id=user_id):
            """Record a rejected transaction and release its event lock."""
            with state_lock:
                timeline.append((current_user_id, "rollback", active_count["value"]))
            release_event_lock(current_user_id)

        session.commit.side_effect = commit
        session.rollback.side_effect = rollback
        sessions[user_id] = session
        repositories[user_id] = make_repository(session)

    def register_after_barrier(user_id):
        """Start registration only when both independent workers are ready."""
        try:
            start_barrier.wait(timeout=5)
            try:
                repositories[user_id].register(7, user_id)
            except EventCapacityExceededError:
                return "capacity_exceeded"
            return "accepted"
        finally:
            release_event_lock(user_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(register_after_barrier, user_id) for user_id in user_ids
        ]
        start_barrier.wait(timeout=5)
        outcomes = [future.result(timeout=5) for future in futures]

    assert sorted(outcomes) == ["accepted", "capacity_exceeded"]
    assert active_count["value"] == event.capacity
    assert sorted(item[2] for item in timeline if item[1] == "capacity_checked") == [
        1,
        2,
    ]
    for user_id in user_ids:
        user_events = [item[1] for item in timeline if item[0] == user_id]
        assert user_events[:2] == ["event_locked", "capacity_checked"]
        assert user_events[-1] in {"commit", "rollback"}
        assert sessions[user_id].scalar.call_count == 3

    assert sum(session.commit.call_count for session in sessions.values()) == 1
    assert sum(session.rollback.call_count for session in sessions.values()) == 1
    assert sum(session.add.call_count for session in sessions.values()) == 1


def test_list_by_user_returns_both_statuses_and_joins_public_event_fields():
    """Query one user's registrations with their event data and no status filter."""
    registration = SimpleNamespace(
        id=31,
        user_id=22,
        event_id=7,
        status="registered",
        registered_at=NOW,
    )
    cancelled_registration = SimpleNamespace(
        id=32,
        user_id=22,
        event_id=8,
        status="cancelled",
        registered_at=NOW,
    )
    event = SimpleNamespace(
        id=7,
        title="First Event",
        description="Details",
        location="Bogota",
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(hours=2),
        capacity=10,
        status="published",
        created_by_id=5,
        version=1,
    )
    cancelled_event = SimpleNamespace(
        id=8,
        title="Second Event",
        description=None,
        location=None,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, hours=1),
        capacity=5,
        status="cancelled",
        created_by_id=6,
        version=2,
    )
    session = Mock()
    session.scalar.return_value = 2
    session.execute.return_value.all.return_value = [
        (registration, event),
        (cancelled_registration, cancelled_event),
    ]
    repository = make_repository(session)

    details, total = repository.list_by_user(22, page=1, page_size=20)

    assert total == 2
    assert [item.status for item in details] == ["registered", "cancelled"]
    assert [item.event.id for item in details] == [7, 8]
    assert details[0].event.title == "First Event"
    assert details[1].event.status == "cancelled"
    count_statement = session.scalar.call_args.args[0]
    list_statement = session.execute.call_args.args[0]
    assert "registrations.user_id" in str(
        count_statement.compile(dialect=postgresql.dialect())
    )
    compiled_list = list_statement.compile(dialect=postgresql.dialect())
    list_sql = str(compiled_list)
    assert "JOIN events" in str(compiled_list)
    assert "WHERE registrations.user_id" in list_sql
    assert "LIMIT" in str(compiled_list)
    assert "OFFSET" in str(compiled_list)
    assert "ORDER BY events.starts_at ASC, events.id ASC" in list_sql
    assert "WHERE registrations.status" not in list_sql
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_list_by_user_returns_empty_results_without_mutating_persistence():
    """Return an empty page when the requested user has no registrations."""
    session = Mock()
    session.scalar.return_value = 0
    session.execute.return_value.all.return_value = []
    repository = make_repository(session)

    details, total = repository.list_by_user(22, page=1, page_size=20)

    assert details == []
    assert total == 0
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()

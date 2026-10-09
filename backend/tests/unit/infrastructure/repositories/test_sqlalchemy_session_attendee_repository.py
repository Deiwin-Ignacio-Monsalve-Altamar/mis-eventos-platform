"""Verify attendee persistence using a mocked SQLAlchemy session."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import (
    CapacityExceededError,
    DuplicateRegistrationError,
    NotFoundError,
    ValidationError,
)
from app.domain.entities.session_attendee import SessionOccupancy
from app.infrastructure.repositories.sqlalchemy_session_attendee_repository import (
    SQLAlchemySessionAttendeeRepository,
)


def test_enroll_locks_session_and_creates_session_registration():
    """Lock event, active parent registration, and session before counting seats."""
    event = SimpleNamespace(id=4, capacity=20)
    session_model = SimpleNamespace(id=9, event_id=4, capacity=3)
    event_registration = SimpleNamespace(id=14)
    session = Mock()
    session.scalar.side_effect = [event, event_registration, session_model, None, 2]
    repository = SQLAlchemySessionAttendeeRepository(session)

    repository.enroll(4, 9, 21)

    event_lock = session.scalar.call_args_list[0].args[0]
    registration_lock = session.scalar.call_args_list[1].args[0]
    session_lock = session.scalar.call_args_list[2].args[0]
    event_sql = str(event_lock.compile(dialect=postgresql.dialect()))
    registration_sql = str(registration_lock.compile(dialect=postgresql.dialect()))
    session_sql = str(session_lock.compile(dialect=postgresql.dialect()))
    assert "FROM events" in event_sql
    assert "FOR UPDATE" in event_sql
    assert "registrations" in registration_sql
    assert "FOR UPDATE" in registration_sql
    assert "event_sessions" in session_sql
    assert "FOR UPDATE" in session_sql
    added_registration = session.add.call_args.args[0]
    assert added_registration.session_id == 9
    assert added_registration.registration_id == 14
    assert added_registration.status == "active"
    session.commit.assert_called_once()


def test_enroll_rejects_full_session_without_commit():
    """Reject enrollment at capacity without committing a new registration."""
    session_model = SimpleNamespace(id=9, event_id=4, capacity=1)
    event_registration = SimpleNamespace(id=14)
    session = Mock()
    session.scalar.side_effect = [
        SimpleNamespace(id=4),
        event_registration,
        session_model,
        None,
        1,
    ]
    repository = SQLAlchemySessionAttendeeRepository(session)

    with pytest.raises(CapacityExceededError):
        repository.enroll(4, 9, 21)

    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_concurrent_enrollments_serialize_on_event_lock_and_recheck_capacity():
    """Run two repository calls concurrently through lock-aware session mocks."""
    event = SimpleNamespace(id=4, capacity=20)
    session_model = SimpleNamespace(id=9, event_id=4, capacity=2)
    event_lock = Lock()
    start_barrier = Barrier(3)
    state_lock = Lock()
    lock_owner = {"user_id": None}
    timeline = []
    active_count = {"value": 1}
    user_ids = (21, 22)
    registration_ids = {21: 14, 22: 15}
    persistence_sessions = {}
    repositories = {}

    def acquire_event_lock(user_id):
        """Acquire the mocked event lock within the test's bounded time."""
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
        """Release the lock only when this worker currently owns it."""
        with state_lock:
            if lock_owner["user_id"] != user_id:
                return
            lock_owner["user_id"] = None
        event_lock.release()

    for user_id in user_ids:
        persistence_session = Mock()
        step = {"value": 0}

        def scalar(statement, *, current_user_id=user_id, current_step=step):
            """Emulate database reads while enforcing the SQL event-row lock."""
            sql = str(statement.compile(dialect=postgresql.dialect()))
            position = current_step["value"]
            current_step["value"] += 1
            expected_tables = (
                "events",
                "registrations",
                "event_sessions",
                "session_registrations",
                "session_registrations",
            )
            assert f"FROM {expected_tables[position]}" in sql
            if position == 0:
                assert "FOR UPDATE" in sql
                acquire_event_lock(current_user_id)
                return event
            if position == 1:
                assert "FOR UPDATE" in sql
                return SimpleNamespace(id=registration_ids[current_user_id])
            if position == 2:
                assert "FOR UPDATE" in sql
                return session_model
            if position == 3:
                assert "FOR UPDATE" in sql
                return None

            with state_lock:
                observed_count = active_count["value"]
                timeline.append((current_user_id, "capacity_checked", observed_count))
            return observed_count

        persistence_session.scalar.side_effect = scalar

        def commit(*, current_user_id=user_id):
            """Commit one seat while holding the mocked event row lock."""
            with state_lock:
                active_count["value"] += 1
                timeline.append((current_user_id, "commit", active_count["value"]))
            release_event_lock(current_user_id)

        def rollback(*, current_user_id=user_id):
            """Roll back a rejected attempt and release its event row lock."""
            with state_lock:
                timeline.append((current_user_id, "rollback", active_count["value"]))
            release_event_lock(current_user_id)

        persistence_session.commit.side_effect = commit
        persistence_session.rollback.side_effect = rollback
        persistence_sessions[user_id] = persistence_session
        repositories[user_id] = SQLAlchemySessionAttendeeRepository(persistence_session)

    def enroll_after_barrier(user_id):
        """Begin enrollment only after both independent workers are ready."""
        try:
            start_barrier.wait(timeout=5)
            try:
                repositories[user_id].enroll(4, 9, user_id)
            except CapacityExceededError:
                return "capacity_exceeded"
            return "accepted"
        finally:
            release_event_lock(user_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(enroll_after_barrier, user_id) for user_id in user_ids
        ]
        start_barrier.wait(timeout=5)
        outcomes = [future.result(timeout=5) for future in futures]

    assert sorted(outcomes) == ["accepted", "capacity_exceeded"]
    assert active_count["value"] == session_model.capacity

    for user_id in user_ids:
        user_timeline = [item[1] for item in timeline if item[0] == user_id]
        assert user_timeline[:2] == ["event_locked", "capacity_checked"]
        assert user_timeline[-1] in {"commit", "rollback"}
        assert persistence_sessions[user_id].scalar.call_count == 5

    checked_counts = [item[2] for item in timeline if item[1] == "capacity_checked"]
    assert sorted(checked_counts) == [1, 2]
    accepted_user = next(
        user
        for user in user_ids
        if "commit" in [item[1] for item in timeline if item[0] == user]
    )
    rejected_user = next(user for user in user_ids if user != accepted_user)
    assert persistence_sessions[accepted_user].commit.call_count == 1
    persistence_sessions[accepted_user].rollback.assert_not_called()
    assert persistence_sessions[accepted_user].add.call_count == 1
    persistence_sessions[rejected_user].commit.assert_not_called()
    persistence_sessions[rejected_user].rollback.assert_called_once()
    persistence_sessions[rejected_user].add.assert_not_called()


def test_enroll_rejects_attendee_without_active_event_registration():
    """Require a registered event attendee before adding a session enrollment."""
    session = Mock()
    session.scalar.side_effect = [SimpleNamespace(id=4), None]
    repository = SQLAlchemySessionAttendeeRepository(session)

    with pytest.raises(ValidationError, match="active event registration"):
        repository.enroll(4, 9, 21)

    session.commit.assert_not_called()


def test_enroll_rejects_duplicate_active_registration():
    """Prevent a second active enrollment for the same event registration."""
    session_model = SimpleNamespace(id=9, event_id=4, capacity=3)
    event_registration = SimpleNamespace(id=14)
    existing = SimpleNamespace(status="active")
    session = Mock()
    session.scalar.side_effect = [
        SimpleNamespace(id=4),
        event_registration,
        session_model,
        existing,
    ]
    repository = SQLAlchemySessionAttendeeRepository(session)

    with pytest.raises(DuplicateRegistrationError):
        repository.enroll(4, 9, 21)

    session.commit.assert_not_called()


def test_enroll_reactivates_cancelled_registration_when_seat_is_available():
    """Reuse a cancelled registration row and consume a free session seat."""
    session_model = SimpleNamespace(id=9, event_id=4, capacity=3)
    event_registration = SimpleNamespace(id=14)
    existing = SimpleNamespace(status="cancelled")
    session = Mock()
    session.scalar.side_effect = [
        SimpleNamespace(id=4),
        event_registration,
        session_model,
        existing,
        1,
    ]
    repository = SQLAlchemySessionAttendeeRepository(session)

    repository.enroll(4, 9, 21)

    assert existing.status == "active"
    session.add.assert_called_once_with(existing)
    session.commit.assert_called_once()


def test_session_reactivation_keeps_cancelled_state_when_capacity_is_full():
    """Do not reactivate a cancelled child enrollment when no seat remains."""
    session_model = SimpleNamespace(id=9, event_id=4, capacity=1)
    event_registration = SimpleNamespace(id=14)
    existing = SimpleNamespace(status="cancelled")
    session = Mock()
    session.scalar.side_effect = [
        SimpleNamespace(id=4),
        event_registration,
        session_model,
        existing,
        1,
    ]
    repository = SQLAlchemySessionAttendeeRepository(session)

    with pytest.raises(CapacityExceededError):
        repository.enroll(4, 9, 21)

    assert existing.status == "cancelled"
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_cancel_marks_only_the_active_registration_cancelled():
    """Follow the shared event, parent registration, session, child lock order."""
    enrollment = SimpleNamespace(status="active")
    session = Mock()
    session.scalar.side_effect = [
        SimpleNamespace(id=4),
        SimpleNamespace(id=14),
        9,
        enrollment,
    ]
    repository = SQLAlchemySessionAttendeeRepository(session)

    assert repository.cancel(4, 9, 21) is True

    assert enrollment.status == "cancelled"
    session.commit.assert_called_once()

    statements = [
        call.args[0].compile(dialect=postgresql.dialect())
        for call in session.scalar.call_args_list
    ]
    tables = ("events", "registrations", "event_sessions", "session_registrations")
    assert [
        next(table for table in tables if f"FROM {table}" in str(statement))
        for statement in statements
    ] == list(tables)
    assert all("FOR UPDATE" in str(statement) for statement in statements)


def test_cancel_does_not_touch_session_when_parent_registration_is_inactive():
    """Do not mutate child enrollments when their event registration is inactive."""
    session = Mock()
    session.scalar.side_effect = [SimpleNamespace(id=4), None]
    repository = SQLAlchemySessionAttendeeRepository(session)

    assert repository.cancel(4, 9, 21) is False

    assert session.scalar.call_count == 2
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_enroll_rolls_back_when_commit_fails():
    """Roll back the whole enrollment if the database commit raises unexpectedly."""
    session_model = SimpleNamespace(id=9, event_id=4, capacity=3)
    event_registration = SimpleNamespace(id=14)
    session = Mock()
    session.scalar.side_effect = [
        SimpleNamespace(id=4),
        event_registration,
        session_model,
        None,
        0,
    ]
    session.commit.side_effect = RuntimeError("commit failed")
    repository = SQLAlchemySessionAttendeeRepository(session)

    with pytest.raises(RuntimeError, match="commit failed"):
        repository.enroll(4, 9, 21)

    session.rollback.assert_called_once()


def test_cancellation_releases_a_session_seat():
    """Show a cancelled enrollment is absent from the next occupancy count."""
    enrollment = SimpleNamespace(status="active")
    session = Mock()
    session.scalar.side_effect = [
        SimpleNamespace(id=4),
        SimpleNamespace(id=14),
        9,
        enrollment,
    ]
    session.execute.return_value.one_or_none.return_value = (1, 0)
    repository = SQLAlchemySessionAttendeeRepository(session)

    assert repository.cancel(4, 9, 21) is True
    occupancy = repository.get_occupancy(4, 9)

    assert occupancy == SessionOccupancy(capacity=1, occupied=0, available=1)


def test_occupancy_counts_only_session_enrollments():
    """Read capacity and eligible session enrollment count in a single query."""
    session = Mock()
    session.execute.return_value.one_or_none.return_value = (5, 3)
    repository = SQLAlchemySessionAttendeeRepository(session)

    assert repository.get_occupancy(4, 9) == SessionOccupancy(5, 3, 2)
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "event_sessions.capacity" in sql
    assert "session_registrations.status" in sql
    assert "registrations.status" in sql
    assert "GROUP BY event_sessions.capacity" in sql
    session.scalar.assert_not_called()


def test_occupancy_reports_missing_session():
    """Return a not-found error when the aggregate query finds no session."""
    session = Mock()
    session.execute.return_value.one_or_none.return_value = None
    repository = SQLAlchemySessionAttendeeRepository(session)

    with pytest.raises(NotFoundError, match="Session not found for this event"):
        repository.get_occupancy(4, 99)

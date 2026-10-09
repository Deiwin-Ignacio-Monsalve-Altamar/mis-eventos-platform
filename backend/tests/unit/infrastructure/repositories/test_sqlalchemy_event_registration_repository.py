"""Verify event registration transactions through mocked persistence."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import EventCapacityExceededError
from app.infrastructure.repositories.sqlalchemy_event_registration_repository import (
    SQLAlchemyEventRegistrationRepository,
)


def test_cancel_updates_event_and_active_session_registrations_in_one_transaction():
    """Cancel the parent and issue a child update before the same commit."""
    event = SimpleNamespace(id=7, capacity=10)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="registered")
    session = Mock()
    session.scalar.side_effect = [event, registration]
    repository = SQLAlchemyEventRegistrationRepository(session)

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
    repository = SQLAlchemyEventRegistrationRepository(session)

    with pytest.raises(RuntimeError, match="transaction failed"):
        repository.cancel(7, 22)

    assert registration.status == "registered"
    session.execute.assert_called_once()
    session.commit.assert_called_once()
    session.rollback.assert_called_once()


def test_reactivation_does_not_touch_session_registrations():
    """Reactivate only the event registration without redundant child updates."""
    event = SimpleNamespace(id=7, capacity=10)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="cancelled")
    session = Mock()
    session.scalar.side_effect = [event, registration, 0]
    repository = SQLAlchemyEventRegistrationRepository(session)

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
    repository = SQLAlchemyEventRegistrationRepository(session)

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
    event = SimpleNamespace(id=7, capacity=1)
    session = Mock()
    session.scalar.side_effect = [event, None, 1]
    repository = SQLAlchemyEventRegistrationRepository(session)

    with pytest.raises(EventCapacityExceededError):
        repository.register(7, 22)

    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_reactivation_rechecks_event_capacity_before_changing_status():
    """Keep a cancelled registration unchanged when the event filled meanwhile."""
    event = SimpleNamespace(id=7, capacity=1)
    registration = SimpleNamespace(id=12, event_id=7, user_id=22, status="cancelled")
    session = Mock()
    session.scalar.side_effect = [event, registration, 1]
    repository = SQLAlchemyEventRegistrationRepository(session)

    with pytest.raises(EventCapacityExceededError):
        repository.register(7, 22)

    assert registration.status == "cancelled"
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_new_event_registration_is_created_transactionally():
    """Create a new active event registration using the authenticated user ID."""
    event = SimpleNamespace(id=7, capacity=2)
    session = Mock()
    session.scalar.side_effect = [event, None, 0]

    def assign_registration_id():
        """Assign the identity a database flush would generate for the new row."""
        session.add.call_args.args[0].id = 31

    session.commit.side_effect = assign_registration_id
    repository = SQLAlchemyEventRegistrationRepository(session)

    registration = repository.register(7, 22)

    assert registration.id == 31
    assert registration.user_id == 22
    assert registration.status == "registered"
    session.commit.assert_called_once()

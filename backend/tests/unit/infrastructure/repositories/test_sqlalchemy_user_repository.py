"""Verify user repository queries and persistence with mocked SQLAlchemy sessions."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import DuplicateAccountError
from app.domain.entities.user_account import UserAccount
from app.infrastructure.database.models import User
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)


def make_user(user_id: int = 17) -> User:
    """Create a user model with representative persisted account fields."""
    return User(
        id=user_id,
        email="attendee@example.test",
        password_hash="encoded-password",
        first_name="Ada",
        last_name="Lovelace",
    )


def make_account() -> UserAccount:
    """Create the domain account passed to repository persistence."""
    return UserAccount(
        id=None,
        email="attendee@example.test",
        password_hash="encoded-password",
        first_name="Ada",
        last_name="Lovelace",
    )


def test_find_by_email_returns_mapped_account_when_user_exists():
    """Map the selected user row to a domain account for a matching email."""
    user = make_user()
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = user
    repository = SQLAlchemyUserRepository(session)

    result = repository.find_by_email(user.email)

    assert result == UserAccount(
        id=17,
        email="attendee@example.test",
        password_hash="encoded-password",
        first_name="Ada",
        last_name="Lovelace",
    )
    query = session.execute.call_args.args[0]
    assert "users.email" in str(query)
    assert "attendee@example.test" in str(query.compile().params.values())


def test_find_by_email_returns_none_when_user_does_not_exist():
    """Return no account when the email query has no matching row."""
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    repository = SQLAlchemyUserRepository(session)

    assert repository.find_by_email("missing@example.test") is None


def test_find_by_id_returns_mapped_account_when_user_exists():
    """Map the user row returned by the session identity lookup."""
    user = make_user()
    session = Mock()
    session.get.return_value = user
    repository = SQLAlchemyUserRepository(session)

    result = repository.find_by_id(17)

    assert result == UserAccount(
        id=17,
        email="attendee@example.test",
        password_hash="encoded-password",
        first_name="Ada",
        last_name="Lovelace",
    )
    session.get.assert_called_once_with(User, 17)


def test_find_by_id_returns_none_when_user_does_not_exist():
    """Return no account when the requested identifier is absent."""
    session = Mock()
    session.get.return_value = None
    repository = SQLAlchemyUserRepository(session)

    assert repository.find_by_id(99) is None


def test_add_persists_user_and_returns_domain_account():
    """Persist all account fields and map the generated identifier back."""
    session = Mock()
    session.commit.side_effect = lambda: setattr(
        session.add.call_args.args[0], "id", 23
    )
    repository = SQLAlchemyUserRepository(session)

    result = repository.add(make_account())

    persisted_user = session.add.call_args.args[0]
    assert isinstance(persisted_user, User)
    assert (
        persisted_user.email,
        persisted_user.password_hash,
        persisted_user.first_name,
        persisted_user.last_name,
    ) == (
        "attendee@example.test",
        "encoded-password",
        "Ada",
        "Lovelace",
    )
    assert result == UserAccount(
        id=23,
        email="attendee@example.test",
        password_hash="encoded-password",
        first_name="Ada",
        last_name="Lovelace",
    )
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_add_rolls_back_and_translates_duplicate_email_integrity_error():
    """Translate a unique email violation into the domain duplicate error."""
    original_error = IntegrityError(
        "INSERT", {}, Exception("UNIQUE constraint failed: users.email")
    )
    session = Mock()
    session.commit.side_effect = original_error
    repository = SQLAlchemyUserRepository(session)

    with pytest.raises(DuplicateAccountError, match="already exists") as error:
        repository.add(make_account())

    assert error.value.__cause__ is original_error
    session.rollback.assert_called_once()


def test_add_rolls_back_and_reraises_unrelated_integrity_error():
    """Preserve integrity failures that do not concern the email constraint."""
    original_error = IntegrityError(
        "INSERT", {}, Exception("foreign key constraint failed")
    )
    session = Mock()
    session.commit.side_effect = original_error
    repository = SQLAlchemyUserRepository(session)

    with pytest.raises(IntegrityError) as error:
        repository.add(make_account())

    assert error.value is original_error
    session.rollback.assert_called_once()


@pytest.mark.parametrize(
    "original_error, expected",
    [
        (
            SimpleNamespace(diag=SimpleNamespace(constraint_name="ix_users_email")),
            True,
        ),
        (Exception("UNIQUE constraint failed: users.email"), True),
        (Exception("duplicate key violates another constraint"), False),
    ],
)
def test_is_email_conflict_matches_only_email_integrity_violations(
    original_error: Exception, expected: bool
):
    """Recognize PostgreSQL and SQLite email conflicts but reject unrelated ones."""
    error = IntegrityError("INSERT", {}, original_error)

    assert SQLAlchemyUserRepository._is_email_conflict(error) is expected


def test_to_account_maps_every_user_model_identity_field():
    """Preserve identifier, credentials hash, email, and names in domain mapping."""
    user = make_user(user_id=31)

    account = SQLAlchemyUserRepository._to_account(user)

    assert account == UserAccount(
        id=31,
        email="attendee@example.test",
        password_hash="encoded-password",
        first_name="Ada",
        last_name="Lovelace",
    )

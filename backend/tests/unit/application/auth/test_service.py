"""Verify authentication use cases with the user repository mocked."""

from dataclasses import replace
from unittest.mock import Mock

import jwt
import pytest

from app.application.auth.service import AuthService
from app.core.exceptions import (
    AuthenticationError,
    DuplicateAccountError,
    ValidationError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.entities.user_account import UserAccount
from app.domain.repositories.user_repository import UserRepository

JWT_SECRET = "unit-test-secret-with-more-than-thirty-two-bytes"


@pytest.fixture
def auth_service():
    """Build the authentication service with a mocked user repository."""
    repository = Mock(spec=UserRepository)
    repository.find_by_email.return_value = None
    repository.find_by_id.return_value = None
    repository.add.side_effect = lambda account: replace(account, id=23)
    return AuthService(repository, JWT_SECRET, 1800), repository


def test_registration_normalizes_email_hashes_password_and_uses_repository(
    auth_service,
):
    """Normalize account input and persist a password hash through the repository."""
    service, repository = auth_service

    account = service.register(
        " ATTENDEE@EXAMPLE.TEST ", "correct-horse", " Alex ", " Rivera "
    )

    assert account.id == 23
    assert account.email == "attendee@example.test"
    assert account.first_name == "Alex"
    assert verify_password("correct-horse", account.password_hash)
    repository.find_by_email.assert_called_once_with("attendee@example.test")
    repository.add.assert_called_once()


def test_registration_rejects_duplicate_email_without_persisting(auth_service):
    """Raise a duplicate-account error before attempting repository persistence."""
    service, repository = auth_service
    repository.find_by_email.return_value = UserAccount(
        id=9,
        email="attendee@example.test",
        password_hash=hash_password("existing-password"),
        first_name="Taylor",
        last_name="Jones",
    )

    with pytest.raises(DuplicateAccountError):
        service.register("attendee@example.test", "correct-horse", "Alex", "Rivera")

    repository.add.assert_not_called()


def test_registration_rejects_invalid_fields_before_repository_calls(auth_service):
    """Reject malformed input before performing any repository lookup or write."""
    service, repository = auth_service

    with pytest.raises(ValidationError):
        service.register("invalid-email", "correct-horse", "Alex", "Rivera")

    repository.find_by_email.assert_not_called()
    repository.add.assert_not_called()


def test_login_verifies_credentials_and_returns_signed_token(auth_service):
    """Return a token for a matching password and normalized email address."""
    service, repository = auth_service
    account = UserAccount(
        id=23,
        email="attendee@example.test",
        password_hash=hash_password("correct-horse"),
        first_name="Alex",
        last_name="Rivera",
    )
    repository.find_by_email.return_value = account

    authenticated_account, token = service.authenticate(
        "ATTENDEE@example.test", "correct-horse"
    )

    assert authenticated_account == account
    assert jwt.decode(token, JWT_SECRET, algorithms=["HS256"])["sub"] == "23"
    repository.find_by_email.assert_called_once_with("attendee@example.test")


def test_login_rejects_incorrect_credentials(auth_service):
    """Raise a generic authentication error when the password does not match."""
    service, repository = auth_service
    repository.find_by_email.return_value = UserAccount(
        id=23,
        email="attendee@example.test",
        password_hash=hash_password("correct-horse"),
        first_name="Alex",
        last_name="Rivera",
    )

    with pytest.raises(AuthenticationError):
        service.authenticate("attendee@example.test", "wrong-password")


def test_expired_token_is_rejected_without_repository_lookup(auth_service):
    """Reject an expired access token before querying for its account."""
    service, repository = auth_service
    token = jwt.encode(
        {"sub": "23", "iat": 1, "exp": 2, "type": "access"},
        JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        service.get_authenticated_user(token)

    repository.find_by_id.assert_not_called()


@pytest.mark.parametrize(
    "email, password",
    [("invalid-email", "correct-horse"), ("attendee@example.test", None)],
)
def test_login_rejects_malformed_email_or_empty_password_without_lookup(
    auth_service, email, password
):
    """Return the same authentication error without looking up malformed credentials."""
    service, repository = auth_service

    with pytest.raises(AuthenticationError, match="Email or password is incorrect"):
        service.authenticate(email, password)

    repository.find_by_email.assert_not_called()


def test_authenticated_token_for_missing_account_is_rejected(auth_service):
    """Reject a validly signed token when its subject account no longer exists."""
    service, repository = auth_service
    valid_token = create_access_token(404, service._jwt_secret, 300)
    repository.find_by_id.return_value = None

    with pytest.raises(AuthenticationError, match="access token is invalid"):
        service.get_authenticated_user(valid_token)

    repository.find_by_id.assert_called_once_with(404)

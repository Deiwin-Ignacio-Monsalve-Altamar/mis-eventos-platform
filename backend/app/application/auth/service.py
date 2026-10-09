"""Validate account input and coordinate registration, login, and token authentication."""

import re

from app.core.exceptions import (
    AuthenticationError,
    DuplicateAccountError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.domain.entities.user_account import UserAccount
from app.domain.repositories.user_repository import UserRepository

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MINIMUM_PASSWORD_LENGTH = 8
MAXIMUM_PASSWORD_LENGTH = 128


class AuthService:
    """Coordinate account validation, storage, password checks, and access tokens."""

    def __init__(
        self,
        user_repository: UserRepository,
        jwt_secret: str | None,
        access_token_ttl_seconds: int,
    ) -> None:
        """Set the persistence port and token configuration used by this service."""
        self._user_repository = user_repository
        self._jwt_secret = jwt_secret
        self._access_token_ttl_seconds = access_token_ttl_seconds

    def register(
        self, email: object, password: object, first_name: object, last_name: object
    ) -> UserAccount:
        """Validate, normalize, hash, and persist a new attendee account."""
        normalized_email = self._validate_email(email)
        normalized_first_name = self._validate_name(first_name, "first_name")
        normalized_last_name = self._validate_name(last_name, "last_name")
        validated_password = self._validate_password(password)

        if self._user_repository.find_by_email(normalized_email) is not None:
            raise DuplicateAccountError("An account with this email already exists.")

        account = UserAccount(
            email=normalized_email,
            password_hash=hash_password(validated_password),
            first_name=normalized_first_name,
            last_name=normalized_last_name,
        )
        return self._user_repository.add(account)

    def authenticate(self, email: object, password: object) -> tuple[UserAccount, str]:
        """Verify credentials and return the account with a signed access token."""
        try:
            normalized_email = self._validate_email(email)
        except ValidationError as error:
            raise AuthenticationError("Email or password is incorrect.") from error

        if not isinstance(password, str) or not password:
            raise AuthenticationError("Email or password is incorrect.")

        account = self._user_repository.find_by_email(normalized_email)
        if account is None or not verify_password(password, account.password_hash):
            raise AuthenticationError("Email or password is incorrect.")

        token = create_access_token(
            account.id, self._jwt_secret, self._access_token_ttl_seconds
        )
        return account, token

    def get_authenticated_user(self, token: str) -> UserAccount:
        """Validate an access token and return its existing account."""
        user_id = decode_access_token(token, self._jwt_secret)
        account = self._user_repository.find_by_id(user_id)
        if account is None:
            raise AuthenticationError("The access token is invalid.")
        return account

    @staticmethod
    def _validate_email(email: object) -> str:
        """Normalize email input and reject malformed or overlong values."""
        if not isinstance(email, str):
            raise ValidationError("A valid email address is required.")
        normalized_email = email.strip().lower()
        if (
            len(normalized_email) > 320
            or EMAIL_PATTERN.fullmatch(normalized_email) is None
        ):
            raise ValidationError("A valid email address is required.")
        return normalized_email

    @staticmethod
    def _validate_name(value: object, field_name: str) -> str:
        """Trim and validate a required account name field."""
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} is required.")
        normalized_value = value.strip()
        if not normalized_value or len(normalized_value) > 100:
            raise ValidationError(
                f"{field_name} must contain between 1 and 100 characters."
            )
        return normalized_value

    @staticmethod
    def _validate_password(password: object) -> str:
        """Validate password length without altering meaningful whitespace."""
        if (
            not isinstance(password, str)
            or len(password) < MINIMUM_PASSWORD_LENGTH
            or len(password) > MAXIMUM_PASSWORD_LENGTH
        ):
            raise ValidationError("Password must contain between 8 and 128 characters.")
        return password

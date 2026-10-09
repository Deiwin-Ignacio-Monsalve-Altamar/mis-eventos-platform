"""Define the persistence operations required by account use cases."""

from typing import Protocol

from app.domain.entities.user_account import UserAccount


class UserRepository(Protocol):
    """Describe account lookup and persistence without binding the use case to SQLAlchemy."""

    def find_by_email(self, email: str) -> UserAccount | None:
        """Return an account matching a normalized email, if one exists."""
        ...

    def find_by_id(self, user_id: int) -> UserAccount | None:
        """Return an account matching a primary key, if one exists."""
        ...

    def add(self, account: UserAccount) -> UserAccount:
        """Persist a new account and return its database identity."""
        ...

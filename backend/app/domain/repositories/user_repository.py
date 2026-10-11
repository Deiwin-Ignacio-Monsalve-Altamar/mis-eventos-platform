"""Define the persistence operations required by account use cases."""

from typing import Protocol

from app.domain.entities.user_account import UserAccount
from app.domain.entities.user_summary import UserSummary


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

    def promote_attendee_to_organizer(self, user_id: int) -> UserAccount:
        """Promote an attendee or return an existing organizer unchanged."""
        ...

    def bootstrap_first_admin(self, email: str) -> UserAccount:
        """Initialize the first administrator if none exists."""
        ...

    def list_users(
        self, query: str | None, page: int, page_size: int
    ) -> tuple[list[UserSummary], int]:
        """Return one stable page of minimal user-directory fields."""
        ...

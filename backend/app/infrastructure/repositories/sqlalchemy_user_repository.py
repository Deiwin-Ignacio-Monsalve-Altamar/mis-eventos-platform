"""Persist domain user accounts with the application's SQLAlchemy session."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateAccountError
from app.domain.entities.user_account import UserAccount
from app.infrastructure.database.models import User


class SQLAlchemyUserRepository:
    """Adapt SQLAlchemy user rows to the domain account repository contract."""

    def __init__(self, session: Session) -> None:
        """Receive the active SQLAlchemy session used for account persistence."""
        self._session = session

    def find_by_email(self, email: str) -> UserAccount | None:
        """Load an account by its normalized email address."""
        user = self._session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        return self._to_account(user) if user is not None else None

    def find_by_id(self, user_id: int) -> UserAccount | None:
        """Load an account by its database identifier."""
        user = self._session.get(User, user_id)
        return self._to_account(user) if user is not None else None

    def add(self, account: UserAccount) -> UserAccount:
        """Insert a user row and translate email uniqueness violations."""
        user = User(
            email=account.email,
            password_hash=account.password_hash,
            first_name=account.first_name,
            last_name=account.last_name,
        )
        self._session.add(user)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            if self._is_email_conflict(error):
                raise DuplicateAccountError(
                    "An account with this email already exists."
                ) from error
            raise
        return self._to_account(user)

    @staticmethod
    def _to_account(user: User) -> UserAccount:
        """Map a persistence row to its domain account representation."""
        return UserAccount(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            first_name=user.first_name,
            last_name=user.last_name,
        )

    @staticmethod
    def _is_email_conflict(error: IntegrityError) -> bool:
        """Recognize unique-email failures across PostgreSQL and SQLite."""
        constraint_name = getattr(
            getattr(error.orig, "diag", None), "constraint_name", None
        )
        return constraint_name == "ix_users_email" or "users.email" in str(error.orig)

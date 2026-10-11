"""Persist domain user accounts with the application's SQLAlchemy session."""

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateAccountError,
    NotFoundError,
    RoleConflictError,
)
from app.domain.entities.user_account import UserAccount
from app.domain.entities.user_role import UserRole
from app.domain.entities.user_summary import UserSummary
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
            role=account.role.value,
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
            role=UserRole(user.role),
        )

    def promote_attendee_to_organizer(self, user_id: int) -> UserAccount:
        """Promote one attendee atomically and allow repeat requests idempotently."""
        user = self._session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )
        if user is None:
            raise NotFoundError("User not found.")
        if user.role == UserRole.ADMIN.value:
            raise RoleConflictError("Administrators cannot be promoted to organizer.")
        if user.role == UserRole.ATTENDEE.value:
            user.role = UserRole.ORGANIZER.value
            self._session.add(user)
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
                raise
        return self._to_account(user)

    def bootstrap_first_admin(self, email: str) -> UserAccount:
        """Set the first administrator under a transaction that serializes bootstraps."""
        try:
            first_user_id = self._session.scalar(
                select(User.id).order_by(User.id).limit(1)
            )
            if first_user_id is None:
                raise NotFoundError("The target user does not exist.")
            self._session.scalar(
                select(User).where(User.id == first_user_id).with_for_update()
            )
            admin_exists = self._session.scalar(
                select(func.count(User.id)).where(User.role == UserRole.ADMIN.value)
            )
            if admin_exists:
                raise RoleConflictError("An administrator is already initialized.")
            user = self._session.scalar(
                select(User).where(User.email == email).with_for_update()
            )
            if user is None:
                raise NotFoundError("The target user does not exist.")
            if user.role == UserRole.ADMIN.value:
                raise RoleConflictError("The target user is already an administrator.")
            user.role = UserRole.ADMIN.value
            self._session.add(user)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return self._to_account(user)

    def list_users(
        self, query: str | None, page: int, page_size: int
    ) -> tuple[list[UserSummary], int]:
        """Search users by name or email and select only public directory fields."""
        filters = []
        if query:
            full_name = User.first_name + " " + User.last_name
            filters.append(
                or_(
                    User.first_name.icontains(query, autoescape=True),
                    User.last_name.icontains(query, autoescape=True),
                    User.email.icontains(query, autoescape=True),
                    full_name.icontains(query, autoescape=True),
                )
            )
        total = self._session.scalar(select(func.count(User.id)).where(*filters)) or 0
        statement = (
            select(User.id, User.email, User.first_name, User.last_name, User.role)
            .where(*filters)
            .order_by(User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = self._session.execute(statement).all()
        users = [
            UserSummary(
                id=row.id,
                email=row.email,
                first_name=row.first_name,
                last_name=row.last_name,
                role=UserRole(row.role),
            )
            for row in rows
        ]
        return users, total

    @staticmethod
    def _is_email_conflict(error: IntegrityError) -> bool:
        """Recognize unique-email failures across PostgreSQL and SQLite."""
        constraint_name = getattr(
            getattr(error.orig, "diag", None), "constraint_name", None
        )
        return constraint_name == "ix_users_email" or "users.email" in str(error.orig)

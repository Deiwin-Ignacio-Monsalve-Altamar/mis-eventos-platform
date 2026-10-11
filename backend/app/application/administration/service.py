"""Coordinate privileged role transitions without trusting request fields."""

from app.core.exceptions import AuthorizationError, ValidationError
from app.domain.entities.user_account import UserAccount
from app.domain.entities.user_role import UserRole
from app.domain.repositories.user_repository import UserRepository


class AdministrationService:
    """Apply administrator-only role changes through the user repository."""

    def __init__(self, user_repository: UserRepository) -> None:
        """Receive the user repository used for atomic role changes."""
        self._user_repository = user_repository

    def promote_to_organizer(
        self, user_id: int, actor_id: int, actor_role: UserRole
    ) -> UserAccount:
        """Promote another attendee and reject self-promotion at the use-case boundary."""
        if actor_role is not UserRole.ADMIN:
            raise AuthorizationError("Only administrators can promote users.")
        if user_id == actor_id:
            raise ValidationError("Users cannot promote their own account.")
        return self._user_repository.promote_attendee_to_organizer(user_id)

    def bootstrap_first_admin(self, email: str) -> UserAccount:
        """Initialize an administrator from an explicit trusted CLI invocation."""
        if not isinstance(email, str) or not email.strip():
            raise ValidationError("A target email address is required.")
        return self._user_repository.bootstrap_first_admin(email.strip().lower())

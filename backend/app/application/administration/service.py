"""Coordinate privileged role transitions without trusting request fields."""

from app.application.dto.user_page import UserPage
from app.application.pagination import positive_integer
from app.core.exceptions import AuthorizationError, ValidationError
from app.domain.entities.user_account import UserAccount
from app.domain.entities.user_role import UserRole
from app.domain.repositories.user_repository import UserRepository
from app.settings import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAXIMUM_PAGE_NUMBER,
    MAXIMUM_PAGE_SIZE,
    MAXIMUM_SEARCH_LENGTH,
)


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

    def list_users(
        self, page: object, page_size: object, search_query: object
    ) -> UserPage:
        """Validate paging and search input before querying the user directory."""
        validated_page = positive_integer(
            page, "page", DEFAULT_PAGE, MAXIMUM_PAGE_NUMBER
        )
        validated_page_size = positive_integer(
            page_size, "page_size", DEFAULT_PAGE_SIZE, MAXIMUM_PAGE_SIZE
        )
        if search_query is not None and not isinstance(search_query, str):
            raise ValidationError("q must be a text search query.")
        normalized_query = search_query.strip() if isinstance(search_query, str) else ""
        if len(normalized_query) > MAXIMUM_SEARCH_LENGTH:
            raise ValidationError(
                f"q must contain at most {MAXIMUM_SEARCH_LENGTH} characters."
            )
        users, total = self._user_repository.list_users(
            normalized_query or None, validated_page, validated_page_size
        )
        return UserPage(tuple(users), validated_page, validated_page_size, total)

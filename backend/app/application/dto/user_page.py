"""Represent a paginated directory result for administrator user searches."""

from dataclasses import dataclass

from app.domain.entities.user_summary import UserSummary


@dataclass(frozen=True, slots=True)
class UserPage:
    """Carry the requested user summaries and stable pagination metadata."""

    users: tuple[UserSummary, ...]
    page: int
    page_size: int
    total: int

"""Represent the limited identity fields exposed by the user directory."""

from dataclasses import dataclass

from app.domain.entities.user_role import UserRole


@dataclass(frozen=True, slots=True)
class UserSummary:
    """Carry directory fields without credentials or other private account data."""

    id: int
    email: str
    first_name: str
    last_name: str
    role: UserRole

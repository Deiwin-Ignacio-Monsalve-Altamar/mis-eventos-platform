"""Represent account credentials and identity in the application domain."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserAccount:
    """Hold persisted account identity and its encoded password hash."""

    email: str
    password_hash: str
    first_name: str
    last_name: str
    id: int | None = None

"""Define the authorization roles assigned to user accounts."""

from enum import StrEnum


class UserRole(StrEnum):
    """Represent the supported account roles stored in the database."""

    ATTENDEE = "ATTENDEE"
    ORGANIZER = "ORGANIZER"
    ADMIN = "ADMIN"

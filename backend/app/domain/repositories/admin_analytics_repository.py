"""Define aggregate reads used by the administrator dashboard."""

from datetime import datetime
from typing import Protocol


class AdminAnalyticsRepository(Protocol):
    """Describe platform-wide analytics without exposing persistence details."""

    def dashboard(self, now: datetime, month_count: int) -> dict[str, object]:
        """Return platform counts, recent monthly trends, and organizer activity."""
        ...

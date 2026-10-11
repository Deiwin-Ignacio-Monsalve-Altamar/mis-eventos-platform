"""Coordinate administrator analytics and normalize monthly trend output."""

from datetime import UTC, datetime

from app.domain.repositories.admin_analytics_repository import AdminAnalyticsRepository


class AdminAnalyticsService:
    """Provide bounded platform-wide metrics to administrator-only routes."""

    def __init__(self, repository: AdminAnalyticsRepository) -> None:
        """Receive the request-scoped aggregate repository."""
        self._repository = repository

    def dashboard(self, now: datetime | None = None) -> dict[str, object]:
        """Return real platform metrics for the current and five prior months."""
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Dashboard time must be timezone-aware.")
        return self._repository.dashboard(timestamp.astimezone(UTC), month_count=6)

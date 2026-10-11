"""Read bounded platform analytics through aggregate SQLAlchemy queries."""

from datetime import datetime

from sqlalchemy import case, distinct, extract, func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Event, Registration, User


class SQLAlchemyAdminAnalyticsRepository:
    """Query platform counts and activity without loading full user records."""

    def __init__(self, session: Session) -> None:
        """Receive the active SQLAlchemy session."""
        self._session = session

    def dashboard(self, now: datetime, month_count: int) -> dict[str, object]:
        """Return role, event, registration, monthly, and organizer aggregates."""
        role_counts = {role: 0 for role in ("ATTENDEE", "ORGANIZER", "ADMIN")}
        for role, count in self._session.execute(
            select(User.role, func.count(User.id)).group_by(User.role)
        ):
            role_counts[role] = int(count)

        active_status = Event.status.in_(("draft", "published"))
        event_row = self._session.execute(
            select(
                func.count(Event.id).label("total"),
                func.sum(case((Event.status == "draft", 1), else_=0)).label("draft"),
                func.sum(case((Event.status == "published", 1), else_=0)).label(
                    "published"
                ),
                func.sum(case((Event.status == "cancelled", 1), else_=0)).label(
                    "cancelled"
                ),
                func.sum(case((Event.status == "completed", 1), else_=0)).label(
                    "completed"
                ),
                func.sum(
                    case((active_status & (Event.starts_at > now), 1), else_=0)
                ).label("upcoming"),
                func.sum(
                    case(
                        (
                            active_status
                            & (Event.starts_at <= now)
                            & (Event.ends_at > now),
                            1,
                        ),
                        else_=0,
                    )
                ).label("active"),
                func.sum(
                    case(
                        (
                            (Event.status == "completed")
                            | ((Event.ends_at <= now) & (Event.status != "cancelled")),
                            1,
                        ),
                        else_=0,
                    )
                ).label("finished"),
            )
        ).one()
        event_counts = {
            key: int(value or 0) for key, value in event_row._mapping.items()
        }

        registration_row = self._session.execute(
            select(
                func.count(Registration.id).label("total"),
                func.sum(case((Registration.status == "registered", 1), else_=0)).label(
                    "active"
                ),
                func.sum(case((Registration.status == "cancelled", 1), else_=0)).label(
                    "cancelled"
                ),
            )
        ).one()
        registration_counts = {
            key: int(value or 0) for key, value in registration_row._mapping.items()
        }

        creation_trend = self._monthly_counts(Event.created_at, month_count, now)
        registration_trend = self._monthly_counts(
            Registration.registered_at, month_count, now
        )
        organizer_activity = self._organizer_activity()
        return {
            "summary": {
                "users": {
                    "total": sum(role_counts.values()),
                    "role_counts": role_counts,
                },
                "events": {
                    "total": event_counts["total"],
                    "status_counts": {
                        key: event_counts[key]
                        for key in ("draft", "published", "cancelled", "completed")
                    },
                    "upcoming": event_counts["upcoming"],
                    "active": event_counts["active"],
                    "finished": event_counts["finished"],
                },
                "registrations": registration_counts,
            },
            "event_creation_by_month": creation_trend,
            "registration_activity_by_month": registration_trend,
            "organizer_activity": organizer_activity,
        }

    def _monthly_counts(
        self, column, month_count: int, now: datetime
    ) -> list[dict[str, int | str]]:
        """Return a contiguous month series, including zero-count months."""
        first_month = _month_start(now, month_count - 1)
        next_month = _month_start(now, -1)
        rows = self._session.execute(
            select(extract("year", column), extract("month", column), func.count())
            .where(column >= first_month, column < next_month)
            .group_by(extract("year", column), extract("month", column))
        )
        counts = {(int(year), int(month)): int(count) for year, month, count in rows}
        first = _month_start(now, month_count - 1)
        result = []
        for offset in range(month_count):
            year, month = _add_months(first.year, first.month, offset)
            result.append(
                {
                    "month": f"{year:04d}-{month:02d}",
                    "count": counts.get((year, month), 0),
                }
            )
        return result

    def _organizer_activity(self) -> list[dict[str, int | str]]:
        """Summarize event and active enrollment counts per organizer in one query."""
        statement = (
            select(
                User.id.label("user_id"),
                User.first_name,
                User.last_name,
                func.count(distinct(Event.id)).label("event_count"),
                func.count(distinct(Registration.id)).label("active_registrations"),
            )
            .select_from(User)
            .outerjoin(Event, Event.created_by_id == User.id)
            .outerjoin(
                Registration,
                (Registration.event_id == Event.id)
                & (Registration.status == "registered"),
            )
            .where(User.role == "ORGANIZER")
            .group_by(User.id, User.first_name, User.last_name)
            .order_by(func.count(distinct(Event.id)).desc(), User.id.asc())
            .limit(10)
        )
        return [
            {
                "user_id": row.user_id,
                "name": f"{row.first_name} {row.last_name}".strip(),
                "event_count": int(row.event_count),
                "active_registrations": int(row.active_registrations),
            }
            for row in self._session.execute(statement)
        ]


def _month_start(now: datetime, months_ago: int) -> datetime:
    """Return the first day of the requested month relative to a timestamp."""
    year, month = _add_months(now.year, now.month, -months_ago)
    return now.replace(
        year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
    )


def _add_months(year: int, month: int, offset: int) -> tuple[int, int]:
    """Shift a year and month pair by a signed number of calendar months."""
    absolute = year * 12 + month - 1 + offset
    return absolute // 12, absolute % 12 + 1

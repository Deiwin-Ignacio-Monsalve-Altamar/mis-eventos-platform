"""Verify profile analytics and recommendations use aggregate owner-safe queries."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.entities.user_role import UserRole
from app.infrastructure.database.models import Event, EventSession, Registration, User
from app.infrastructure.repositories.sqlalchemy_admin_analytics_repository import (
    SQLAlchemyAdminAnalyticsRepository,
)
from app.infrastructure.repositories.sqlalchemy_event_repository import (
    SQLAlchemyEventRepository,
)


def make_user(email: str, role: UserRole) -> User:
    """Build a minimal persisted test identity."""
    local = email.split("@", maxsplit=1)[0]
    return User(
        email=email,
        password_hash="test-only",
        first_name=local.title(),
        last_name="Example",
        role=role.value,
    )


def make_event(
    owner_id: int,
    title: str,
    starts_at: datetime,
    status="published",
    capacity=10,
    created_at=None,
) -> Event:
    """Build an event row with explicit time and status values."""
    return Event(
        created_by_id=owner_id,
        title=title,
        description="Description",
        location="Bogotá",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=2),
        capacity=capacity,
        status=status,
        created_at=created_at or datetime.now(UTC),
    )


def test_admin_dashboard_reports_real_role_event_registration_and_trend_counts():
    """Aggregate platform data while preserving zeros in the six-month series."""
    engine = create_engine("sqlite://")
    User.metadata.create_all(engine)
    now = datetime(2030, 6, 15, tzinfo=UTC)
    with Session(engine) as session:
        attendee = make_user("attendee@example.test", UserRole.ATTENDEE)
        organizer = make_user("organizer@example.test", UserRole.ORGANIZER)
        admin = make_user("admin@example.test", UserRole.ADMIN)
        session.add_all([attendee, organizer, admin])
        session.flush()
        upcoming = make_event(
            organizer.id,
            "Upcoming",
            now + timedelta(days=10),
            created_at=datetime(2030, 6, 1, tzinfo=UTC),
        )
        finished = make_event(
            organizer.id,
            "Finished",
            now - timedelta(days=10),
            status="completed",
            created_at=datetime(2030, 5, 1, tzinfo=UTC),
        )
        session.add_all([upcoming, finished])
        session.flush()
        session.add_all(
            [
                Registration(
                    user_id=attendee.id, event_id=upcoming.id, status="registered"
                ),
                Registration(
                    user_id=attendee.id, event_id=finished.id, status="cancelled"
                ),
            ]
        )
        session.commit()

        result = SQLAlchemyAdminAnalyticsRepository(session).dashboard(
            now, month_count=6
        )

        assert result["summary"]["users"] == {
            "total": 3,
            "role_counts": {"ATTENDEE": 1, "ORGANIZER": 1, "ADMIN": 1},
        }
        assert result["summary"]["events"]["total"] == 2
        assert result["summary"]["events"]["upcoming"] == 1
        assert result["summary"]["events"]["finished"] == 1
        assert result["summary"]["registrations"] == {
            "total": 2,
            "active": 1,
            "cancelled": 1,
        }
        assert result["event_creation_by_month"] == [
            {"month": "2030-01", "count": 0},
            {"month": "2030-02", "count": 0},
            {"month": "2030-03", "count": 0},
            {"month": "2030-04", "count": 0},
            {"month": "2030-05", "count": 1},
            {"month": "2030-06", "count": 1},
        ]
        assert result["organizer_activity"][0]["event_count"] == 2
        assert result["organizer_activity"][0]["active_registrations"] == 1
    engine.dispose()


def test_recommendations_exclude_enrolled_full_draft_and_past_events():
    """Only published future events with free seats and no active user registration qualify."""
    engine = create_engine("sqlite://")
    User.metadata.create_all(engine)
    now = datetime(2030, 6, 15, tzinfo=UTC)
    with Session(engine) as session:
        attendee = make_user("attendee@example.test", UserRole.ATTENDEE)
        other = make_user("other@example.test", UserRole.ATTENDEE)
        organizer = make_user("organizer@example.test", UserRole.ORGANIZER)
        session.add_all([attendee, other, organizer])
        session.flush()
        enrolled = make_event(
            organizer.id, "Enrolled", now + timedelta(days=1), capacity=1
        )
        full = make_event(organizer.id, "Full", now + timedelta(days=2), capacity=1)
        draft = make_event(
            organizer.id, "Draft", now + timedelta(days=3), status="draft"
        )
        past = make_event(organizer.id, "Past", now - timedelta(days=3))
        available = make_event(
            organizer.id, "Available", now + timedelta(days=4), capacity=4
        )
        session.add_all([enrolled, full, draft, past, available])
        session.flush()
        session.add_all(
            [
                Registration(
                    user_id=attendee.id, event_id=enrolled.id, status="registered"
                ),
                Registration(user_id=other.id, event_id=full.id, status="registered"),
            ]
        )
        session.commit()

        results = SQLAlchemyEventRepository(session).recommendations_for_user(
            attendee.id, now, limit=8
        )

        assert [(event.title, seats) for event, seats in results] == [("Available", 4)]
    engine.dispose()


def test_owner_event_activity_counts_only_events_created_by_requested_user():
    """Scope registration and session counts to the authenticated creator's events."""
    engine = create_engine("sqlite://")
    User.metadata.create_all(engine)
    now = datetime(2030, 6, 15, tzinfo=UTC)
    with Session(engine) as session:
        owner = make_user("owner@example.test", UserRole.ORGANIZER)
        other_owner = make_user("other@example.test", UserRole.ORGANIZER)
        attendee = make_user("attendee@example.test", UserRole.ATTENDEE)
        session.add_all([owner, other_owner, attendee])
        session.flush()
        own_event = make_event(owner.id, "Own", now + timedelta(days=2))
        foreign_event = make_event(other_owner.id, "Foreign", now + timedelta(days=1))
        session.add_all([own_event, foreign_event])
        session.flush()
        session.add_all(
            [
                EventSession(
                    event_id=own_event.id,
                    title="Session",
                    starts_at=now + timedelta(days=2),
                    ends_at=now + timedelta(days=2, hours=1),
                    capacity=10,
                ),
                Registration(
                    user_id=attendee.id, event_id=own_event.id, status="registered"
                ),
                Registration(
                    user_id=attendee.id, event_id=foreign_event.id, status="registered"
                ),
            ]
        )
        session.commit()

        repository = SQLAlchemyEventRepository(session)
        metrics = repository.event_activity_by_creator(owner.id, now, limit=6)

        assert [item["event"].title for item in metrics] == ["Own"]
        assert metrics[0]["active_registrations"] == 1
        assert metrics[0]["session_count"] == 1
        assert repository.active_registration_count_by_creator(owner.id) == 1
    engine.dispose()

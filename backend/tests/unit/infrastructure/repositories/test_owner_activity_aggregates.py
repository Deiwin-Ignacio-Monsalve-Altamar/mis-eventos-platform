"""Verify owner and attendee dashboards against isolated SQLite records."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.extensions import db
from app.infrastructure.database.models import Event, Registration, User
from app.infrastructure.repositories.sqlalchemy_event_registration_repository import (
    SQLAlchemyEventRegistrationRepository,
)
from app.infrastructure.repositories.sqlalchemy_event_repository import (
    SQLAlchemyEventRepository,
)


def test_activity_aggregates_isolate_users_and_apply_date_boundaries():
    """Count event and registration activity independently at an exact UTC instant."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    db.Model.metadata.create_all(engine)
    now = datetime(2030, 1, 1, 12, tzinfo=UTC)

    try:
        with Session(engine) as session:
            creator = User(
                id=1,
                email="creator@example.test",
                password_hash="hash",
                first_name="Creator",
                last_name="One",
            )
            attendee = User(
                id=2,
                email="attendee@example.test",
                password_hash="hash",
                first_name="Attendee",
                last_name="Two",
            )
            other = User(
                id=3,
                email="other@example.test",
                password_hash="hash",
                first_name="Other",
                last_name="Three",
            )
            events = [
                Event(
                    id=10,
                    created_by_id=1,
                    title="Upcoming",
                    starts_at=now + timedelta(hours=1),
                    ends_at=now + timedelta(hours=2),
                    capacity=10,
                    status="published",
                ),
                Event(
                    id=11,
                    created_by_id=1,
                    title="Active",
                    starts_at=now - timedelta(hours=1),
                    ends_at=now + timedelta(hours=1),
                    capacity=10,
                    status="draft",
                ),
                Event(
                    id=12,
                    created_by_id=1,
                    title="Ended at boundary",
                    starts_at=now - timedelta(hours=2),
                    ends_at=now,
                    capacity=10,
                    status="published",
                ),
                Event(
                    id=13,
                    created_by_id=1,
                    title="Cancelled",
                    starts_at=now - timedelta(days=2),
                    ends_at=now - timedelta(days=1),
                    capacity=10,
                    status="cancelled",
                ),
                Event(
                    id=14,
                    created_by_id=1,
                    title="Completed status",
                    starts_at=now + timedelta(days=1),
                    ends_at=now + timedelta(days=1, hours=1),
                    capacity=10,
                    status="completed",
                ),
                Event(
                    id=15,
                    created_by_id=3,
                    title="Another creator",
                    starts_at=now + timedelta(days=1),
                    ends_at=now + timedelta(days=1, hours=1),
                    capacity=10,
                    status="published",
                ),
            ]
            registrations = [
                Registration(id=20, user_id=2, event_id=10, status="registered"),
                Registration(id=21, user_id=2, event_id=12, status="registered"),
                Registration(id=22, user_id=2, event_id=15, status="cancelled"),
                Registration(id=23, user_id=3, event_id=10, status="registered"),
            ]
            session.add_all([creator, attendee, other, *events, *registrations])
            session.commit()

            event_summary = SQLAlchemyEventRepository(session).dashboard_counts(1, now)
            empty_event_summary = SQLAlchemyEventRepository(session).dashboard_counts(
                2, now
            )
            attendance_summary = SQLAlchemyEventRegistrationRepository(
                session
            ).summary_by_user(2, now)
            other_attendance_summary = SQLAlchemyEventRegistrationRepository(
                session
            ).summary_by_user(3, now)
            registration_repository = SQLAlchemyEventRegistrationRepository(session)
            active_event_capacity = registration_repository.capacity_for_event(10)
            cancelled_only_capacity = registration_repository.capacity_for_event(15)
            missing_event_capacity = registration_repository.capacity_for_event(999)

            assert event_summary == {
                "total": 5,
                "draft": 1,
                "published": 2,
                "cancelled": 1,
                "completed": 1,
                "upcoming": 1,
                "active": 1,
                "finished": 2,
            }
            assert empty_event_summary["total"] == 0
            assert attendance_summary == {
                "total": 3,
                "active": 2,
                "upcoming": 1,
                "past": 1,
                "cancelled": 1,
            }
            assert other_attendance_summary == {
                "total": 1,
                "active": 1,
                "upcoming": 1,
                "past": 0,
                "cancelled": 0,
            }
            assert active_event_capacity == (10, 2)
            assert cancelled_only_capacity == (10, 0)
            assert missing_event_capacity is None

            assert registration_repository.cancel(10, 2) is True
            assert registration_repository.capacity_for_event(10) == (10, 1)
            after_cancel = registration_repository.summary_by_user(2, now)
            assert after_cancel["active"] == 1
            assert after_cancel["cancelled"] == 2

    finally:
        db.Model.metadata.drop_all(engine)
        engine.dispose()

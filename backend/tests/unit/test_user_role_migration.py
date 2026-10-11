"""Verify the role migration classifies owners and reverses without deleting rows."""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_role_migration_classifies_event_owners_and_downgrades(monkeypatch):
    """Classify owners as organizers, retain attendees, and never grant admin."""
    migration = importlib.import_module(
        "migrations.versions.e4a91c6d2f70_add_user_roles"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
        )
        connection.execute(
            text("CREATE TABLE events (id INTEGER PRIMARY KEY, created_by_id INTEGER)")
        )
        connection.execute(
            text(
                "INSERT INTO users (id, email) VALUES (1, 'owner@example.test'), (2, 'attendee@example.test')"
            )
        )
        connection.execute(text("INSERT INTO events (id, created_by_id) VALUES (1, 1)"))
        monkeypatch.setattr(
            migration,
            "op",
            Operations(MigrationContext.configure(connection)),
        )

        migration.upgrade()
        roles = dict(connection.execute(text("SELECT id, role FROM users")).all())

        assert roles == {1: "ORGANIZER", 2: "ATTENDEE"}
        assert "ADMIN" not in roles.values()

        migration.downgrade()
        assert "role" not in {
            column["name"] for column in inspect(connection).get_columns("users")
        }
        assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 2
        assert connection.execute(text("SELECT COUNT(*) FROM events")).scalar_one() == 1
    engine.dispose()

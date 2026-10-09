"""Add optimistic concurrency versions to events and sessions.

Revision ID: d17f3a6bc920
Revises: c4e8b7a219d0
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d17f3a6bc920"
down_revision: str | Sequence[str] | None = "c4e8b7a219d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Initialize existing event and session rows at version one."""
    op.add_column(
        "events",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "event_sessions",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_check_constraint("ck_events_version_positive", "events", "version > 0")
    op.create_check_constraint(
        "ck_event_sessions_version_positive", "event_sessions", "version > 0"
    )


def downgrade() -> None:
    """Remove version constraints and columns from events and sessions."""
    op.drop_constraint("ck_event_sessions_version_positive", "event_sessions")
    op.drop_constraint("ck_events_version_positive", "events")
    op.drop_column("event_sessions", "version")
    op.drop_column("events", "version")

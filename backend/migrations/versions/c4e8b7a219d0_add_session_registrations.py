"""Add attendee registrations for scheduled sessions.

Revision ID: c4e8b7a219d0
Revises: 91c0b2a4d6e8
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8b7a219d0"
down_revision: str | Sequence[str] | None = "91c0b2a4d6e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create session enrollment rows linked to sessions and event registrations."""
    op.create_table(
        "session_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="ck_session_registrations_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"], ["registrations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["event_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "registration_id",
            name="uq_session_registrations_session_registration",
        ),
    )
    op.create_index(
        op.f("ix_session_registrations_registration_id"),
        "session_registrations",
        ["registration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_session_registrations_session_id"),
        "session_registrations",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_session_registrations_status"),
        "session_registrations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Remove session enrollment rows and their indexes."""
    op.drop_index(
        op.f("ix_session_registrations_status"), table_name="session_registrations"
    )
    op.drop_index(
        op.f("ix_session_registrations_session_id"), table_name="session_registrations"
    )
    op.drop_index(
        op.f("ix_session_registrations_registration_id"),
        table_name="session_registrations",
    )
    op.drop_table("session_registrations")

"""Add nullable creator attribution to existing events.

Revision ID: 91c0b2a4d6e8
Revises: a10ffe923ac3
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "91c0b2a4d6e8"
down_revision: str | Sequence[str] | None = "a10ffe923ac3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add optional event creator attribution without disrupting existing rows."""
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("created_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_events_created_by_id_users",
            "users",
            ["created_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_events_created_by_id", ["created_by_id"])


def downgrade() -> None:
    """Remove event creator attribution."""
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_index("ix_events_created_by_id")
        batch_op.drop_constraint("fk_events_created_by_id_users", type_="foreignkey")
        batch_op.drop_column("created_by_id")

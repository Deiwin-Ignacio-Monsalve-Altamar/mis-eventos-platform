"""Add user roles and classify existing event owners as organizers.

Revision ID: e4a91c6d2f70
Revises: d17f3a6bc920
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4a91c6d2f70"
down_revision: str | Sequence[str] | None = "d17f3a6bc920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a safe attendee default and preserve current event-owner access."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=20),
                server_default=sa.text("'ATTENDEE'"),
                nullable=False,
            )
        )
    op.execute(
        sa.text(
            "UPDATE users SET role = 'ORGANIZER' "
            "WHERE EXISTS ("
            "SELECT 1 FROM events WHERE events.created_by_id = users.id"
            ")"
        )
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_check_constraint(
            "ck_users_role_valid", "role IN ('ATTENDEE', 'ORGANIZER', 'ADMIN')"
        )


def downgrade() -> None:
    """Remove the role column while leaving account and event data intact."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role_valid", type_="check")
        batch_op.drop_column("role")

"""single-role RBAC

Enforces "one user = one active role".

Existing installs may have users with several active role assignments
(``expires_at IS NULL``). Those conflicts are resolved safely *without losing
history*: for each user the earliest active assignment is kept and every extra
assignment is expired (``expires_at = now()``) rather than deleted. A partial
unique index on ``user_role_assignments.user_id`` (``WHERE expires_at IS NULL``)
then guarantees at most one active role per user, including under concurrent
writes.

Revision ID: f1a2b3c4d5e6
Revises: e9f0a1b2c3d4
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep the earliest active assignment per user; expire the rest (history kept).
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id
                           ORDER BY (expires_at IS NULL) DESC, id
                       ) AS rn
                FROM user_role_assignments
                WHERE expires_at IS NULL OR expires_at > now()
            )
            UPDATE user_role_assignments AS ura
            SET expires_at = now()
            FROM ranked
            WHERE ura.id = ranked.id AND ranked.rn > 1
            """
        )
    )
    op.create_index(
        "uq_user_role_assignments_active_user",
        "user_role_assignments",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("expires_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_role_assignments_active_user", table_name="user_role_assignments")

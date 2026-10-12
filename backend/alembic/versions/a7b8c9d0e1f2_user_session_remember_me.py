"""user session remember me

Adds the ``remember_me`` flag to ``user_sessions``. Sessions created with
"Remember me" persist across browser restarts and keep the configured refresh
lifetime; all other sessions use browser-session cookies and a short
server-enforced deadline.

Revision ID: a7b8c9d0e1f2
Revises: c9d0e1f2a3b4
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column("remember_me", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_sessions", "remember_me")

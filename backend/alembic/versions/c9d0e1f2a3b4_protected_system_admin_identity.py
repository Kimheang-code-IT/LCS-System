"""protected system administrator identity

Adds a stable machine identifier to the built-in administrator account. For an
existing installation, the oldest account ever assigned Platform Administrator
is treated as the original setup account. Future application logic uses only this
identifier—not username, email, display name, or user code—for protection.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("system_identity", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_users_system_identity",
        "users",
        ["system_identity"],
    )
    op.execute(
        """
        UPDATE users
        SET system_identity = 'DEFAULT_SYSTEM_ADMIN'
        WHERE id = (
            SELECT MIN(ura.user_id)
            FROM user_role_assignments AS ura
            JOIN roles AS r ON r.id = ura.role_id
            WHERE r.code = 'PLATFORM_ADMIN'
        )
        """
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_system_identity", "users", type_="unique")
    op.drop_column("users", "system_identity")

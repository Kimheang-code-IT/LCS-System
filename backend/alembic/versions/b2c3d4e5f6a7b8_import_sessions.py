"""Durable import sessions: a validated preview survives a backend restart.

Replaces the in-memory session store. The claim is single-use: the commit
deletes the row atomically, so a repeated confirmation finds nothing.

Revision ID: b2c3d4e5f6a7b8
Revises: 46ce79ab12df
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7b8"
down_revision: str | None = "46ce79ab12df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rows_data", sa.JSON(), nullable=False),
        sa.Column("preview_data", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_import_sessions_expires_at", "import_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_import_sessions_expires_at", table_name="import_sessions")
    op.drop_table("import_sessions")

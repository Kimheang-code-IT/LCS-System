"""Stable sessions and consumed refresh credentials.

Revision ID: 24ac57ef90bd
Revises: 12ab34cd56ef
"""
import sqlalchemy as sa

from alembic import op

revision: str = "24ac57ef90bd"
down_revision: str | None = "12ab34cd56ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_sessions", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE user_sessions SET last_activity_at = created_at WHERE last_activity_at IS NULL")
    op.create_table(
        "used_refresh_tokens",
        sa.Column("token_hash", sa.String(128), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_used_refresh_tokens_session_id", "used_refresh_tokens", ["session_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS used_refresh_tokens")
    op.drop_column("user_sessions", "last_activity_at")

"""archive recycle bin

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SOFT_DELETE_TABLES = (
    "business_parties",
    "places",
    "trade_directions",
    "container_types",
    "transport_types",
    "transport_assets",
    "fee_types",
    "module_records",
)


def upgrade() -> None:
    op.create_table(
        "archive_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("record_reference", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("original_owner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("restored_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hard_deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("hard_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["original_owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["restored_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hard_deleted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_archive_records_entity"),
    )
    for column in ("entity_type", "entity_id", "status", "deleted_by_user_id", "deleted_at"):
        op.create_index(f"ix_archive_records_{column}", "archive_records", [column], unique=False)

    for table in SOFT_DELETE_TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_deleted_by_user_id_users",
            table,
            "users",
            ["deleted_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"], unique=False)
        op.create_index(f"ix_{table}_deleted_by_user_id", table, ["deleted_by_user_id"], unique=False)


def downgrade() -> None:
    for table in reversed(SOFT_DELETE_TABLES):
        op.drop_index(f"ix_{table}_deleted_by_user_id", table_name=table)
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_constraint(f"fk_{table}_deleted_by_user_id_users", table, type_="foreignkey")
        op.drop_column(table, "deleted_by_user_id")
        op.drop_column(table, "deleted_at")
    op.drop_table("archive_records")

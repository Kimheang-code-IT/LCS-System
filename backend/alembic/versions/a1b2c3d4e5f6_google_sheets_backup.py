"""google sheets backup tables

Revision ID: a1b2c3d4e5f6
Revises: b7f1c2a9d4e0
Create Date: 2026-09-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "b7f1c2a9d4e0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tables_total", sa.Integer(), nullable=False),
        sa.Column("tables_processed", sa.Integer(), nullable=False),
        sa.Column("rows_scanned", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("rows_skipped", sa.Integer(), nullable=False),
        sa.Column("rows_failed", sa.Integer(), nullable=False),
        sa.Column("spreadsheet_id", sa.String(length=255), nullable=True),
        sa.Column("triggered_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], name=op.f("fk_backup_runs_triggered_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backup_runs")),
    )
    op.create_index(op.f("ix_backup_runs_status"), "backup_runs", ["status"], unique=False)

    op.create_table(
        "backup_records",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=False),
        sa.Column("backup_version", sa.BigInteger(), nullable=False),
        sa.Column("backup_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_kind", sa.String(length=16), nullable=False),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["backup_runs.id"], name=op.f("fk_backup_records_run_id_backup_runs"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backup_records")),
        sa.UniqueConstraint("table_name", "record_id", "row_hash", name="uq_backup_records_version"),
    )
    op.create_index(op.f("ix_backup_records_table_name"), "backup_records", ["table_name"], unique=False)
    op.create_index(op.f("ix_backup_records_synced"), "backup_records", ["synced"], unique=False)
    op.create_index("ix_backup_records_table_record", "backup_records", ["table_name", "record_id"], unique=False)

    op.create_table(
        "backup_states",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=False),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.Column("backup_version", sa.BigInteger(), nullable=False),
        sa.Column("last_backup_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backup_states")),
        sa.UniqueConstraint("table_name", "record_id", name="uq_backup_states_record"),
    )
    op.create_index(op.f("ix_backup_states_table_name"), "backup_states", ["table_name"], unique=False)

    op.create_table(
        "backup_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["backup_runs.id"], name=op.f("fk_backup_logs_run_id_backup_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backup_logs")),
    )
    op.create_index(op.f("ix_backup_logs_run_id"), "backup_logs", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_backup_logs_run_id"), table_name="backup_logs")
    op.drop_table("backup_logs")
    op.drop_index(op.f("ix_backup_states_table_name"), table_name="backup_states")
    op.drop_table("backup_states")
    op.drop_index("ix_backup_records_table_record", table_name="backup_records")
    op.drop_index(op.f("ix_backup_records_synced"), table_name="backup_records")
    op.drop_index(op.f("ix_backup_records_table_name"), table_name="backup_records")
    op.drop_table("backup_records")
    op.drop_index(op.f("ix_backup_runs_status"), table_name="backup_runs")
    op.drop_table("backup_runs")

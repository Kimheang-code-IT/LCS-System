"""Multi-provider storage: file replicas and storage jobs.

Two small additive tables back the Storage & Backup settings feature:

* ``storage_replicas`` — one row per (attachment, backup provider) copy. A
  ``PENDING`` row is a durable backup request: the scheduler sweeps it and
  flips it to ``ACTIVE`` only after a size/checksum verification, so a crash
  or a temporarily unavailable backup provider never loses the intent.
* ``storage_jobs``     — progress for interactive management runs (backup
  sweeps, historical-file migrations, restores) so the UI can poll progress
  and a restart can resume an interrupted job.

Attachment file metadata already exists in ``attachments`` (storage_provider,
storage_key, checksum, file_size_bytes); no columns are added or changed.
Historical 'local' rows keep working from disk; MinIO-era rows are soft-deleted
by the later b1c2d3e4f5a6 migration (MinIO objects are gone).

Revision ID: a0b1c2d3e4f5
Revises: b7c8d9e0f1a2
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storage_replicas",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("attachment_id", sa.BigInteger(), nullable=False),
        sa.Column("backup_provider", sa.String(length=32), nullable=False),
        sa.Column("backup_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_by_migration", sa.Boolean(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], name=op.f("fk_storage_replicas_attachment_id_attachments"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_replicas")),
        sa.UniqueConstraint("attachment_id", "backup_provider", name="uq_storage_replicas_target"),
    )
    op.create_index(op.f("ix_storage_replicas_status"), "storage_replicas", ["status"], unique=False)
    op.create_table(
        "storage_jobs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("job_type", sa.String(length=16), nullable=False),
        sa.Column("target_provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("started_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"], name=op.f("fk_storage_jobs_started_by_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_jobs")),
    )
    op.create_index(op.f("ix_storage_jobs_job_type"), "storage_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_storage_jobs_status"), "storage_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_storage_jobs_status"), table_name="storage_jobs")
    op.drop_index(op.f("ix_storage_jobs_job_type"), table_name="storage_jobs")
    op.drop_table("storage_jobs")
    op.drop_index(op.f("ix_storage_replicas_status"), table_name="storage_replicas")
    op.drop_table("storage_replicas")

"""Persistence for the multi-provider storage feature.

* :class:`StorageReplica` — one copy of one attachment on one backup provider
  (also used by migration, which is a controlled replication to the new target).
* :class:`StorageJob`     — one management job (backup sweep, migration, restore)
  with progress counters, so long-running work survives a page reload.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin


class StorageReplica(PKMixin, TimestampMixin, Base):
    """A verified copy of an attachment on a non-primary provider.

    ``status`` PENDING → ACTIVE: PENDING is a durable backup job (the file is
    not yet replicated), so pending copies can be detected and retried.
    """

    __tablename__ = "storage_replicas"
    __table_args__ = (
        UniqueConstraint("attachment_id", "backup_provider", name="uq_storage_replicas_target"),
        Index("ix_storage_replicas_status", "status"),
    )

    attachment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False
    )
    backup_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    backup_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_migration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StorageJob(PKMixin, TimestampMixin, Base):
    """One management job: file-backup sweep, migration or restore.

    ``updated_at`` (TimestampMixin) doubles as the heartbeat the scheduler uses
    to reset jobs left RUNNING by a restart.
    """

    __tablename__ = "storage_jobs"

    job_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    target_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

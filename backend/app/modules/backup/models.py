"""Persistence for the Google Sheets backup feature.

The tables here are append-only journals. Rows are never deleted by the backup
process, so a complete history of every record version is preserved and can be
restored after data loss.

* :class:`BackupRun`   — one job execution (manual or scheduled) with counters.
* :class:`BackupRecord` — one immutable version of one database row.
* :class:`BackupState`  — the latest known hash per row, used to detect changes.
* :class:`BackupLog`    — structured success/failure log lines per run.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin, utcnow
from app.core.types import JSONType


class BackupRun(PKMixin, TimestampMixin, Base):
    __tablename__ = "backup_runs"

    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    tables_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tables_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spreadsheet_id: Mapped[str | None] = mapped_column(String(255))
    triggered_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    message: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)


class BackupRecord(PKMixin, TimestampMixin, Base):
    __tablename__ = "backup_records"
    __table_args__ = (
        UniqueConstraint("table_name", "record_id", "row_hash", name="uq_backup_records_version"),
        Index("ix_backup_records_table_record", "table_name", "record_id"),
    )

    run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("backup_runs.id", ondelete="SET NULL"))
    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    backup_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    backup_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    change_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="insert")
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackupState(PKMixin, TimestampMixin, Base):
    __tablename__ = "backup_states"
    __table_args__ = (UniqueConstraint("table_name", "record_id", name="uq_backup_states_record"),)

    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    backup_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    last_backup_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BackupLog(PKMixin, Base):
    __tablename__ = "backup_logs"

    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("backup_runs.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    table_name: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

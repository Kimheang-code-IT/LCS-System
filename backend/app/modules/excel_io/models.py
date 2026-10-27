"""Excel import bookkeeping: history plus durable pending sessions.

`ImportJob` is the permanent history row (one per confirmed/failed batch).
`ImportSession` holds a not-yet-committed preview so the confirm step survives
a backend restart; workbook contents live as JSON and the row is deleted the
moment it is claimed, so nothing sensitive lingers beyond the TTL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin


class ImportJob(PKMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"

    module: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    #: VALIDATED (confirmed session), COMPLETED, FAILED, CANCELLED.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportSession(PKMixin, TimestampMixin, Base):
    """A validated, not-yet-committed import preview (single-use claim row)."""

    __tablename__ = "import_sessions"

    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Parsed workbook rows and the validated preview. Deleted with the claim.
    rows_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    preview_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

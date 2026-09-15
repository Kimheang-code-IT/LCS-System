from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, utcnow
from app.core.types import JSONType


class AuditEvent(PKMixin, Base):
    __tablename__ = "audit_events"

    organization_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(BigInteger)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    before_json: Mapped[dict | None] = mapped_column(JSONType)
    after_json: Mapped[dict | None] = mapped_column(JSONType)
    metadata_json: Mapped[dict | None] = mapped_column(JSONType)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

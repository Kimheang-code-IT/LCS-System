from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin, utcnow
from app.core.types import JSONType


class TelegramLink(Base):
    __tablename__ = "telegram_links"
    __table_args__ = (CheckConstraint("chat_id = telegram_user_id AND telegram_user_id > 0", name="private_identity"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    bot_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TelegramPairing(Base):
    __tablename__ = "telegram_pairings"
    __table_args__ = (CheckConstraint("kind IN ('PRIVATE', 'GROUP')", name="pairing_kind"), UniqueConstraint("user_id", "kind", name="uq_telegram_pairing_owner_kind"))

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    bot_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_id: Mapped[int | None] = mapped_column(BigInteger)
    candidate_name: Mapped[str | None] = mapped_column(String(255))


class TelegramUpdate(Base):
    __tablename__ = "telegram_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class NotificationOutbox(PKMixin, TimestampMixin, Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        Index("ix_notification_due", "status", "next_attempt_at"),
        Index("ix_notification_history", "created_at"),
        CheckConstraint("destination_type IN ('PRIVATE', 'ADMIN')", name="notification_destination"),
        CheckConstraint("category <> 'recovery' OR destination_type = 'PRIVATE'", name="recovery_private_only"),
        CheckConstraint("sensitive_payload IS NULL OR (category = 'recovery' AND destination_type = 'PRIVATE')", name="secret_private_only"),
        CheckConstraint("status IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'CANCELLED')", name="notification_status"),
    )

    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(16), nullable=False)
    destination_reference: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    sensitive_payload: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(64))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))
    deduplication_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)


class NotificationIncident(Base):
    __tablename__ = "notification_incidents"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    measured_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

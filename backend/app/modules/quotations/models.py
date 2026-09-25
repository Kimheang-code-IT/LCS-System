from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin, utcnow
from app.core.types import JSONType


class Quotation(PKMixin, TimestampMixin, Base):
    __tablename__ = "quotations"
    __table_args__ = (UniqueConstraint("quotation_no", name="uq_quotations_no"),)

    quotation_no: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("business_parties.id"), nullable=False)
    trade_direction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trade_directions.id"), nullable=False)
    current_revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class QuotationRevision(PKMixin, TimestampMixin, Base):
    __tablename__ = "quotation_revisions"
    __table_args__ = (UniqueConstraint("quotation_id", "revision_no", name="uq_quotation_revisions_no"),)

    quotation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class QuotationRevisionPlace(PKMixin, Base):
    __tablename__ = "quotation_revision_places"

    quotation_revision_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quotation_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    place_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("places.id"))
    place_role: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    free_text: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class QuotationRevisionContainer(PKMixin, Base):
    __tablename__ = "quotation_revision_containers"

    quotation_revision_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quotation_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    container_type_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("container_types.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    description: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)


class QuotationRevisionLine(PKMixin, Base):
    __tablename__ = "quotation_revision_lines"
    __table_args__ = (UniqueConstraint("quotation_revision_id", "line_no", name="uq_quotation_revision_lines_no"),)

    quotation_revision_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quotation_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fee_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fee_types.id"))
    container_requirement_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("quotation_revision_containers.id"))
    service_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    unit_code: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    line_discount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    line_tax: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)


class QuotationConversion(PKMixin, Base):
    __tablename__ = "quotation_conversions"

    quotation_revision_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quotation_revisions.id"), nullable=False, unique=True
    )
    service_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    converted_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    converted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin, utcnow
from app.core.types import JSONType


class ServiceOrder(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_orders"
    __table_args__ = (UniqueConstraint("service_order_no", name="uq_service_orders_no"),)

    service_order_no: Mapped[str] = mapped_column(String(50), nullable=False)
    quotation_revision_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("quotation_revisions.id"))
    customer_party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("business_parties.id"), nullable=False)
    trade_direction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trade_directions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class ServiceOrderPlace(PKMixin, Base):
    __tablename__ = "service_order_places"

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("places.id"))
    place_role: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    free_text: Mapped[str | None] = mapped_column(Text)
    is_actual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ServiceOrderContainerRequirement(PKMixin, Base):
    __tablename__ = "service_order_container_requirements"

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    source_quotation_container_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("quotation_revision_containers.id"))
    container_type_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("container_types.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    description: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)


class ServiceOrderContainer(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_order_containers"
    __table_args__ = (UniqueConstraint("container_number", name="uq_service_order_containers_number"),)

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    container_requirement_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service_order_container_requirements.id"))
    container_type_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("container_types.id"), nullable=False)
    container_number: Mapped[str] = mapped_column(String(32), nullable=False)
    seal_serial: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="EXPECTED")
    net_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    pickup_date: Mapped[date | None] = mapped_column(Date)
    return_date: Mapped[date | None] = mapped_column(Date)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class ServiceOrderPricing(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_order_pricing"

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")


class ServiceOrderPricingLine(PKMixin, Base):
    __tablename__ = "service_order_pricing_lines"
    __table_args__ = (UniqueConstraint("service_order_pricing_id", "line_no", name="uq_so_pricing_lines_no"),)

    service_order_pricing_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_order_pricing.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_quotation_line_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("quotation_revision_lines.id"))
    fee_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fee_types.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    unit_code: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)


class ServiceOrderComponent(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_order_components"

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_direction_component_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("trade_direction_components.id"))
    component_group_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("component_groups.id"))
    component_template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("component_templates.id"), nullable=False)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    component_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    instance_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="SINGLE")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    completed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class ServiceComponentValue(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_component_values"
    __table_args__ = (UniqueConstraint("component_id", "template_attribute_id", name="uq_service_component_values_attr"),)

    component_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_order_components.id", ondelete="CASCADE"), nullable=False, index=True)
    template_attribute_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("template_attributes.id"), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(19, 6))
    value_date: Mapped[date | None] = mapped_column(Date)
    value_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    value_boolean: Mapped[bool | None] = mapped_column(Boolean)
    value_reference_type: Mapped[str | None] = mapped_column(String(64))
    value_reference_id: Mapped[int | None] = mapped_column(BigInteger)
    value_json: Mapped[Any | None] = mapped_column(JSONType)


class ServiceOrderMovement(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_order_movements"

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    transport_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("transport_types.id"))
    transport_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("transport_assets.id"))
    origin_place_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("places.id"))
    destination_place_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("places.id"))
    planned_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class ServiceOrderMilestone(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_order_milestones"

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_code: Mapped[str] = mapped_column(String(64), nullable=False)
    milestone_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    notes: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class ServiceOrderCharge(PKMixin, TimestampMixin, Base):
    __tablename__ = "service_order_charges"
    __table_args__ = (UniqueConstraint("charge_no", name="uq_service_order_charges_no"),)

    service_order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    charge_no: Mapped[str] = mapped_column(String(50), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False, default="SERVICE_NOTE")
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class ServiceOrderChargeLine(PKMixin, Base):
    __tablename__ = "service_order_charge_lines"
    __table_args__ = (UniqueConstraint("service_order_charge_id", "line_no", name="uq_service_order_charge_lines_no"),)

    service_order_charge_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("service_order_charges.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fee_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fee_types.id"))
    service_order_container_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service_order_containers.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    unit_code: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)


class ServiceOrderTabRow(PKMixin, TimestampMixin, Base):
    """One row of a configurable Service Order dynamic-table tab.

    Column values are stored as JSONB keyed by ``ServiceOrderColumnConfig.field_key``
    so adding a column never requires a schema migration.
    """

    __tablename__ = "service_order_tab_rows"

    service_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tab_config_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("service_order_tab_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tab_code: Mapped[str] = mapped_column(String(64), nullable=False)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))


class Attachment(PKMixin, Base):
    __tablename__ = "attachments"

    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128))
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    document_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AttachmentLink(PKMixin, Base):
    __tablename__ = "attachment_links"
    __table_args__ = (UniqueConstraint("attachment_id", "entity_type", "entity_id", "attachment_role", name="uq_attachment_links_target"),)

    attachment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attachment_role: Mapped[str] = mapped_column(String(64), nullable=False, default="ATTACHMENT")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

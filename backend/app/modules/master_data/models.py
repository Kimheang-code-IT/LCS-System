from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin
from app.core.types import JSONType


class Place(PKMixin, TimestampMixin, Base):
    __tablename__ = "places"

    code: Mapped[str | None] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    place_category: Mapped[str] = mapped_column(String(64), nullable=False, default="City")
    parent_place_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("places.id"))
    address: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class TradeDirection(PKMixin, TimestampMixin, Base):
    __tablename__ = "trade_directions"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ContainerType(PKMixin, TimestampMixin, Base):
    __tablename__ = "container_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    container_size: Mapped[str | None] = mapped_column(String(32))
    container_kind: Mapped[str | None] = mapped_column(String(32))
    iso_code: Mapped[str | None] = mapped_column(String(16))
    length_feet: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    width_millimeter: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    height_millimeter: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    max_gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class TransportType(PKMixin, TimestampMixin, Base):
    __tablename__ = "transport_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class FeeType(PKMixin, TimestampMixin, Base):
    __tablename__ = "fee_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class BusinessParty(PKMixin, TimestampMixin, Base):
    __tablename__ = "business_parties"

    party_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    vat_tin: Mapped[str | None] = mapped_column(String(64), unique=True)
    contact_person: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class PartyRole(Base):
    __tablename__ = "party_roles"

    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("business_parties.id", ondelete="CASCADE"), primary_key=True)
    role_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PartyPlace(Base):
    __tablename__ = "party_places"

    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("business_parties.id", ondelete="CASCADE"), primary_key=True)
    place_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("places.id"), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TransportAsset(PKMixin, TimestampMixin, Base):
    __tablename__ = "transport_assets"
    __table_args__ = (UniqueConstraint("transport_type_id", "identity", name="uq_transport_assets_type_identity"),)

    asset_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    transport_type_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transport_types.id"), nullable=False)
    identity: Mapped[str] = mapped_column(String(128), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="PLATE")
    registration_country_code: Mapped[str | None] = mapped_column(String(2))
    owner_party_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("business_parties.id"))
    operator_party_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("business_parties.id"))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class CustomerCustomsAccount(PKMixin, TimestampMixin, Base):
    __tablename__ = "customer_customs_accounts"

    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("business_parties.id", ondelete="CASCADE"), nullable=False)
    system_name: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_secret_reference: Mapped[str | None] = mapped_column(String(255))
    encrypted_password: Mapped[bytes | None] = mapped_column(LargeBinary)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ComponentGroup(PKMixin, TimestampMixin, Base):
    __tablename__ = "component_groups"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    show_on_job_workspace: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ComponentTemplate(PKMixin, TimestampMixin, Base):
    __tablename__ = "component_templates"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_component_templates_code_version"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    instance_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="SINGLE")
    minimum_instances: Mapped[int | None] = mapped_column(Integer)
    maximum_instances: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class TemplateAttribute(PKMixin, TimestampMixin, Base):
    __tablename__ = "template_attributes"
    __table_args__ = (UniqueConstraint("template_id", "code", name="uq_template_attributes_template_code"),)

    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("component_templates.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    input_type: Mapped[str | None] = mapped_column(String(32))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    reference_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ServiceOrderTabConfig(PKMixin, TimestampMixin, Base):
    """Configurable Service Order operational tab (renders as a dynamic table)."""

    __tablename__ = "service_order_tab_configs"
    __table_args__ = (UniqueConstraint("code", name="uq_so_tab_configs_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_km: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_multiple_rows: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ServiceOrderColumnConfig(PKMixin, TimestampMixin, Base):
    """Configurable table column for a Service Order tab."""

    __tablename__ = "service_order_column_configs"
    __table_args__ = (UniqueConstraint("tab_id", "field_key", name="uq_so_column_configs_tab_key"),)

    tab_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("service_order_tab_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    label_km: Mapped[str | None] = mapped_column(String(255))
    field_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    reference_type: Mapped[str | None] = mapped_column(String(32))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_in_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    width: Mapped[str | None] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_value: Mapped[str | None] = mapped_column(String(255))
    placeholder: Mapped[str | None] = mapped_column(String(255))
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    options: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)


class ModuleRecord(PKMixin, TimestampMixin, Base):
    """Generic record store backing metadata-driven frontend collections.

    Used for secondary/legacy collections that the frontend renders from its
    module schema (for example ``companies``, ``shipments``, ``customs`` and
    ``documents``) without a dedicated relational table. The full configured
    payload lives in ``data``; the key columns support scoping, listing and
    filtering.
    """

    __tablename__ = "module_records"

    collection: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    record_no: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class TradeDirectionComponent(PKMixin, TimestampMixin, Base):
    __tablename__ = "trade_direction_components"
    __table_args__ = (
        UniqueConstraint("trade_direction_id", "component_template_id", name="uq_tdc_direction_template"),
    )

    trade_direction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trade_directions.id"), nullable=False)
    component_group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("component_groups.id"), nullable=False)
    component_template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("component_templates.id"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    instance_mode_override: Mapped[str] = mapped_column(String(20), nullable=False, default="INHERIT")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

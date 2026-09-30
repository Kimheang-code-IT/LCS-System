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

from app.core.database import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.core.types import JSONType


class Place(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
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


class TradeDirection(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "trade_directions"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ContainerType(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
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


class TransportType(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "transport_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class FeeType(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fee_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class BusinessParty(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
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


class TransportAsset(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
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


class ComponentAttribute(PKMixin, TimestampMixin, Base):
    """Reusable dynamic-form attribute (field) in the global catalog.

    Attributes are defined once and then referenced by one or more component
    groups, so a field such as "Container No." can be reused everywhere.
    """

    __tablename__ = "component_attributes"
    __table_args__ = (UniqueConstraint("code", name="uq_component_attributes_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    label_km: Mapped[str | None] = mapped_column(String(255))
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    input_type: Mapped[str | None] = mapped_column(String(32))
    reference_type: Mapped[str | None] = mapped_column(String(32))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_value: Mapped[str | None] = mapped_column(String(255))
    placeholder: Mapped[str | None] = mapped_column(String(255))
    width: Mapped[str | None] = mapped_column(String(16))
    options: Mapped[list[Any]] = mapped_column(JSONType, nullable=False, default=list)
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ComponentGroup(PKMixin, TimestampMixin, Base):
    """A group of attributes rendered together.

    ``render_mode`` decides how the group appears on a Service Order:
    ``table`` = a repeatable editable table (many rows), ``form`` = a single
    row shown as a form.
    """

    __tablename__ = "component_groups"
    __table_args__ = (UniqueConstraint("code", name="uq_component_groups_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_km: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    render_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="table")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ComponentGroupAttribute(PKMixin, TimestampMixin, Base):
    """Membership of a reusable attribute in a component group, with overrides."""

    __tablename__ = "component_group_attributes"
    __table_args__ = (UniqueConstraint("group_id", "attribute_id", name="uq_component_group_attributes_group_attr"),)

    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("component_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attribute_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("component_attributes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_required: Mapped[bool | None] = mapped_column(Boolean)
    width: Mapped[str | None] = mapped_column(String(16))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ComponentTab(PKMixin, TimestampMixin, Base):
    """A Service Order tab composed of component groups, shown for chosen trade directions."""

    __tablename__ = "component_tabs"
    __table_args__ = (UniqueConstraint("code", name="uq_component_tabs_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_km: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(64))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ComponentTabGroup(PKMixin, TimestampMixin, Base):
    """Membership of a component group in a component tab."""

    __tablename__ = "component_tab_groups"
    __table_args__ = (UniqueConstraint("tab_id", "group_id", name="uq_component_tab_groups_tab_group"),)

    tab_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("component_tabs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("component_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ComponentTabTradeDirection(PKMixin, TimestampMixin, Base):
    """Assignment of a component tab to a trade direction."""

    __tablename__ = "component_tab_trade_directions"
    __table_args__ = (UniqueConstraint("tab_id", "trade_direction_id", name="uq_component_tab_directions_tab_direction"),)

    tab_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("component_tabs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trade_direction_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trade_directions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class ModuleRecord(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
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

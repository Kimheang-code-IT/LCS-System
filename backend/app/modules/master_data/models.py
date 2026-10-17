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
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.core.types import JSONType


def active_unique_index(name: str, *columns: str) -> Index:
    """Uniqueness enforced only for non-archived rows.

    Archived (soft-deleted) records keep their codes, so a code must be
    reusable once the record is deleted. The archive/restore logic already
    treats uniqueness as active-only; this index makes the database agree.
    """
    return Index(
        name,
        *columns,
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
        sqlite_where=text("deleted_at IS NULL"),
    )


class Place(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "places"
    __table_args__ = (active_unique_index("uq_places_code_active", "code"),)

    code: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class TradeDirection(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "trade_directions"
    __table_args__ = (active_unique_index("uq_trade_directions_code_active", "code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class Currency(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Currency master data.

    Currency used to be an unconstrained ``VARCHAR(3)`` on every money-bearing
    table, so a typo silently created a currency nobody could report on. The
    monetary columns keep their ``currency_code`` string for backward
    compatibility, but new writes resolve it against this table.

    ``decimal_places`` is the currency's own precision, used to round every
    converted (base-currency) amount — JPY and KHR are configured with 0 rather
    than being forced into two decimals they do not have.
    """

    __tablename__ = "currencies"
    __table_args__ = (active_unique_index("uq_currencies_code_active", "code"),)

    code: Mapped[str] = mapped_column(String(3), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(10))
    numeric_code: Mapped[str | None] = mapped_column(String(3))
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class CurrencyRate(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """An approved conversion rate between two currencies, effective from a date.

    ``rate`` answers "1 ``from_currency_code`` = rate ``to_currency_code``", the
    direction the UI shows ("1 USD = 4,000 KHR"). A document stores the
    conversion the other way round — ``base = amount * exchange_rate`` — so the
    resolver in ``master_data/currency_rates.py`` inverts a pair when only the
    inverse row exists, and the rate copied onto the document is what a posting
    is later explained by.

    Rates are versioned by ``effective_date``: a correction is a new row, never
    an edit of one already used, which is why uniqueness is scoped to the pair
    and the date. Only the resolver reads this table; nothing posts from it.
    """

    __tablename__ = "currency_rates"
    __table_args__ = (
        active_unique_index(
            "uq_currency_rates_pair_date",
            "from_currency_code",
            "to_currency_code",
            "effective_date",
        ),
        Index(
            "ix_currency_rates_lookup",
            "from_currency_code",
            "to_currency_code",
            "effective_date",
            "status",
        ),
    )

    from_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    source: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)


class ContainerType(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "container_types"
    __table_args__ = (active_unique_index("uq_container_types_code_active", "code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
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
    __table_args__ = (active_unique_index("uq_transport_types_code_active", "code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class FeeType(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fee_types"
    __table_args__ = (active_unique_index("uq_fee_types_code_active", "code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class BusinessParty(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "business_parties"
    __table_args__ = (
        active_unique_index("uq_business_parties_party_code_active", "party_code"),
        active_unique_index("uq_business_parties_vat_tin_active", "vat_tin"),
    )

    party_code: Mapped[str] = mapped_column(String(50), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    vat_tin: Mapped[str | None] = mapped_column(String(64))
    contact_person: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    roles: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class TransportAsset(PKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "transport_assets"
    __table_args__ = (
        active_unique_index("uq_transport_assets_asset_code_active", "asset_code"),
        active_unique_index("uq_transport_assets_type_identity_active", "transport_type_id", "identity"),
    )

    asset_code: Mapped[str] = mapped_column(String(50), nullable=False)
    transport_type_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transport_types.id"), nullable=False)
    identity: Mapped[str] = mapped_column(String(128), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="PLATE")
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


class ConfigurationVersion(PKMixin, TimestampMixin, Base):
    """A published snapshot of the dynamic Service Order configuration.

    Tabs, groups and attributes are edited in place, so without a snapshot a
    historical Service Order could no longer be rendered the way it was filled
    in. Publishing copies the live configuration into ``config_snapshot`` and
    stamps the rows that participated, which makes both the *definition* and the
    *layout* of a saved order reproducible.

    Exactly one version may be ``PUBLISHED`` at a time (partial unique index);
    ``RETIRED`` keeps a snapshot readable after it stops being the current one.
    ``config_snapshot`` is data only — nothing in it is executed.
    """

    __tablename__ = "configuration_versions"
    __table_args__ = (
        UniqueConstraint("version_no", name="uq_configuration_versions_no"),
        Index(
            "uq_configuration_versions_published",
            "status",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED'"),
            sqlite_where=text("status = 'PUBLISHED'"),
        ),
    )

    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    change_note: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))


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
    """A Service Order tab composed of component groups, shown for one trade direction."""

    __tablename__ = "component_tabs"
    __table_args__ = (UniqueConstraint("code", name="uq_component_tabs_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    trade_direction_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("trade_directions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The published configuration this tab was part of. Historical orders keep
    # resolving against the snapshot even after the tab is edited or removed.
    config_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("configuration_versions.id", ondelete="SET NULL"), nullable=True
    )


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

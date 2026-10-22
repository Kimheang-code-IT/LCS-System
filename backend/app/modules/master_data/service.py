from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache, deletion
from app.core.config import settings
from app.core.context import RequestContext
from app.core.crypto import encrypt_secret, is_sensitive_field
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, paged
from app.core.serialization import jsonable, to_camel
from app.core.validation import FieldSpec, RecordSchema, field_from_column
from app.modules.master_data.currency_rates import normalize_rate_input
from app.modules.master_data.models import (
    BusinessParty,
    BusinessPartyRole,
    ContainerType,
    Currency,
    CurrencyRate,
    FeeType,
    ModuleRecord,
    PartyRole,
    PlaceRole,
    TradeDirection,
    TransportAsset,
    TransportType,
)
from app.modules.master_data.repository import MasterDataRepository


@dataclass
class RefSpec:
    target: str
    label: str


@dataclass
class Spec:
    model: type
    title: str
    fields: dict[str, str]
    search: list[str]
    output_map: dict[str, str] = field(default_factory=dict)
    refs: dict[str, RefSpec] = field(default_factory=dict)
    computed: Callable[[Any, AsyncSession], dict[str, Any]] | None = None
    transform_input: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    after_create: Callable[[Any, dict, AsyncSession], None] | None = None
    before_delete: Callable[[Any, AsyncSession], None] | None = None
    status_field: str = "status"
    #: API field keys the record cannot do without, checked before the write so a
    #: blank one is reported on the field instead of failing on a NOT NULL column.
    required: tuple[str, ...] = ()
    #: Closed vocabularies that are not obvious from the column type (statuses).
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Per-field rule overrides (bounds/patterns) applied over the column-derived
    #: rule. Keep business rules here, beside the collection they belong to.
    rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Default ORDER BY column names for the list endpoint. Empty keeps the
    #: generic newest-first order. Place roles use it to honour ``sort_order``.
    default_order: tuple[str, ...] = ()


def _enum(value: Any) -> Any:
    return jsonable(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "active", "enabled"}
    return bool(value)


def _parse_date(value: Any, field_key: str) -> date:
    """An ISO date from a JSON payload, refused as a field error when malformed."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError as exc:
        raise ValidationFailed(
            "A valid date is required.",
            {field_key: "Use a date such as 2026-01-31."},
        ) from exc


async def serialize(spec: Spec, model: Any, session: AsyncSession) -> dict[str, Any]:
    output: dict[str, Any] = {"id": str(model.id)}
    for camel, attr in spec.fields.items():
        output[camel] = _enum(getattr(model, attr, None))
    for camel, attr in spec.output_map.items():
        output[camel] = _enum(getattr(model, attr, None))
    if spec.computed is not None:
        output.update(await spec.computed(model, session))
    output.setdefault("status", getattr(model, spec.status_field, None))
    for column in model.__table__.columns:
        output.setdefault(to_camel(column.name), _enum(getattr(model, column.name, None)))
    return output


async def resolve_reference(session: AsyncSession, target: str, value: Any) -> Any:
    """Resolve a user-supplied reference (code/name/id) to a numeric id."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    lookup: dict[str, tuple[type, str]] = {
        "place_role": (PlaceRole, "name"),
        "trade_direction": (TradeDirection, "name"),
        "container_type": (ContainerType, "name"),
        "transport_type": (TransportType, "name"),
        "fee_type": (FeeType, "name"),
        "business_party": (BusinessParty, "legal_name"),
        "party_role": (PartyRole, "name"),
        "currency": (Currency, "code"),
    }
    if target == "chart_of_account":
        from app.modules.finance.models import ChartOfAccount

        row = (
            await session.execute(
                select(ChartOfAccount).where(or_(ChartOfAccount.account_code == text, ChartOfAccount.account_name == text))
            )
        ).scalars().first()
        return row.id if row else None
    if target not in lookup:
        return None
    model, attribute = lookup[target]
    conditions = [getattr(model, attribute) == text]
    code_column = getattr(model, "code", None)
    if code_column is not None:
        conditions.append(code_column == text)
    row = (
        await session.execute(select(model).where(or_(*conditions), model.deleted_at.is_(None)))
    ).scalars().first()
    return row.id if row else None


async def resolve_reference_id(
    session: AsyncSession,
    target: str,
    raw_id: Any = None,
    value: Any = None,
) -> int | None:
    """Resolve a reference id from an explicit id, falling back to a code/name."""
    if raw_id not in (None, ""):
        try:
            return int(raw_id)
        except (TypeError, ValueError):
            pass
    if value in (None, ""):
        return None
    resolved = await resolve_reference(session, target, value)
    return int(resolved) if resolved is not None else None


async def resolve_or_create_container_type(session: AsyncSession, value: Any) -> int | None:
    """Resolve a container type by id, code or name, creating it when unknown.

    Reference data ships empty and the quotation/job forms submit standard ISO
    container codes (``40HC`` ...). When the value matches no ``container_types``
    row we register a minimal ACTIVE record instead of writing a dangling FK â€”
    the previous ``or 1`` fallback violated the foreign key on an empty table.
    """
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, int):
        row = await session.get(ContainerType, value)
        return row.id if row is not None else None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        row = await session.get(ContainerType, int(text))
        if row is not None:
            return row.id
    row = (
        await session.execute(
            select(ContainerType).where(or_(ContainerType.code == text, ContainerType.name == text))
        )
    ).scalars().first()
    if row is not None:
        return row.id
    created = ContainerType(code=text[:50], name=text[:255], status="ACTIVE")
    session.add(created)
    await session.flush()
    await cache.bump("master_data")
    return created.id


async def apply_input(spec: Spec, model: Any, data: dict[str, Any], session: AsyncSession) -> None:
    for camel, attr in spec.fields.items():
        if camel in data:
            value = data[camel]
            column = spec.model.__table__.columns.get(attr)
            if column is not None and str(column.type).startswith("BOOLEAN"):
                value = _bool(value)
            elif column is not None and str(column.type) == "DATE" and value not in (None, ""):
                # A date arrives as JSON text. Coercing it here, by column type,
                # is the same rule the BOOLEAN and JSON branches apply, so a
                # reference model with a date does not need its own parser.
                value = _parse_date(value, camel)
            elif column is not None and str(column.type).startswith("JSON") and value is not None and not isinstance(value, list):
                value = [value]
            setattr(model, attr, value)
    for camel, ref in spec.refs.items():
        if camel in data:
            supplied = data[camel]
            resolved = await resolve_reference(session, ref.target, supplied)
            if resolved is None and supplied not in (None, ""):
                # Writing NULL here would silently discard the operator's input
                # and leave a dangling-looking record, so reject it instead.
                label = ref.target.replace("_", " ")
                raise ValidationFailed(
                    f"Unknown {label}: {supplied!r} was not found.",
                    {camel: f"'{supplied}' does not match any {label}."},
                )
            setattr(model, ref.label, resolved)


def _place_role_transform(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise a place role before it is written.

    Codes are upper-cased so ``pickup`` and ``PICKUP`` cannot become two records
    that look identical in a dropdown; names are trimmed for the same reason.
    """
    if isinstance(data.get("code"), str):
        data["code"] = data["code"].strip().upper()
    if isinstance(data.get("name"), str):
        data["name"] = data["name"].strip()
    if isinstance(data.get("description"), str):
        data["description"] = data["description"].strip()
    return data


async def _asset_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    transport_type = await session.get(TransportType, model.transport_type_id) if model.transport_type_id else None
    owner = await session.get(BusinessParty, model.owner_party_id) if model.owner_party_id else None
    operator = await session.get(BusinessParty, model.operator_party_id) if model.operator_party_id else None
    return {
        "transportType": transport_type.name if transport_type else None,
        "transportTypeId": model.transport_type_id,
        "ownerParty": owner.legal_name if owner else None,
        "operatorParty": operator.legal_name if operator else None,
    }


def _container_transform(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise the container-type form before it reaches the model.

    Width and height are edited in metres and stored in millimetres. The
    conversion uses ``Decimal`` so the round trip is exact (``2.438`` m is
    ``2438`` mm, never ``2437.999â€¦``), and every numeric field is validated here
    so a bad dimension is a field error rather than a database error.
    """
    errors: dict[str, str] = {}
    for key in ("code", "name", "size", "kind", "isoCode", "description"):
        if isinstance(data.get(key), str):
            data[key] = data[key].strip()

    for meters_key, millimeter_key in (("widthMeters", "widthMillimeter"), ("heightMeters", "heightMillimeter")):
        if meters_key not in data:
            continue
        value = data.get(meters_key)
        if value in (None, ""):
            data[millimeter_key] = None
            continue
        try:
            meters = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            errors[meters_key] = "Enter a number."
            continue
        if meters < 0:
            errors[meters_key] = "Cannot be negative."
            continue
        # 1 mm precision is the storage granularity; keep it exact in Decimal.
        data[millimeter_key] = (meters * 1000).quantize(Decimal("0.01"))

    for key in ("lengthFeet", "maxGrossWeightKg"):
        value = data.get(key)
        if value in (None, ""):
            continue
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            errors[key] = "Enter a number."
            continue
        if number < 0:
            errors[key] = "Cannot be negative."

    if errors:
        raise ValidationFailed("Please correct the container dimensions.", errors)
    return data


async def _container_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    width = float(model.width_millimeter) / 1000 if model.width_millimeter else None
    height = float(model.height_millimeter) / 1000 if model.height_millimeter else None
    return {
        "size": model.container_size,
        "kind": model.container_kind,
        "isoCode": model.iso_code,
        "maxGrossWeightKg": model.max_gross_weight_kg,
        "widthMeters": width,
        "heightMeters": height,
    }


# --- Transport assets ---------------------------------------------------------
# `identity_type` records what the `identity` value *is*. The stored vocabulary
# is the human-readable label shown in the form dropdown, mirroring `PARTY_ROLES`
# and `ACTIVE_STATUS` in `frontend/app/config/freight-options.ts`; the legacy
# codes the column used to default to are accepted on write and normalised, so a
# row written by an older build keeps loading and editing without a data migration.
IDENTITY_TYPES: tuple[str, ...] = (
    "License Plate",
    "IMO Number",
    "Flight Number",
    "Other",
)

_IDENTITY_TYPE_ALIASES: dict[str, str] = {
    "plate": "License Plate",
    "license plate": "License Plate",
    "licence plate": "License Plate",
    "imo": "IMO Number",
    "imo number": "IMO Number",
    "flight": "Flight Number",
    "flight number": "Flight Number",
    "tail": "Flight Number",
    "registration": "Other",
    "other": "Other",
}


def _asset_transform(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise a transport asset before it is written.

    The identity type is a closed set, so an unrecognised value is refused with a
    field error instead of being stored as free text and later failing to match
    the dropdown. Identifiers are trimmed because the unique indexes compare the
    raw column, and `` "TRK-001 " `` would otherwise look distinct from
    ``"TRK-001"`` while the operator sees the same code twice in the list.
    """
    supplied = data.get("identityType")
    if supplied not in (None, ""):
        canonical = _IDENTITY_TYPE_ALIASES.get(str(supplied).strip().lower())
        if canonical is None:
            raise ValidationFailed(
                "Unsupported identity type.",
                {"identityType": f"Choose one of: {', '.join(IDENTITY_TYPES)}."},
            )
        data["identityType"] = canonical
    for key in ("assetCode", "identity", "description"):
        if isinstance(data.get(key), str):
            data[key] = data[key].strip()
    return data


def _validate_required(spec: Spec, data: dict[str, Any], model: Any = None) -> None:
    """Refuse a record that would violate a ``NOT NULL`` column, naming the field.

    Without this the column rejects the row at flush time and the caller sees a
    constraint error, not a field error â€” so the operator is told nothing is wrong
    with a specific field. On update the value already stored counts, so a partial
    save that omits an unchanged required field still passes.
    """
    missing: dict[str, str] = {}
    for key in spec.required:
        supplied = data.get(key)
        blank = supplied is None or (isinstance(supplied, str) and not supplied.strip())
        if not blank:
            continue
        if model is not None:
            attribute = spec.refs[key].label if key in spec.refs else spec.fields.get(key)
            current = getattr(model, attribute, None) if attribute else None
            if current is not None and str(current).strip():
                continue
        missing[key] = "This field is required."
    if missing:
        raise ValidationFailed("Please complete the required fields.", missing)


async def _business_party_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    """Role names for display and ids for the form's multi-select."""
    rows = (
        await session.execute(
            select(PartyRole.id, PartyRole.name)
            .join(BusinessPartyRole, BusinessPartyRole.party_role_id == PartyRole.id)
            .where(
                BusinessPartyRole.business_party_id == model.id,
                PartyRole.deleted_at.is_(None),
            )
            .order_by(PartyRole.name)
        )
    ).all()
    return {
        "roles": [name for _, name in rows],
        "roleIds": [str(role_id) for role_id, _ in rows],
    }


async def _sync_business_party_roles(model: Any, data: dict[str, Any], session: AsyncSession) -> None:
    """Replace a party's assignments from ``roleIds`` (or the legacy ``roles``).

    Labels are accepted on write so pre-existing API clients keep working; the
    join table is the only storage, so a role rename is reflected everywhere.
    """
    key = "roleIds" if "roleIds" in data else "roles"
    if key not in data:
        return
    supplied = data.get(key)
    values = supplied if isinstance(supplied, list) else ([] if supplied in (None, "") else [supplied])
    ids: list[int] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if text.isdigit():
            ids.append(int(text))
            continue
        resolved = await resolve_reference(session, "party_role", text)
        if resolved is None:
            raise ValidationFailed(
                "Please correct the party roles.",
                {key: f"'{text}' does not match any party role."},
            )
        ids.append(resolved)
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise ValidationFailed("Please correct the party roles.", {key: "Choose at least one role."})
    known = set(
        (
            await session.execute(
                select(PartyRole.id).where(PartyRole.id.in_(ids), PartyRole.deleted_at.is_(None))
            )
        ).scalars().all()
    )
    unknown = [role_id for role_id in ids if role_id not in known]
    if unknown:
        raise ValidationFailed(
            "Please correct the party roles.",
            {key: f"Unknown party role id: {unknown[0]}."},
        )
    await session.execute(
        delete(BusinessPartyRole).where(BusinessPartyRole.business_party_id == model.id)
    )
    session.add_all(
        BusinessPartyRole(business_party_id=model.id, party_role_id=role_id) for role_id in ids
    )


def _party_role_transform(data: dict[str, Any]) -> dict[str, Any]:
    """Upper-case the code and trim the labels before uniqueness is checked."""
    if isinstance(data.get("code"), str):
        data["code"] = data["code"].strip().upper()
    if isinstance(data.get("name"), str):
        data["name"] = data["name"].strip()
    if isinstance(data.get("description"), str):
        data["description"] = data["description"].strip()
    return data


def _spec_schema(spec: Spec) -> RecordSchema:
    """Build the write-time schema for one reference collection.

    Types, lengths and decimal scale are read from the model columns; the
    collection's own ``required``/``enums``/``rules`` add the business rules the
    database cannot express (a status vocabulary, ``rate > 0`` â€¦). Built per
    call because a ``Spec`` is cheap and this keeps the definition in one place.
    """
    fields: list[FieldSpec] = []
    for key, attribute in spec.fields.items():
        column = spec.model.__table__.columns.get(attribute)
        if column is None:  # pragma: no cover - a typo in SPECS is a startup bug
            continue
        fields.append(
            field_from_column(
                key,
                column,
                required=key in spec.required,
                choices=spec.enums.get(key),
                **(spec.rules.get(key) or {}),
            )
        )
    for key in spec.refs:
        fields.append(FieldSpec(key, "reference", required=key in spec.required))
    return RecordSchema(tuple(fields))


SPECS: dict[str, Spec] = {
    "businessParties": Spec(
        model=BusinessParty,
        title="legal_name",
        fields={
            "partyCode": "party_code",
            "legalName": "legal_name",
            "displayName": "display_name",
            "contactPerson": "contact_person",
            "phone": "phone",
            "email": "email",
            "address": "address",
            "status": "status",
            "taxIdentifier": "vat_tin",
        },
        search=["party_code", "legal_name", "display_name", "phone", "email"],
        required=("partyCode", "legalName"),
        enums={"status": ("ACTIVE", "INACTIVE")},
        rules={
            "partyCode": {"pattern": r"[A-Za-z0-9][A-Za-z0-9._/-]*"},
            "email": {"kind": "email"},
            "phone": {"kind": "phone"},
        },
        # `roleIds` is a relation stored in `business_party_roles`, not a column.
        # `_sync_business_party_roles` also accepts the legacy `roles` labels.
        computed=_business_party_computed,
        after_create=_sync_business_party_roles,
    ),
    # The route-stop vocabulary. Administrators own this list; the default rows
    # are seeded as data (see `provision_baseline`), never as form options.
    "placeRoles": Spec(
        model=PlaceRole,
        title="name",
        fields={
            "code": "code",
            "name": "name",
            "description": "description",
            "sortOrder": "sort_order",
            "status": "status",
        },
        search=["code", "name"],
        required=("code", "name"),
        enums={"status": ("ACTIVE", "INACTIVE")},
        rules={
            "code": {"pattern": r"[A-Za-z][A-Za-z0-9_-]*"},
            "sortOrder": {"minimum": Decimal("0")},
        },
        transform_input=_place_role_transform,
        default_order=("sort_order", "name"),
    ),
    # Business-party vocabulary, replacing the hardcoded Customer/Supplier/
    # Company options. Defaults are seeded as data, never as form options.
    "partyRoles": Spec(
        model=PartyRole,
        title="name",
        fields={"code": "code", "name": "name", "description": "description", "status": "status"},
        search=["code", "name"],
        required=("code", "name"),
        enums={"status": ("ACTIVE", "INACTIVE")},
        rules={"code": {"pattern": r"[A-Za-z][A-Za-z0-9_-]*"}},
        transform_input=_party_role_transform,
        default_order=("name",),
    ),
    "tradeDirections": Spec(
        model=TradeDirection,
        title="name",
        fields={"code": "code", "name": "name", "description": "description", "status": "status"},
        search=["code", "name"],
        required=("code", "name"),
        enums={"status": ("ACTIVE", "INACTIVE")},
    ),
    "containerTypes": Spec(
        model=ContainerType,
        title="name",
        fields={
            "code": "code",
            "name": "name",
            "size": "container_size",
            "kind": "container_kind",
            "isoCode": "iso_code",
            "lengthFeet": "length_feet",
            "widthMillimeter": "width_millimeter",
            "heightMillimeter": "height_millimeter",
            "maxGrossWeightKg": "max_gross_weight_kg",
            "description": "description",
            "status": "status",
        },
        search=["code", "name"],
        required=("code", "name"),
        enums={"status": ("ACTIVE", "INACTIVE")},
        rules={
            "lengthFeet": {"minimum": Decimal("0")},
            "maxGrossWeightKg": {"minimum": Decimal("0")},
        },
        computed=_container_computed,
        transform_input=_container_transform,
    ),
    "transportTypes": Spec(
        model=TransportType,
        title="name",
        fields={"code": "code", "name": "name", "description": "description", "status": "status"},
        search=["code", "name"],
        required=("code", "name"),
        enums={"status": ("ACTIVE", "INACTIVE")},
    ),
    "transportAssets": Spec(
        model=TransportAsset,
        title="identity",
        fields={
            "assetCode": "asset_code",
            "identity": "identity",
            "identityType": "identity_type",
            "description": "description",
            "status": "status",
        },
        refs={
            "transportType": RefSpec("transport_type", "transport_type_id"),
            "ownerParty": RefSpec("business_party", "owner_party_id"),
            "operatorParty": RefSpec("business_party", "operator_party_id"),
        },
        search=["asset_code", "identity"],
        computed=_asset_computed,
        transform_input=_asset_transform,
        required=("assetCode", "transportType", "identity"),
        enums={"status": ("ACTIVE", "INACTIVE")},
    ),
    "feeTypes": Spec(
        model=FeeType,
        title="name",
        fields={"code": "code", "name": "name", "description": "description", "status": "status"},
        search=["code", "name"],
        required=("code", "name"),
        enums={"status": ("ACTIVE", "INACTIVE")},
    ),
    "currencies": Spec(
        model=Currency,
        title="name",
        fields={
            "code": "code",
            "name": "name",
            "symbol": "symbol",
            "numericCode": "numeric_code",
            "decimalPlaces": "decimal_places",
            "description": "description",
            "status": "status",
        },
        search=["code", "name", "symbol"],
        required=("code", "name"),
        enums={"status": ("ACTIVE", "INACTIVE")},
        rules={
            "code": {"min_length": 3, "max_length": 3, "pattern": r"[A-Za-z]{3}"},
            "decimalPlaces": {"minimum": Decimal("0"), "maximum": Decimal("6")},
        },
    ),
    # The rate store the document form reads from. Rows are versioned by
    # effective date and only an APPROVED row is ever applied to a document; see
    # `master_data/currency_rates.py` for the resolution rules and
    # `app/core/fx.py` for the arithmetic.
    "currencyRates": Spec(
        model=CurrencyRate,
        title="fromCurrencyCode",
        fields={
            "fromCurrencyCode": "from_currency_code",
            "toCurrencyCode": "to_currency_code",
            "effectiveDate": "effective_date",
            "rate": "rate",
            "status": "status",
            "source": "source",
            "description": "description",
        },
        search=["from_currency_code", "to_currency_code", "source"],
        transform_input=normalize_rate_input,
        required=("fromCurrencyCode", "toCurrencyCode", "effectiveDate", "rate"),
        enums={"status": ("PENDING", "APPROVED", "INACTIVE")},
        rules={
            "fromCurrencyCode": {"min_length": 3, "max_length": 3, "pattern": r"[A-Za-z]{3}"},
            "toCurrencyCode": {"min_length": 3, "max_length": 3, "pattern": r"[A-Za-z]{3}"},
            # A zero or negative rate would make every converted amount zero or
            # invert the sign of the ledger, so it is refused at the edge.
            "rate": {"minimum": Decimal("0.00000001")},
        },
    ),
}

# Collection slugs that resolve to the generic record store.
GENERIC_COLLECTIONS = {
    "companies",
    "shipments",
    "customs",
    "documents",
    "deliveries",
    "customerPayments",
    "supplierCosts",
    "supplierPayments",
}

# Generic collections safe to cache: small, non-sensitive option lists only.
CACHEABLE_GENERIC_COLLECTIONS: set[str] = set()


def get_spec(collection: str) -> Spec:
    spec = SPECS.get(collection)
    if spec is None:
        raise NotFound(f"Unknown reference collection: {collection}")
    return spec


def list_cache_parts(collection: str, page: PageParams, *, kind: str = "reference") -> tuple:
    """Every query-affecting input forms the cache key, so a cached page can
    never be served for a different search/filter/sort/pagination request."""
    return (
        kind,
        collection,
        page.page,
        page.page_size,
        (page.q or "").strip(),
        (page.status or "").strip().upper(),
        page.sort_by or "",
        page.sort_order or "",
        page.from_date or "",
        page.to_date or "",
    )


async def list_reference(session: AsyncSession, context: RequestContext, collection: str, page: PageParams) -> dict:
    spec = get_spec(collection)
    parts = list_cache_parts(collection, page)
    # The router guard already verified the caller may read this collection, so
    # every caller reaching this point sees the same rows (no per-row scoping).
    cached = await cache.get_json("master_data", *parts)
    if cached is not None:
        return cached
    rows, total = await MasterDataRepository(session).reference_page(
        spec.model,
        search_columns=spec.search,
        status_field=spec.status_field,
        page=page,
        order_by=spec.default_order,
    )
    items = [await serialize(spec, row, session) for row in rows]
    result = paged(items, page, total)
    await cache.set_json(
        "master_data", *parts, value=result, ttl_seconds=settings.cache_ttl_reference_seconds
    )
    return result


async def get_reference(session: AsyncSession, collection: str, record_id: int) -> dict:
    spec = get_spec(collection)
    cached = await cache.get_json("master_data", "detail", collection, record_id)
    if cached is not None:
        return cached
    model = await MasterDataRepository(session).reference(spec.model, record_id)
    if model is None:
        raise NotFound()
    result = await serialize(spec, model, session)
    await cache.set_json(
        "master_data", "detail", collection, record_id, value=result,
        ttl_seconds=settings.cache_ttl_reference_seconds,
    )
    return result


# (API field, message, tokens in the DB error). Ordered most-specific first;
# tokens match both Postgres constraint names and SQLite "table.column" text.
_UNIQUE_FIELD_ERRORS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("partyCode", "This party code is already in use.", ("party_code",)),
    ("taxIdentifier", "This tax identifier is already in use.", ("vat_tin",)),
    ("name", "This role name is already in use.", ("party_roles.name", "uq_party_roles_name_active")),
    ("code", "This role code is already in use.", ("party_roles.code", "uq_party_roles_code_active")),
    ("assetCode", "This asset code is already in use.", ("asset_code",)),
    ("identity", "This transport type and identity already exist.", ("transport_type_id",)),
    (
        "effectiveDate",
        "A rate for this currency pair and effective date already exists.",
        ("currency_rates.from_currency_code", "uq_currency_rates_pair_date"),
    ),
    ("code", "This code is already in use.", ("code",)),
)


def _unique_violation(exc: IntegrityError) -> ValidationFailed:
    detail = str(getattr(exc, "orig", exc)).lower()
    # A blank NOT NULL column reaches here too, and must not be reported as a
    # duplicate: the operator needs to be told which field is empty, not that
    # someone else already used it.
    if "null value" in detail or "not-null" in detail or "not null" in detail:
        return ValidationFailed("A required field was left empty.")
    for field_key, message, tokens in _UNIQUE_FIELD_ERRORS:
        if any(token in detail for token in tokens):
            return ValidationFailed(message, {field_key: message})
    return ValidationFailed("A record with the same unique value already exists.")


async def create_reference(session: AsyncSession, collection: str, data: dict) -> dict:
    spec = get_spec(collection)
    if spec.transform_input is not None:
        data = spec.transform_input(dict(data))
    # Schema validation runs after the form transform, so it sees the values the
    # model will actually receive (width/height already in millimetres). It
    # collects every problem at once instead of failing on the first one.
    data = _spec_schema(spec).validate(data)
    _validate_required(spec, data)
    model = spec.model()
    await apply_input(spec, model, data, session)
    session.add(model)
    try:
        await session.flush()
        if spec.after_create is not None:
            await spec.after_create(model, data, session)
            await session.flush()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _unique_violation(exc) from exc
    await session.refresh(model)
    await cache.bump("master_data")
    return await serialize(spec, model, session)


async def update_reference(session: AsyncSession, collection: str, record_id: int, data: dict) -> dict:
    spec = get_spec(collection)
    model = await MasterDataRepository(session).reference(spec.model, record_id)
    if model is None:
        raise NotFound()
    if spec.transform_input is not None:
        data = spec.transform_input(dict(data))
    # A partial update only checks the keys it was sent, so an unchanged stored
    # value is never re-required. An explicitly blank supplied value still fails.
    data = _spec_schema(spec).validate(data, partial=True)
    _validate_required(spec, data, model)
    await apply_input(spec, model, data, session)
    if spec.after_create is not None:
        await spec.after_create(model, data, session)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _unique_violation(exc) from exc
    await session.refresh(model)
    await cache.bump("master_data")
    return await serialize(spec, model, session)


async def delete_reference(
    session: AsyncSession, context: RequestContext, collection: str, ids: list[int]
) -> None:
    """Delete reference rows, but never an active one.

    Master Data / Configuration records follow the activate/deactivate rule:
    a record must be deactivated from the row "..." menu before it can be
    removed. This mirrors the UI and guards direct API calls.
    """
    spec = get_spec(collection)
    models = await MasterDataRepository(session).references(spec.model, ids)
    if any(str(getattr(model, spec.status_field, "") or "").strip().upper() == "ACTIVE" for model in models):
        raise Conflict(
            "REFERENCE_ACTIVE",
            "Active records cannot be deleted. Deactivate the record first.",
        )
    if collection == "partyRoles" and models:
        in_use = (
            await session.execute(
                select(BusinessPartyRole.party_role_id)
                .where(BusinessPartyRole.party_role_id.in_([model.id for model in models]))
                .limit(1)
            )
        ).scalars().first()
        if in_use is not None:
            raise Conflict(
                "PARTY_ROLE_IN_USE",
                "This party role is assigned to a business party. Deactivate it instead of deleting it.",
            )
    from app.modules.archive.service import archive_record

    for model in models:
        await archive_record(session, context, collection, model.id)
    await cache.bump("master_data")


# --- Generic record store -----------------------------------------------------
async def list_generic(session: AsyncSession, context: RequestContext, collection: str, page: PageParams) -> dict:
    parts = list_cache_parts(collection, page, kind="generic")
    if collection in CACHEABLE_GENERIC_COLLECTIONS:
        cached = await cache.get_json("master_data", *parts)
        if cached is not None:
            return cached
    rows, total = await MasterDataRepository(session).generic_page(collection, page)
    items = [_generic_payload(row) for row in rows]
    result = paged(items, page, total)
    if collection in CACHEABLE_GENERIC_COLLECTIONS:
        await cache.set_json(
            "master_data", *parts, value=result, ttl_seconds=settings.cache_ttl_reference_seconds
        )
    return result


MASKED_SECRET = "********"


def _encrypt_payload(data: dict[str, Any]) -> dict[str, Any]:
    protected: dict[str, Any] = {}
    for key, value in data.items():
        if is_sensitive_field(key) and isinstance(value, str) and value:
            protected[key] = encrypt_secret(value)
        else:
            protected[key] = value
    return protected


def _generic_payload(row: ModuleRecord) -> dict[str, Any]:
    payload = dict(row.data or {})
    for key in list(payload.keys()):
        if is_sensitive_field(key):
            payload[key] = MASKED_SECRET
    payload["id"] = str(row.id)
    payload.setdefault("status", row.status)
    payload.setdefault("createdAt", row.created_at.isoformat() if row.created_at else None)
    payload.setdefault("updatedAt", row.updated_at.isoformat() if row.updated_at else None)
    return payload


async def get_generic(session: AsyncSession, context: RequestContext, collection: str, record_id: int) -> dict:
    row = await MasterDataRepository(session).generic(collection, record_id)
    if row is None:
        raise NotFound()
    return _generic_payload(row)


async def get_ui_schema(session: AsyncSession, page: str) -> dict[str, Any] | None:
    row = await MasterDataRepository(session).generic_by_record_no("__ui_schema__", page)
    return dict(row.data or {}) if row is not None else None


#: Generic collections have no relational model, but the identity keys that
#: drive their list/title/search behaviour still have a bounded shape.
_GENERIC_SCHEMA = RecordSchema(
    (
        FieldSpec("code", max_length=64, label="Code"),
        FieldSpec("name", max_length=255, label="Name"),
        FieldSpec("documentNo", max_length=64, label="Document number"),
        FieldSpec("status", max_length=32, label="Status"),
    )
)


async def create_generic(session: AsyncSession, context: RequestContext, collection: str, data: dict) -> dict:
    data = _GENERIC_SCHEMA.validate(data)
    payload = _encrypt_payload(
        {key: value for key, value in data.items() if key not in {"id"}}
    )
    row = ModuleRecord(
        collection=collection,
        record_no=str(payload.get("code") or payload.get("name") or payload.get("documentNo") or "") or None,
        status=str(payload.get("status") or "Active"),
        data=payload,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    if collection in CACHEABLE_GENERIC_COLLECTIONS:
        await cache.bump("master_data")
    return _generic_payload(row)


async def update_generic(session: AsyncSession, context: RequestContext, collection: str, record_id: int, data: dict) -> dict:
    row = await MasterDataRepository(session).generic(collection, record_id)
    if row is None:
        raise NotFound()
    data = _GENERIC_SCHEMA.validate(data, partial=True)
    payload = _encrypt_payload(
        {key: value for key, value in data.items() if key not in {"id"}}
    )
    merged = {**(row.data or {}), **payload}
    row.data = merged
    if "status" in payload:
        row.status = str(payload["status"])
    row.record_no = str(merged.get("code") or merged.get("name") or merged.get("documentNo") or "") or None
    await session.commit()
    await session.refresh(row)
    if collection in CACHEABLE_GENERIC_COLLECTIONS:
        await cache.bump("master_data")
    return _generic_payload(row)


async def delete_generic(session: AsyncSession, context: RequestContext, collection: str, ids: list[int]) -> None:
    from app.modules.archive.service import ARCHIVABLE_GENERIC_COLLECTIONS, archive_record

    rows: list[ModuleRecord] = []
    for record_id in ids:
        row = await session.get(ModuleRecord, record_id)
        if row is not None and row.collection == collection:
            await deletion.require_inactive(row.status, label=f"{collection} record")
            rows.append(row)
    for row in rows:
        if collection in ARCHIVABLE_GENERIC_COLLECTIONS:
            await archive_record(session, context, collection, row.id)
        else:
            await session.delete(row)
    if collection not in ARCHIVABLE_GENERIC_COLLECTIONS:
        await session.commit()
    if collection in CACHEABLE_GENERIC_COLLECTIONS:
        await cache.bump("master_data")

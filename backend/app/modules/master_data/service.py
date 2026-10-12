from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.config import settings
from app.core.context import RequestContext
from app.core.crypto import encrypt_secret, is_sensitive_field
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, paged
from app.core.serialization import jsonable, to_camel
from app.modules.master_data.models import (
    BusinessParty,
    ContainerType,
    FeeType,
    ModuleRecord,
    Place,
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


def _enum(value: Any) -> Any:
    return jsonable(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "active", "enabled"}
    return bool(value)


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
        "place": (Place, "name"),
        "trade_direction": (TradeDirection, "name"),
        "container_type": (ContainerType, "name"),
        "transport_type": (TransportType, "name"),
        "fee_type": (FeeType, "name"),
        "business_party": (BusinessParty, "legal_name"),
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
    row we register a minimal ACTIVE record instead of writing a dangling FK —
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
            elif column is not None and str(column.type).startswith("JSON") and value is not None and not isinstance(value, list):
                value = [value]
            setattr(model, attr, value)
    for camel, ref in spec.refs.items():
        if camel in data:
            resolved = await resolve_reference(session, ref.target, data[camel])
            setattr(model, ref.label, resolved)


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
    """The form edits width/height in meters; the table stores millimeters."""
    for meters_key, millimeter_key in (("widthMeters", "widthMillimeter"), ("heightMeters", "heightMillimeter")):
        if meters_key not in data:
            continue
        value = data[meters_key]
        if value in (None, ""):
            data[millimeter_key] = None
            continue
        try:
            data[millimeter_key] = round(float(value) * 1000, 2)
        except (TypeError, ValueError):
            continue
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
            "roles": "roles",
            "status": "status",
            "taxIdentifier": "vat_tin",
        },
        search=["party_code", "legal_name", "display_name", "phone", "email"],
    ),
    "places": Spec(
        model=Place,
        title="name",
        fields={
            "code": "code",
            "name": "name",
            "description": "description",
            "address": "address",
            "status": "status",
        },
        search=["code", "name"],
    ),
    "tradeDirections": Spec(
        model=TradeDirection,
        title="name",
        fields={"code": "code", "name": "name", "description": "description", "status": "status"},
        search=["code", "name"],
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
        computed=_container_computed,
        transform_input=_container_transform,
    ),
    "transportTypes": Spec(
        model=TransportType,
        title="name",
        fields={"code": "code", "name": "name", "description": "description", "status": "status"},
        search=["code", "name"],
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
    ),
    "feeTypes": Spec(
        model=FeeType,
        title="name",
        fields={"code": "code", "name": "name", "description": "description", "status": "status"},
        search=["code", "name"],
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
    "currencies",
}

# Generic collections safe to cache: small, non-sensitive option lists only.
CACHEABLE_GENERIC_COLLECTIONS = {"currencies"}


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
    ("assetCode", "This asset code is already in use.", ("asset_code",)),
    ("identity", "This transport type and identity already exist.", ("transport_type_id",)),
    ("code", "This code is already in use.", ("code",)),
)


def _unique_violation(exc: IntegrityError) -> ValidationFailed:
    detail = str(getattr(exc, "orig", exc)).lower()
    for field_key, message, tokens in _UNIQUE_FIELD_ERRORS:
        if any(token in detail for token in tokens):
            return ValidationFailed(message, {field_key: message})
    return ValidationFailed("A record with the same unique value already exists.")


async def create_reference(session: AsyncSession, collection: str, data: dict) -> dict:
    spec = get_spec(collection)
    if spec.transform_input is not None:
        data = spec.transform_input(dict(data))
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


async def create_generic(session: AsyncSession, context: RequestContext, collection: str, data: dict) -> dict:
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

    for record_id in ids:
        row = await session.get(ModuleRecord, record_id)
        if row is not None and row.collection == collection:
            if collection in ARCHIVABLE_GENERIC_COLLECTIONS:
                await archive_record(session, context, collection, record_id)
            else:
                await session.delete(row)
    if collection not in ARCHIVABLE_GENERIC_COLLECTIONS:
        await session.commit()
    if collection in CACHEABLE_GENERIC_COLLECTIONS:
        await cache.bump("master_data")

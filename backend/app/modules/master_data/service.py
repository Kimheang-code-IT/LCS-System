from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.crypto import encrypt_secret, is_sensitive_field
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, list_sort_orders, paged
from app.core.serialization import jsonable, to_camel
from app.modules.master_data.models import (
    BusinessParty,
    ContainerType,
    FeeType,
    ModuleRecord,
    PartyRole,
    Place,
    TradeDirection,
    TransportAsset,
    TransportType,
)


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
    return created.id


async def apply_input(spec: Spec, model: Any, data: dict[str, Any], session: AsyncSession) -> None:
    for camel, attr in spec.fields.items():
        if camel in data:
            value = data[camel]
            column = spec.model.__table__.columns.get(attr)
            if column is not None and str(column.type).startswith("BOOLEAN"):
                value = _bool(value)
            setattr(model, attr, value)
    for camel, ref in spec.refs.items():
        if camel in data:
            resolved = await resolve_reference(session, ref.target, data[camel])
            setattr(model, ref.label, resolved)


async def _party_roles(model: BusinessParty, session: AsyncSession) -> dict[str, Any]:
    roles = (
        await session.execute(select(PartyRole.role_type).where(PartyRole.party_id == model.id))
    ).scalars().all()
    return {"roles": list(roles), "country": model.country_code, "taxIdentifier": model.vat_tin}


async def _sync_party_roles(model: Any, data: dict[str, Any], session: AsyncSession) -> None:
    if "roles" not in data:
        return
    roles = data["roles"]
    if isinstance(roles, str):
        roles = [roles]
    from sqlalchemy import delete

    await session.execute(delete(PartyRole).where(PartyRole.party_id == model.id))
    for role in roles:
        session.add(PartyRole(party_id=model.id, role_type=str(role), is_primary=False))


async def _asset_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    transport_type = await session.get(TransportType, model.transport_type_id) if model.transport_type_id else None
    owner = await session.get(BusinessParty, model.owner_party_id) if model.owner_party_id else None
    operator = await session.get(BusinessParty, model.operator_party_id) if model.operator_party_id else None
    return {
        "transportType": transport_type.name if transport_type else None,
        "transportTypeId": model.transport_type_id,
        "ownerParty": owner.legal_name if owner else None,
        "operatorParty": operator.legal_name if operator else None,
        "registrationCountry": model.registration_country_code,
    }


async def _place_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    parent = await session.get(Place, model.parent_place_id) if model.parent_place_id else None
    return {"parentPlace": parent.name if parent else None, "category": model.place_category, "country": model.country_code}


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
            "status": "status",
            "taxIdentifier": "vat_tin",
            "country": "country_code",
        },
        search=["party_code", "legal_name", "display_name", "phone", "email"],
        computed=_party_roles,
        after_create=_sync_party_roles,
    ),
    "places": Spec(
        model=Place,
        title="name",
        fields={
            "code": "code",
            "name": "name",
            "description": "description",
            "category": "place_category",
            "address": "address",
            "latitude": "latitude",
            "longitude": "longitude",
            "status": "status",
            "country": "country_code",
        },
        refs={"parentPlace": RefSpec("place", "parent_place_id")},
        search=["code", "name"],
        computed=_place_computed,
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
            "maxGrossWeightKg": "max_gross_weight_kg",
            "description": "description",
            "status": "status",
        },
        search=["code", "name"],
        computed=_container_computed,
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
            "registrationCountry": "registration_country_code",
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


def get_spec(collection: str) -> Spec:
    spec = SPECS.get(collection)
    if spec is None:
        raise NotFound(f"Unknown reference collection: {collection}")
    return spec


async def list_reference(session: AsyncSession, context: RequestContext, collection: str, page: PageParams) -> dict:
    spec = get_spec(collection)
    stmt = select(spec.model).where(spec.model.deleted_at.is_(None))
    if page.q:
        pattern = f"%{page.q}%"
        conditions = [getattr(spec.model, column).ilike(pattern) for column in spec.search]
        if conditions:
            stmt = stmt.where(or_(*conditions))
    if page.status:
        stmt = stmt.where(getattr(spec.model, spec.status_field) == page.status)
    total = await count_query(session, stmt)
    stmt = stmt.order_by(*list_sort_orders(spec.model, page, spec.model.id.desc()))
    rows = (await session.execute(stmt.limit(page.page_size).offset(page.offset))).scalars().all()
    items = [await serialize(spec, row, session) for row in rows]
    return paged(items, page, total)


async def get_reference(session: AsyncSession, collection: str, record_id: int) -> dict:
    spec = get_spec(collection)
    model = await session.get(spec.model, record_id)
    if model is None or model.deleted_at is not None:
        raise NotFound()
    return await serialize(spec, model, session)


async def create_reference(session: AsyncSession, collection: str, data: dict) -> dict:
    spec = get_spec(collection)
    model = spec.model()
    await apply_input(spec, model, data, session)
    session.add(model)
    await session.flush()
    if spec.after_create is not None:
        await spec.after_create(model, data, session)
        await session.flush()
    await session.commit()
    await session.refresh(model)
    return await serialize(spec, model, session)


async def update_reference(session: AsyncSession, collection: str, record_id: int, data: dict) -> dict:
    spec = get_spec(collection)
    model = await session.get(spec.model, record_id)
    if model is None or model.deleted_at is not None:
        raise NotFound()
    await apply_input(spec, model, data, session)
    if spec.after_create is not None:
        await spec.after_create(model, data, session)
    await session.commit()
    await session.refresh(model)
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
    models: list[Any] = []
    for record_id in ids:
        model = await session.get(spec.model, record_id)
        if model is not None:
            models.append(model)
    if any(str(getattr(model, spec.status_field, "") or "").strip().upper() == "ACTIVE" for model in models):
        raise Conflict(
            "REFERENCE_ACTIVE",
            "Active records cannot be deleted. Deactivate the record first.",
        )
    from app.modules.archive.service import archive_record

    for model in models:
        await archive_record(session, context, collection, model.id)


# --- Generic record store -----------------------------------------------------
async def list_generic(session: AsyncSession, context: RequestContext, collection: str, page: PageParams) -> dict:
    stmt = select(ModuleRecord).where(ModuleRecord.collection == collection, ModuleRecord.deleted_at.is_(None))
    if page.q:
        stmt = stmt.where(ModuleRecord.data["name"].as_string().ilike(f"%{page.q}%"))
    if page.status:
        stmt = stmt.where(ModuleRecord.status == page.status)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(ModuleRecord, page, ModuleRecord.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    items = [_generic_payload(row) for row in rows]
    return paged(items, page, total)


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
    row = await session.get(ModuleRecord, record_id)
    if row is None or row.collection != collection or row.deleted_at is not None:
        raise NotFound()
    return _generic_payload(row)


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
    return _generic_payload(row)


async def update_generic(session: AsyncSession, context: RequestContext, collection: str, record_id: int, data: dict) -> dict:
    row = await session.get(ModuleRecord, record_id)
    if row is None or row.collection != collection or row.deleted_at is not None:
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


async def assert_reference_exists(session: AsyncSession, model: type, record_id: int | None, message: str) -> None:
    if record_id is None:
        return
    if await session.get(model, record_id) is None:
        raise ValidationFailed(message)

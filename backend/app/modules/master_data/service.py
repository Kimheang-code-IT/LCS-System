from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.crypto import encrypt_secret, is_sensitive_field
from app.core.exceptions import NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, paged
from app.core.serialization import jsonable, to_camel
from app.modules.master_data.models import (
    BusinessParty,
    ComponentGroup,
    ComponentTemplate,
    ContainerType,
    FeeType,
    ModuleRecord,
    PartyRole,
    Place,
    TemplateAttribute,
    TradeDirection,
    TradeDirectionComponent,
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
        "component_group": (ComponentGroup, "name"),
        "business_party": (BusinessParty, "legal_name"),
    }
    if target == "component_template":
        row = (
            await session.execute(
                select(ComponentTemplate).where(or_(ComponentTemplate.code == text, ComponentTemplate.name == text)).order_by(ComponentTemplate.version.desc())
            )
        ).scalars().first()
        return row.id if row else None
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
    row = (await session.execute(select(model).where(getattr(model, attribute) == text))).scalars().first()
    return row.id if row else None


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


async def _template_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    count = await session.scalar(
        select(func.count()).select_from(TemplateAttribute).where(TemplateAttribute.template_id == model.id)
    )
    attributes = (
        await session.execute(
            select(TemplateAttribute).where(TemplateAttribute.template_id == model.id).order_by(TemplateAttribute.display_order)
        )
    ).scalars().all()
    return {
        "templateVersion": model.version,
        "version": model.version,
        "attributeCount": int(count or 0),
        "minimumInstances": model.minimum_instances,
        "maximumInstances": model.maximum_instances,
        "group": model.category,
        "attributes": [
            {
                "id": attr.id,
                "code": attr.code,
                "label": attr.label,
                "dataType": attr.data_type,
                "inputType": attr.input_type,
                "required": attr.is_required,
                "repeatable": attr.is_repeatable,
                "displayOrder": attr.display_order,
                "referenceType": attr.reference_type,
                "validationRules": attr.validation_rules,
                "status": attr.status,
            }
            for attr in attributes
        ],
    }


async def _sync_template_attributes(model: Any, data: dict[str, Any], session: AsyncSession) -> None:
    if "attributes" not in data:
        return
    from sqlalchemy import delete

    await session.execute(delete(TemplateAttribute).where(TemplateAttribute.template_id == model.id))
    for index, item in enumerate(data["attributes"]):
        if not isinstance(item, dict):
            continue
        rules = item.get("validationRules")
        if isinstance(rules, str):
            rules = {"expression": rules}
        session.add(
            TemplateAttribute(
                template_id=model.id,
                code=str(item.get("code") or f"ATTR{index + 1}"),
                label=str(item.get("label") or item.get("code") or f"Attribute {index + 1}"),
                data_type=str(item.get("dataType") or item.get("data_type") or "text").lower(),
                input_type=item.get("inputType"),
                is_required=_bool(item.get("required", False)),
                is_repeatable=_bool(item.get("repeatable", False)),
                display_order=int(item.get("displayOrder") or index + 1),
                validation_rules=rules if isinstance(rules, dict) else {},
                reference_type=item.get("referenceType"),
                status=str(item.get("status") or "ACTIVE"),
            )
        )


async def _tdc_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    direction = await session.get(TradeDirection, model.trade_direction_id)
    group = await session.get(ComponentGroup, model.component_group_id) if model.component_group_id else None
    template = await session.get(ComponentTemplate, model.component_template_id) if model.component_template_id else None
    return {
        "tradeDirection": direction.name if direction else None,
        "tradeDirectionId": model.trade_direction_id,
        "componentGroup": group.name if group else None,
        "componentGroupId": model.component_group_id,
        "componentTemplate": template.name if template else None,
        "componentTemplateId": model.component_template_id,
        "templateVersion": template.version if template else None,
        "required": model.is_required,
        "instanceModeOverride": model.instance_mode_override,
    }


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


async def _group_computed(model: Any, session: AsyncSession) -> dict[str, Any]:
    return {"showOnJobWorkspace": model.show_on_job_workspace, "displayOrder": model.display_order}


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
    "componentGroups": Spec(
        model=ComponentGroup,
        title="name",
        fields={
            "code": "code",
            "name": "name",
            "description": "description",
            "displayOrder": "display_order",
            "showOnJobWorkspace": "show_on_job_workspace",
            "status": "status",
        },
        search=["code", "name"],
        computed=_group_computed,
    ),
    "componentTemplates": Spec(
        model=ComponentTemplate,
        title="name",
        fields={
            "code": "code",
            "name": "name",
            "description": "description",
            "group": "category",
            "instanceMode": "instance_mode",
            "version": "version",
            "minimumInstances": "minimum_instances",
            "maximumInstances": "maximum_instances",
            "status": "status",
        },
        search=["code", "name"],
        computed=_template_computed,
        after_create=_sync_template_attributes,
    ),
    "tradeDirectionComponents": Spec(
        model=TradeDirectionComponent,
        title="component_template_id",
        fields={
            "displayOrder": "display_order",
            "required": "is_required",
            "instanceModeOverride": "instance_mode_override",
            "status": "status",
        },
        refs={
            "tradeDirection": RefSpec("trade_direction", "trade_direction_id"),
            "componentGroup": RefSpec("component_group", "component_group_id"),
            "componentTemplate": RefSpec("component_template", "component_template_id"),
        },
        search=[],
        computed=_tdc_computed,
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


def get_spec(collection: str) -> Spec:
    spec = SPECS.get(collection)
    if spec is None:
        raise NotFound(f"Unknown reference collection: {collection}")
    return spec


async def list_reference(session: AsyncSession, context: RequestContext, collection: str, page: PageParams) -> dict:
    spec = get_spec(collection)
    stmt = select(spec.model)
    if page.q:
        pattern = f"%{page.q}%"
        conditions = [getattr(spec.model, column).ilike(pattern) for column in spec.search]
        if conditions:
            stmt = stmt.where(or_(*conditions))
    if page.status:
        stmt = stmt.where(getattr(spec.model, spec.status_field) == page.status)
    total = await count_query(session, stmt)
    order_column = spec.model.id
    if page.sort_by and page.sort_by in spec.model.__table__.columns:
        order_column = getattr(spec.model, page.sort_by)
    stmt = stmt.order_by(order_column.desc() if page.sort_order == "desc" else order_column.asc())
    rows = (await session.execute(stmt.limit(page.page_size).offset(page.offset))).scalars().all()
    items = [await serialize(spec, row, session) for row in rows]
    return paged(items, page, total)


async def get_reference(session: AsyncSession, collection: str, record_id: int) -> dict:
    spec = get_spec(collection)
    model = await session.get(spec.model, record_id)
    if model is None:
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
    if model is None:
        raise NotFound()
    await apply_input(spec, model, data, session)
    if spec.after_create is not None:
        await spec.after_create(model, data, session)
    await session.commit()
    await session.refresh(model)
    return await serialize(spec, model, session)


async def delete_reference(session: AsyncSession, collection: str, ids: list[int]) -> None:
    spec = get_spec(collection)
    for record_id in ids:
        model = await session.get(spec.model, record_id)
        if model is not None:
            await session.delete(model)
    await session.commit()


# --- Generic record store -----------------------------------------------------
async def list_generic(session: AsyncSession, context: RequestContext, collection: str, page: PageParams) -> dict:
    stmt = select(ModuleRecord).where(ModuleRecord.collection == collection)
    if page.q:
        stmt = stmt.where(ModuleRecord.data["name"].as_string().ilike(f"%{page.q}%"))
    if page.status:
        stmt = stmt.where(ModuleRecord.status == page.status)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(stmt.order_by(ModuleRecord.id.desc()).limit(page.page_size).offset(page.offset))
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
    if row is None or row.collection != collection:
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
    if row is None or row.collection != collection:
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
    for record_id in ids:
        row = await session.get(ModuleRecord, record_id)
        if row is not None and row.collection == collection:
            await session.delete(row)
    await session.commit()


async def assert_reference_exists(session: AsyncSession, model: type, record_id: int | None, message: str) -> None:
    if record_id is None:
        return
    if await session.get(model, record_id) is None:
        raise ValidationFailed(message)

"""Component configuration: reusable attributes, groups of attributes, and tabs of groups.

The hierarchy is Attribute → Group → Tab. A group renders as a ``table``
(repeatable rows) or a ``form`` (single record). Tabs are assigned to trade
directions and decide what the Service Order form shows. No structural change
requires a schema migration: attributes/options/validation live as JSON.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, list_sort_orders, paged
from app.core.serialization import jsonable
from app.modules.master_data.models import (
    ComponentAttribute,
    ComponentGroup,
    ComponentGroupAttribute,
    ComponentTab,
    ComponentTabGroup,
    ComponentTabTradeDirection,
)
from app.modules.operations.models import ServiceOrderComponentRow

REFERENCE_TYPES = (
    "business_party",
    "place",
    "transport_asset",
    "transport_type",
    "container",
    "fee_type",
    "user",
)

DATA_TYPES = (
    "text",
    "textarea",
    "number",
    "decimal",
    "money",
    "currency",
    "date",
    "datetime",
    "select",
    "multi_select",
    "checkbox",
    "boolean",
    "reference",
)
RENDER_MODES = ("table", "form")


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "on"}


def _normalize_code(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "-").replace("_", "-")


def _validate_data_type(value: Any) -> str:
    data_type = str(value or "text").strip().lower()
    if data_type not in DATA_TYPES:
        raise ValidationFailed(f"Unsupported attribute type: {data_type}", {"dataType": "Unsupported"})
    return data_type


# --- Attributes --------------------------------------------------------------
def attribute_payload(attribute: ComponentAttribute) -> dict[str, Any]:
    return {
        "id": str(attribute.id),
        "code": attribute.code,
        "label": attribute.label,
        "labelKm": attribute.label_km,
        "dataType": attribute.data_type,
        "inputType": attribute.input_type,
        "referenceType": attribute.reference_type,
        "isRequired": attribute.is_required,
        "defaultValue": attribute.default_value,
        "placeholder": attribute.placeholder,
        "width": attribute.width,
        "options": attribute.options or [],
        "validationRules": attribute.validation_rules or {},
        "status": attribute.status,
        "createdAt": attribute.created_at.isoformat() if attribute.created_at else None,
        "updatedAt": attribute.updated_at.isoformat() if attribute.updated_at else None,
    }


async def list_attributes(
    session: AsyncSession, context: RequestContext, page: PageParams, include_archived: bool = False
) -> dict:
    stmt = select(ComponentAttribute)
    if page.q:
        stmt = stmt.where(ComponentAttribute.label.ilike(f"%{page.q}%") | ComponentAttribute.code.ilike(f"%{page.q}%"))
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(ComponentAttribute, page, ComponentAttribute.label, ComponentAttribute.id))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    return paged([attribute_payload(row) for row in rows], page, total)


async def _get_attribute(session: AsyncSession, attribute_id: int) -> ComponentAttribute:
    attribute = await session.get(ComponentAttribute, attribute_id)
    if attribute is None:
        raise NotFound("Component attribute not found.")
    return attribute


async def create_attribute(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    code = _normalize_code(data.get("code") or data.get("label"))
    if not code:
        raise ValidationFailed("An attribute code or label is required.", {"code": "Required"})
    exists = (
        await session.execute(select(ComponentAttribute).where(ComponentAttribute.code == code))
    ).scalars().first()
    if exists is not None:
        raise Conflict("DUPLICATE_ATTRIBUTE_CODE", "An attribute with this code already exists.", {"code": "Already in use"})
    data_type = _validate_data_type(data.get("dataType") or data.get("data_type"))
    reference_type = data.get("referenceType")
    if data_type == "reference" and reference_type not in REFERENCE_TYPES:
        raise ValidationFailed("A valid reference type is required.", {"referenceType": "Required"})
    attribute = ComponentAttribute(
        code=code,
        label=str(data.get("label") or code.replace("-", " ").title()),
        label_km=data.get("labelKm"),
        data_type=data_type,
        input_type=data.get("inputType"),
        reference_type=reference_type if data_type == "reference" else None,
        is_required=_bool(data.get("isRequired"), False),
        default_value=data.get("defaultValue"),
        placeholder=data.get("placeholder"),
        width=data.get("width"),
        options=jsonable(data.get("options") or []),
        validation_rules=jsonable(data.get("validationRules") or {}),
        status=str(data.get("status") or "ACTIVE"),
    )
    session.add(attribute)
    await session.commit()
    return attribute_payload(attribute)


async def update_attribute(session: AsyncSession, context: RequestContext, attribute_id: int, data: dict[str, Any]) -> dict:
    attribute = await _get_attribute(session, attribute_id)
    if data.get("label") is not None:
        attribute.label = str(data["label"])
    if data.get("labelKm") is not None:
        attribute.label_km = data.get("labelKm")
    if data.get("dataType") is not None:
        attribute.data_type = _validate_data_type(data["dataType"])
    if data.get("inputType") is not None:
        attribute.input_type = data.get("inputType")
    if data.get("referenceType") is not None:
        attribute.reference_type = data.get("referenceType")
    if attribute.data_type == "reference" and attribute.reference_type not in REFERENCE_TYPES:
        raise ValidationFailed("A valid reference type is required.", {"referenceType": "Required"})
    if data.get("isRequired") is not None:
        attribute.is_required = _bool(data["isRequired"], attribute.is_required)
    if data.get("defaultValue") is not None:
        attribute.default_value = data.get("defaultValue")
    if data.get("placeholder") is not None:
        attribute.placeholder = data.get("placeholder")
    if data.get("width") is not None:
        attribute.width = data.get("width")
    if data.get("options") is not None:
        attribute.options = jsonable(data["options"])
    if data.get("validationRules") is not None:
        attribute.validation_rules = jsonable(data["validationRules"])
    if data.get("status") is not None:
        attribute.status = str(data["status"])
    await session.commit()
    return attribute_payload(attribute)


async def delete_attribute(session: AsyncSession, context: RequestContext, attribute_id: int) -> dict[str, Any]:
    attribute = await _get_attribute(session, attribute_id)
    in_use = await session.scalar(
        select(func.count()).select_from(ComponentGroupAttribute).where(ComponentGroupAttribute.attribute_id == attribute.id)
    )
    if in_use:
        attribute.status = "INACTIVE"
        await session.commit()
        return {"archived": True, "id": str(attribute.id)}
    await session.delete(attribute)
    await session.commit()
    return {"archived": False, "id": str(attribute_id)}


# --- Groups ------------------------------------------------------------------
def group_payload(group: ComponentGroup, attribute_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(group.id),
        "code": group.code,
        "name": group.name,
        "nameKm": group.name_km,
        "description": group.description,
        "renderMode": group.render_mode,
        "displayOrder": group.display_order,
        "isActive": group.is_active,
        "isArchived": group.is_archived,
        "attributeCount": attribute_count,
        "createdAt": group.created_at.isoformat() if group.created_at else None,
        "updatedAt": group.updated_at.isoformat() if group.updated_at else None,
    }


async def list_groups(session: AsyncSession, context: RequestContext, page: PageParams, include_archived: bool = False) -> dict:
    stmt = select(ComponentGroup)
    if not include_archived:
        stmt = stmt.where(ComponentGroup.is_archived.is_(False))
    if page.q:
        stmt = stmt.where(ComponentGroup.name.ilike(f"%{page.q}%") | ComponentGroup.code.ilike(f"%{page.q}%"))
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(ComponentGroup, page, ComponentGroup.display_order, ComponentGroup.id))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    items = []
    for row in rows:
        count = await session.scalar(
            select(func.count()).select_from(ComponentGroupAttribute).where(
                ComponentGroupAttribute.group_id == row.id, ComponentGroupAttribute.status == "ACTIVE"
            )
        )
        items.append(group_payload(row, int(count or 0)))
    return paged(items, page, total)


async def _get_group(session: AsyncSession, group_id: int) -> ComponentGroup:
    group = await session.get(ComponentGroup, group_id)
    if group is None:
        raise NotFound("Component group not found.")
    return group


async def create_group(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    code = _normalize_code(data.get("code") or data.get("name"))
    if not code:
        raise ValidationFailed("A group code or name is required.", {"code": "Required"})
    exists = (
        await session.execute(select(ComponentGroup).where(ComponentGroup.code == code))
    ).scalars().first()
    if exists is not None:
        raise Conflict("DUPLICATE_GROUP_CODE", "A group with this code already exists.", {"code": "Already in use"})
    render_mode = str(data.get("renderMode") or "table").strip().lower()
    if render_mode not in RENDER_MODES:
        raise ValidationFailed("renderMode must be 'table' or 'form'.", {"renderMode": "Unsupported"})
    max_order = await session.scalar(select(func.max(ComponentGroup.display_order)))
    group = ComponentGroup(
        code=code,
        name=str(data.get("name") or code.replace("-", " ").title()),
        name_km=data.get("nameKm"),
        description=data.get("description"),
        render_mode=render_mode,
        display_order=int(data.get("displayOrder") if data.get("displayOrder") is not None else (max_order or 0) + 10),
        is_active=_bool(data.get("isActive"), True),
    )
    session.add(group)
    await session.commit()
    return group_payload(group)


async def update_group(session: AsyncSession, context: RequestContext, group_id: int, data: dict[str, Any]) -> dict:
    group = await _get_group(session, group_id)
    if data.get("name") is not None:
        group.name = str(data["name"])
    if data.get("nameKm") is not None:
        group.name_km = data.get("nameKm")
    if data.get("description") is not None:
        group.description = data.get("description")
    if data.get("renderMode") is not None:
        render_mode = str(data["renderMode"]).strip().lower()
        if render_mode not in RENDER_MODES:
            raise ValidationFailed("renderMode must be 'table' or 'form'.", {"renderMode": "Unsupported"})
        group.render_mode = render_mode
    if data.get("displayOrder") is not None:
        group.display_order = int(data["displayOrder"])
    if data.get("isActive") is not None:
        group.is_active = _bool(data["isActive"], group.is_active)
    if data.get("isArchived") is not None:
        group.is_archived = _bool(data["isArchived"], group.is_archived)
        if group.is_archived:
            group.is_active = False
    await session.commit()
    return group_payload(group)


async def delete_group(session: AsyncSession, context: RequestContext, group_id: int) -> dict[str, Any]:
    group = await _get_group(session, group_id)
    used = await session.scalar(
        select(func.count()).select_from(ServiceOrderComponentRow).where(ServiceOrderComponentRow.group_id == group.id)
    ) or await session.scalar(
        select(func.count()).select_from(ComponentTabGroup).where(ComponentTabGroup.group_id == group.id)
    )
    if used:
        group.is_archived = True
        group.is_active = False
        await session.commit()
        return {"archived": True, "id": str(group.id)}
    await session.delete(group)
    await session.commit()
    return {"archived": False, "id": str(group_id)}


# --- Group attributes --------------------------------------------------------
def membership_payload(membership: ComponentGroupAttribute, attribute: ComponentAttribute) -> dict[str, Any]:
    return {
        "id": str(membership.id),
        "groupId": str(membership.group_id),
        "attributeId": str(attribute.id),
        "code": attribute.code,
        "label": attribute.label,
        "labelKm": attribute.label_km,
        "dataType": attribute.data_type,
        "inputType": attribute.input_type,
        "referenceType": attribute.reference_type,
        "isRequired": membership.is_required if membership.is_required is not None else attribute.is_required,
        "width": membership.width or attribute.width,
        "options": attribute.options or [],
        "defaultValue": attribute.default_value,
        "placeholder": attribute.placeholder,
        "displayOrder": membership.display_order,
        "status": membership.status,
    }


async def list_group_attributes(session: AsyncSession, context: RequestContext, group_id: int) -> list[dict]:
    await _get_group(session, group_id)
    rows = (
        await session.execute(
            select(ComponentGroupAttribute, ComponentAttribute)
            .join(ComponentAttribute, ComponentAttribute.id == ComponentGroupAttribute.attribute_id)
            .where(ComponentGroupAttribute.group_id == group_id)
            .order_by(ComponentGroupAttribute.display_order, ComponentGroupAttribute.id)
        )
    ).all()
    return [membership_payload(membership, attribute) for membership, attribute in rows]


async def _resolve_attribute(session: AsyncSession, data: dict[str, Any]) -> ComponentAttribute:
    attribute_id = data.get("attributeId") or data.get("id")
    if attribute_id not in (None, ""):
        return await _get_attribute(session, int(attribute_id))
    code = data.get("code")
    if not code:
        raise ValidationFailed("An attributeId or code is required.", {"attributeId": "Required"})
    attribute = (
        await session.execute(select(ComponentAttribute).where(ComponentAttribute.code == str(code)))
    ).scalars().first()
    if attribute is None:
        raise NotFound("Component attribute not found.")
    return attribute


async def add_group_attribute(session: AsyncSession, context: RequestContext, group_id: int, data: dict[str, Any]) -> dict:
    group = await _get_group(session, group_id)
    attribute = await _resolve_attribute(session, data)
    exists = (
        await session.execute(
            select(ComponentGroupAttribute).where(
                ComponentGroupAttribute.group_id == group.id, ComponentGroupAttribute.attribute_id == attribute.id
            )
        )
    ).scalars().first()
    if exists is not None:
        raise Conflict("DUPLICATE_GROUP_ATTRIBUTE", "This attribute is already in the group.", {"attributeId": "Already in use"})
    max_order = await session.scalar(
        select(func.max(ComponentGroupAttribute.display_order)).where(ComponentGroupAttribute.group_id == group.id)
    )
    membership = ComponentGroupAttribute(
        group_id=group.id,
        attribute_id=attribute.id,
        is_required=(_bool(data["isRequired"]) if data.get("isRequired") is not None else None),
        width=data.get("width"),
        display_order=int(data.get("displayOrder") if data.get("displayOrder") is not None else (max_order or 0) + 10),
        status=str(data.get("status") or "ACTIVE"),
    )
    session.add(membership)
    await session.commit()
    return membership_payload(membership, attribute)


async def _get_membership(session: AsyncSession, membership_id: int) -> ComponentGroupAttribute:
    membership = await session.get(ComponentGroupAttribute, membership_id)
    if membership is None:
        raise NotFound("Group attribute not found.")
    return membership


async def update_group_attribute(session: AsyncSession, context: RequestContext, membership_id: int, data: dict[str, Any]) -> dict:
    membership = await _get_membership(session, membership_id)
    if data.get("isRequired") is not None:
        membership.is_required = _bool(data["isRequired"])
    if data.get("width") is not None:
        membership.width = data.get("width")
    if data.get("displayOrder") is not None:
        membership.display_order = int(data["displayOrder"])
    if data.get("status") is not None:
        membership.status = str(data["status"])
    await session.commit()
    attribute = await _get_attribute(session, membership.attribute_id)
    return membership_payload(membership, attribute)


async def remove_group_attribute(session: AsyncSession, context: RequestContext, membership_id: int) -> dict[str, Any]:
    membership = await _get_membership(session, membership_id)
    await session.delete(membership)
    await session.commit()
    return {"removed": True, "id": str(membership_id)}


async def reorder_group_attributes(session: AsyncSession, context: RequestContext, group_id: int, ordered_ids: list[int]) -> list[dict]:
    await _get_group(session, group_id)
    for index, membership_id in enumerate(ordered_ids):
        membership = await session.get(ComponentGroupAttribute, membership_id)
        if membership is not None and membership.group_id == group_id:
            membership.display_order = (index + 1) * 10
    await session.commit()
    return await list_group_attributes(session, context, group_id)


# --- Tabs --------------------------------------------------------------------
def tab_payload(tab: ComponentTab, group_count: int = 0, direction_ids: list[int] | None = None) -> dict[str, Any]:
    return {
        "id": str(tab.id),
        "code": tab.code,
        "name": tab.name,
        "nameKm": tab.name_km,
        "description": tab.description,
        "icon": tab.icon,
        "displayOrder": tab.display_order,
        "isActive": tab.is_active,
        "isArchived": tab.is_archived,
        "groupCount": group_count,
        "tradeDirectionIds": [str(item) for item in (direction_ids or [])],
        "createdAt": tab.created_at.isoformat() if tab.created_at else None,
        "updatedAt": tab.updated_at.isoformat() if tab.updated_at else None,
    }


async def list_tabs(session: AsyncSession, context: RequestContext, page: PageParams, include_archived: bool = False) -> dict:
    stmt = select(ComponentTab)
    if not include_archived:
        stmt = stmt.where(ComponentTab.is_archived.is_(False))
    if page.q:
        stmt = stmt.where(ComponentTab.name.ilike(f"%{page.q}%") | ComponentTab.code.ilike(f"%{page.q}%"))
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(ComponentTab, page, ComponentTab.display_order, ComponentTab.id))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    items = []
    for row in rows:
        count = await session.scalar(
            select(func.count()).select_from(ComponentTabGroup).where(
                ComponentTabGroup.tab_id == row.id, ComponentTabGroup.status == "ACTIVE"
            )
        )
        directions = (
            await session.execute(
                select(ComponentTabTradeDirection.trade_direction_id).where(
                    ComponentTabTradeDirection.tab_id == row.id, ComponentTabTradeDirection.status == "ACTIVE"
                )
            )
        ).scalars().all()
        items.append(tab_payload(row, int(count or 0), list(directions)))
    return paged(items, page, total)


async def _get_tab(session: AsyncSession, tab_id: int) -> ComponentTab:
    tab = await session.get(ComponentTab, tab_id)
    if tab is None:
        raise NotFound("Component tab not found.")
    return tab


async def create_tab(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    code = _normalize_code(data.get("code") or data.get("name"))
    if not code:
        raise ValidationFailed("A tab code or name is required.", {"code": "Required"})
    exists = (
        await session.execute(select(ComponentTab).where(ComponentTab.code == code))
    ).scalars().first()
    if exists is not None:
        raise Conflict("DUPLICATE_TAB_CODE", "A tab with this code already exists.", {"code": "Already in use"})
    max_order = await session.scalar(select(func.max(ComponentTab.display_order)))
    tab = ComponentTab(
        code=code,
        name=str(data.get("name") or code.replace("-", " ").title()),
        name_km=data.get("nameKm"),
        description=data.get("description"),
        icon=data.get("icon") or "i-lucide-table",
        display_order=int(data.get("displayOrder") if data.get("displayOrder") is not None else (max_order or 0) + 10),
        is_active=_bool(data.get("isActive"), True),
    )
    session.add(tab)
    await session.flush()
    direction_ids = data.get("tradeDirectionIds")
    if isinstance(direction_ids, list):
        for index, direction_id in enumerate(direction_ids):
            session.add(
                ComponentTabTradeDirection(
                    tab_id=tab.id, trade_direction_id=int(direction_id), display_order=(index + 1) * 10
                )
            )
    await session.commit()
    return tab_payload(tab, 0, [int(item) for item in direction_ids] if isinstance(direction_ids, list) else [])


async def update_tab(session: AsyncSession, context: RequestContext, tab_id: int, data: dict[str, Any]) -> dict:
    tab = await _get_tab(session, tab_id)
    if data.get("name") is not None:
        tab.name = str(data["name"])
    if data.get("nameKm") is not None:
        tab.name_km = data.get("nameKm")
    if data.get("description") is not None:
        tab.description = data.get("description")
    if data.get("icon") is not None:
        tab.icon = data.get("icon")
    if data.get("displayOrder") is not None:
        tab.display_order = int(data["displayOrder"])
    if data.get("isActive") is not None:
        tab.is_active = _bool(data["isActive"], tab.is_active)
    if data.get("isArchived") is not None:
        tab.is_archived = _bool(data["isArchived"], tab.is_archived)
        if tab.is_archived:
            tab.is_active = False
    if isinstance(data.get("tradeDirectionIds"), list):
        from sqlalchemy import delete

        await session.execute(
            delete(ComponentTabTradeDirection).where(ComponentTabTradeDirection.tab_id == tab.id)
        )
        for index, direction_id in enumerate(data["tradeDirectionIds"]):
            session.add(
                ComponentTabTradeDirection(
                    tab_id=tab.id, trade_direction_id=int(direction_id), display_order=(index + 1) * 10
                )
            )
    await session.commit()
    return await _tab_detail(session, context, tab.id)


async def delete_tab(session: AsyncSession, context: RequestContext, tab_id: int) -> dict[str, Any]:
    tab = await _get_tab(session, tab_id)
    await session.delete(tab)
    await session.commit()
    return {"archived": False, "id": str(tab_id)}


async def _tab_detail(session: AsyncSession, context: RequestContext, tab_id: int) -> dict:
    tab = await _get_tab(session, tab_id)
    groups = await list_tab_groups(session, context, tab_id)
    directions = (
        await session.execute(
            select(ComponentTabTradeDirection.trade_direction_id).where(ComponentTabTradeDirection.tab_id == tab.id)
        )
    ).scalars().all()
    payload = tab_payload(tab, len(groups), list(directions))
    payload["groups"] = groups
    return payload


async def list_tab_groups(session: AsyncSession, context: RequestContext, tab_id: int) -> list[dict]:
    await _get_tab(session, tab_id)
    rows = (
        await session.execute(
            select(ComponentTabGroup, ComponentGroup)
            .join(ComponentGroup, ComponentGroup.id == ComponentTabGroup.group_id)
            .where(ComponentTabGroup.tab_id == tab_id)
            .order_by(ComponentTabGroup.display_order, ComponentTabGroup.id)
        )
    ).all()
    return [
        {**group_payload(group), "tabGroupId": str(membership.id), "displayOrder": membership.display_order}
        for membership, group in rows
    ]


async def add_tab_group(session: AsyncSession, context: RequestContext, tab_id: int, data: dict[str, Any]) -> dict:
    tab = await _get_tab(session, tab_id)
    group_id = data.get("groupId") or data.get("group_id")
    if group_id in (None, ""):
        raise ValidationFailed("A groupId is required.", {"groupId": "Required"})
    group = await _get_group(session, int(group_id))
    exists = (
        await session.execute(
            select(ComponentTabGroup).where(ComponentTabGroup.tab_id == tab.id, ComponentTabGroup.group_id == group.id)
        )
    ).scalars().first()
    if exists is not None:
        raise Conflict("DUPLICATE_TAB_GROUP", "This group is already on the tab.", {"groupId": "Already in use"})
    max_order = await session.scalar(
        select(func.max(ComponentTabGroup.display_order)).where(ComponentTabGroup.tab_id == tab.id)
    )
    membership = ComponentTabGroup(
        tab_id=tab.id,
        group_id=group.id,
        display_order=int(data.get("displayOrder") if data.get("displayOrder") is not None else (max_order or 0) + 10),
        status=str(data.get("status") or "ACTIVE"),
    )
    session.add(membership)
    await session.commit()
    return await _tab_detail(session, context, tab.id)


async def remove_tab_group(session: AsyncSession, context: RequestContext, tab_group_id: int) -> dict[str, Any]:
    membership = await session.get(ComponentTabGroup, tab_group_id)
    if membership is None:
        raise NotFound("Tab group not found.")
    await session.delete(membership)
    await session.commit()
    return {"removed": True, "id": str(tab_group_id)}


async def reorder_tab_groups(session: AsyncSession, context: RequestContext, tab_id: int, ordered_ids: list[int]) -> list[dict]:
    await _get_tab(session, tab_id)
    for index, membership_id in enumerate(ordered_ids):
        membership = await session.get(ComponentTabGroup, membership_id)
        if membership is not None and membership.tab_id == tab_id:
            membership.display_order = (index + 1) * 10
    await session.commit()
    return await list_tab_groups(session, context, tab_id)


async def set_tab_directions(session: AsyncSession, context: RequestContext, tab_id: int, direction_ids: list[int]) -> list[str]:
    from sqlalchemy import delete

    await _get_tab(session, tab_id)
    await session.execute(delete(ComponentTabTradeDirection).where(ComponentTabTradeDirection.tab_id == tab_id))
    for index, direction_id in enumerate(direction_ids):
        session.add(
            ComponentTabTradeDirection(tab_id=tab_id, trade_direction_id=int(direction_id), display_order=(index + 1) * 10)
        )
    await session.commit()
    return [str(item) for item in direction_ids]

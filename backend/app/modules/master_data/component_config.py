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
)
from app.modules.operations.models import ServiceOrderComponentRow

REFERENCE_TYPES = (
    "business_party",
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

# Per-tab-assignment layout. ``displayMode`` decides which renderers participate,
# ``dataCardinality`` limits how many rows the group may hold.
LAYOUT_DISPLAY_MODES = ("form_only", "table_only", "form_and_table")
DATA_CARDINALITIES = ("single", "multiple")
FORM_COLUMN_COUNTS = (1, 2, 3, 4)
DEFAULT_FORM_COLUMNS = 3

# Legacy groups only know ``render_mode``; these values are what that mode means
# once layout moved onto the tab/group assignment.
_LEGACY_LAYOUT_DEFAULTS = {
    "table": {"displayMode": "table_only", "dataCardinality": "multiple"},
    "form": {"displayMode": "form_only", "dataCardinality": "single"},
}


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


# --- Group layout ------------------------------------------------------------
def _legacy_layout(group: ComponentGroup) -> dict[str, Any]:
    """What a group rendered as before layouts were configurable per assignment."""
    render_mode = str(group.render_mode or "table").strip().lower()
    defaults = _LEGACY_LAYOUT_DEFAULTS.get(render_mode, _LEGACY_LAYOUT_DEFAULTS["table"])
    return {
        "displayMode": defaults["displayMode"],
        "dataCardinality": defaults["dataCardinality"],
        "formColumns": DEFAULT_FORM_COLUMNS,
        "showGroupTitle": True,
        "editable": True,
        "collapsible": False,
        "defaultExpanded": True,
    }


def resolve_layout(link: ComponentTabGroup | None, group: ComponentGroup) -> dict[str, Any]:
    """Effective layout of one group assignment.

    NULL columns inherit the legacy group default, so a configuration written
    before per-tab layouts existed renders exactly as it did.
    """
    layout = _legacy_layout(group)
    if link is not None:
        if link.display_mode:
            layout["displayMode"] = link.display_mode
        if link.data_cardinality:
            layout["dataCardinality"] = link.data_cardinality
        if link.form_columns is not None:
            layout["formColumns"] = int(link.form_columns)
        if link.show_group_title is not None:
            layout["showGroupTitle"] = bool(link.show_group_title)
        if link.editable is not None:
            layout["editable"] = bool(link.editable)
        if link.collapsible is not None:
            layout["collapsible"] = bool(link.collapsible)
        if link.default_expanded is not None:
            layout["defaultExpanded"] = bool(link.default_expanded)
    return layout


def _validate_layout_values(display_mode: str, cardinality: str, form_columns: int) -> None:
    if display_mode not in LAYOUT_DISPLAY_MODES:
        raise ValidationFailed("Unsupported display mode.", {"displayMode": "Unsupported"})
    if cardinality not in DATA_CARDINALITIES:
        raise ValidationFailed("Unsupported data cardinality.", {"dataCardinality": "Unsupported"})
    if form_columns not in FORM_COLUMN_COUNTS:
        raise ValidationFailed("Form columns must be 1, 2, 3 or 4.", {"formColumns": "Unsupported"})
    # A form-only group has no records table, so a second row could never be
    # reached. Refusing the combination is what keeps saved rows visible.
    if display_mode == "form_only" and cardinality == "multiple":
        raise ValidationFailed(
            "A form-only group can hold a single record; use form and table for multiple records.",
            {"dataCardinality": "Incompatible with form only"},
        )


def _layout_patch(data: dict[str, Any], layout: dict[str, Any]) -> dict[str, Any]:
    """Apply only the layout keys present in a request onto an effective layout."""
    patch = dict(layout)
    if data.get("displayMode") is not None:
        patch["displayMode"] = str(data["displayMode"]).strip().lower()
    if data.get("dataCardinality") is not None:
        patch["dataCardinality"] = str(data["dataCardinality"]).strip().lower()
    if data.get("formColumns") is not None:
        try:
            patch["formColumns"] = int(data["formColumns"])
        except (TypeError, ValueError) as exc:
            raise ValidationFailed("Form columns must be 1, 2, 3 or 4.", {"formColumns": "Unsupported"}) from exc
    if data.get("showGroupTitle") is not None:
        patch["showGroupTitle"] = _bool(data["showGroupTitle"], True)
    if data.get("editable") is not None:
        patch["editable"] = _bool(data["editable"], True)
    if data.get("collapsible") is not None:
        patch["collapsible"] = _bool(data["collapsible"], False)
    if data.get("defaultExpanded") is not None:
        patch["defaultExpanded"] = _bool(data["defaultExpanded"], True)
    return patch


async def _orders_with_multiple_rows(session: AsyncSession, group_id: int) -> list[int]:
    """Service Orders that currently store more than one row for this group."""
    subquery = (
        select(ServiceOrderComponentRow.service_order_id)
        .where(
            ServiceOrderComponentRow.group_id == group_id,
            ServiceOrderComponentRow.is_archived.is_(False),
        )
        .group_by(ServiceOrderComponentRow.service_order_id)
        .having(func.count(ServiceOrderComponentRow.id) > 1)
    )
    return list((await session.execute(subquery)).scalars().all())


async def _guard_layout_change(
    session: AsyncSession, group_id: int, current: dict[str, Any], target: dict[str, Any]
) -> None:
    """Refuse a layout that would make saved rows unreachable.

    A single-record layout (or a form-only one, which has no table) can only show
    one row. If an order already stores several, changing the layout would not
    delete them but would hide them, so the change is rejected instead.
    """
    becomes_single = (
        target["dataCardinality"] == "single" or target["displayMode"] == "form_only"
    ) and (
        current["dataCardinality"] != "single" or current["displayMode"] != "form_only"
    )
    if not becomes_single:
        return
    orders = await _orders_with_multiple_rows(session, group_id)
    if orders:
        raise Conflict(
            "LAYOUT_CHANGE_WOULD_HIDE_ROWS",
            "This group already has Service Orders with more than one saved record. "
            "A single-record layout would hide them; keep multiple records or remove the extra rows first.",
            {"dataCardinality": "Incompatible with saved records"},
        )


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


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def create_attribute(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    label = str(data.get("label") or "").strip()
    if not label:
        raise ValidationFailed("Label is required.", {"label": "Required"})
    code = _normalize_code(data.get("code") or label)
    if not code:
        raise ValidationFailed("An attribute code or label is required.", {"label": "Required"})
    if len(code) > 64:
        raise ValidationFailed("The attribute code is too long.", {"label": "At most 64 characters"})
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
        label=label,
        label_km=data.get("labelKm"),
        data_type=data_type,
        input_type=data.get("inputType"),
        reference_type=reference_type if data_type == "reference" else None,
        is_required=_bool(data.get("isRequired"), False),
        default_value=data.get("defaultValue"),
        placeholder=_optional_text(data.get("placeholder")),
        width=data.get("width"),
        options=jsonable(data.get("options") or []),
        validation_rules=jsonable(data.get("validationRules") or {}),
        status=str(data.get("status") or "ACTIVE"),
    )
    session.add(attribute)
    await session.commit()
    return attribute_payload(attribute)


async def _attribute_row_references(session: AsyncSession, attribute_id: int) -> int:
    """How many saved Service Order component rows hold values for this attribute.

    Component values are stored as JSON keyed by the attribute ``code``, so a
    rename would orphan every stored value. Group membership is what links a row
    to an attribute, which keeps this check dialect-independent.
    """
    from app.modules.operations.models import ServiceOrderComponentRow

    return int(
        await session.scalar(
            select(func.count())
            .select_from(ServiceOrderComponentRow)
            .join(ComponentGroupAttribute, ComponentGroupAttribute.group_id == ServiceOrderComponentRow.group_id)
            .where(ComponentGroupAttribute.attribute_id == attribute_id)
        )
        or 0
    )


async def _rename_attribute(session: AsyncSession, attribute: ComponentAttribute, raw_code: Any) -> None:
    code = _normalize_code(raw_code)
    if not code or code == attribute.code:
        return
    duplicate = (
        await session.execute(
            select(ComponentAttribute).where(ComponentAttribute.code == code, ComponentAttribute.id != attribute.id)
        )
    ).scalars().first()
    if duplicate is not None:
        raise Conflict("DUPLICATE_ATTRIBUTE_CODE", "An attribute with this code already exists.", {"code": "Already in use"})
    if await _attribute_row_references(session, attribute.id):
        raise Conflict(
            "ATTRIBUTE_CODE_IN_USE",
            "This field already has values saved against its code, so the code cannot change. "
            "Deactivate it and create a replacement field instead.",
            {"code": "In use by saved Service Orders"},
        )
    attribute.code = code


async def update_attribute(session: AsyncSession, context: RequestContext, attribute_id: int, data: dict[str, Any]) -> dict:
    attribute = await _get_attribute(session, attribute_id)
    if data.get("code") is not None:
        await _rename_attribute(session, attribute, data["code"])
    if data.get("label") is not None:
        label = str(data["label"]).strip()
        if not label:
            raise ValidationFailed("Label is required.", {"label": "Required"})
        attribute.label = label
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
        attribute.placeholder = _optional_text(data["placeholder"])
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
    # Group membership is what links an attribute to a Component Group, and
    # groups are what Component Tabs render. Saved Service Order values are
    # keyed by the attribute code, so any of these references means the record
    # must be archived (status INACTIVE) rather than deleted.
    in_use = await session.scalar(
        select(func.count()).select_from(ComponentGroupAttribute).where(ComponentGroupAttribute.attribute_id == attribute.id)
    )
    if in_use or await _attribute_row_references(session, attribute.id):
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
        "isVisible": membership.is_visible,
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
        is_visible=_bool(data.get("isVisible"), True),
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
    if data.get("isVisible") is not None:
        membership.is_visible = _bool(data["isVisible"], membership.is_visible)
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
def _direction_id(data: dict[str, Any]) -> int | None:
    value = data.get("tradeDirectionId")
    if value in (None, ""):
        legacy = data.get("tradeDirectionIds")
        if isinstance(legacy, list) and legacy:
            value = legacy[0]
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def tab_group_payload(membership: ComponentTabGroup, group: ComponentGroup) -> dict[str, Any]:
    """A group as attached to one tab, with the layout of *that* assignment."""
    return {
        **group_payload(group),
        "tabGroupId": str(membership.id),
        "displayOrder": membership.display_order,
        "status": membership.status,
        **resolve_layout(membership, group),
    }


def tab_payload(tab: ComponentTab, group_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(tab.id),
        "code": tab.code,
        "name": tab.name,
        "description": tab.description,
        "tradeDirectionId": str(tab.trade_direction_id) if tab.trade_direction_id else None,
        "displayOrder": tab.display_order,
        "isActive": tab.is_active,
        "isArchived": tab.is_archived,
        "groupCount": group_count,
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
        items.append(tab_payload(row, int(count or 0)))
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
        description=data.get("description"),
        trade_direction_id=_direction_id(data),
        display_order=int(data.get("displayOrder") if data.get("displayOrder") is not None else (max_order or 0) + 10),
        is_active=_bool(data.get("isActive"), True),
    )
    session.add(tab)
    await session.commit()
    return tab_payload(tab, 0)


async def update_tab(session: AsyncSession, context: RequestContext, tab_id: int, data: dict[str, Any]) -> dict:
    tab = await _get_tab(session, tab_id)
    if data.get("name") is not None:
        tab.name = str(data["name"])
    if data.get("description") is not None:
        tab.description = data.get("description")
    if "tradeDirectionId" in data or "tradeDirectionIds" in data:
        tab.trade_direction_id = _direction_id(data)
    if data.get("displayOrder") is not None:
        tab.display_order = int(data["displayOrder"])
    if data.get("isActive") is not None:
        tab.is_active = _bool(data["isActive"], tab.is_active)
    if data.get("isArchived") is not None:
        tab.is_archived = _bool(data["isArchived"], tab.is_archived)
        if tab.is_archived:
            tab.is_active = False
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
    payload = tab_payload(tab, len(groups))
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
    return [tab_group_payload(membership, group) for membership, group in rows]


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
    # Omitting layout keeps the pre-existing behaviour: the group's legacy
    # ``render_mode`` decides. Supplying a display mode without a cardinality
    # picks the compatible default for that mode.
    layout = _layout_patch(data, _legacy_layout(group))
    if data.get("displayMode") is not None and data.get("dataCardinality") is None:
        layout["dataCardinality"] = "single" if layout["displayMode"] == "form_only" else "multiple"
    _validate_layout_values(layout["displayMode"], layout["dataCardinality"], int(layout["formColumns"]))
    await _guard_layout_change(session, group.id, _legacy_layout(group), layout)

    max_order = await session.scalar(
        select(func.max(ComponentTabGroup.display_order)).where(ComponentTabGroup.tab_id == tab.id)
    )
    membership = ComponentTabGroup(
        tab_id=tab.id,
        group_id=group.id,
        display_order=int(data.get("displayOrder") if data.get("displayOrder") is not None else (max_order or 0) + 10),
        display_mode=layout["displayMode"],
        data_cardinality=layout["dataCardinality"],
        form_columns=layout["formColumns"],
        show_group_title=layout["showGroupTitle"],
        editable=layout["editable"],
        collapsible=layout["collapsible"],
        default_expanded=layout["defaultExpanded"],
        status=str(data.get("status") or "ACTIVE"),
    )
    session.add(membership)
    await session.commit()
    return await _tab_detail(session, context, tab.id)


async def _get_tab_group(session: AsyncSession, tab_group_id: int) -> tuple[ComponentTabGroup, ComponentGroup]:
    membership = await session.get(ComponentTabGroup, tab_group_id)
    if membership is None:
        raise NotFound("Tab group not found.")
    group = await _get_group(session, membership.group_id)
    return membership, group


async def update_tab_group(
    session: AsyncSession, context: RequestContext, tab_group_id: int, data: dict[str, Any]
) -> dict:
    """Update the layout of one group *within its tab*."""
    membership, group = await _get_tab_group(session, tab_group_id)

    current = resolve_layout(membership, group)
    layout = _layout_patch(data, current)
    # Supplying a display mode on its own also realigns the cardinality, so
    # changing to form-only cannot silently keep "multiple" from the old layout.
    if data.get("displayMode") is not None and data.get("dataCardinality") is None:
        layout["dataCardinality"] = "single" if layout["displayMode"] == "form_only" else "multiple"
    _validate_layout_values(layout["displayMode"], layout["dataCardinality"], int(layout["formColumns"]))
    await _guard_layout_change(session, group.id, current, layout)

    membership.display_mode = layout["displayMode"]
    membership.data_cardinality = layout["dataCardinality"]
    membership.form_columns = int(layout["formColumns"])
    membership.show_group_title = layout["showGroupTitle"]
    membership.editable = layout["editable"]
    membership.collapsible = layout["collapsible"]
    membership.default_expanded = layout["defaultExpanded"]
    if data.get("displayOrder") is not None:
        membership.display_order = int(data["displayOrder"])
    if data.get("status") is not None:
        membership.status = str(data["status"])
    await session.commit()
    membership, group = await _get_tab_group(session, tab_group_id)
    return tab_group_payload(membership, group)


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

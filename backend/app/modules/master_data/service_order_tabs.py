"""Configurable Service Order operational tabs and their dynamic-table columns.

Tabs and columns are stored in configuration tables so that adding a tab or a
column never requires a frontend change or a new database migration. Row values
live under the ``operations`` module (``service_order_tab_rows``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, paged
from app.core.serialization import jsonable
from app.modules.master_data.models import ServiceOrderColumnConfig, ServiceOrderTabConfig
from app.modules.operations.models import ServiceOrderTabRow

COLUMN_TYPES = (
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
    "reference",
)

REFERENCE_TYPES = (
    "business_party",
    "place",
    "transport_asset",
    "transport_type",
    "container",
    "fee_type",
    "user",
)


def tab_payload(tab: ServiceOrderTabConfig, column_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(tab.id),
        "code": tab.code,
        "name": tab.name,
        "nameKm": tab.name_km,
        "description": tab.description,
        "icon": tab.icon,
        "sortOrder": tab.sort_order,
        "isActive": tab.is_active,
        "allowMultipleRows": tab.allow_multiple_rows,
        "isArchived": tab.is_archived,
        "columnCount": column_count,
        "createdAt": tab.created_at.isoformat() if tab.created_at else None,
        "updatedAt": tab.updated_at.isoformat() if tab.updated_at else None,
    }


def column_payload(column: ServiceOrderColumnConfig) -> dict[str, Any]:
    return {
        "id": str(column.id),
        "tabId": str(column.tab_id),
        "fieldKey": column.field_key,
        "label": column.label,
        "labelKm": column.label_km,
        "fieldType": column.field_type,
        "referenceType": column.reference_type,
        "isRequired": column.is_required,
        "isActive": column.is_active,
        "isArchived": column.is_archived,
        "showInSummary": column.show_in_summary,
        "width": column.width,
        "sortOrder": column.sort_order,
        "defaultValue": column.default_value,
        "placeholder": column.placeholder,
        "validationRules": column.validation_rules or {},
        "options": column.options or [],
        "createdAt": column.created_at.isoformat() if column.created_at else None,
        "updatedAt": column.updated_at.isoformat() if column.updated_at else None,
    }


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "active", "enabled"}


async def list_tabs(session: AsyncSession, context: RequestContext, page: PageParams, include_archived: bool = False) -> dict:
    stmt = select(ServiceOrderTabConfig)
    if not include_archived:
        stmt = stmt.where(ServiceOrderTabConfig.is_archived.is_(False))
    if page.q:
        stmt = stmt.where(ServiceOrderTabConfig.name.ilike(f"%{page.q}%") | ServiceOrderTabConfig.code.ilike(f"%{page.q}%"))
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(ServiceOrderTabConfig.sort_order, ServiceOrderTabConfig.id).limit(page.page_size).offset(page.offset)
        )
    ).scalars().all()
    items = []
    for row in rows:
        count = await session.scalar(
            select(func.count()).select_from(ServiceOrderColumnConfig).where(
                ServiceOrderColumnConfig.tab_id == row.id, ServiceOrderColumnConfig.is_archived.is_(False)
            )
        )
        items.append(tab_payload(row, int(count or 0)))
    return paged(items, page, total)


async def _get_tab(session: AsyncSession, context: RequestContext, tab_id: int) -> ServiceOrderTabConfig:
    tab = await session.get(ServiceOrderTabConfig, tab_id)
    if tab is None:
        raise NotFound("Service order tab not found.")
    return tab


def _normalize_code(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "-").replace("_", "-")


async def create_tab(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    code = _normalize_code(data.get("code") or data.get("name"))
    if not code:
        raise ValidationFailed("A tab code or name is required.", {"code": "Required"})
    existing = (
        await session.execute(
            select(ServiceOrderTabConfig).where(
                ServiceOrderTabConfig.code == code,
            )
        )
    ).scalars().first()
    if existing is not None:
        raise Conflict("DUPLICATE_TAB_CODE", "A tab with this code already exists.", {"code": "Already in use"})
    max_order = await session.scalar(
        select(func.max(ServiceOrderTabConfig.sort_order))
    )
    tab = ServiceOrderTabConfig(
        code=code,
        name=str(data.get("name") or code.title()),
        name_km=data.get("nameKm"),
        description=data.get("description"),
        icon=data.get("icon") or "i-lucide-table",
        sort_order=int(data.get("sortOrder") if data.get("sortOrder") is not None else (max_order or 0) + 10),
        is_active=_bool(data.get("isActive"), True),
        allow_multiple_rows=_bool(data.get("allowMultipleRows"), True),
    )
    session.add(tab)
    await session.commit()
    return tab_payload(tab)


async def update_tab(session: AsyncSession, context: RequestContext, tab_id: int, data: dict[str, Any]) -> dict:
    tab = await _get_tab(session, context, tab_id)
    if data.get("name") is not None:
        tab.name = str(data["name"])
    if data.get("nameKm") is not None:
        tab.name_km = data.get("nameKm")
    if data.get("description") is not None:
        tab.description = data.get("description")
    if data.get("icon") is not None:
        tab.icon = data.get("icon")
    if data.get("sortOrder") is not None:
        tab.sort_order = int(data["sortOrder"])
    if data.get("isActive") is not None:
        tab.is_active = _bool(data["isActive"], tab.is_active)
    if data.get("allowMultipleRows") is not None:
        tab.allow_multiple_rows = _bool(data["allowMultipleRows"], tab.allow_multiple_rows)
    if data.get("isArchived") is not None:
        tab.is_archived = _bool(data["isArchived"], tab.is_archived)
        if tab.is_archived:
            tab.is_active = False
    await session.commit()
    return tab_payload(tab)


async def delete_tab(session: AsyncSession, context: RequestContext, tab_id: int) -> dict[str, Any]:
    tab = await _get_tab(session, context, tab_id)
    used = await session.scalar(
        select(func.count()).select_from(ServiceOrderTabRow).where(ServiceOrderTabRow.tab_config_id == tab.id)
    )
    if used:
        tab.is_archived = True
        tab.is_active = False
        await session.commit()
        return {"archived": True, "id": str(tab.id)}
    await session.delete(tab)
    await session.commit()
    return {"archived": False, "id": str(tab_id)}


async def list_columns(session: AsyncSession, context: RequestContext, tab_id: int, include_archived: bool = False) -> list[dict]:
    tab = await _get_tab(session, context, tab_id)
    stmt = select(ServiceOrderColumnConfig).where(ServiceOrderColumnConfig.tab_id == tab.id)
    if not include_archived:
        stmt = stmt.where(ServiceOrderColumnConfig.is_archived.is_(False))
    rows = (await session.execute(stmt.order_by(ServiceOrderColumnConfig.sort_order, ServiceOrderColumnConfig.id))).scalars().all()
    return [column_payload(row) for row in rows]


async def _get_column(session: AsyncSession, context: RequestContext, column_id: int) -> ServiceOrderColumnConfig:
    column = await session.get(ServiceOrderColumnConfig, column_id)
    if column is None:
        raise NotFound("Service order column not found.")
    await _get_tab(session, context, column.tab_id)
    return column


async def create_column(session: AsyncSession, context: RequestContext, tab_id: int, data: dict[str, Any]) -> dict:
    tab = await _get_tab(session, context, tab_id)
    field_key = _normalize_code(data.get("fieldKey") or data.get("label"))
    field_key = field_key.replace("-", "_")
    if not field_key:
        raise ValidationFailed("A field key or label is required.", {"fieldKey": "Required"})
    field_type = str(data.get("fieldType") or "text").strip().lower()
    if field_type not in COLUMN_TYPES:
        raise ValidationFailed(f"Unsupported column type: {field_type}", {"fieldType": "Unsupported"})
    reference_type = data.get("referenceType")
    if field_type == "reference" and reference_type not in REFERENCE_TYPES:
        raise ValidationFailed("A valid reference type is required for reference columns.", {"referenceType": "Required"})
    existing = (
        await session.execute(
            select(ServiceOrderColumnConfig).where(
                ServiceOrderColumnConfig.tab_id == tab.id, ServiceOrderColumnConfig.field_key == field_key
            )
        )
    ).scalars().first()
    if existing is not None:
        raise Conflict("DUPLICATE_COLUMN_KEY", "A column with this key already exists.", {"fieldKey": "Already in use"})
    max_order = await session.scalar(
        select(func.max(ServiceOrderColumnConfig.sort_order)).where(ServiceOrderColumnConfig.tab_id == tab.id)
    )
    column = ServiceOrderColumnConfig(
        tab_id=tab.id,
        field_key=field_key,
        label=str(data.get("label") or field_key.replace("_", " ").title()),
        label_km=data.get("labelKm"),
        field_type=field_type,
        reference_type=reference_type if field_type == "reference" else None,
        is_required=_bool(data.get("isRequired"), False),
        is_active=_bool(data.get("isActive"), True),
        show_in_summary=_bool(data.get("showInSummary"), False),
        width=data.get("width"),
        sort_order=int(data.get("sortOrder") if data.get("sortOrder") is not None else (max_order or 0) + 10),
        default_value=data.get("defaultValue"),
        placeholder=data.get("placeholder"),
        validation_rules=jsonable(data.get("validationRules") or {}),
        options=jsonable(data.get("options") or []),
    )
    session.add(column)
    await session.commit()
    return column_payload(column)


async def update_column(session: AsyncSession, context: RequestContext, column_id: int, data: dict[str, Any]) -> dict:
    column = await _get_column(session, context, column_id)
    if data.get("label") is not None:
        column.label = str(data["label"])
    if data.get("labelKm") is not None:
        column.label_km = data.get("labelKm")
    if data.get("fieldType") is not None:
        field_type = str(data["fieldType"]).strip().lower()
        if field_type not in COLUMN_TYPES:
            raise ValidationFailed(f"Unsupported column type: {field_type}", {"fieldType": "Unsupported"})
        column.field_type = field_type
    if data.get("referenceType") is not None:
        column.reference_type = data.get("referenceType")
    if column.field_type == "reference" and column.reference_type not in REFERENCE_TYPES:
        raise ValidationFailed("A valid reference type is required for reference columns.", {"referenceType": "Required"})
    if data.get("isRequired") is not None:
        column.is_required = _bool(data["isRequired"], column.is_required)
    if data.get("isActive") is not None:
        column.is_active = _bool(data["isActive"], column.is_active)
    if data.get("showInSummary") is not None:
        column.show_in_summary = _bool(data["showInSummary"], column.show_in_summary)
    if data.get("width") is not None:
        column.width = data.get("width")
    if data.get("sortOrder") is not None:
        column.sort_order = int(data["sortOrder"])
    if data.get("defaultValue") is not None:
        column.default_value = data.get("defaultValue")
    if data.get("placeholder") is not None:
        column.placeholder = data.get("placeholder")
    if data.get("validationRules") is not None:
        column.validation_rules = jsonable(data["validationRules"])
    if data.get("options") is not None:
        column.options = jsonable(data["options"])
    if data.get("isArchived") is not None:
        column.is_archived = _bool(data["isArchived"], column.is_archived)
        if column.is_archived:
            column.is_active = False
    await session.commit()
    return column_payload(column)


async def delete_column(session: AsyncSession, context: RequestContext, column_id: int) -> dict[str, Any]:
    column = await _get_column(session, context, column_id)
    rows = (
        await session.execute(select(ServiceOrderTabRow.values).where(ServiceOrderTabRow.tab_config_id == column.tab_id))
    ).scalars().all()
    if any(column.field_key in (values or {}) for values in rows):
        column.is_archived = True
        column.is_active = False
        await session.commit()
        return {"archived": True, "id": str(column.id)}
    await session.delete(column)
    await session.commit()
    return {"archived": False, "id": str(column_id)}


async def reorder_columns(session: AsyncSession, context: RequestContext, tab_id: int, ordered_ids: list[int]) -> list[dict]:
    tab = await _get_tab(session, context, tab_id)
    for index, column_id in enumerate(ordered_ids):
        column = await session.get(ServiceOrderColumnConfig, column_id)
        if column is not None and column.tab_id == tab.id:
            column.sort_order = (index + 1) * 10
    await session.commit()
    return await list_columns(session, context, tab_id, include_archived=True)


# --- Seed --------------------------------------------------------------------
TAB_SEED: list[dict[str, Any]] = [
    {
        "code": "invoice",
        "name": "Invoice",
        "icon": "i-lucide-file-text",
        "sort_order": 10,
        "columns": [
            {"field_key": "invoice_no", "label": "Invoice No.", "field_type": "text", "is_required": True, "sort_order": 10, "width": "160px"},
            {"field_key": "invoice_date", "label": "Invoice Date", "field_type": "date", "is_required": True, "sort_order": 20},
            {"field_key": "seller", "label": "Seller", "field_type": "reference", "reference_type": "business_party", "sort_order": 30},
            {"field_key": "invoice_amount", "label": "Invoice Amount", "field_type": "money", "sort_order": 40},
            {"field_key": "currency", "label": "Currency", "field_type": "currency", "sort_order": 50, "options": ["USD", "KHR", "VND"]},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 60, "options": ["Pending", "Approved", "Paid", "Cancelled"]},
            {"field_key": "remark", "label": "Remark", "field_type": "text", "sort_order": 70},
        ],
    },
    {
        "code": "packing-list",
        "name": "Packing List",
        "icon": "i-lucide-list",
        "sort_order": 20,
        "columns": [
            {"field_key": "packing_list_no", "label": "Packing List No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "date", "label": "Date", "field_type": "date", "sort_order": 20},
            {"field_key": "package_type", "label": "Package Type", "field_type": "text", "sort_order": 30},
            {"field_key": "quantity", "label": "Quantity", "field_type": "number", "sort_order": 40},
            {"field_key": "gross_weight", "label": "Gross Weight (kg)", "field_type": "decimal", "sort_order": 50},
            {"field_key": "net_weight", "label": "Net Weight (kg)", "field_type": "decimal", "sort_order": 60},
            {"field_key": "remark", "label": "Remark", "field_type": "textarea", "sort_order": 70},
        ],
    },
    {
        "code": "shipment-registration",
        "name": "Shipment Registration No.",
        "icon": "i-lucide-clipboard-list",
        "sort_order": 30,
        "columns": [
            {"field_key": "registration_no", "label": "Registration No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "registration_date", "label": "Registration Date", "field_type": "date", "sort_order": 20},
            {"field_key": "authority", "label": "Authority", "field_type": "text", "sort_order": 30},
            {"field_key": "reference", "label": "Reference", "field_type": "text", "sort_order": 40},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 50, "options": ["Draft", "Submitted", "Registered", "Cancelled"]},
            {"field_key": "remark", "label": "Remark", "field_type": "text", "sort_order": 60},
        ],
    },
    {
        "code": "bill",
        "name": "Bill",
        "icon": "i-lucide-receipt",
        "sort_order": 40,
        "columns": [
            {"field_key": "bill_no", "label": "Bill No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "bill_date", "label": "Bill Date", "field_type": "date", "sort_order": 20},
            {"field_key": "party", "label": "Party", "field_type": "reference", "reference_type": "business_party", "sort_order": 30},
            {"field_key": "description", "label": "Description", "field_type": "text", "sort_order": 40},
            {"field_key": "amount", "label": "Amount", "field_type": "money", "sort_order": 50},
            {"field_key": "currency", "label": "Currency", "field_type": "currency", "sort_order": 60, "options": ["USD", "KHR", "VND"]},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 70, "options": ["Pending", "Approved", "Paid", "Overdue", "Cancelled"]},
        ],
    },
    {
        "code": "customs",
        "name": "Customs",
        "icon": "i-lucide-landmark",
        "sort_order": 50,
        "columns": [
            {"field_key": "declaration_no", "label": "Declaration No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "declaration_date", "label": "Declaration Date", "field_type": "date", "sort_order": 20},
            {"field_key": "checkpoint", "label": "Checkpoint", "field_type": "reference", "reference_type": "place", "sort_order": 30},
            {"field_key": "broker", "label": "Broker", "field_type": "reference", "reference_type": "business_party", "sort_order": 40},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 50, "options": ["Preparing", "Submitted", "Processing", "On Hold", "Cleared"]},
            {"field_key": "clearance_date", "label": "Clearance Date", "field_type": "date", "sort_order": 60},
            {"field_key": "remark", "label": "Remark", "field_type": "text", "sort_order": 70},
        ],
    },
    {
        "code": "transport",
        "name": "Transport",
        "icon": "i-lucide-truck",
        "sort_order": 60,
        "columns": [
            {"field_key": "transport_type", "label": "Transport Type", "field_type": "reference", "reference_type": "transport_type", "sort_order": 10},
            {"field_key": "vehicle", "label": "Vehicle", "field_type": "reference", "reference_type": "transport_asset", "sort_order": 20},
            {"field_key": "driver", "label": "Driver", "field_type": "text", "sort_order": 30},
            {"field_key": "origin", "label": "Origin", "field_type": "reference", "reference_type": "place", "sort_order": 40},
            {"field_key": "destination", "label": "Destination", "field_type": "reference", "reference_type": "place", "sort_order": 50},
            {"field_key": "departure", "label": "Departure", "field_type": "datetime", "sort_order": 60},
            {"field_key": "arrival", "label": "Arrival", "field_type": "datetime", "sort_order": 70},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 80, "options": ["Planned", "Loading", "In Transit", "Arrived", "Delivered", "Cancelled"]},
        ],
    },
]

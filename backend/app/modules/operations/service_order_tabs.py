"""Service Order configurable dynamic-table rows.

Row values are validated against the column configuration stored by the
``master_data`` module. Values are kept in a JSONB ``values`` object so adding a
column never requires a schema migration.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, paged
from app.core.serialization import jsonable
from app.modules.auth.models import User
from app.modules.master_data.models import (
    BusinessParty,
    FeeType,
    Place,
    ServiceOrderColumnConfig,
    ServiceOrderTabConfig,
    TransportAsset,
    TransportType,
)
from app.modules.operations.models import ServiceOrder, ServiceOrderContainer, ServiceOrderTabRow


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _option_values(options: Any) -> list[str]:
    if not isinstance(options, list):
        return []
    values: list[str] = []
    for option in options:
        if isinstance(option, dict):
            candidate = option.get("value", option.get("label"))
        else:
            candidate = option
        if candidate is not None and str(candidate) != "":
            values.append(str(candidate))
    return values


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
    }


def tab_payload(tab: ServiceOrderTabConfig, columns: list[ServiceOrderColumnConfig]) -> dict[str, Any]:
    return {
        "id": str(tab.id),
        "code": tab.code,
        "name": tab.name,
        "nameKm": tab.name_km,
        "icon": tab.icon,
        "sortOrder": tab.sort_order,
        "isActive": tab.is_active,
        "allowMultipleRows": tab.allow_multiple_rows,
        "columns": [column_payload(column) for column in columns],
    }


def row_payload(row: ServiceOrderTabRow) -> dict[str, Any]:
    payload = dict(row.values or {})
    payload.update(
        {
            "id": str(row.id),
            "tabId": str(row.tab_config_id),
            "tabCode": row.tab_code,
            "rowNo": row.row_no,
            "values": dict(row.values or {}),
            "createdAt": row.created_at.isoformat() if row.created_at else None,
            "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


async def _get_service_order(session: AsyncSession, context: RequestContext, service_order_id: int) -> ServiceOrder:
    order = await session.get(ServiceOrder, service_order_id)
    if order is None or order.organization_id != context.organization_id:
        raise NotFound("Service order not found.")
    return order


async def _get_tab(session: AsyncSession, context: RequestContext, tab_id: int) -> ServiceOrderTabConfig:
    tab = await session.get(ServiceOrderTabConfig, tab_id)
    if tab is None or tab.organization_id != context.organization_id:
        raise NotFound("Service order tab not found.")
    return tab


async def _columns(session: AsyncSession, tab_id: int, include_archived: bool = False) -> list[ServiceOrderColumnConfig]:
    stmt = select(ServiceOrderColumnConfig).where(ServiceOrderColumnConfig.tab_id == tab_id)
    if not include_archived:
        stmt = stmt.where(ServiceOrderColumnConfig.is_archived.is_(False))
    return list((await session.execute(stmt.order_by(ServiceOrderColumnConfig.sort_order, ServiceOrderColumnConfig.id))).scalars().all())


async def _reference_options(session: AsyncSession, context: RequestContext, reference_type: str, order_id: int) -> dict[int, str]:
    if reference_type == "business_party":
        rows = (
            await session.execute(
                select(BusinessParty.id, BusinessParty.legal_name).where(BusinessParty.status == "ACTIVE")
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "place":
        rows = (await session.execute(select(Place.id, Place.name).where(Place.status == "ACTIVE"))).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "transport_asset":
        rows = (
            await session.execute(
                select(TransportAsset.id, TransportAsset.identity).where(TransportAsset.status == "ACTIVE")
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "transport_type":
        rows = (await session.execute(select(TransportType.id, TransportType.name))).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "fee_type":
        rows = (await session.execute(select(FeeType.id, FeeType.name))).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "container":
        rows = (
            await session.execute(
                select(ServiceOrderContainer.id, ServiceOrderContainer.container_number).where(
                    ServiceOrderContainer.service_order_id == order_id
                )
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "user":
        rows = (
            await session.execute(
                select(User.id, User.display_name).where(
                    User.status == "ACTIVE"
                )
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}
    return {}


async def reference_options(
    session: AsyncSession, context: RequestContext, order_id: int, reference_types: list[str] | None = None
) -> dict[str, dict[str, str]]:
    types = reference_types or ["business_party", "place", "transport_asset", "transport_type", "fee_type", "container", "user"]
    result: dict[str, dict[str, str]] = {}
    for reference_type in types:
        options = await _reference_options(session, context, reference_type, order_id)
        result[reference_type] = {str(key): label for key, label in options.items()}
    return result


async def validate_values(
    session: AsyncSession,
    context: RequestContext,
    order: ServiceOrder,
    columns: list[ServiceOrderColumnConfig],
    provided: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = existing or {}
    known_keys = {column.field_key for column in columns}
    merged = {key: value for key, value in provided.items() if key in known_keys}
    result: dict[str, Any] = {key: value for key, value in existing.items() if key not in known_keys}
    errors: dict[str, str] = {}

    for column in columns:
        if not column.is_active:
            if column.field_key in existing and column.field_key not in provided:
                result[column.field_key] = existing[column.field_key]
            continue
        value = merged.get(column.field_key, existing.get(column.field_key))
        field_type = column.field_type

        if _empty(value):
            if column.is_required:
                errors[column.field_key] = "Required"
            continue

        try:
            result[column.field_key] = _coerce_value(column, value)
        except ValueError as exc:
            errors[column.field_key] = str(exc)
            continue

        normalized = result[column.field_key]
        if field_type in {"select", "currency"}:
            allowed = _option_values(column.options)
            if allowed and str(normalized) not in allowed:
                errors[column.field_key] = "Invalid option"
        elif field_type == "multi_select":
            allowed = _option_values(column.options)
            if not isinstance(normalized, list):
                errors[column.field_key] = "Must be a list"
            elif allowed and any(str(item) not in allowed for item in normalized):
                errors[column.field_key] = "Invalid option"
        elif field_type == "reference":
            reference_type = column.reference_type or ""
            ref_id = normalized
            options = await _reference_options(session, context, reference_type, order.id)
            if int(ref_id) not in options:
                errors[column.field_key] = "Reference not found"

    if errors:
        raise ValidationFailed("Some row values are invalid.", errors)
    return result


def _coerce_value(column: ServiceOrderColumnConfig, value: Any) -> Any:
    field_type = column.field_type
    if field_type in {"number"}:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Must be a number") from exc
        return int(number) if number == number.to_integral_value() else float(number)
    if field_type in {"decimal", "money"}:
        try:
            return float(Decimal(str(value)))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Must be a number") from exc
    if field_type == "date":
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date().isoformat()
        except ValueError as exc:
            raise ValueError("Must be a valid date") from exc
    if field_type == "datetime":
        text = str(value).replace("Z", "+00:00")
        try:
            datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("Must be a valid date/time") from exc
        return text
    if field_type == "checkbox":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "yes", "1", "on"}
    if field_type == "multi_select":
        if isinstance(value, list):
            return value
        return [value]
    if field_type == "reference":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Must be a reference id") from exc
    return str(value)


async def bootstrap(session: AsyncSession, context: RequestContext, service_order_id: int) -> dict:
    order = await _get_service_order(session, context, service_order_id)
    tabs = (
        await session.execute(
            select(ServiceOrderTabConfig)
            .where(
                ServiceOrderTabConfig.organization_id == context.organization_id,
                ServiceOrderTabConfig.is_active.is_(True),
                ServiceOrderTabConfig.is_archived.is_(False),
            )
            .order_by(ServiceOrderTabConfig.sort_order, ServiceOrderTabConfig.id)
        )
    ).scalars().all()
    rows = (
        await session.execute(
            select(ServiceOrderTabRow)
            .where(ServiceOrderTabRow.service_order_id == order.id, ServiceOrderTabRow.is_archived.is_(False))
            .order_by(ServiceOrderTabRow.tab_config_id, ServiceOrderTabRow.row_no, ServiceOrderTabRow.id)
        )
    ).scalars().all()

    rows_by_tab: dict[int, list[dict]] = {}
    for row in rows:
        rows_by_tab.setdefault(row.tab_config_id, []).append(row_payload(row))

    reference_types: set[str] = set()
    tab_items = []
    for tab in tabs:
        columns = await _columns(session, tab.id)
        for column in columns:
            if column.field_type == "reference" and column.reference_type:
                reference_types.add(column.reference_type)
        tab_items.append({**tab_payload(tab, columns), "rows": rows_by_tab.get(tab.id, [])})

    references = await reference_options(session, context, order.id, sorted(reference_types))
    return {"serviceOrderId": str(order.id), "jobNo": order.service_order_no, "tabs": tab_items, "references": references}


async def list_rows(session: AsyncSession, context: RequestContext, service_order_id: int, tab_id: int, page: PageParams) -> dict:
    order = await _get_service_order(session, context, service_order_id)
    tab = await _get_tab(session, context, tab_id)
    stmt = select(ServiceOrderTabRow).where(
        ServiceOrderTabRow.service_order_id == order.id,
        ServiceOrderTabRow.tab_config_id == tab.id,
        ServiceOrderTabRow.is_archived.is_(False),
    )
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(ServiceOrderTabRow.row_no, ServiceOrderTabRow.id).limit(page.page_size).offset(page.offset)
        )
    ).scalars().all()
    return paged([row_payload(row) for row in rows], page, total)


async def create_row(
    session: AsyncSession, context: RequestContext, service_order_id: int, tab_id: int, data: dict[str, Any]
) -> dict:
    order = await _get_service_order(session, context, service_order_id)
    tab = await _get_tab(session, context, tab_id)
    if not tab.is_active:
        raise ValidationFailed("This tab is disabled.")
    columns = await _columns(session, tab.id)
    raw_values = data.get("values") if isinstance(data.get("values"), dict) else data
    values = await validate_values(session, context, order, columns, raw_values or {})
    if not tab.allow_multiple_rows:
        existing = await session.scalar(
            select(func.count()).select_from(ServiceOrderTabRow).where(
                ServiceOrderTabRow.service_order_id == order.id,
                ServiceOrderTabRow.tab_config_id == tab.id,
                ServiceOrderTabRow.is_archived.is_(False),
            )
        )
        if existing:
            raise ValidationFailed("This tab allows a single row only.")
    max_row = await session.scalar(
        select(func.max(ServiceOrderTabRow.row_no)).where(
            ServiceOrderTabRow.service_order_id == order.id, ServiceOrderTabRow.tab_config_id == tab.id
        )
    )
    row = ServiceOrderTabRow(
        service_order_id=order.id,
        tab_config_id=tab.id,
        tab_code=tab.code,
        row_no=int(max_row or 0) + 1,
        values=jsonable(values),
        created_by_user_id=context.user_id,
        updated_by_user_id=context.user_id,
    )
    session.add(row)
    await session.commit()
    return row_payload(row)


async def update_row(
    session: AsyncSession, context: RequestContext, service_order_id: int, tab_id: int, row_id: int, data: dict[str, Any]
) -> dict:
    order = await _get_service_order(session, context, service_order_id)
    tab = await _get_tab(session, context, tab_id)
    columns = await _columns(session, tab.id)
    row = await session.get(ServiceOrderTabRow, row_id)
    if row is None or row.service_order_id != order.id or row.tab_config_id != tab.id:
        raise NotFound("Row not found.")
    raw_values = data.get("values") if isinstance(data.get("values"), dict) else data
    values = await validate_values(session, context, order, columns, raw_values or {}, row.values or {})
    row.values = jsonable(values)
    row.updated_by_user_id = context.user_id
    if data.get("rowNo") is not None:
        row.row_no = int(data["rowNo"])
    await session.commit()
    return row_payload(row)


async def delete_row(session: AsyncSession, context: RequestContext, service_order_id: int, tab_id: int, row_id: int) -> dict:
    order = await _get_service_order(session, context, service_order_id)
    tab = await _get_tab(session, context, tab_id)
    row = await session.get(ServiceOrderTabRow, row_id)
    if row is None or row.service_order_id != order.id or row.tab_config_id != tab.id:
        raise NotFound("Row not found.")
    await session.delete(row)
    await session.commit()
    return {"removed": True, "id": str(row_id)}


async def bulk_save(
    session: AsyncSession, context: RequestContext, service_order_id: int, tab_id: int, rows: list[dict[str, Any]]
) -> dict:
    order = await _get_service_order(session, context, service_order_id)
    tab = await _get_tab(session, context, tab_id)
    if not tab.is_active:
        raise ValidationFailed("This tab is disabled.")
    columns = await _columns(session, tab.id)
    if not tab.allow_multiple_rows and len(rows) > 1:
        raise ValidationFailed("This tab allows a single row only.")

    existing_rows = (
        await session.execute(
            select(ServiceOrderTabRow).where(
                ServiceOrderTabRow.service_order_id == order.id, ServiceOrderTabRow.tab_config_id == tab.id
            )
        )
    ).scalars().all()
    existing_by_id = {str(row.id): row for row in existing_rows}

    kept_ids: set[str] = set()
    errors: dict[str, str] = {}
    validated: list[tuple[ServiceOrderTabRow | None, dict[str, Any], int]] = []
    for index, item in enumerate(rows, start=1):
        row_id = str(item.get("id") or "") if isinstance(item, dict) else ""
        raw_values = item.get("values") if isinstance(item, dict) and isinstance(item.get("values"), dict) else (item or {})
        existing_row = existing_by_id.get(row_id) if row_id else None
        try:
            values = await validate_values(session, context, order, columns, raw_values, existing_row.values if existing_row else {})
        except ValidationFailed as exc:
            if exc.field_errors:
                errors.update({f"{index}.{key}": message for key, message in exc.field_errors.items()})
            continue
        if existing_row is not None:
            kept_ids.add(str(existing_row.id))
        validated.append((existing_row, values, index))

    if errors:
        raise ValidationFailed("Some rows are invalid.", errors)

    for row_id, existing_row in existing_by_id.items():
        if row_id not in kept_ids:
            await session.delete(existing_row)

    result = []
    for existing_row, values, index in validated:
        if existing_row is None:
            created = ServiceOrderTabRow(
                service_order_id=order.id,
                tab_config_id=tab.id,
                tab_code=tab.code,
                row_no=index,
                values=jsonable(values),
                created_by_user_id=context.user_id,
                updated_by_user_id=context.user_id,
            )
            session.add(created)
            await session.flush()
            result.append(row_payload(created))
        else:
            existing_row.values = jsonable(values)
            existing_row.row_no = index
            existing_row.updated_by_user_id = context.user_id
            result.append(row_payload(existing_row))
    await session.commit()
    return {"items": result, "meta": {"page": 1, "page_size": len(result), "total": len(result)}}

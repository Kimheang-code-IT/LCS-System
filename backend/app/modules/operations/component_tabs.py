"""Service Order configurable component tabs.

A component tab is composed of component groups; each group is a set of reusable
attributes rendered either as a repeatable table or as a single form. Trade
direction decides which tabs are visible. Row values are stored per Service
Order as JSON keyed by the attribute ``code`` so config changes never require a
schema migration.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import NotFound, ValidationFailed
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
from app.modules.operations.models import ServiceOrder, ServiceOrderComponentRow
from app.modules.operations.reference_options import reference_options


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "on"}


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _option_values(options: Any) -> list[str]:
    if not isinstance(options, list):
        return []
    values: list[str] = []
    for option in options:
        candidate = option.get("value", option.get("label")) if isinstance(option, dict) else option
        if candidate is not None and str(candidate) != "":
            values.append(str(candidate))
    return values


def attribute_payload(
    attribute: ComponentAttribute,
    membership: ComponentGroupAttribute | None = None,
    display_order: int | None = None,
) -> dict[str, Any]:
    required = attribute.is_required
    if membership is not None and membership.is_required is not None:
        required = membership.is_required
    width = membership.width if membership is not None and membership.width else attribute.width
    return {
        "id": str(attribute.id),
        "code": attribute.code,
        "label": attribute.label,
        "labelKm": attribute.label_km,
        "fieldType": attribute.data_type,
        "inputType": attribute.input_type,
        "referenceType": attribute.reference_type,
        "isRequired": required,
        "defaultValue": attribute.default_value,
        "placeholder": attribute.placeholder,
        "width": width,
        "options": attribute.options or [],
        "validationRules": attribute.validation_rules or {},
        "sortOrder": display_order if display_order is not None else (membership.display_order if membership else 0),
    }


def group_payload(group: ComponentGroup, attributes: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(group.id),
        "code": group.code,
        "name": group.name,
        "nameKm": group.name_km,
        "renderMode": group.render_mode,
        "displayOrder": group.display_order,
        "attributes": attributes,
        "rows": rows,
    }


def row_payload(row: ServiceOrderComponentRow) -> dict[str, Any]:
    payload = dict(row.values or {})
    payload.update(
        {
            "id": str(row.id),
            "groupId": str(row.group_id),
            "rowNo": row.row_no,
            "values": dict(row.values or {}),
            "createdAt": row.created_at.isoformat() if row.created_at else None,
            "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        }
    )
    return payload


async def _get_order(session: AsyncSession, service_order_id: int) -> ServiceOrder:
    order = await session.get(ServiceOrder, service_order_id)
    if order is None:
        raise NotFound("Service order not found.")
    return order


async def _get_group(session: AsyncSession, group_id: int) -> ComponentGroup:
    group = await session.get(ComponentGroup, group_id)
    if group is None:
        raise NotFound("Component group not found.")
    return group


async def _group_attributes(session: AsyncSession, group_id: int) -> list[tuple[ComponentGroupAttribute, ComponentAttribute]]:
    rows = (
        await session.execute(
            select(ComponentGroupAttribute, ComponentAttribute)
            .join(ComponentAttribute, ComponentAttribute.id == ComponentGroupAttribute.attribute_id)
            .where(
                ComponentGroupAttribute.group_id == group_id,
                ComponentGroupAttribute.status == "ACTIVE",
                ComponentAttribute.status == "ACTIVE",
            )
            .order_by(ComponentGroupAttribute.display_order, ComponentGroupAttribute.id)
        )
    ).all()
    return [(membership, attribute) for membership, attribute in rows]


async def _validate_values(
    session: AsyncSession,
    context: RequestContext,
    order: ServiceOrder,
    memberships: list[tuple[ComponentGroupAttribute, ComponentAttribute]],
    provided: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = existing or {}
    by_code = {attribute.code: (membership, attribute) for membership, attribute in memberships}
    merged = {key: value for key, value in provided.items() if key in by_code}
    result: dict[str, Any] = {key: value for key, value in existing.items() if key not in by_code}
    errors: dict[str, str] = {}

    for code, (membership, attribute) in by_code.items():
        required = attribute.is_required
        if membership.is_required is not None:
            required = membership.is_required
        value = merged.get(code, existing.get(code))
        if _empty(value):
            if required:
                errors[code] = "Required"
            continue
        try:
            coerced = _coerce_value(attribute, value)
        except ValueError as exc:
            errors[code] = str(exc)
            continue
        result[code] = coerced

        field_type = attribute.data_type
        if field_type in {"select", "currency"}:
            allowed = _option_values(attribute.options)
            if allowed and str(coerced) not in allowed:
                errors[code] = "Invalid option"
        elif field_type == "multi_select":
            allowed = _option_values(attribute.options)
            if not isinstance(coerced, list):
                errors[code] = "Must be a list"
            elif allowed and any(str(item) not in allowed for item in coerced):
                errors[code] = "Invalid option"
        elif field_type == "reference":
            from app.modules.operations.reference_options import _reference_options

            options = await _reference_options(session, context, attribute.reference_type or "", order.id)
            try:
                if int(coerced) not in options:
                    errors[code] = "Reference not found"
            except (TypeError, ValueError):
                errors[code] = "Reference not found"

    if errors:
        raise ValidationFailed("Some group values are invalid.", errors)
    return result


def _coerce_value(attribute: ComponentAttribute, value: Any) -> Any:
    field_type = attribute.data_type
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
    if field_type in {"checkbox", "boolean"}:
        return value if isinstance(value, bool) else str(value).strip().lower() in {"true", "yes", "1", "on"}
    if field_type == "multi_select":
        return value if isinstance(value, list) else [value]
    if field_type == "reference":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Must be a reference id") from exc
    return str(value)


async def bootstrap(
    session: AsyncSession, context: RequestContext, service_order_id: int, direction_id: int | None = None
) -> dict:
    order = await _get_order(session, service_order_id)
    selected_direction_id = direction_id or order.trade_direction_id

    tab_ids = (
        await session.execute(
            select(ComponentTabTradeDirection.tab_id)
            .where(
                ComponentTabTradeDirection.trade_direction_id == selected_direction_id,
                ComponentTabTradeDirection.status == "ACTIVE",
            )
            .order_by(ComponentTabTradeDirection.display_order, ComponentTabTradeDirection.id)
        )
    ).scalars().all()

    tabs: list[ComponentTab] = []
    if tab_ids:
        tabs = list(
            (
                await session.execute(
                    select(ComponentTab)
                    .where(
                        ComponentTab.id.in_(list(tab_ids)),
                        ComponentTab.is_active.is_(True),
                        ComponentTab.is_archived.is_(False),
                    )
                    .order_by(ComponentTab.display_order, ComponentTab.id)
                )
            ).scalars().all()
        )

    rows = (
        await session.execute(
            select(ServiceOrderComponentRow)
            .where(
                ServiceOrderComponentRow.service_order_id == order.id,
                ServiceOrderComponentRow.is_archived.is_(False),
            )
            .order_by(ServiceOrderComponentRow.group_id, ServiceOrderComponentRow.row_no, ServiceOrderComponentRow.id)
        )
    ).scalars().all()
    rows_by_group: dict[int, list[dict]] = {}
    for row in rows:
        rows_by_group.setdefault(row.group_id, []).append(row_payload(row))

    reference_types: set[str] = set()
    tab_items = []
    for tab in tabs:
        group_rows = (
            await session.execute(
                select(ComponentTabGroup, ComponentGroup)
                .join(ComponentGroup, ComponentGroup.id == ComponentTabGroup.group_id)
                .where(
                    ComponentTabGroup.tab_id == tab.id,
                    ComponentTabGroup.status == "ACTIVE",
                    ComponentGroup.is_active.is_(True),
                    ComponentGroup.is_archived.is_(False),
                )
                .order_by(ComponentTabGroup.display_order, ComponentTabGroup.id)
            )
        ).all()
        groups = []
        for _tab_group, group in group_rows:
            memberships = await _group_attributes(session, group.id)
            attributes = []
            for membership, attribute in memberships:
                if attribute.data_type == "reference" and attribute.reference_type:
                    reference_types.add(attribute.reference_type)
                attributes.append(attribute_payload(attribute, membership))
            groups.append(group_payload(group, attributes, rows_by_group.get(group.id, [])))
        tab_items.append(
            {
                "id": str(tab.id),
                "code": tab.code,
                "name": tab.name,
                "nameKm": tab.name_km,
                "icon": tab.icon,
                "displayOrder": tab.display_order,
                "groups": groups,
            }
        )

    references = await reference_options(session, context, order.id, sorted(reference_types))
    return {
        "serviceOrderId": str(order.id),
        "jobNo": order.service_order_no,
        "tradeDirectionId": str(selected_direction_id) if selected_direction_id else None,
        "tabs": tab_items,
        "references": references,
    }


async def list_rows(
    session: AsyncSession, context: RequestContext, service_order_id: int, group_id: int, page: PageParams
) -> dict:
    order = await _get_order(session, service_order_id)
    await _get_group(session, group_id)
    stmt = select(ServiceOrderComponentRow).where(
        ServiceOrderComponentRow.service_order_id == order.id,
        ServiceOrderComponentRow.group_id == group_id,
        ServiceOrderComponentRow.is_archived.is_(False),
    )
    total = await count_query(session, stmt)
    orders = list_sort_orders(
        ServiceOrderComponentRow, page, ServiceOrderComponentRow.row_no, ServiceOrderComponentRow.id
    )
    rows = (
        await session.execute(
            stmt.order_by(*orders).limit(page.page_size).offset(page.offset)
        )
    ).scalars().all()
    return paged([row_payload(row) for row in rows], page, total)


async def bulk_save(
    session: AsyncSession,
    context: RequestContext,
    service_order_id: int,
    group_id: int,
    rows: list[dict[str, Any]],
) -> dict:
    order = await _get_order(session, service_order_id)
    group = await _get_group(session, group_id)
    memberships = await _group_attributes(session, group.id)
    if group.render_mode == "form" and len(rows) > 1:
        raise ValidationFailed("This group allows a single record only.")

    existing_rows = (
        await session.execute(
            select(ServiceOrderComponentRow).where(
                ServiceOrderComponentRow.service_order_id == order.id,
                ServiceOrderComponentRow.group_id == group.id,
            )
        )
    ).scalars().all()
    existing_by_id = {str(row.id): row for row in existing_rows}

    kept_ids: set[str] = set()
    errors: dict[str, str] = {}
    validated: list[tuple[ServiceOrderComponentRow | None, dict[str, Any], int]] = []
    for index, item in enumerate(rows, start=1):
        row_id = str(item.get("id") or "") if isinstance(item, dict) else ""
        raw_values = item.get("values") if isinstance(item, dict) and isinstance(item.get("values"), dict) else (item or {})
        existing_row = existing_by_id.get(row_id) if row_id else None
        try:
            values = await _validate_values(
                session, context, order, memberships, raw_values, existing_row.values if existing_row else {}
            )
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
            created = ServiceOrderComponentRow(
                service_order_id=order.id,
                group_id=group.id,
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

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
from app.modules.master_data import config_versions
from app.modules.master_data.models import (
    ComponentAttribute,
    ComponentGroup,
    ComponentGroupAttribute,
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


class _SnapshotAttribute:
    """A published attribute entry, exposing the fields value validation reads."""

    __slots__ = ("code", "data_type", "is_required", "options", "reference_type")

    def __init__(self, entry: dict[str, Any]) -> None:
        self.code = str(entry.get("code") or "")
        self.data_type = str(entry.get("dataType") or "text")
        self.is_required = bool(entry.get("isRequired"))
        self.options = entry.get("options") or []
        self.reference_type = entry.get("referenceType")


class _SnapshotMembership:
    """The per-tab required override; a snapshot already merges it into the attribute."""

    is_required = None


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
    if field_type == "integer":
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Must be a whole number") from exc
        if number != number.to_integral_value():
            raise ValueError("Must be a whole number")
        return int(number)
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


def snapshot_tabs(
    snapshot: dict[str, Any],
    direction_id: int | None,
    rows_by_group: dict[int, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Render the tabs recorded in a published snapshot.

    The snapshot is the only source of layout here: live tabs, groups and
    attributes may have been renamed, reordered or removed since publication.
    Saved rows are still matched by their stable group id.
    """
    reference_types: set[str] = set()
    tabs: list[dict[str, Any]] = []
    for tab in snapshot.get("tabs") or []:
        if not isinstance(tab, dict):
            continue
        if direction_id is not None and str(tab.get("tradeDirectionId") or "") != str(direction_id):
            continue
        groups: list[dict[str, Any]] = []
        for group in tab.get("groups") or []:
            if not isinstance(group, dict):
                continue
            attributes: list[dict[str, Any]] = []
            for attribute in group.get("attributes") or []:
                if not isinstance(attribute, dict) or attribute.get("isVisible") is False:
                    continue
                data_type = attribute.get("dataType")
                reference_type = attribute.get("referenceType")
                if data_type == "reference" and reference_type:
                    reference_types.add(str(reference_type))
                attributes.append({
                    "id": str(attribute.get("id") or ""),
                    "code": attribute.get("code"),
                    "label": attribute.get("label"),
                    "labelKm": attribute.get("labelKm"),
                    "fieldType": data_type,
                    "inputType": attribute.get("inputType"),
                    "referenceType": reference_type,
                    "isRequired": bool(attribute.get("isRequired")),
                    "isVisible": attribute.get("isVisible", True) is not False,
                    "defaultValue": attribute.get("defaultValue"),
                    "placeholder": attribute.get("placeholder"),
                    "width": attribute.get("width"),
                    "options": attribute.get("options") or [],
                    "validationRules": attribute.get("validationRules") or {},
                    "sortOrder": int(attribute.get("displayOrder") or 0),
                })
            render_mode = str(group.get("renderMode") or "table")
            legacy_form = render_mode == "form"
            group_id = int(group["id"]) if str(group.get("id") or "").isdigit() else 0
            groups.append({
                "id": str(group.get("id") or ""),
                "tabGroupId": group.get("tabGroupId"),
                "code": group.get("code"),
                "name": group.get("name"),
                "nameKm": group.get("nameKm"),
                "renderMode": render_mode,
                "displayOrder": int(group.get("displayOrder") or 0),
                "attributes": attributes,
                "rows": rows_by_group.get(group_id, []),
                "displayMode": group.get("displayMode") or ("form_only" if legacy_form else "table_only"),
                "dataCardinality": group.get("dataCardinality") or ("single" if legacy_form else "multiple"),
                "formColumns": int(group.get("formColumns") or 3),
                "showGroupTitle": group.get("showGroupTitle", True) is not False,
                "editable": group.get("editable", True) is not False,
                "collapsible": bool(group.get("collapsible")),
                "defaultExpanded": group.get("defaultExpanded", True) is not False,
            })
        tabs.append({
            "id": str(tab.get("id") or ""),
            "code": tab.get("code"),
            "name": tab.get("name"),
            "displayOrder": int(tab.get("displayOrder") or 0),
            "groups": groups,
        })
    return tabs, reference_types


async def bootstrap(
    session: AsyncSession, context: RequestContext, service_order_id: int, direction_id: int | None = None
) -> dict:
    order = await _get_order(session, service_order_id)
    selected_direction_id = direction_id or order.trade_direction_id

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

    configuration = await effective_configuration(session, order)
    snapshot = (configuration or {}).get("configSnapshot") or {}
    # Without a trade direction the form has no tab scope; the live query this
    # replaced also returned none, so keep that.
    tab_items, reference_types = (
        snapshot_tabs(snapshot, selected_direction_id, rows_by_group)
        if selected_direction_id is not None
        else ([], set())
    )

    references = await reference_options(session, context, order.id, sorted(reference_types))
    return {
        "serviceOrderId": str(order.id),
        "jobNo": order.service_order_no,
        "tradeDirectionId": str(selected_direction_id) if selected_direction_id else None,
        "tabs": tab_items,
        "references": references,
        # The configuration the order was captured under, so the client can keep
        # rendering historical rows against the layout they were entered in.
        "configVersionId": str(order.configuration_version_id) if order.configuration_version_id else None,
        "configVersion": configuration,
    }


async def effective_configuration(session: AsyncSession, order: ServiceOrder) -> dict | None:
    """The published layout a Service Order renders under.

    A pinned version wins, so a historical order keeps the layout it was captured
    under. An order without a pin — created before versioning existed, or while
    nothing had been published — renders the active published version. When
    nothing has ever been published there is no layout at all: the live draft
    tables are never used as a fallback, because that would expose unpublished
    configuration to operational users.
    """
    configuration = await config_versions.version_for_order(session, order)
    if configuration is None:
        configuration = await config_versions.published_snapshot(session)
    return configuration


def snapshot_group(snapshot: dict[str, Any], group_id: int | str) -> dict[str, Any] | None:
    """The group entry inside a published snapshot, or ``None`` when absent."""
    wanted = str(group_id)
    for tab in snapshot.get("tabs") or []:
        for group in tab.get("groups") or []:
            if isinstance(group, dict) and str(group.get("id") or "") == wanted:
                return group
    return None


async def list_rows(
    session: AsyncSession, context: RequestContext, service_order_id: int, group_id: int, page: PageParams
) -> dict:
    order = await _get_order(session, service_order_id)
    await _get_group(session, group_id)
    snapshot = (await effective_configuration(session, order) or {}).get("configSnapshot") or {}
    if snapshot_group(snapshot, group_id) is None:
        raise NotFound("This group is not part of the published configuration.")
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
    tab_group_id: int | None = None,
) -> dict:
    order = await _get_order(session, service_order_id)
    from app.modules.operations.service import _ensure_order_editing

    _ensure_order_editing(order)
    group = await _get_group(session, group_id)

    # Operational writes follow the published layout, never the draft tables: a
    # group or attribute added after the last publish must not receive values.
    snapshot = (await effective_configuration(session, order) or {}).get("configSnapshot") or {}
    published_group = snapshot_group(snapshot, group.id)
    if published_group is None:
        raise ValidationFailed(
            "This group is not part of the published configuration.",
            {"groupId": "Not published"},
        )
    if tab_group_id is not None:
        published_tab_group = str(published_group.get("tabGroupId") or "")
        if published_tab_group and published_tab_group != str(tab_group_id):
            raise ValidationFailed("The group does not belong to that tab.", {"tabGroupId": "Mismatch"})
    layout = {
        "displayMode": str(published_group.get("displayMode") or "table_only"),
        "dataCardinality": str(published_group.get("dataCardinality") or "multiple"),
        "editable": published_group.get("editable", True) is not False,
    }
    memberships = [
        (_SnapshotMembership(), _SnapshotAttribute(entry))
        for entry in published_group.get("attributes") or []
        if isinstance(entry, dict) and entry.get("isVisible") is not False
    ]
    if layout["editable"] is False:
        raise ValidationFailed(
            "This group is configured as read-only.",
            {"rows": "This group is read-only."},
        )
    single_record = layout["dataCardinality"] == "single" or layout["displayMode"] == "form_only"
    if single_record and len(rows) > 1:
        raise ValidationFailed(
            "This group allows a single record only.",
            {"rows": "Only one record is allowed in this group."},
        )

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
    seen_ids: set[str] = set()
    validated: list[tuple[ServiceOrderComponentRow | None, dict[str, Any], int]] = []
    for index, item in enumerate(rows, start=1):
        row_id = str(item.get("id") or "") if isinstance(item, dict) else ""
        # A repeated client id would let one save update the same persisted row
        # twice, so the last value would silently win.
        if row_id and row_id in seen_ids:
            errors[f"{index}.id"] = "Duplicate row"
            continue
        if row_id:
            seen_ids.add(row_id)
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
                config_version_id=order.configuration_version_id,
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

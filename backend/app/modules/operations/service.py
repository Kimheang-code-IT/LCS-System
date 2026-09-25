from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import RequestContext
from app.core.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, paged
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.core.storage import get_storage, guess_content_type
from app.modules.master_data.models import (
    BusinessParty,
    ComponentGroup,
    ComponentTemplate,
    TemplateAttribute,
    TradeDirectionComponent,
)
from app.modules.operations.models import (
    Attachment,
    AttachmentLink,
    ServiceComponentValue,
    ServiceOrder,
    ServiceOrderCharge,
    ServiceOrderChargeLine,
    ServiceOrderComponent,
    ServiceOrderContainer,
    ServiceOrderContainerRequirement,
    ServiceOrderPlace,
    ServiceOrderPricing,
    ServiceOrderPricingLine,
)
from app.modules.quotations.models import (
    Quotation,
    QuotationRevision,
    QuotationRevisionContainer,
    QuotationRevisionLine,
)

ORDER_STATUS = {
    "draft": "DRAFT",
    "open": "OPEN",
    "in_progress": "IN_PROGRESS",
    "in progress": "IN_PROGRESS",
    "on_hold": "ON_HOLD",
    "on hold": "ON_HOLD",
    "completed": "COMPLETED",
    "closed": "CLOSED",
    "cancelled": "CANCELLED",
}


def normalize_order_status(value: Any, default: str = "DRAFT") -> str:
    if value is None:
        return default
    return ORDER_STATUS.get(str(value).strip().lower(), str(value).strip().upper() or default)


def _decimal(value: Any, default: Decimal | None = Decimal("0")) -> Decimal | None:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return default


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def order_record(order: ServiceOrder, data: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(data or {})
    payload.update(
        {
            "id": str(order.id),
            "serviceOrderId": str(order.id),
            "jobNo": order.service_order_no,
            "serviceOrderNo": order.service_order_no,
            "status": order.status.capitalize() if order.status.isupper() else order.status,
            "rawStatus": order.status,
            "currency": order.currency_code,
            "createdAt": order.created_at.isoformat() if order.created_at else None,
            "updatedAt": order.updated_at.isoformat() if order.updated_at else None,
        }
    )
    if extra:
        payload.update(extra)
    return payload


async def resolve_order(session: AsyncSession, context: RequestContext, identifier: str | int) -> ServiceOrder:
    order: ServiceOrder | None = None
    text = str(identifier)
    if text.isdigit():
        order = await session.get(ServiceOrder, int(text))
    if order is None:
        order = (
            await session.execute(select(ServiceOrder).where(ServiceOrder.service_order_no == text))
        ).scalars().first()
    if order is None:
        raise NotFound("Service order not found.")
    return order


async def list_service_orders(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(ServiceOrder)
    if page.status:
        stmt = stmt.where(ServiceOrder.status == normalize_order_status(page.status))
    if page.q:
        pattern = f"%{page.q}%"
        stmt = stmt.where(
            ServiceOrder.service_order_no.ilike(pattern) | ServiceOrder.data["customer"].as_string().ilike(pattern)
        )
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(ServiceOrder.id.desc()).limit(page.page_size).offset(page.offset))).scalars().all()
    return paged([order_record(row, row.data or {}) for row in rows], page, total)


async def get_service_order(session: AsyncSession, context: RequestContext, identifier: str) -> dict:
    order = await resolve_order(session, context, identifier)
    containers = (
        await session.execute(select(ServiceOrderContainer).where(ServiceOrderContainer.service_order_id == order.id))
    ).scalars().all()
    requirements = (
        await session.execute(
            select(ServiceOrderContainerRequirement).where(ServiceOrderContainerRequirement.service_order_id == order.id)
        )
    ).scalars().all()
    components = await list_components(session, context, identifier)
    return order_record(
        order,
        order.data or {},
        {
            "containers": [_container_payload(c) for c in containers],
            "containerRequirements": [_requirement_payload(r) for r in requirements],
            "components": components,
        },
    )


async def _resolve_party(session: AsyncSession, name: str | None, context: RequestContext) -> BusinessParty:
    from app.modules.quotations.service import resolve_party_by_name

    return await resolve_party_by_name(session, name, context)


async def save_service_order(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    from app.modules.quotations.service import resolve_direction

    identifier = data.get("id") or data.get("serviceOrderId") or data.get("jobNo")
    order: ServiceOrder | None = None
    if identifier:
        try:
            order = await resolve_order(session, context, identifier)
        except NotFound:
            order = None
    party = await _resolve_party(session, data.get("customer"), context)
    direction = await resolve_direction(session, data.get("direction"))

    if order is None:
        number = data.get("jobNo") or data.get("serviceOrderNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, "SERVICE_ORDER")
        order = ServiceOrder(
            service_order_no=str(number),
            customer_party_id=party.id,
            trade_direction_id=direction.id,
            status=normalize_order_status(data.get("status"), "DRAFT"),
            currency_code=data.get("currency") or "USD",
            created_by_user_id=context.user_id,
            data={},
        )
        session.add(order)
        await session.flush()
    else:
        order.customer_party_id = party.id
        order.trade_direction_id = direction.id
        order.status = normalize_order_status(data.get("status"), order.status)
        order.currency_code = data.get("currency") or order.currency_code

    payload = {key: value for key, value in data.items() if key not in {"id", "createdAt", "updatedAt"}}
    order.data = jsonable(payload)
    await session.commit()
    return order_record(order, order.data or {})


async def update_status(session: AsyncSession, context: RequestContext, order_id: int, status_value: str) -> dict:
    order = await session.get(ServiceOrder, order_id)
    if order is None:
        raise NotFound("Service order not found.")
    order.status = normalize_order_status(status_value)
    await session.commit()
    return order_record(order, order.data or {})


async def create_service_order_from_quotation(
    session: AsyncSession, context: RequestContext, quotation: Quotation, revision: QuotationRevision
) -> ServiceOrder:
    number = await allocate_number(session, "SERVICE_ORDER")
    data = dict(quotation.data or {})
    order = ServiceOrder(
        service_order_no=number,
        quotation_revision_id=revision.id,
        customer_party_id=quotation.customer_party_id,
        trade_direction_id=quotation.trade_direction_id,
        status="OPEN",
        currency_code=revision.currency_code or "USD",
        description=revision.description,
        created_by_user_id=context.user_id,
        data=data,
    )
    session.add(order)
    await session.flush()

    for role in ("pickup", "border", "delivery"):
        value = data.get(role)
        if value:
            session.add(ServiceOrderPlace(service_order_id=order.id, place_role=role.upper(), free_text=str(value), sequence_no=1))

    requirements = (
        await session.execute(
            select(QuotationRevisionContainer).where(QuotationRevisionContainer.quotation_revision_id == revision.id)
        )
    ).scalars().all()
    requirement_by_source: dict[int, ServiceOrderContainerRequirement] = {}
    for source in requirements:
        requirement = ServiceOrderContainerRequirement(
            service_order_id=order.id,
            source_quotation_container_id=source.id,
            container_type_id=source.container_type_id,
            quantity=source.quantity,
            gross_weight_kg=source.gross_weight_kg,
            description=source.description,
            remarks=source.remarks,
        )
        session.add(requirement)
        await session.flush()
        requirement_by_source[source.id] = requirement

    pricing = ServiceOrderPricing(
        service_order_id=order.id,
        currency_code=revision.currency_code or "USD",
        subtotal_amount=revision.subtotal_amount,
        discount_amount=revision.discount_amount,
        tax_amount=revision.tax_amount,
        total_amount=revision.total_amount,
    )
    session.add(pricing)
    await session.flush()
    lines = (
        await session.execute(select(QuotationRevisionLine).where(QuotationRevisionLine.quotation_revision_id == revision.id))
    ).scalars().all()
    for line in lines:
        session.add(
            ServiceOrderPricingLine(
                service_order_pricing_id=pricing.id,
                line_no=line.line_no,
                source_quotation_line_id=line.id,
                fee_type_id=line.fee_type_id,
                description=line.service_description,
                quantity=line.quantity,
                unit_code=line.unit_code,
                unit_price=line.unit_price,
                discount_rate=line.discount_rate,
                tax_rate=line.tax_rate,
                line_total=line.line_total,
            )
        )

    direction_components = (
        await session.execute(
            select(TradeDirectionComponent).where(
                TradeDirectionComponent.trade_direction_id == quotation.trade_direction_id,
                TradeDirectionComponent.status == "ACTIVE",
            )
        )
    ).scalars().all()
    for tdc in direction_components:
        session.add(
            ServiceOrderComponent(
                service_order_id=order.id,
                trade_direction_component_id=tdc.id,
                component_group_id=tdc.component_group_id,
                component_template_id=tdc.component_template_id,
                template_version=(await session.get(ComponentTemplate, tdc.component_template_id)).version,
                component_status="PENDING",
                sequence_no=tdc.display_order,
                is_required=tdc.is_required,
            )
        )
    await session.flush()
    return order


def _container_payload(container: ServiceOrderContainer) -> dict[str, Any]:
    payload = dict(container.data or {})
    payload.update(
        {
            "id": str(container.id),
            "serviceOrderId": str(container.service_order_id),
            "containerRequirementId": str(container.container_requirement_id) if container.container_requirement_id else None,
            "containerType": str(container.container_type_id),
            "containerTypeId": container.container_type_id,
            "containerNumber": container.container_number,
            "containerNo": container.container_number,
            "sealSerial": container.seal_serial,
            "status": container.status,
            "netWeightKg": float(container.net_weight_kg) if container.net_weight_kg is not None else None,
            "grossWeightKg": float(container.gross_weight_kg) if container.gross_weight_kg is not None else None,
            "pickupDate": container.pickup_date.isoformat() if container.pickup_date else None,
            "returnDate": container.return_date.isoformat() if container.return_date else None,
        }
    )
    return payload


def _requirement_payload(requirement: ServiceOrderContainerRequirement) -> dict[str, Any]:
    return {
        "id": str(requirement.id),
        "serviceOrderId": str(requirement.service_order_id),
        "containerTypeId": requirement.container_type_id,
        "containerType": str(requirement.container_type_id),
        "quantity": float(requirement.quantity or 0),
        "grossWeightKg": float(requirement.gross_weight_kg) if requirement.gross_weight_kg is not None else None,
        "remarks": requirement.remarks,
    }


async def list_containers(session: AsyncSession, context: RequestContext, identifier: str) -> list[dict]:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(select(ServiceOrderContainer).where(ServiceOrderContainer.service_order_id == order.id))
    ).scalars().all()
    return [_container_payload(row) for row in rows]


async def add_container(session: AsyncSession, context: RequestContext, identifier: str, data: dict[str, Any]) -> dict:
    order = await resolve_order(session, context, identifier)
    if order.status in {"CLOSED", "CANCELLED"}:
        raise InvalidState("Cannot add containers to a closed order.")
    container_number = str(data.get("containerNumber") or data.get("container_number") or data.get("containerNo") or "").strip()
    if not container_number:
        raise ValidationFailed("Container number is required.", {"containerNumber": "Required"})
    if (
        await session.execute(select(ServiceOrderContainer).where(ServiceOrderContainer.container_number == container_number))
    ).scalars().first():
        raise Conflict("DUPLICATE_NUMBER", "Container number already exists.", {"containerNumber": "Already in use"})
    container_type_id = data.get("containerTypeId") or data.get("container_type_id")
    if not container_type_id:
        from app.modules.master_data.service import resolve_reference

        container_type_id = await resolve_reference(session, "container_type", data.get("containerType"))
    container = ServiceOrderContainer(
        service_order_id=order.id,
        container_requirement_id=_int_or_none(data.get("containerRequirementId") or data.get("container_requirement_id")),
        container_type_id=int(container_type_id or 1),
        container_number=container_number,
        seal_serial=data.get("sealSerial") or data.get("seal_serial"),
        status=str(data.get("status") or "EXPECTED"),
        net_weight_kg=_decimal(data.get("netWeightKg")),
        gross_weight_kg=_decimal(data.get("grossWeightKg")),
        pickup_date=_date(data.get("pickupDate")),
        return_date=_date(data.get("returnDate")),
        data=jsonable({k: v for k, v in data.items() if k not in {"id"}}),
    )
    session.add(container)
    await session.commit()
    return _container_payload(container)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _resolve_component_group(
    session: AsyncSession, group_code: Any, template: ComponentTemplate | None
) -> ComponentGroup | None:
    code = group_code or (template.category if template is not None else None)
    if not code:
        return None
    return (
        await session.execute(select(ComponentGroup).where(ComponentGroup.code == str(code)))
    ).scalars().first()


async def _component_group_code(session: AsyncSession, component: ServiceOrderComponent, template: ComponentTemplate | None) -> str | None:
    if component.component_group_id:
        group = await session.get(ComponentGroup, component.component_group_id)
        if group is not None:
            return group.code
    stored = (component.data or {}).get("groupCode")
    if stored:
        return str(stored)
    if template is not None and template.category:
        return str(template.category)
    return None


async def _component_payload(session: AsyncSession, component: ServiceOrderComponent) -> dict[str, Any]:
    template = await session.get(ComponentTemplate, component.component_template_id)
    order = await session.get(ServiceOrder, component.service_order_id)
    group_code = await _component_group_code(session, component, template)
    values = (
        await session.execute(select(ServiceComponentValue).where(ServiceComponentValue.component_id == component.id))
    ).scalars().all()
    attributes = {
        attr.id: attr
        for attr in (
            await session.execute(select(TemplateAttribute).where(TemplateAttribute.template_id == component.component_template_id))
        ).scalars().all()
    }
    value_payload = []
    for value in values:
        attr = attributes.get(value.template_attribute_id)
        item: dict[str, Any] = {
            "template_attribute_id": value.template_attribute_id,
            "templateAttributeId": value.template_attribute_id,
            "code": attr.code if attr else None,
            "label": attr.label if attr else None,
            "data_type": attr.data_type if attr else "text",
            "dataType": attr.data_type if attr else "text",
            "required": attr.is_required if attr else False,
            "resolved_instance_mode": (attr.is_repeatable and "REPEATABLE") or "SINGLE",
            "value_text": value.value_text,
            "value_number": float(value.value_number) if value.value_number is not None else None,
            "value_date": value.value_date.isoformat() if value.value_date else None,
            "value_boolean": value.value_boolean,
            "value_json": value.value_json,
        }
        value_payload.append(item)
    payload = dict(component.data or {})
    payload.update(
        {
            "id": str(component.id),
            "serviceOrderId": str(component.service_order_id),
            "serviceOrderNo": order.service_order_no if order else None,
            "jobNo": order.service_order_no if order else None,
            "templateCode": component.template_code or (template.code if template else None),
            "templateName": template.name if template else None,
            "templateVersion": str(component.template_version),
            "groupCode": group_code,
            "group": group_code,
            "status": component.component_status,
            "sequenceNo": component.sequence_no,
            "required": component.is_required,
            "repeatable": component.is_repeatable,
            "instanceMode": component.instance_mode,
            "values": value_payload,
        }
    )
    return payload


async def list_components(session: AsyncSession, context: RequestContext, identifier: str) -> list[dict]:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(
            select(ServiceOrderComponent)
            .where(ServiceOrderComponent.service_order_id == order.id)
            .order_by(ServiceOrderComponent.sequence_no)
        )
    ).scalars().all()
    return [await _component_payload(session, row) for row in rows]


async def list_all_components(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    """List every service-order component."""
    stmt = select(ServiceOrderComponent).join(ServiceOrder, ServiceOrder.id == ServiceOrderComponent.service_order_id)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(ServiceOrderComponent.service_order_id.desc(), ServiceOrderComponent.sequence_no)
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    return paged([await _component_payload(session, row) for row in rows], page, total)


async def ensure_component(session: AsyncSession, context: RequestContext, identifier: str, data: dict[str, Any]) -> dict:
    order = await resolve_order(session, context, identifier)
    template = None
    if data.get("templateCode"):
        template = (
            await session.execute(
                select(ComponentTemplate)
                .where(ComponentTemplate.code == data["templateCode"])
                .order_by(ComponentTemplate.version.desc())
            )
        ).scalars().first()
    if template is None:
        raise ValidationFailed("Component template not found.", {"templateCode": "Unknown template"})
    group = await _resolve_component_group(session, data.get("groupCode"), template)
    existing = (
        await session.execute(
            select(ServiceOrderComponent).where(
                ServiceOrderComponent.service_order_id == order.id,
                ServiceOrderComponent.component_template_id == template.id,
            )
        )
    ).scalars().first()
    if existing is not None and not data.get("forceNew"):
        if data.get("values"):
            await replace_component_values(session, context, str(existing.id), data["values"])
        return await _component_payload(session, existing)
    component = ServiceOrderComponent(
        service_order_id=order.id,
        component_template_id=template.id,
        component_group_id=group.id if group is not None else None,
        trade_direction_component_id=_int_or_none(data.get("tradeDirectionComponentId")),
        template_code=template.code,
        template_version=template.version,
        component_status="PENDING",
        sequence_no=_int_or_none(data.get("sequenceNo")) or 1,
        is_required=bool(data.get("required", template.is_required)),
        is_repeatable=bool(data.get("repeatable", template.is_repeatable)),
        instance_mode=str(data.get("instanceMode") or template.instance_mode),
    )
    session.add(component)
    await session.commit()
    if data.get("values"):
        await replace_component_values(session, context, str(component.id), data["values"])
    return await _component_payload(session, component)


async def replace_component_values(session: AsyncSession, context: RequestContext, component_id: str, values: list[dict[str, Any]]) -> dict:
    component = await session.get(ServiceOrderComponent, int(component_id))
    if component is None:
        raise NotFound("Component not found.")
    await session.execute(delete(ServiceComponentValue).where(ServiceComponentValue.component_id == component.id))
    for item in values or []:
        if not isinstance(item, dict):
            continue
        attribute_id = item.get("template_attribute_id") or item.get("templateAttributeId") or item.get("id")
        if attribute_id:
            attribute_id = int(attribute_id)
        else:
            code = item.get("code")
            attribute = (
                await session.execute(
                    select(TemplateAttribute).where(
                        TemplateAttribute.template_id == component.component_template_id, TemplateAttribute.code == code
                    )
                )
            ).scalars().first()
            attribute_id = attribute.id if attribute else None
        if attribute_id is None:
            continue
        session.add(
            ServiceComponentValue(
                component_id=component.id,
                template_attribute_id=int(attribute_id),
                value_text=_str_or_none(item.get("value_text") if "value_text" in item else item.get("valueText")),
                value_number=_decimal(item.get("value_number") if "value_number" in item else item.get("valueNumber"), None),
                value_date=_date(item.get("value_date") if "value_date" in item else item.get("valueDate")),
                value_boolean=item.get("value_boolean") if "value_boolean" in item else item.get("valueBoolean"),
                value_reference_type=item.get("value_reference_type"),
                value_reference_id=_int_or_none(item.get("value_reference_id")),
                value_json=item.get("value_json") if "value_json" in item else item.get("valueJson"),
            )
        )
    await session.commit()
    return await _component_payload(session, component)


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


async def complete_component(session: AsyncSession, context: RequestContext, component_id: str) -> dict:
    component = await session.get(ServiceOrderComponent, int(component_id))
    if component is None:
        raise NotFound("Component not found.")
    if component.component_status == "COMPLETED":
        return await _component_payload(session, component)
    attributes = (
        await session.execute(
            select(TemplateAttribute).where(
                TemplateAttribute.template_id == component.component_template_id,
                TemplateAttribute.is_required.is_(True),
            )
        )
    ).scalars().all()
    existing = {
        value.template_attribute_id
        for value in (
            await session.execute(select(ServiceComponentValue).where(ServiceComponentValue.component_id == component.id))
        ).scalars().all()
    }
    missing = [attr.code for attr in attributes if attr.id not in existing]
    if missing:
        raise ValidationFailed("Required component values are missing.", {code: "Required" for code in missing})
    component.component_status = "COMPLETED"
    component.completed_at = datetime.now(UTC)
    component.completed_by_user_id = context.user_id
    await session.commit()
    return await _component_payload(session, component)


async def remove_component(session: AsyncSession, context: RequestContext, component_id: str) -> dict:
    component = await session.get(ServiceOrderComponent, int(component_id))
    if component is None:
        raise NotFound("Component not found.")
    if component.component_status == "COMPLETED":
        raise InvalidState("Completed components cannot be deleted; use a controlled correction.")
    payload = await _component_payload(session, component)
    await session.delete(component)
    await session.commit()
    return payload


# --- Service charges ---------------------------------------------------------
def charge_record(charge: ServiceOrderCharge, data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data or {})
    payload.update(
        {
            "id": str(charge.id),
            "jobNo": None,
            "serviceOrderId": str(charge.service_order_id),
            "chargeNo": charge.charge_no,
            "documentNo": charge.charge_no,
            "documentType": charge.document_type,
            "documentDate": charge.document_date.isoformat() if charge.document_date else None,
            "currency": charge.currency_code,
            "status": charge.status.capitalize() if charge.status.isupper() else charge.status,
            "rawStatus": charge.status,
            "amount": float(charge.total_amount or 0),
            "subtotal": float(charge.subtotal_amount or 0),
            "discount": float(charge.discount_amount or 0),
            "tax": float(charge.tax_amount or 0),
            "total": float(charge.total_amount or 0),
            "createdAt": charge.created_at.isoformat() if charge.created_at else None,
        }
    )
    return payload


async def _order_no(session: AsyncSession, order_id: int) -> str | None:
    order = await session.get(ServiceOrder, order_id)
    return order.service_order_no if order else None


async def list_charges(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(ServiceOrderCharge)
    if page.status:
        stmt = stmt.where(ServiceOrderCharge.status == str(page.status).upper())
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(ServiceOrderCharge.id.desc()).limit(page.page_size).offset(page.offset))).scalars().all()
    items = []
    for row in rows:
        payload = charge_record(row, row.data or {})
        payload["jobNo"] = await _order_no(session, row.service_order_id)
        items.append(payload)
    return paged(items, page, total)


async def get_charge(session: AsyncSession, context: RequestContext, charge_id: int) -> dict:
    charge = await session.get(ServiceOrderCharge, charge_id)
    if charge is None:
        raise NotFound("Service charge not found.")
    payload = charge_record(charge, charge.data or {})
    payload["jobNo"] = await _order_no(session, charge.service_order_id)
    return payload


async def save_charge(session: AsyncSession, context: RequestContext, data: dict[str, Any], order_identifier: str | None = None) -> dict:
    charge_id = data.get("id")
    charge: ServiceOrderCharge | None = None
    if charge_id and str(charge_id).isdigit():
        charge = await session.get(ServiceOrderCharge, int(charge_id))
    identifier = order_identifier or data.get("jobNo") or data.get("serviceOrderId") or (charge.service_order_id if charge else None)
    if not identifier:
        raise ValidationFailed("A service order is required.", {"jobNo": "Required"})
    order = await resolve_order(session, context, str(identifier))
    if order.status == "CANCELLED":
        raise InvalidState("Cannot add charges to a cancelled service order.")
    if charge is None:
        number = data.get("chargeNo") or data.get("documentNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, "SERVICE_CHARGE")
        charge = ServiceOrderCharge(
            service_order_id=order.id,
            charge_no=str(number),
            document_type=str(data.get("documentType") or "SERVICE_NOTE"),
            document_date=_date(data.get("documentDate")) or date.today(),
            currency_code=data.get("currency") or order.currency_code,
            status=str(data.get("status") or "DRAFT").upper(),
            created_by_user_id=context.user_id,
            data={},
        )
        session.add(charge)
        await session.flush()
    else:
        charge.status = str(data.get("status") or charge.status).upper()

    lines = data.get("lines") or data.get("chargeLines") or []
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")
    await session.execute(delete(ServiceOrderChargeLine).where(ServiceOrderChargeLine.service_order_charge_id == charge.id))
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        quantity = _decimal(line.get("quantity"), Decimal("1")) or Decimal("1")
        unit_price = _decimal(line.get("unitPrice"), Decimal("0")) or Decimal("0")
        discount = _decimal(line.get("discount"), Decimal("0")) or Decimal("0")
        tax_rate = _decimal(line.get("tax"), Decimal("0")) or Decimal("0")
        base = quantity * unit_price
        tax_amount = (base - discount) * tax_rate / Decimal("100") if tax_rate else Decimal("0")
        line_total = _decimal(line.get("total"), base - discount + tax_amount) or (base - discount + tax_amount)
        subtotal += base
        discount_total += discount
        tax_total += tax_amount
        session.add(
            ServiceOrderChargeLine(
                service_order_charge_id=charge.id,
                line_no=index + 1,
                fee_type_id=_int_or_none(line.get("feeTypeId")),
                service_order_container_id=_int_or_none(line.get("containerId") or line.get("serviceOrderContainerId")),
                description=str(line.get("description") or line.get("feeType") or "Charge"),
                quantity=quantity,
                unit_code=line.get("unit"),
                unit_price=unit_price,
                discount_amount=discount,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                line_amount=line_total,
            )
        )
    charge.subtotal_amount = subtotal
    charge.discount_amount = discount_total
    charge.tax_amount = tax_total
    charge.total_amount = subtotal - discount_total + tax_total
    charge.remark = data.get("remark")
    charge.data = jsonable({key: value for key, value in data.items() if key not in {"id", "lines", "createdAt", "updatedAt"}})
    await session.commit()
    payload = charge_record(charge, charge.data or {})
    payload["jobNo"] = order.service_order_no
    return payload


async def issue_charge(session: AsyncSession, context: RequestContext, charge_id: int) -> dict:
    charge = await session.get(ServiceOrderCharge, charge_id)
    if charge is None:
        raise NotFound("Service charge not found.")
    if charge.status == "ISSUED":
        payload = charge_record(charge, charge.data or {})
        payload["jobNo"] = await _order_no(session, charge.service_order_id)
        return payload
    if charge.status != "DRAFT":
        raise InvalidState(f"Cannot issue a charge in status {charge.status}.")
    charge.status = "ISSUED"
    await session.commit()
    payload = charge_record(charge, charge.data or {})
    payload["jobNo"] = await _order_no(session, charge.service_order_id)
    return payload


async def charge_to_invoice(session: AsyncSession, context: RequestContext, charge_id: int) -> dict:
    from app.modules.finance import service as finance_service

    charge = await session.get(ServiceOrderCharge, charge_id)
    if charge is None:
        raise NotFound("Service charge not found.")
    document = await finance_service.create_invoice_from_charge(session, context, charge)
    return document


# --- Attachments -------------------------------------------------------------
async def list_attachments(session: AsyncSession, context: RequestContext, module: str, record_no: str) -> list[dict]:
    links = (
        await session.execute(
            select(Attachment)
            .join(AttachmentLink, AttachmentLink.attachment_id == Attachment.id)
            .where(
                AttachmentLink.entity_type == module,
                AttachmentLink.entity_id == _int_or_none(record_no) or 0,
                Attachment.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    return [_attachment_payload(item) for item in links]


def _attachment_payload(attachment: Attachment) -> dict[str, Any]:
    storage = get_storage()
    url = storage.presigned_get(attachment.storage_key) if storage.supports_presign else None
    if not url:
        url = f"{settings.storage_public_base_url}/{attachment.storage_key}"
    return {
        "id": str(attachment.id),
        "fileName": attachment.file_name,
        "name": attachment.file_name,
        "mimeType": attachment.mime_type,
        "sizeBytes": attachment.file_size_bytes,
        "storageProvider": attachment.storage_provider,
        "storageKey": attachment.storage_key,
        "uploadedAt": attachment.uploaded_at.isoformat() if attachment.uploaded_at else None,
        "url": url,
    }


def presign(file_name: str, mime_type: str = "") -> dict[str, Any]:
    storage = get_storage()
    key = f"{uuid.uuid4().hex}-{os.path.basename(file_name)}"
    content_type = guess_content_type(file_name, mime_type or None)
    if storage.supports_presign:
        upload_url = storage.presigned_put(key, content_type)
        if upload_url:
            return {
                "upload_url": upload_url,
                "file_name": file_name,
                "storage_key": key,
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "provider": storage.provider,
            }
    return {"upload_url": f"/api/v1/attachments/upload?storage_key={key}", "file_name": file_name, "storage_key": key, "method": "POST", "provider": storage.provider}


async def store_upload(
    session: AsyncSession, context: RequestContext, file_name: str, mime_type: str, content: bytes, storage_key: str | None = None
) -> dict:
    storage = get_storage()
    key = storage_key or f"{uuid.uuid4().hex}-{os.path.basename(file_name)}"
    content_type = guess_content_type(file_name, mime_type or None)
    storage.put(key, content, content_type)
    attachment = Attachment(
        file_name=file_name,
        storage_key=key,
        mime_type=content_type,
        file_size_bytes=len(content),
        storage_provider=storage.provider,
        uploaded_by_user_id=context.user_id,
    )
    session.add(attachment)
    await session.commit()
    return _attachment_payload(attachment)


async def read_attachment(storage_key: str) -> tuple[bytes, str]:
    storage = get_storage()
    if not storage.exists(storage_key):
        raise NotFound("File not found.")
    return storage.get(storage_key)

from __future__ import annotations

import os
import re
import uuid
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.config import settings
from app.core.context import RequestContext
from app.core.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, list_sort_orders, paged
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.core.storage import get_storage
from app.modules.master_data import config_versions
from app.modules.master_data.models import BusinessParty
from app.modules.operations.models import (
    Attachment,
    AttachmentLink,
    ServiceOrder,
    ServiceOrderCharge,
    ServiceOrderChargeLine,
    ServiceOrderContainer,
    ServiceOrderContainerRequirement,
    ServiceOrderMilestone,
    ServiceOrderMovement,
    ServiceOrderPlace,
    ServiceOrderPricing,
    ServiceOrderPricingLine,
)
from app.modules.operations.repository import OperationsRepository
from app.modules.quotations.models import (
    Quotation,
    QuotationRevision,
    QuotationRevisionContainer,
    QuotationRevisionLine,
)
from app.modules.settings.service import get_default_currency

ORDER_STATUS = {
    "active": "ACTIVE",
    "inactive": "INACTIVE",
    "finished": "FINISHED",
    "completed": "FINISHED",
    "complete": "FINISHED",
}

# Legacy lifecycle statuses from before the Active/Inactive simplification.
_LEGACY_INACTIVE = {"cancelled", "canceled", "closed", "inactive", "voided"}


def normalize_order_status(value: Any, default: str = "ACTIVE") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    mapped = ORDER_STATUS.get(text.lower())
    if mapped:
        return mapped
    return "INACTIVE" if text.lower() in _LEGACY_INACTIVE else "ACTIVE"


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
    order = await OperationsRepository(session).resolve_order(identifier)
    if order is None:
        raise NotFound("Service order not found.")
    return order


async def list_service_orders(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    rows, total = await OperationsRepository(session).order_page(
        page,
        status=normalize_order_status(page.status) if page.status else None,
    )
    return paged([order_record(row, row.data or {}) for row in rows], page, total)


async def get_service_order(session: AsyncSession, context: RequestContext, identifier: str) -> dict:
    order = await resolve_order(session, context, identifier)
    containers, requirements = await OperationsRepository(session).order_containers(order.id)
    return order_record(
        order,
        order.data or {},
        {
            "containers": [_container_payload(c) for c in containers],
            "containerRequirements": [_requirement_payload(r) for r in requirements],
            "components": [],
        },
    )


async def _resolve_party(session: AsyncSession, name: str | None, context: RequestContext) -> BusinessParty:
    from app.modules.quotations.service import resolve_party_by_name

    return await resolve_party_by_name(session, name, context)


async def save_service_order(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    default_currency = await get_default_currency(session)
    from app.modules.quotations.service import resolve_direction

    identifier = data.get("id") or data.get("serviceOrderId") or data.get("jobNo")
    order: ServiceOrder | None = None
    if identifier:
        try:
            order = await resolve_order(session, context, identifier)
        except NotFound:
            order = None
    if order is None:
        party = await _resolve_party(session, data.get("customer"), context)
        direction = await resolve_direction(session, data.get("direction"))
        number = data.get("jobNo") or data.get("serviceOrderNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, "SERVICE_ORDER")
        order = ServiceOrder(
            service_order_no=str(number),
            customer_party_id=party.id,
            trade_direction_id=direction.id,
            status=normalize_order_status(data.get("status"), "ACTIVE"),
            currency_code=data.get("currency") or default_currency,
            created_by_user_id=context.user_id,
            data={},
        )
        session.add(order)
        await session.flush()
        # Pin the order to the configuration in force right now, so a later
        # publish cannot re-interpret the component rows it will collect.
        await config_versions.stamp_service_order(session, order)
    else:
        # Only reassign when the caller actually supplied the field, otherwise a
        # partial save would silently repoint the order at another party/direction.
        if "customer" in data:
            order.customer_party_id = (await _resolve_party(session, data.get("customer"), context)).id
        if "direction" in data:
            order.trade_direction_id = (await resolve_direction(session, data.get("direction"))).id
        order.status = normalize_order_status(data.get("status"), order.status)
        order.currency_code = data.get("currency") or order.currency_code

    payload = {key: value for key, value in data.items() if key not in {"id", "createdAt", "updatedAt"}}
    # Merge so a partial update does not discard previously stored fields.
    order.data = jsonable({**(order.data or {}), **payload})
    await session.commit()
    await cache.bump("reports")
    return order_record(order, order.data or {})


async def finish_service_order(session: AsyncSession, context: RequestContext, identifier: str) -> dict:
    """Mark a service order as finished (idempotent)."""
    order = await resolve_order(session, context, identifier)
    if order.status == "INACTIVE":
        raise InvalidState("Cannot finish an inactive service order.")
    if order.status != "FINISHED":
        order.status = "FINISHED"
        await session.commit()
        await cache.bump("reports")
    return order_record(order, order.data or {})


async def set_service_order_status(
    session: AsyncSession, identifier: str | int, status: str
) -> dict:
    """Activate, deactivate or reopen a service order.

    Finishing stays with :func:`finish_service_order` because it is a workflow
    action; this is the plain status write the shared status endpoint uses for
    the remaining lifecycle moves.
    """
    order = await OperationsRepository(session).resolve_order(identifier)
    if order is None:
        raise NotFound("Service order not found.")
    order.status = normalize_order_status(status, order.status)
    await session.commit()
    await cache.bump("reports")
    return order_record(order, order.data or {})


async def order_status(session: AsyncSession, identifier: str | int) -> str | None:
    """Current status of one order, for the audit trail of a transition."""
    order = await OperationsRepository(session).resolve_order(identifier)
    return None if order is None else str(order.status)


async def record_order_status_change(
    session: AsyncSession,
    context: RequestContext,
    record: dict,
    before: str | None,
    event_type: str,
    action: str,
) -> None:
    """Every service-order transition leaves one audit row with both statuses."""
    from app.modules.audit.service import write_audit

    await write_audit(
        session,
        context,
        event_type=event_type,
        entity_type="service_order",
        entity_id=int(record.get("id") or 0),
        action=action,
        before={"status": before} if before else None,
        after={"status": record.get("rawStatus") or record.get("status")},
    )
    await session.commit()


async def charge_status(session: AsyncSession, charge_id: int) -> str | None:
    charge = await session.get(ServiceOrderCharge, charge_id)
    return None if charge is None else str(charge.status)


async def record_charge_status_change(
    session: AsyncSession,
    context: RequestContext,
    charge_id: int,
    before: str | None,
    record: dict,
) -> None:
    """Issuing is the only charge transition; record it with both statuses."""
    from app.modules.audit.service import write_audit

    await write_audit(
        session,
        context,
        event_type="SERVICE_CHARGE_ISSUED",
        entity_type="service_charge",
        entity_id=charge_id,
        action="issue",
        before={"status": before} if before else None,
        after={"status": record.get("status")},
    )
    await session.commit()


async def delete_service_orders(session: AsyncSession, ids: list[int]) -> int:
    orders = await OperationsRepository(session).orders_by_ids(ids)
    if any(str(order.status).upper() != "INACTIVE" for order in orders):
        raise Conflict("ORDER_ACTIVE", "Active service orders cannot be deleted. Deactivate the order first.")
    for order in orders:
        await session.delete(order)
    await session.commit()
    await cache.bump("reports")
    return len(orders)


async def create_service_order_from_quotation(
    session: AsyncSession, context: RequestContext, quotation: Quotation, revision: QuotationRevision
) -> ServiceOrder:
    default_currency = await get_default_currency(session)
    number = await allocate_number(session, "SERVICE_ORDER")
    data = dict(quotation.data or {})
    order = ServiceOrder(
        service_order_no=number,
        quotation_revision_id=revision.id,
        customer_party_id=quotation.customer_party_id,
        trade_direction_id=quotation.trade_direction_id,
        status="ACTIVE",
        currency_code=revision.currency_code or default_currency,
        description=revision.description,
        created_by_user_id=context.user_id,
        data=data,
    )
    session.add(order)
    await session.flush()
    # Pin the order to the configuration published when the quotation converts,
    # so a later publish cannot re-interpret its dynamic component rows.
    await config_versions.stamp_service_order(session, order)

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
        currency_code=revision.currency_code or default_currency,
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
    if order.status == "INACTIVE":
        raise InvalidState("Cannot add containers to an inactive service order.")
    container_number = str(data.get("containerNumber") or data.get("container_number") or data.get("containerNo") or "").strip()
    if not container_number:
        raise ValidationFailed("Container number is required.", {"containerNumber": "Required"})
    if (
        await session.execute(select(ServiceOrderContainer).where(ServiceOrderContainer.container_number == container_number))
    ).scalars().first():
        raise Conflict("DUPLICATE_NUMBER", "Container number already exists.", {"containerNumber": "Already in use"})
    container_type_id = data.get("containerTypeId") or data.get("container_type_id")
    if not container_type_id:
        from app.modules.master_data.service import resolve_or_create_container_type

        container_type_id = await resolve_or_create_container_type(session, data.get("containerType"))
    if not container_type_id:
        raise ValidationFailed("Container type is required.", {"containerType": "Required"})
    container = ServiceOrderContainer(
        service_order_id=order.id,
        container_requirement_id=_int_or_none(data.get("containerRequirementId") or data.get("container_requirement_id")),
        container_type_id=int(container_type_id),
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


async def _charge_with_details(session: AsyncSession, charge: ServiceOrderCharge) -> dict[str, Any]:
    """Charge payload enriched with its fee lines and, when present, the linked invoice."""
    from app.modules.finance.models import FinancialDocument, FinancialDocumentSource

    payload = charge_record(charge, charge.data or {})
    payload["jobNo"] = await _order_no(session, charge.service_order_id)
    lines = (
        await session.execute(
            select(ServiceOrderChargeLine)
            .where(ServiceOrderChargeLine.service_order_charge_id == charge.id)
            .order_by(ServiceOrderChargeLine.line_no)
        )
    ).scalars().all()
    payload["feeLines"] = [
        {
            "id": str(line.id),
            "lineNo": line.line_no,
            "feeTypeId": line.fee_type_id,
            "description": line.description,
            "quantity": float(line.quantity or 0),
            "unit": line.unit_code,
            "unitPrice": float(line.unit_price or 0),
            "discount": float(line.discount_amount or 0),
            "tax": float(line.tax_rate or 0),
            "taxAmount": float(line.tax_amount or 0),
            "total": float(line.line_amount or 0),
        }
        for line in lines
    ]
    source = (
        await session.execute(
            select(FinancialDocumentSource).where(
                FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE",
                FinancialDocumentSource.source_id == charge.id,
            )
        )
    ).scalars().first()
    if source is not None:
        document = await session.get(FinancialDocument, source.financial_document_id)
        if document is not None:
            payload["financialDocumentId"] = str(document.id)
            payload["invoiceNo"] = document.document_no
    return payload


async def list_charges(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(ServiceOrderCharge)
    if page.status:
        stmt = stmt.where(ServiceOrderCharge.status == str(page.status).upper())
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(ServiceOrderCharge, page, ServiceOrderCharge.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    items = [await _charge_with_details(session, row) for row in rows]
    return paged(items, page, total)


async def list_order_charges(session: AsyncSession, context: RequestContext, identifier: str) -> list[dict]:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(
            select(ServiceOrderCharge)
            .where(ServiceOrderCharge.service_order_id == order.id)
            .order_by(ServiceOrderCharge.id)
        )
    ).scalars().all()
    return [await _charge_with_details(session, row) for row in rows]


async def get_charge(session: AsyncSession, context: RequestContext, charge_id: int) -> dict:
    charge = await session.get(ServiceOrderCharge, charge_id)
    if charge is None:
        raise NotFound("Service charge not found.")
    return await _charge_with_details(session, charge)


async def save_charge(session: AsyncSession, context: RequestContext, data: dict[str, Any], order_identifier: str | None = None) -> dict:
    charge_id = data.get("id")
    charge: ServiceOrderCharge | None = None
    if charge_id and str(charge_id).isdigit():
        charge = await session.get(ServiceOrderCharge, int(charge_id))
    identifier = order_identifier or data.get("jobNo") or data.get("serviceOrderId") or (charge.service_order_id if charge else None)
    if not identifier:
        raise ValidationFailed("A service order is required.", {"jobNo": "Required"})
    order = await resolve_order(session, context, str(identifier))
    if order.status == "INACTIVE":
        raise InvalidState("Cannot add charges to an inactive service order.")
    if charge is not None and charge.status != "DRAFT":
        raise InvalidState("Only draft service charges can be edited.")
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
            status="DRAFT",
            created_by_user_id=context.user_id,
            data={},
        )
        session.add(charge)
        await session.flush()
    # Only rebuild priced lines when the caller supplied them; a partial update
    # (e.g. just a status change) must not wipe the existing lines and totals.
    if "lines" in data or "chargeLines" in data:
        from app.modules.master_data.service import resolve_reference_id

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
            # The charge line editor exposes `taxRate` and the serializer emits the
            # rate under `tax`, so accept both. Reading only `tax` silently dropped
            # the rate a user typed: the server stored zero tax while the form showed
            # a taxed total, and the resulting invoice carried no tax.
            tax_rate_field = "taxRate" if line.get("taxRate") not in (None, "") else "tax"
            tax_rate = _decimal(line.get(tax_rate_field), Decimal("0")) or Decimal("0")
            if quantity <= 0:
                raise ValidationFailed("Charge quantity must be greater than zero.", {f"lines.{index}.quantity": "Must be positive"})
            if unit_price < 0:
                raise ValidationFailed("Charge unit price cannot be negative.", {f"lines.{index}.unitPrice": "Cannot be negative"})
            base = quantity * unit_price
            if discount < 0 or discount > base:
                raise ValidationFailed(
                    "Charge discount must be between zero and the line subtotal.",
                    {f"lines.{index}.discount": "Invalid discount"},
                )
            if tax_rate < 0 or tax_rate > 100:
                raise ValidationFailed(
                    "Charge tax rate must be between 0 and 100.",
                    {f"lines.{index}.{tax_rate_field}": "Invalid tax rate"},
                )
            tax_amount = (base - discount) * tax_rate / Decimal("100") if tax_rate else Decimal("0")
            line_total = base - discount + tax_amount
            container_id = _int_or_none(line.get("containerId") or line.get("serviceOrderContainerId"))
            if container_id is not None:
                container = await session.get(ServiceOrderContainer, container_id)
                if container is None or container.service_order_id != order.id:
                    raise ValidationFailed(
                        "A charge line container must belong to the service order.",
                        {f"lines.{index}.containerId": "Container does not belong to this service order"},
                    )
            subtotal += base
            discount_total += discount
            tax_total += tax_amount
            session.add(
                ServiceOrderChargeLine(
                    service_order_charge_id=charge.id,
                    line_no=index + 1,
                    fee_type_id=await resolve_reference_id(
                        session,
                        "fee_type",
                        line.get("feeTypeId") or line.get("fee_type_id"),
                        line.get("feeType") or line.get("fee_type"),
                    ),
                    service_order_container_id=container_id,
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
    if "remark" in data:
        charge.remark = data.get("remark")
    charge.data = jsonable({
        **(charge.data or {}),
        **{key: value for key, value in data.items() if key not in {"id", "lines", "createdAt", "updatedAt"}},
    })
    await session.commit()
    await cache.bump("reports")
    return await _charge_with_details(session, charge)


async def issue_charge(session: AsyncSession, context: RequestContext, charge_id: int) -> dict:
    charge = (
        await session.execute(
            select(ServiceOrderCharge).where(ServiceOrderCharge.id == charge_id).with_for_update()
        )
    ).scalars().first()
    if charge is None:
        raise NotFound("Service charge not found.")
    if charge.status not in {"DRAFT", "ISSUED"}:
        raise InvalidState(f"Cannot issue a charge in status {charge.status}.")
    lines = (
        await session.execute(
            select(ServiceOrderChargeLine).where(ServiceOrderChargeLine.service_order_charge_id == charge.id)
        )
    ).scalars().all()
    if not lines or (charge.total_amount or Decimal("0")) <= 0:
        raise ValidationFailed("A service charge must have at least one positive line before it can be issued.")

    # Issuing confirms the commercial charge and automatically prepares the
    # accounting draft. Posting remains a separate finance-authorized action.
    charge.status = "ISSUED"
    from app.modules.finance import service as finance_service

    await finance_service.create_invoice_from_charge(session, context, charge, commit=False)
    await session.commit()
    await cache.bump("reports")
    return await _charge_with_details(session, charge)


async def delete_charges(session: AsyncSession, ids: list[int]) -> int:
    charges = await OperationsRepository(session).charges_by_ids(ids)
    drafts = [charge for charge in charges if charge.status == "DRAFT"]
    for charge in drafts:
        await session.delete(charge)
    await session.commit()
    if drafts:
        await cache.bump("reports")
    return len(drafts)


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
                AttachmentLink.entity_id == (_int_or_none(record_no) or 0),
                Attachment.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    return [_attachment_payload(item) for item in links]


async def delete_attachments(session: AsyncSession, context: RequestContext, ids: list[int]) -> int:
    """Soft-delete attachments so they stop being served.

    The row is flagged rather than removed: the file may be referenced by an audit
    trail, and a hard delete would also have to remove the object from storage. The
    storage object is deleted on a best-effort basis — a storage failure must not
    leave the database claiming the file is still available.
    """
    if not ids:
        return 0
    attachments = (
        await session.execute(select(Attachment).where(Attachment.id.in_(ids)))
    ).scalars().all()
    storage = get_storage()
    removed = 0
    for attachment in attachments:
        if attachment.is_deleted:
            continue
        attachment.is_deleted = True
        await session.execute(
            delete(AttachmentLink).where(AttachmentLink.attachment_id == attachment.id)
        )
        try:
            if storage.exists(attachment.storage_key):
                storage.delete(attachment.storage_key)
        except Exception:  # noqa: BLE001 - the flag is the source of truth, not the object store
            pass
        removed += 1
    await session.commit()
    return removed


def _attachment_payload(attachment: Attachment) -> dict[str, Any]:
    storage = get_storage()
    url = (
        storage.presigned_get(attachment.storage_key, settings.presigned_url_expire_seconds)
        if storage.supports_presign
        else None
    )
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


_UPLOAD_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "txt": "text/plain",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _upload_metadata(file_name: str, allowed: set[str] | None = None) -> tuple[str, str, str]:
    clean_name = os.path.basename(str(file_name or "").replace("\\", "/")).strip()
    if not clean_name or len(clean_name) > 255 or clean_name in {".", ".."}:
        raise ValidationFailed("The file name is invalid.", {"file": "Invalid file name"})
    extension = os.path.splitext(clean_name)[1].lower().lstrip(".")
    permitted = allowed if allowed is not None else settings.upload_allowed_extension_set
    if extension not in permitted or extension not in _UPLOAD_TYPES:
        raise ValidationFailed("This file type is not allowed.", {"file": "Unsupported file type"})
    return clean_name, extension, _UPLOAD_TYPES[extension]


async def effective_upload_extensions(session: AsyncSession) -> set[str]:
    """The extensions uploads may use: the environment list minus any the
    administrator disabled through ``app_settings('security').allowedUploadExtensions``.

    The stored list can only *narrow* what the environment allows. It can never
    widen it, because the environment list is the operator's control and
    ``_UPLOAD_TYPES`` is the set the content-signature validator understands —
    letting a database row add an extension the validator cannot inspect would
    turn a validation rule into a hole.

    A missing or unusable setting means "no restriction beyond the environment".
    """
    from app.modules.settings.service import get_app_config

    allowed = set(settings.upload_allowed_extension_set)
    try:
        config = await get_app_config(session)
    except Exception:  # noqa: BLE001 - a broken settings document must not block uploads
        return allowed
    security = config.get("security") if isinstance(config, dict) else None
    security = security if isinstance(security, dict) else {}
    configured = security.get("allowedUploadExtensions")
    if not isinstance(configured, list):
        return allowed
    chosen = {
        str(value).strip().lower().lstrip(".")
        for value in configured
        if str(value).strip()
    }
    if not chosen:
        # An empty list is ambiguous, not "allow nothing": refusing every upload
        # because a field was cleared would be a worse failure than ignoring it.
        return allowed
    return {extension for extension in allowed if extension in chosen and extension in _UPLOAD_TYPES}


def _validate_upload_content(extension: str, content: bytes) -> None:
    signatures = {
        "pdf": lambda value: value.startswith(b"%PDF-"),
        "png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "gif": lambda value: value.startswith((b"GIF87a", b"GIF89a")),
        "webp": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP",
    }
    if extension in signatures and not signatures[extension](content):
        raise ValidationFailed("The file content does not match its extension.", {"file": "Invalid content"})
    if extension in {"txt", "csv"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationFailed("Text uploads must use UTF-8 encoding.", {"file": "Invalid encoding"}) from exc
        if b"\x00" in content:
            raise ValidationFailed("The text file contains invalid binary data.", {"file": "Invalid content"})
    if extension in {"docx", "xlsx"}:
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
                expected_prefix = "word/" if extension == "docx" else "xl/"
                valid = "[Content_Types].xml" in names and any(name.startswith(expected_prefix) for name in names)
        except (zipfile.BadZipFile, OSError):
            valid = False
        if not valid:
            raise ValidationFailed("The Office document is invalid.", {"file": "Invalid content"})


async def presign(session: AsyncSession, file_name: str, mime_type: str = "") -> dict[str, Any]:
    storage = get_storage()
    clean_name, _, content_type = _upload_metadata(file_name, await effective_upload_extensions(session))
    key = f"{uuid.uuid4().hex}-{clean_name}"
    if storage.supports_presign and settings.storage_presigned_uploads_enabled:
        upload_url = storage.presigned_put(key, content_type, settings.presigned_url_expire_seconds)
        if upload_url:
            return {
                "upload_url": upload_url,
                "file_name": clean_name,
                "storage_key": key,
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "provider": storage.provider,
            }
    return {"upload_url": f"/api/v1/attachments/upload?storage_key={key}", "file_name": clean_name, "storage_key": key, "method": "POST", "provider": storage.provider}


async def store_upload(
    session: AsyncSession, context: RequestContext, file_name: str, mime_type: str, content: bytes, storage_key: str | None = None
) -> dict:
    storage = get_storage()
    clean_name, extension, content_type = _upload_metadata(file_name, await effective_upload_extensions(session))
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    if not content or len(content) > max_bytes:
        raise ValidationFailed(
            f"File size must be between 1 byte and {settings.upload_max_size_mb} MB.",
            {"file": "Invalid file size"},
        )
    _validate_upload_content(extension, content)
    key = storage_key or f"{uuid.uuid4().hex}-{clean_name}"
    if not re.fullmatch(r"[0-9a-f]{32}-[^/\\]{1,255}", key) or storage.exists(key):
        raise ValidationFailed("The storage key is invalid or already used.", {"file": "Invalid storage key"})
    storage.put(key, content, content_type)
    attachment = Attachment(
        file_name=clean_name,
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


# --- Movements ---------------------------------------------------------------
# A movement is one leg of the transport chain (origin -> destination, planned
# and actual times). The tables existed but had no service or endpoints, so the
# capability was unreachable from the application.

# Movement statuses are plain values rather than an enum so a new state does not
# need a migration; the API normalises casing and rejects anything unknown.
MOVEMENT_STATUSES = ("PLANNED", "IN_TRANSIT", "ARRIVED", "COMPLETED", "CANCELLED")


def _normalize_movement_status(value: Any, default: str = "PLANNED") -> str:
    if value in (None, ""):
        return default
    candidate = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return candidate if candidate in MOVEMENT_STATUSES else default


def _as_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _movement_payload(row: ServiceOrderMovement, *, transport_type: str | None = None) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "serviceOrderId": str(row.service_order_id),
        "sequenceNo": row.sequence_no,
        "transportTypeId": row.transport_type_id,
        "transportType": transport_type,
        "transportAssetId": row.transport_asset_id,
        "originPlaceId": row.origin_place_id,
        "destinationPlaceId": row.destination_place_id,
        "plannedDeparture": row.planned_departure.isoformat() if row.planned_departure else None,
        "actualDeparture": row.actual_departure.isoformat() if row.actual_departure else None,
        "plannedArrival": row.planned_arrival.isoformat() if row.planned_arrival else None,
        "actualArrival": row.actual_arrival.isoformat() if row.actual_arrival else None,
        "status": row.status,
        "notes": row.data.get("notes") if isinstance(row.data, dict) else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_movements(session: AsyncSession, context: RequestContext, identifier: str) -> list[dict]:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(
            select(ServiceOrderMovement)
            .where(ServiceOrderMovement.service_order_id == order.id)
            .order_by(ServiceOrderMovement.sequence_no, ServiceOrderMovement.id)
        )
    ).scalars().all()
    return [_movement_payload(row) for row in rows]


async def save_movement(
    session: AsyncSession, context: RequestContext, identifier: str, data: dict[str, Any]
) -> dict:
    """Create or update one movement leg.

    ``sequence_no`` is unique per order, so the next free sequence is allocated on
    create and a conflicting explicit value is rejected rather than silently
    renumbering a leg that other records may reference.
    """
    order = await resolve_order(session, context, identifier)
    if order.status == "INACTIVE":
        raise InvalidState("Cannot change movements on an inactive service order.")

    movement_id = _int_or_none(data.get("id"))
    movement: ServiceOrderMovement | None = None
    if movement_id is not None:
        movement = await session.get(ServiceOrderMovement, movement_id)
        if movement is None or movement.service_order_id != order.id:
            raise NotFound("Movement not found on this service order.")

    if movement is None:
        if "sequenceNo" in data and data.get("sequenceNo") not in (None, ""):
            sequence_no = int(data["sequenceNo"])
        else:
            highest = (
                await session.execute(
                    select(func.max(ServiceOrderMovement.sequence_no)).where(
                        ServiceOrderMovement.service_order_id == order.id
                    )
                )
            ).scalar()
            sequence_no = int(highest or 0) + 1
        if sequence_no <= 0:
            raise ValidationFailed("Sequence must be a positive number.", {"sequenceNo": "Enter 1 or more."})
        clash = (
            await session.execute(
                select(ServiceOrderMovement).where(
                    ServiceOrderMovement.service_order_id == order.id,
                    ServiceOrderMovement.sequence_no == sequence_no,
                )
            )
        ).scalars().first()
        if clash is not None:
            raise Conflict(
                "DUPLICATE_SEQUENCE",
                f"Movement sequence {sequence_no} already exists on this service order.",
                {"sequenceNo": "Already in use"},
            )
        movement = ServiceOrderMovement(service_order_id=order.id, sequence_no=sequence_no, data={})
        session.add(movement)
    elif "sequenceNo" in data and data.get("sequenceNo") not in (None, ""):
        requested = int(data["sequenceNo"])
        if requested != movement.sequence_no:
            # (service_order_id, sequence_no) is unique, so a renumber that
            # collides must be reported as a conflict rather than surfacing as a
            # database error.
            clash = (
                await session.execute(
                    select(ServiceOrderMovement).where(
                        ServiceOrderMovement.service_order_id == order.id,
                        ServiceOrderMovement.sequence_no == requested,
                        ServiceOrderMovement.id != movement.id,
                    )
                )
            ).scalars().first()
            if clash is not None:
                raise Conflict(
                    "DUPLICATE_SEQUENCE",
                    f"Movement sequence {requested} already exists on this service order.",
                    {"sequenceNo": "Already in use"},
                )
            movement.sequence_no = requested

    origin = await _resolve_place_id(session, data, "originPlaceId", "originPlace", "origin")
    destination = await _resolve_place_id(session, data, "destinationPlaceId", "destinationPlace", "destination")
    if origin is not None:
        movement.origin_place_id = origin
    if destination is not None:
        movement.destination_place_id = destination

    transport_type_id = _int_or_none(data.get("transportTypeId"))
    if transport_type_id is None and data.get("transportType"):
        from app.modules.master_data.service import resolve_reference_id

        transport_type_id = await resolve_reference_id(session, "transport_type", value=data.get("transportType"))
    if transport_type_id is not None:
        movement.transport_type_id = transport_type_id
    if data.get("transportAssetId") is not None:
        movement.transport_asset_id = _int_or_none(data.get("transportAssetId"))

    for camel, attribute in (
        ("plannedDeparture", "planned_departure"),
        ("actualDeparture", "actual_departure"),
        ("plannedArrival", "planned_arrival"),
        ("actualArrival", "actual_arrival"),
    ):
        if camel in data:
            try:
                setattr(movement, attribute, _as_utc(data.get(camel)))
            except ValueError as exc:
                raise ValidationFailed(
                    "Movement times must be valid timestamps.", {camel: "Use an ISO-8601 date/time."}
                ) from exc

    movement.status = _normalize_movement_status(data.get("status"), movement.status or "PLANNED")
    stored = dict(movement.data or {})
    if "notes" in data:
        stored["notes"] = data.get("notes")
    movement.data = jsonable(stored)
    await session.commit()
    return _movement_payload(movement)


async def delete_movements(session: AsyncSession, context: RequestContext, identifier: str, ids: list[int]) -> int:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(
            select(ServiceOrderMovement).where(
                ServiceOrderMovement.service_order_id == order.id, ServiceOrderMovement.id.in_(ids)
            )
        )
    ).scalars().all()
    for row in rows:
        await session.delete(row)
    await session.commit()
    return len(rows)


# --- Milestones --------------------------------------------------------------
MILESTONE_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED")


def _normalize_milestone_status(value: Any, default: str = "PENDING") -> str:
    if value in (None, ""):
        return default
    candidate = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return candidate if candidate in MILESTONE_STATUSES else default


def _milestone_payload(row: ServiceOrderMilestone) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "serviceOrderId": str(row.service_order_id),
        "milestoneCode": row.milestone_code,
        "milestoneName": row.milestone_name,
        "sequenceNo": row.sequence_no,
        "plannedAt": row.planned_at.isoformat() if row.planned_at else None,
        "actualAt": row.actual_at.isoformat() if row.actual_at else None,
        "status": row.status,
        "notes": row.notes,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_milestones(session: AsyncSession, context: RequestContext, identifier: str) -> list[dict]:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(
            select(ServiceOrderMilestone)
            .where(ServiceOrderMilestone.service_order_id == order.id)
            .order_by(ServiceOrderMilestone.sequence_no, ServiceOrderMilestone.id)
        )
    ).scalars().all()
    return [_milestone_payload(row) for row in rows]


async def save_milestone(
    session: AsyncSession, context: RequestContext, identifier: str, data: dict[str, Any]
) -> dict:
    order = await resolve_order(session, context, identifier)
    if order.status == "INACTIVE":
        raise InvalidState("Cannot change milestones on an inactive service order.")

    milestone_id = _int_or_none(data.get("id"))
    milestone: ServiceOrderMilestone | None = None
    if milestone_id is not None:
        milestone = await session.get(ServiceOrderMilestone, milestone_id)
        if milestone is None or milestone.service_order_id != order.id:
            raise NotFound("Milestone not found on this service order.")

    code = str(data.get("milestoneCode") or data.get("milestone_code") or "").strip().upper().replace(" ", "_")
    name = str(data.get("milestoneName") or data.get("milestone_name") or "").strip()
    if milestone is None:
        if not code:
            raise ValidationFailed("A milestone code is required.", {"milestoneCode": "Required"})
        clash = (
            await session.execute(
                select(ServiceOrderMilestone).where(
                    ServiceOrderMilestone.service_order_id == order.id,
                    ServiceOrderMilestone.milestone_code == code,
                )
            )
        ).scalars().first()
        if clash is not None:
            raise Conflict(
                "DUPLICATE_MILESTONE",
                f"Milestone '{code}' already exists on this service order.",
                {"milestoneCode": "Already in use"},
            )
        milestone = ServiceOrderMilestone(
            service_order_id=order.id,
            milestone_code=code,
            milestone_name=name or code.replace("_", " ").title(),
            sequence_no=int(data.get("sequenceNo") or 1),
            status=_normalize_milestone_status(data.get("status"), "PENDING"),
            notes=data.get("notes"),
        )
        session.add(milestone)
    else:
        if code and code != milestone.milestone_code:
            raise Conflict(
                "MILESTONE_CODE_IMMUTABLE",
                "A milestone code cannot change once created; add a new milestone instead.",
                {"milestoneCode": "Cannot be changed"},
            )
        if name:
            milestone.milestone_name = name
        if data.get("sequenceNo") not in (None, ""):
            milestone.sequence_no = int(data["sequenceNo"])
        milestone.status = _normalize_milestone_status(data.get("status"), milestone.status)
        if "notes" in data:
            milestone.notes = data.get("notes")

    for camel, attribute in (("plannedAt", "planned_at"), ("actualAt", "actual_at")):
        if camel in data:
            try:
                setattr(milestone, attribute, _as_utc(data.get(camel)))
            except ValueError as exc:
                raise ValidationFailed(
                    "Milestone times must be valid timestamps.", {camel: "Use an ISO-8601 date/time."}
                ) from exc

    await session.commit()
    return _milestone_payload(milestone)


async def delete_milestones(session: AsyncSession, context: RequestContext, identifier: str, ids: list[int]) -> int:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(
            select(ServiceOrderMilestone).where(
                ServiceOrderMilestone.service_order_id == order.id, ServiceOrderMilestone.id.in_(ids)
            )
        )
    ).scalars().all()
    for row in rows:
        await session.delete(row)
    await session.commit()
    return len(rows)


async def _resolve_place_id(
    session: AsyncSession, data: dict[str, Any], id_key: str, *name_keys: str
) -> int | None:
    """Accept an explicit place id or resolve a place by name/code."""
    explicit = _int_or_none(data.get(id_key))
    if explicit is not None:
        return explicit
    for key in name_keys:
        value = data.get(key)
        if value in (None, ""):
            continue
        from app.modules.master_data.service import resolve_reference_id

        return await resolve_reference_id(session, "place", value=value)
    return None

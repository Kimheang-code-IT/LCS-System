"""Automatic DRAFT financial documents for a Service Order.

One customer invoice per container and one supplier bill per
supplier/currency/order context. This module never posts: it only creates or
refreshes DRAFT documents, leaves posted/reversed documents untouched, and uses
``generated_key`` plus component allocation rows so a Finish/retry is idempotent.

The calculation sources are the same records the UI shows:
container-payment rows, CUSTOMER charge lines (selling side) and INTERNAL charge
lines (selling side for customer invoice, cost side for supplier bill).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache, fx
from app.core.context import RequestContext
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.modules.finance.models import (
    FinancialDocument,
    FinancialDocumentComponentAllocation,
    FinancialDocumentLine,
    FinancialDocumentSource,
)
from app.modules.finance.service import _document_currency_inputs
from app.modules.operations.models import (
    ServiceOrder,
    ServiceOrderCharge,
    ServiceOrderChargeLine,
    ServiceOrderContainer,
)
from app.modules.settings.service import get_default_currency

ZERO = Decimal("0")
PLACES = Decimal("1").scaleb(-4)


def _so_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return default


def _round(value: Decimal) -> Decimal:
    return value.quantize(PLACES)


def _component(
    *,
    source_kind: str,
    source_key: str,
    container_id: int | None,
    description: str,
    fee_type_id: Any,
    quantity: Decimal,
    unit_price: Decimal,
    discount: Decimal,
    tax_rate: Decimal,
    tax_amount: Decimal,
    line_total: Decimal,
) -> dict[str, Any]:
    return {
        "sourceKind": source_kind,
        "sourceKey": str(source_key),
        "containerId": container_id,
        "description": description,
        "feeTypeId": _so_int(fee_type_id),
        "quantity": quantity,
        "unitPrice": unit_price,
        "discount": discount,
        "taxRate": tax_rate,
        "taxAmount": tax_amount,
        "lineTotal": line_total,
    }


def _split_for_last(component: dict[str, Any], base: Decimal, discount: Decimal, tax: Decimal) -> dict[str, Any]:
    line_total = _round(base - discount + tax)
    return {
        **component,
        "quantity": Decimal("1"),
        "unitPrice": _round(base),
        "discount": _round(discount),
        "taxAmount": _round(tax),
        "lineTotal": line_total,
    }


async def _upsert_document(
    session: AsyncSession,
    context: RequestContext,
    *,
    generated_key: str,
    document_type: str,
    order: ServiceOrder,
    party_id: int | None,
    currency: str,
    description: str,
    components: list[dict[str, Any]],
    container_id: int | None,
    warnings: list[str],
) -> FinancialDocument | None:
    if not components:
        return None
    existing = (
        await session.execute(
            select(FinancialDocument).where(FinancialDocument.generated_key == generated_key)
        )
    ).scalars().first()
    if existing is not None and existing.status != "DRAFT":
        warnings.append(
            f"{existing.document_no} is {existing.status}; the generated draft was not changed."
        )
        return existing

    default_currency = await get_default_currency(session)
    document_currency, rate, base, precision = await _document_currency_inputs(
        session,
        {},
        document_currency=currency or order.currency_code or default_currency,
        base_currency=default_currency,
        on_date=date.today(),
        stored_rate=existing.exchange_rate if existing is not None else None,
    )

    if existing is None:
        number = await allocate_number(session, document_type)
        document = FinancialDocument(
            document_no=str(number),
            document_type=document_type,
            document_date=date.today(),
            status="DRAFT",
            party_id=party_id,
            service_order_id=order.id,
            currency_code=document_currency,
            exchange_rate=rate,
            base_currency_code=base,
            description=description,
            created_by_user_id=context.user_id,
            data={},
            generated_key=generated_key,
        )
        session.add(document)
        await session.flush()
    else:
        document = existing
        document.document_type = document_type
        document.party_id = party_id
        document.service_order_id = order.id
        document.currency_code = document_currency
        document.exchange_rate = rate
        document.base_currency_code = base
        document.description = description
        await session.execute(
            delete(FinancialDocumentLine).where(FinancialDocumentLine.financial_document_id == document.id)
        )
        await session.execute(
            delete(FinancialDocumentComponentAllocation).where(
                FinancialDocumentComponentAllocation.financial_document_id == document.id
            )
        )

    subtotal = ZERO
    discount_total = ZERO
    tax_total = ZERO
    total = ZERO
    for line_no, component in enumerate(components, start=1):
        quantity = _dec(component.get("quantity"), Decimal("1"))
        unit_price = _dec(component.get("unitPrice"))
        discount = _dec(component.get("discount"))
        tax_amount = _dec(component.get("taxAmount"))
        base_amount = _round(quantity * unit_price)
        line_total = _dec(component.get("lineTotal"), base_amount - discount + tax_amount)
        subtotal += base_amount
        discount_total += discount
        tax_total += tax_amount
        total += line_total
        session.add(
            FinancialDocumentLine(
                financial_document_id=document.id,
                line_no=line_no,
                description=str(component.get("description") or "Charge"),
                fee_type_id=component.get("feeTypeId"),
                quantity=quantity,
                unit_price=unit_price,
                discount_amount=discount,
                tax_rate=_dec(component.get("taxRate")),
                tax_amount=tax_amount,
                line_amount=_round(line_total),
                service_order_id=order.id,
                service_order_container_id=container_id,
            )
        )
        session.add(
            FinancialDocumentComponentAllocation(
                financial_document_id=document.id,
                source_kind=str(component.get("sourceKind") or "UNKNOWN"),
                # The line suffix keeps two allocations of the same source row in
                # one document distinct without weakening source traceability.
                source_key=f"{component.get('sourceKey') or ''}:{line_no}",
                container_id=container_id,
                allocated_amount=_round(line_total),
            )
        )

    document.subtotal_amount = _round(subtotal)
    document.discount_amount = _round(discount_total)
    document.tax_amount = _round(tax_total)
    document.total_amount = _round(total)
    document.base_subtotal_amount = fx.convert_to_base(document.subtotal_amount, rate, precision)
    document.base_discount_amount = fx.convert_to_base(document.discount_amount, rate, precision)
    document.base_tax_amount = fx.convert_to_base(document.tax_amount, rate, precision)
    document.base_total_amount = fx.convert_to_base(document.total_amount, rate, precision)
    document.data = jsonable(
        {
            **(document.data or {}),
            "generatedKey": generated_key,
            "generatedContainerId": str(container_id) if container_id is not None else None,
            "serviceOrderNo": order.service_order_no,
        }
    )
    return document


async def refresh_service_order_financial_documents(
    session: AsyncSession,
    context: RequestContext,
    order: ServiceOrder,
) -> dict[str, Any]:
    if not context.has_permission("financial_document.create"):
        return {
            "documents": [],
            "warnings": ["Missing financial_document.create permission; drafts were not generated."],
        }

    charges = (
        await session.execute(
            select(ServiceOrderCharge).where(ServiceOrderCharge.service_order_id == order.id)
        )
    ).scalars().all()
    charge_ids = [charge.id for charge in charges]
    invoiced_charge_ids = set(
        (
            await session.execute(
                select(FinancialDocumentSource.source_id).where(
                    FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE",
                    FinancialDocumentSource.source_id.in_(charge_ids),
                )
            )
        ).scalars().all()
    ) if charge_ids else set()
    charge_lines = (
        (
            await session.execute(
                select(ServiceOrderChargeLine)
                .where(ServiceOrderChargeLine.service_order_charge_id.in_(charge_ids))
                .order_by(ServiceOrderChargeLine.line_no)
            )
        ).scalars().all()
        if charge_ids
        else []
    )
    lines_by_charge: dict[int, list[ServiceOrderChargeLine]] = {}
    for line in charge_lines:
        lines_by_charge.setdefault(line.service_order_charge_id, []).append(line)

    warnings: list[str] = []

    containers = (
        await session.execute(
            select(ServiceOrderContainer)
            .where(ServiceOrderContainer.service_order_id == order.id)
            .order_by(ServiceOrderContainer.id)
        )
    ).scalars().all()
    container_by_id = {container.id: container for container in containers}
    container_by_no = {
        str(container.container_number): container
        for container in containers
        if container.container_number
    }

    direct: dict[int | None, list[dict[str, Any]]] = {container.id: [] for container in containers}
    shared: list[dict[str, Any]] = []
    direct_total: dict[int | None, Decimal] = {container.id: ZERO for container in containers}

    def target_for(row_container_id: Any, container_no: Any = None) -> int | None:
        cid = _so_int(row_container_id)
        if cid in container_by_id:
            return cid
        if container_no and str(container_no) in container_by_no:
            return container_by_no[str(container_no)].id
        return None

    for payment_index, row in enumerate((order.data or {}).get("containerPayments") or []):
        if not isinstance(row, dict):
            continue
        quantity = _dec(row.get("quantity"), Decimal("1"))
        unit_price = _dec(row.get("unitPrice") or row.get("unitAmount"))
        base = _dec(row.get("lineSubtotal"), quantity * unit_price)
        discount = _dec(row.get("discountAmount") or row.get("discount"))
        tax = _dec(row.get("taxAmount"))
        total = _dec(row.get("lineTotal") or row.get("amount"), base - discount + tax)
        component = _component(
            source_kind="CONTAINER_PRICING",
            source_key=str(row.get("id") or f"{order.id}:cp:{payment_index}"),
            container_id=None,
            description=str(row.get("description") or row.get("feeType") or "Container charge"),
            fee_type_id=None,
            quantity=quantity,
            unit_price=unit_price,
            discount=discount,
            tax_rate=_dec(row.get("taxRate")),
            tax_amount=tax,
            line_total=total,
        )
        cid = target_for(row.get("serviceOrderContainerId"), row.get("containerNo"))
        if cid is None:
            shared.append(component)
        else:
            component["containerId"] = cid
            direct.setdefault(cid, []).append(component)
            direct_total[cid] = direct_total.get(cid, ZERO) + total

    for charge in charges:
        if (charge.charge_side or "CUSTOMER").upper() != "CUSTOMER" or charge.status != "ISSUED":
            continue
        # A manually invoiced charge keeps its existing bill-once source; do not
        # bill it a second time through the generated container invoice.
        if charge.id in invoiced_charge_ids:
            continue
        if charge.currency_code and charge.currency_code != order.currency_code:
            warnings.append(
                f"Charge {charge.charge_no} is in {charge.currency_code}; it was not mixed into the "
                f"{order.currency_code} container invoice."
            )
            continue
        for line in lines_by_charge.get(charge.id, []):
            base = _round((line.quantity or ZERO) * (line.unit_price or ZERO))
            total = _dec(
                line.line_amount,
                base - (line.discount_amount or ZERO) + (line.tax_amount or ZERO),
            )
            component = _component(
                source_kind="CUSTOMER_CHARGE_LINE",
                source_key=f"charge-line:{line.id}",
                container_id=_so_int(line.service_order_container_id),
                description=str(line.description or "Customer charge"),
                fee_type_id=line.fee_type_id,
                quantity=line.quantity or Decimal("1"),
                unit_price=line.unit_price or ZERO,
                discount=line.discount_amount or ZERO,
                tax_rate=line.tax_rate or ZERO,
                tax_amount=line.tax_amount or ZERO,
                line_total=total,
            )
            cid = component["containerId"] if component["containerId"] in container_by_id else None
            if cid is None:
                shared.append(component)
            else:
                component["containerId"] = cid
                direct.setdefault(cid, []).append(component)
                direct_total[cid] = direct_total.get(cid, ZERO) + total

    for charge in charges:
        if (charge.charge_side or "CUSTOMER").upper() != "INTERNAL":
            continue
        if charge.currency_code and charge.currency_code != order.currency_code:
            warnings.append(
                f"Internal charge {charge.charge_no} is in {charge.currency_code}; its selling amount "
                f"was not mixed into the {order.currency_code} container invoice."
            )
            continue
        for line in lines_by_charge.get(charge.id, []):
            base = _round((line.quantity or ZERO) * (line.unit_price or ZERO))
            total = _dec(
                line.line_amount,
                base - (line.discount_amount or ZERO) + (line.tax_amount or ZERO),
            )
            component = _component(
                source_kind="INTERNAL_CHARGE_LINE",
                source_key=f"internal-line:{line.id}",
                container_id=_so_int(line.service_order_container_id),
                description=str(line.description or "Internal charge"),
                fee_type_id=line.fee_type_id,
                quantity=line.quantity or Decimal("1"),
                unit_price=line.unit_price or ZERO,
                discount=line.discount_amount or ZERO,
                tax_rate=line.tax_rate or ZERO,
                tax_amount=line.tax_amount or ZERO,
                line_total=total,
            )
            cid = component["containerId"] if component["containerId"] in container_by_id else None
            if cid is None:
                shared.append(component)
            else:
                component["containerId"] = cid
                direct.setdefault(cid, []).append(component)
                direct_total[cid] = direct_total.get(cid, ZERO) + total

    generated: list[dict[str, Any]] = []

    container_keys: list[int | None] = list(direct.keys())
    if not container_keys:
        container_keys = [None]
        direct = {None: []}
        direct_total = {None: ZERO}

    total_weight = sum((direct_total.get(key) or ZERO for key in container_keys), ZERO)
    for component in shared:
        base = _round(component["quantity"] * component["unitPrice"])
        discount = _dec(component.get("discount"))
        tax = _dec(component.get("taxAmount"))
        remaining_base = base
        remaining_discount = discount
        remaining_tax = tax
        for index, key in enumerate(container_keys):
            if index == len(container_keys) - 1:
                allocated = _split_for_last(component, remaining_base, remaining_discount, remaining_tax)
            else:
                weight = direct_total.get(key) or ZERO
                ratio = (weight / total_weight) if total_weight > 0 else (Decimal("1") / Decimal(len(container_keys)))
                allocated_base = _round(base * ratio)
                allocated_discount = _round(discount * ratio)
                allocated_tax = _round(tax * ratio)
                remaining_base -= allocated_base
                remaining_discount -= allocated_discount
                remaining_tax -= allocated_tax
                allocated = _split_for_last(component, allocated_base, allocated_discount, allocated_tax)
                if allocated["lineTotal"] == 0:
                    continue
            if allocated["lineTotal"] == 0:
                continue
            allocated["containerId"] = key
            direct.setdefault(key, []).append(allocated)

    for key in container_keys:
        components = direct.get(key) or []
        if not components:
            continue
        container = container_by_id.get(key) if key is not None else None
        label = container.container_number if container and container.container_number else "order"
        document = await _upsert_document(
            session,
            context,
            generated_key=f"SO:{order.id}:CTR:{key if key is not None else 'ORDER'}:CUSTOMER_INVOICE",
            document_type="CUSTOMER_INVOICE",
            order=order,
            party_id=order.customer_party_id,
            currency=order.currency_code,
            description=f"Service order {order.service_order_no} - container {label}",
            components=components,
            container_id=key,
            warnings=warnings,
        )
        if document is not None:
            generated.append({"id": str(document.id), "documentNo": document.document_no, "type": document.document_type})

    supplier_groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for charge in charges:
        if (charge.charge_side or "CUSTOMER").upper() != "INTERNAL":
            continue
        supplier_id = charge.supplier_party_id
        if supplier_id is None:
            warnings.append(f"Internal charge {charge.charge_no} has no supplier and was not billed.")
            continue
        currency = charge.currency_code or order.currency_code
        for line in lines_by_charge.get(charge.id, []):
            cost = _dec(
                line.cost_amount,
                (line.quantity or ZERO) * (line.cost_unit_price or ZERO),
            )
            if cost == 0:
                continue
            supplier_groups.setdefault((supplier_id, currency), []).append(
                _component(
                    source_kind="INTERNAL_COST_LINE",
                    source_key=f"internal-cost:{line.id}",
                    container_id=_so_int(line.service_order_container_id),
                    description=str(line.description or "Supplier cost"),
                    fee_type_id=line.fee_type_id,
                    quantity=line.quantity or Decimal("1"),
                    unit_price=line.cost_unit_price or ZERO,
                    discount=ZERO,
                    tax_rate=ZERO,
                    tax_amount=ZERO,
                    line_total=cost,
                )
            )

    for (supplier_id, currency), components in supplier_groups.items():
        document = await _upsert_document(
            session,
            context,
            generated_key=f"SO:{order.id}:SUP:{supplier_id}:{currency}:SUPPLIER_BILL",
            document_type="SUPPLIER_BILL",
            order=order,
            party_id=supplier_id,
            currency=currency,
            description=f"Supplier cost for service order {order.service_order_no}",
            components=components,
            container_id=None,
            warnings=warnings,
        )
        if document is not None:
            generated.append({"id": str(document.id), "documentNo": document.document_no, "type": document.document_type})

    await session.commit()
    await cache.bump("reports")
    return {"documents": generated, "warnings": warnings}

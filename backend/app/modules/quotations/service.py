from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import Conflict, InvalidState, NotFound
from app.core.pagination import PageParams, count_query, paged
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.modules.master_data.models import BusinessParty, PartyRole, TradeDirection
from app.modules.quotations.models import (
    Quotation,
    QuotationConversion,
    QuotationRevision,
    QuotationRevisionContainer,
    QuotationRevisionLine,
    QuotationRevisionPlace,
)

IMMUTABLE_STATUSES = {"SENT", "ACCEPTED", "CONVERTED", "SUPERSEDED", "REJECTED", "EXPIRED", "CANCELLED"}
STATUS_MAP = {
    "draft": "DRAFT",
    "sent": "SENT",
    "accepted": "ACCEPTED",
    "converted": "CONVERTED",
    "rejected": "REJECTED",
    "superseded": "SUPERSEDED",
    "expired": "EXPIRED",
    "cancelled": "CANCELLED",
}


def normalize_status(value: Any, default: str = "DRAFT") -> str:
    if value is None:
        return default
    text = str(value).strip().lower()
    return STATUS_MAP.get(text, str(value).strip().upper() or default)


async def resolve_party_by_name(session: AsyncSession, name: str | None, context: RequestContext, role: str = "CUSTOMER") -> BusinessParty:
    if name:
        party = (
            await session.execute(select(BusinessParty).where(BusinessParty.legal_name == name))
        ).scalars().first()
        if party is not None:
            return party
    party = (
        await session.execute(
            select(BusinessParty).join(PartyRole, PartyRole.party_id == BusinessParty.id).where(PartyRole.role_type == role).limit(1)
        )
    ).scalars().first()
    if party is not None and not name:
        return party
    created = BusinessParty(
        party_code=f"P-{datetime.now(UTC).strftime('%y%m%d%H%M%S')}",
        legal_name=name or "Unnamed Party",
        display_name=name or "Unnamed Party",
        status="ACTIVE",
    )
    session.add(created)
    await session.flush()
    session.add(PartyRole(party_id=created.id, role_type=role, is_primary=True))
    await session.flush()
    return created


async def resolve_direction(session: AsyncSession, name: str | None) -> TradeDirection:
    if name:
        direction = (
            await session.execute(
                select(TradeDirection).where(or_(TradeDirection.name == name, TradeDirection.code == str(name).upper()))
            )
        ).scalars().first()
        if direction is not None:
            return direction
    direction = (await session.execute(select(TradeDirection).order_by(TradeDirection.id).limit(1))).scalars().first()
    if direction is None:
        direction = TradeDirection(code="GENERAL", name="General", status="ACTIVE")
        session.add(direction)
        await session.flush()
    return direction


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return default


def _payload_amount(data: dict[str, Any]) -> Decimal:
    for key in ("amount", "totalSelling", "totalAmount", "total"):
        if data.get(key) not in (None, ""):
            return _decimal(data.get(key))
    return Decimal("0")


def quotation_record(quotation: Quotation, revision: QuotationRevision | None, data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data or {})
    payload.update(
        {
            "id": str(quotation.id),
            "quotationId": str(quotation.id),
            "quotationNo": quotation.quotation_no,
            "status": quotation.status.capitalize() if quotation.status.isupper() else quotation.status,
            "rawStatus": quotation.status,
            "orgId": quotation.organization_id,
            "branchId": quotation.branch_id,
            "revisionNo": quotation.current_revision_no,
            "createdAt": quotation.created_at.isoformat() if quotation.created_at else None,
            "updatedAt": quotation.updated_at.isoformat() if quotation.updated_at else None,
        }
    )
    if revision is not None:
        payload.setdefault("date", revision.quotation_date.isoformat() if revision.quotation_date else None)
        payload["validUntil"] = revision.valid_until.isoformat() if revision.valid_until else payload.get("validUntil")
        payload["currency"] = revision.currency_code or payload.get("currency")
        payload["revisionId"] = str(revision.id)
        payload["revisionStatus"] = revision.status
        payload.setdefault("amount", float(revision.total_amount or 0))
    return payload


async def get_latest_revision(session: AsyncSession, quotation: Quotation) -> QuotationRevision | None:
    return (
        await session.execute(
            select(QuotationRevision)
            .where(QuotationRevision.quotation_id == quotation.id)
            .order_by(QuotationRevision.revision_no.desc())
            .limit(1)
        )
    ).scalars().first()


async def _save_revision_children(session: AsyncSession, revision: QuotationRevision, data: dict[str, Any]) -> None:
    await session.execute(delete(QuotationRevisionContainer).where(QuotationRevisionContainer.quotation_revision_id == revision.id))
    await session.execute(delete(QuotationRevisionPlace).where(QuotationRevisionPlace.quotation_revision_id == revision.id))
    await session.execute(delete(QuotationRevisionLine).where(QuotationRevisionLine.quotation_revision_id == revision.id))

    for _index, container in enumerate(data.get("containerRequirements") or []):
        if not isinstance(container, dict):
            continue
        container_type_id = container.get("containerTypeId") or container.get("container_type_id")
        if not container_type_id:
            from app.modules.master_data.service import resolve_reference

            container_type_id = await resolve_reference(session, "container_type", container.get("containerType"))
        session.add(
            QuotationRevisionContainer(
                quotation_revision_id=revision.id,
                container_type_id=int(container_type_id) if container_type_id else 1,
                quantity=_decimal(container.get("quantity"), Decimal("1")),
                gross_weight_kg=_decimal(container.get("grossWeightKg"), None) if container.get("grossWeightKg") else None,
                remarks=container.get("remarks"),
            )
        )
    for index, line in enumerate(data.get("pricingLines") or data.get("lines") or []):
        if not isinstance(line, dict):
            continue
        quantity = _decimal(line.get("quantity"), Decimal("1"))
        unit_price = _decimal(line.get("unitPrice"), Decimal("0"))
        discount = _decimal(line.get("discount"), Decimal("0"))
        tax = _decimal(line.get("tax"), Decimal("0"))
        subtotal = quantity * unit_price
        total = _decimal(line.get("total"), subtotal - discount + tax)
        session.add(
            QuotationRevisionLine(
                quotation_revision_id=revision.id,
                line_no=index + 1,
                fee_type_id=line.get("feeTypeId"),
                service_description=str(line.get("description") or line.get("feeType") or "Service"),
                quantity=quantity,
                unit_code=line.get("unit"),
                unit_price=unit_price,
                discount_rate=discount,
                tax_rate=tax,
                line_subtotal=subtotal,
                line_discount=discount,
                line_tax=tax,
                line_total=total,
            )
        )
    await session.flush()


async def list_quotations(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(Quotation).where(Quotation.organization_id == context.organization_id)
    if not context.can_select_all_branches and context.branch_id is not None:
        stmt = stmt.where(Quotation.branch_id == context.branch_id)
    if page.status:
        stmt = stmt.where(Quotation.status == normalize_status(page.status))
    if page.q:
        pattern = f"%{page.q}%"
        stmt = stmt.where(Quotation.quotation_no.ilike(pattern) | Quotation.data["customer"].as_string().ilike(pattern))
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(Quotation.id.desc()).limit(page.page_size).offset(page.offset))).scalars().all()
    items = []
    for quotation in rows:
        revision = await get_latest_revision(session, quotation)
        items.append(quotation_record(quotation, revision, quotation.data or {}))
    return paged(items, page, total)


async def get_quotation(session: AsyncSession, context: RequestContext, quotation_id: int) -> dict:
    quotation = await session.get(Quotation, quotation_id)
    if quotation is None or quotation.organization_id != context.organization_id:
        raise NotFound("Quotation not found.")
    revision = await get_latest_revision(session, quotation)
    return quotation_record(quotation, revision, quotation.data or {})


async def save_quotation(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    quotation_id = data.get("id") or data.get("quotationId")
    quotation: Quotation | None = None
    if quotation_id and str(quotation_id).isdigit():
        quotation = await session.get(Quotation, int(quotation_id))
        if quotation is not None and quotation.organization_id != context.organization_id:
            raise NotFound("Quotation not found.")

    party = await resolve_party_by_name(session, data.get("customer"), context)
    direction = await resolve_direction(session, data.get("direction"))
    branch_id = int(data.get("branchId") or context.branch_id or 0) or (context.branch_id or 0)

    if quotation is None:
        number = data.get("quotationNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, context.organization_id, "QUOTATION")
        quotation = Quotation(
            organization_id=context.organization_id,
            branch_id=branch_id,
            quotation_no=str(number),
            customer_party_id=party.id,
            trade_direction_id=direction.id,
            status=normalize_status(data.get("status"), "DRAFT"),
            current_revision_no=1,
            data={},
        )
        session.add(quotation)
        await session.flush()
    else:
        quotation.customer_party_id = party.id
        quotation.trade_direction_id = direction.id
        quotation.status = normalize_status(data.get("status"), quotation.status)

    latest = await get_latest_revision(session, quotation)
    if latest is None:
        latest = QuotationRevision(
            quotation_id=quotation.id,
            revision_no=1,
            status="DRAFT",
            quotation_date=_date(data.get("date")) or date.today(),
            valid_until=_date(data.get("validUntil")),
            currency_code=data.get("currency") or "USD",
            created_by_user_id=context.user_id,
        )
        session.add(latest)
        await session.flush()

    if latest.status in IMMUTABLE_STATUSES:
        # A new revision is required instead of overwriting a sent revision.
        latest = await _clone_revision(session, quotation, latest)
        quotation.current_revision_no = latest.revision_no

    latest.quotation_date = _date(data.get("date")) or latest.quotation_date
    latest.valid_until = _date(data.get("validUntil")) or latest.valid_until
    latest.currency_code = data.get("currency") or latest.currency_code
    latest.description = data.get("description") or latest.description
    latest.notes = data.get("notes") or latest.notes
    latest.total_amount = _payload_amount(data)
    await _save_revision_children(session, latest, data)

    payload = {key: value for key, value in data.items() if key not in {"id", "quotationId", "createdAt", "updatedAt"}}
    quotation.data = jsonable(payload)
    await session.commit()
    return quotation_record(quotation, latest, quotation.data or {})


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


async def _clone_revision(session: AsyncSession, quotation: Quotation, source: QuotationRevision) -> QuotationRevision:
    next_no = (
        await session.scalar(select(func.max(QuotationRevision.revision_no)).where(QuotationRevision.quotation_id == quotation.id)) or 0
    ) + 1
    clone = QuotationRevision(
        quotation_id=quotation.id,
        revision_no=next_no,
        status="DRAFT",
        quotation_date=source.quotation_date,
        valid_until=source.valid_until,
        currency_code=source.currency_code,
        description=source.description,
        notes=source.notes,
        subtotal_amount=source.subtotal_amount,
        discount_amount=source.discount_amount,
        tax_amount=source.tax_amount,
        total_amount=source.total_amount,
        data=dict(source.data or {}),
    )
    session.add(clone)
    await session.flush()
    for container in (
        await session.execute(select(QuotationRevisionContainer).where(QuotationRevisionContainer.quotation_revision_id == source.id))
    ).scalars().all():
        session.add(
            QuotationRevisionContainer(
                quotation_revision_id=clone.id,
                container_type_id=container.container_type_id,
                quantity=container.quantity,
                gross_weight_kg=container.gross_weight_kg,
                description=container.description,
                remarks=container.remarks,
            )
        )
    for line in (
        await session.execute(select(QuotationRevisionLine).where(QuotationRevisionLine.quotation_revision_id == source.id))
    ).scalars().all():
        session.add(
            QuotationRevisionLine(
                quotation_revision_id=clone.id,
                line_no=line.line_no,
                fee_type_id=line.fee_type_id,
                service_description=line.service_description,
                quantity=line.quantity,
                unit_code=line.unit_code,
                unit_price=line.unit_price,
                discount_rate=line.discount_rate,
                tax_rate=line.tax_rate,
                line_subtotal=line.line_subtotal,
                line_discount=line.line_discount,
                line_tax=line.line_tax,
                line_total=line.line_total,
            )
        )
    await session.flush()
    return clone


async def create_revision(session: AsyncSession, context: RequestContext, quotation_id: int, data: dict[str, Any]) -> dict:
    quotation = await session.get(Quotation, quotation_id)
    if quotation is None or quotation.organization_id != context.organization_id:
        raise NotFound("Quotation not found.")
    latest = await get_latest_revision(session, quotation)
    clone = await _clone_revision(session, quotation, latest) if latest else None
    if clone is None:
        clone = QuotationRevision(
            quotation_id=quotation.id,
            revision_no=1,
            status="DRAFT",
            quotation_date=date.today(),
            currency_code=data.get("currency") or "USD",
            created_by_user_id=context.user_id,
        )
        session.add(clone)
        await session.flush()
    quotation.current_revision_no = clone.revision_no
    await session.commit()
    return quotation_record(quotation, clone, quotation.data or {})


async def _revision_with_quotation(session: AsyncSession, revision_id: int) -> tuple[Quotation, QuotationRevision]:
    revision = await session.get(QuotationRevision, revision_id)
    if revision is None:
        raise NotFound("Quotation revision not found.")
    quotation = await session.get(Quotation, revision.quotation_id)
    if quotation is None:
        raise NotFound("Quotation not found.")
    return quotation, revision


async def send_revision(session: AsyncSession, context: RequestContext, revision_id: int) -> dict:
    quotation, revision = await _revision_with_quotation(session, revision_id)
    if quotation.organization_id != context.organization_id:
        raise NotFound("Quotation not found.")
    if revision.status == "SENT":
        return quotation_record(quotation, revision, quotation.data or {})
    if revision.status != "DRAFT":
        raise InvalidState(f"Cannot send a revision in status {revision.status}.")
    revision.status = "SENT"
    revision.sent_at = datetime.now(UTC)
    quotation.status = "SENT"
    await session.commit()
    return quotation_record(quotation, revision, quotation.data or {})


async def submit_revision(session: AsyncSession, context: RequestContext, revision_id: int) -> dict:
    _, revision = await _revision_with_quotation(session, revision_id)
    revision.status = "SENT"
    revision.sent_at = revision.sent_at or datetime.now(UTC)
    await session.commit()
    quotation, revision = await _revision_with_quotation(session, revision_id)
    return quotation_record(quotation, revision, quotation.data or {})


async def accept_revision(session: AsyncSession, context: RequestContext, revision_id: int) -> dict:
    quotation, revision = await _revision_with_quotation(session, revision_id)
    if quotation.organization_id != context.organization_id:
        raise NotFound("Quotation not found.")
    if revision.status == "ACCEPTED":
        return quotation_record(quotation, revision, quotation.data or {})
    if revision.status != "SENT":
        raise InvalidState("Only a sent revision can be accepted.")
    revision.status = "ACCEPTED"
    revision.accepted_at = datetime.now(UTC)
    quotation.status = "ACCEPTED"
    competing = (
        await session.execute(
            select(QuotationRevision).where(
                QuotationRevision.quotation_id == quotation.id,
                QuotationRevision.id != revision.id,
                QuotationRevision.status == "SENT",
            )
        )
    ).scalars().all()
    for other in competing:
        other.status = "SUPERSEDED"
    await session.commit()
    return quotation_record(quotation, revision, quotation.data or {})


async def convert_revision(session: AsyncSession, context: RequestContext, revision_id: int) -> dict:
    from app.modules.operations.service import create_service_order_from_quotation

    quotation, revision = await _revision_with_quotation(session, revision_id)
    if quotation.organization_id != context.organization_id:
        raise NotFound("Quotation not found.")
    existing = (
        await session.execute(select(QuotationConversion).where(QuotationConversion.quotation_revision_id == revision.id))
    ).scalars().first()
    if existing is not None:
        raise Conflict("DUPLICATE_CONVERSION", "This quotation revision was already converted.")
    if revision.status != "ACCEPTED":
        raise InvalidState("Only an accepted revision can be converted to a service order.")
    service_order = await create_service_order_from_quotation(session, context, quotation, revision)
    session.add(
        QuotationConversion(
            quotation_revision_id=revision.id,
            service_order_id=service_order.id,
            converted_by_user_id=context.user_id,
        )
    )
    revision.status = "CONVERTED"
    quotation.status = "CONVERTED"
    await session.commit()
    payload = quotation_record(quotation, revision, quotation.data or {})
    payload["serviceOrderId"] = str(service_order.id)
    payload["serviceOrderNo"] = service_order.service_order_no
    return payload


async def delete_quotations(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    for quotation_id in ids:
        quotation = await session.get(Quotation, quotation_id)
        if quotation is not None and quotation.organization_id == context.organization_id:
            await session.delete(quotation)
    await session.commit()

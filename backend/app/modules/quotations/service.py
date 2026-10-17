from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.context import RequestContext
from app.core.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from app.core.pagination import PageParams, paged
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.modules.master_data.models import BusinessParty, TradeDirection
from app.modules.quotations.models import (
    Quotation,
    QuotationConversion,
    QuotationRevision,
    QuotationRevisionContainer,
    QuotationRevisionLine,
    QuotationRevisionPlace,
)
from app.modules.quotations.repository import QuotationRepository
from app.modules.settings.service import get_default_currency

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


async def resolve_party_by_id(session: AsyncSession, party_id: Any) -> BusinessParty:
    """Resolve a Business Party by primary key, rejecting unknown or inactive rows.

    ``customerPartyId`` comes from the company picker; an invalid id must never
    reach the FK column, so callers get a field-scoped validation error.
    """
    try:
        numeric = int(party_id)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed("The selected company is invalid.", {"customerPartyId": "Must be a company id."}) from exc
    party = await session.get(BusinessParty, numeric)
    if party is None or party.deleted_at is not None:
        raise ValidationFailed("The selected company does not exist.", {"customerPartyId": "Unknown company."})
    if str(party.status or "ACTIVE").upper() != "ACTIVE":
        raise ValidationFailed("The selected company is not active.", {"customerPartyId": "Inactive company."})
    return party


def new_party_code(now: datetime | None = None) -> str:
    """Return a party code that is unique among sibling placeholders.

    The former second-precision code (``P-YYMMDDHHMMSS``) was not unique: two
    customers created in the same second — two quotations saved back to back —
    violated the active ``party_code`` index and the request failed. The timestamp
    is kept for readability and a random suffix removes the collision.
    """
    stamp = (now or datetime.now(UTC)).strftime("%y%m%d%H%M%S")
    return f"P-{stamp}-{uuid4().hex[:4].upper()}"


async def resolve_party_by_name(session: AsyncSession, name: str | None, context: RequestContext, role: str = "CUSTOMER") -> BusinessParty:
    if name:
        party = (
            await session.execute(select(BusinessParty).where(BusinessParty.legal_name == name, BusinessParty.deleted_at.is_(None)))
        ).scalars().first()
        if party is not None:
            return party
    else:
        # No customer supplied: reuse any active party to satisfy the FK.
        party = (
            await session.execute(select(BusinessParty).where(BusinessParty.deleted_at.is_(None)).limit(1))
        ).scalars().first()
        if party is not None:
            return party
    # The unique index is partial (active rows only), so only an active code blocks.
    for _ in range(5):
        party_code = new_party_code()
        clash = (
            await session.execute(
                select(BusinessParty.id).where(
                    BusinessParty.party_code == party_code, BusinessParty.deleted_at.is_(None)
                )
            )
        ).first()
        if clash is None:
            break
    else:
        raise Conflict(
            "PARTY_CODE_UNAVAILABLE",
            "Could not allocate a unique party code; please try again.",
        )
    created = BusinessParty(
        party_code=party_code,
        legal_name=name or "Unnamed Party",
        display_name=name or "Unnamed Party",
        roles=[role.strip().title() or "Customer"],
        status="ACTIVE",
    )
    session.add(created)
    await session.flush()
    return created


async def resolve_direction(session: AsyncSession, name: str | None) -> TradeDirection:
    if name:
        direction = (
            await session.execute(
                select(TradeDirection).where(
                    or_(TradeDirection.name == name, TradeDirection.code == str(name).upper()),
                    TradeDirection.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if direction is not None:
            return direction
    direction = (
        await session.execute(
            select(TradeDirection).where(TradeDirection.deleted_at.is_(None)).order_by(TradeDirection.id).limit(1)
        )
    ).scalars().first()
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


def quotation_record(
    quotation: Quotation,
    revision: QuotationRevision | None,
    data: dict[str, Any],
    conversion: tuple[str, str] | None = None,
) -> dict[str, Any]:
    payload = dict(data or {})
    payload.update(
        {
            "id": str(quotation.id),
            "quotationId": str(quotation.id),
            "quotationNo": quotation.quotation_no,
            "customerPartyId": str(quotation.customer_party_id) if quotation.customer_party_id else None,
            "status": quotation.status.capitalize() if quotation.status.isupper() else quotation.status,
            "rawStatus": quotation.status,
            "revisionNo": quotation.current_revision_no,
            "createdAt": quotation.created_at.isoformat() if quotation.created_at else None,
            "updatedAt": quotation.updated_at.isoformat() if quotation.updated_at else None,
        }
    )
    if conversion is not None:
        payload["serviceOrderId"] = conversion[0]
        payload["serviceOrderNo"] = conversion[1]
    if revision is not None:
        payload.setdefault("date", revision.quotation_date.isoformat() if revision.quotation_date else None)
        payload["validUntil"] = revision.valid_until.isoformat() if revision.valid_until else payload.get("validUntil")
        payload["currency"] = revision.currency_code or payload.get("currency")
        payload["revisionId"] = str(revision.id)
        payload["revisionStatus"] = revision.status
        payload.setdefault("amount", float(revision.total_amount or 0))
    return payload


async def _conversions_for(session: AsyncSession, quotation_ids: list[int]) -> dict[int, tuple[str, str]]:
    """Map quotation id -> (service order id, service order no) for converted quotations."""
    return await QuotationRepository(session).conversion_map(quotation_ids)


async def _party_names(session: AsyncSession, party_ids: list[int]) -> dict[int, str]:
    return await QuotationRepository(session).party_names(party_ids)


async def get_latest_revision(session: AsyncSession, quotation: Quotation) -> QuotationRevision | None:
    return await QuotationRepository(session).latest_revision(quotation.id)


async def _save_revision_children(session: AsyncSession, revision: QuotationRevision, data: dict[str, Any]) -> None:
    # Replace a child collection only when the caller supplied it, so a partial
    # save (e.g. editing notes) does not erase containers or priced lines.
    if "containerRequirements" in data:
        await session.execute(delete(QuotationRevisionContainer).where(QuotationRevisionContainer.quotation_revision_id == revision.id))
        for _index, container in enumerate(data.get("containerRequirements") or []):
            if not isinstance(container, dict):
                continue
            container_type_id = container.get("containerTypeId") or container.get("container_type_id")
            if not container_type_id:
                from app.modules.master_data.service import resolve_or_create_container_type

                container_type_id = await resolve_or_create_container_type(session, container.get("containerType"))
            if not container_type_id:
                raise ValidationFailed("Container type is required.", {"containerType": "Required"})
            session.add(
                QuotationRevisionContainer(
                    quotation_revision_id=revision.id,
                    container_type_id=int(container_type_id),
                    quantity=_decimal(container.get("quantity"), Decimal("1")),
                    gross_weight_kg=_decimal(container.get("grossWeightKg"), None) if container.get("grossWeightKg") else None,
                    remarks=container.get("remarks"),
                )
            )
    if "places" in data:
        await session.execute(delete(QuotationRevisionPlace).where(QuotationRevisionPlace.quotation_revision_id == revision.id))
    if "pricingLines" in data or "lines" in data:
        from app.modules.master_data.service import resolve_reference_id

        await session.execute(delete(QuotationRevisionLine).where(QuotationRevisionLine.quotation_revision_id == revision.id))
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
                    fee_type_id=await resolve_reference_id(
                        session,
                        "fee_type",
                        line.get("feeTypeId") or line.get("fee_type_id"),
                        line.get("feeType") or line.get("fee_type"),
                    ),
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
    repository = QuotationRepository(session)
    rows, total = await repository.page(
        page,
        status=normalize_status(page.status) if page.status else None,
    )
    conversions = await _conversions_for(session, [row.id for row in rows])
    party_names = await _party_names(session, [row.customer_party_id for row in rows if row.customer_party_id])
    latest_revisions = await repository.latest_revisions([row.id for row in rows])
    items = []
    for quotation in rows:
        revision = latest_revisions.get(quotation.id)
        record = quotation_record(quotation, revision, quotation.data or {}, conversions.get(quotation.id))
        if not record.get("customer"):
            record["customer"] = party_names.get(quotation.customer_party_id)
        items.append(record)
    return paged(items, page, total)


async def get_quotation(session: AsyncSession, context: RequestContext, quotation_id: int) -> dict:
    quotation = await session.get(Quotation, quotation_id)
    if quotation is None:
        raise NotFound("Quotation not found.")
    revision = await get_latest_revision(session, quotation)
    conversions = await _conversions_for(session, [quotation.id])
    record = quotation_record(quotation, revision, quotation.data or {}, conversions.get(quotation.id))
    if not record.get("customer") and quotation.customer_party_id:
        party_names = await _party_names(session, [quotation.customer_party_id])
        record["customer"] = party_names.get(quotation.customer_party_id)
    return record


async def save_quotation(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    default_currency = await get_default_currency(session)
    quotation_id = data.get("id") or data.get("quotationId")
    quotation: Quotation | None = None
    if quotation_id and str(quotation_id).isdigit():
        quotation = await session.get(Quotation, int(quotation_id))

    if quotation is None:
        party_id = data.get("customerPartyId")
        party = (
            await resolve_party_by_id(session, party_id)
            if party_id not in (None, "")
            else await resolve_party_by_name(session, data.get("customer"), context)
        )
        direction = await resolve_direction(session, data.get("direction"))
        number = data.get("quotationNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, "QUOTATION")
        quotation = Quotation(
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
        # Only reassign when supplied so a partial save cannot repoint the party.
        party_id = data.get("customerPartyId")
        party = None
        if party_id not in (None, ""):
            party = await resolve_party_by_id(session, party_id)
            quotation.customer_party_id = party.id
        elif "customer" in data:
            party = await resolve_party_by_name(session, data.get("customer"), context)
            quotation.customer_party_id = party.id
        if "direction" in data:
            quotation.trade_direction_id = (await resolve_direction(session, data.get("direction"))).id
        quotation.status = normalize_status(data.get("status"), quotation.status)

    latest = await get_latest_revision(session, quotation)
    if latest is None:
        latest = QuotationRevision(
            quotation_id=quotation.id,
            revision_no=1,
            status="DRAFT",
            quotation_date=_date(data.get("date")) or date.today(),
            valid_until=_date(data.get("validUntil")),
            currency_code=data.get("currency") or default_currency,
            created_by_user_id=context.user_id,
        )
        session.add(latest)
        await session.flush()

    if latest.status in IMMUTABLE_STATUSES:
        # A new revision is required instead of overwriting a sent revision.
        latest = await _clone_revision(session, quotation, latest, context.user_id)
        quotation.current_revision_no = latest.revision_no
        # Cloning opens a fresh draft revision, so the quotation becomes editable.
        if "status" not in data:
            quotation.status = "DRAFT"

    latest.quotation_date = _date(data.get("date")) or latest.quotation_date
    latest.valid_until = _date(data.get("validUntil")) or latest.valid_until
    latest.currency_code = data.get("currency") or latest.currency_code
    latest.description = data.get("description") or latest.description
    latest.notes = data.get("notes") or latest.notes
    if any(data.get(key) not in (None, "") for key in ("amount", "totalSelling", "totalAmount", "total")):
        latest.total_amount = _payload_amount(data)
    await _save_revision_children(session, latest, data)

    payload = {key: value for key, value in data.items() if key not in {"id", "quotationId", "createdAt", "updatedAt"}}
    if party is not None:
        # Keep the denormalised display name in sync with the selected party.
        payload["customer"] = party.legal_name
    quotation.data = jsonable({**(quotation.data or {}), **payload})
    await session.commit()
    return quotation_record(quotation, latest, quotation.data or {})


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


async def _clone_revision(
    session: AsyncSession,
    quotation: Quotation,
    source: QuotationRevision,
    created_by_user_id: int | None = None,
) -> QuotationRevision:
    # Serialise revision allocation on the quotation header. Two concurrent
    # "create revision" requests would otherwise both read the same MAX() and
    # race for revision_no; the unique (quotation_id, revision_no) constraint
    # would turn the loser into a 500 instead of a clean second draft.
    await session.execute(select(Quotation.id).where(Quotation.id == quotation.id).with_for_update())
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
        created_by_user_id=created_by_user_id or source.created_by_user_id,
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
    default_currency = await get_default_currency(session)
    quotation = await session.get(Quotation, quotation_id)
    if quotation is None:
        raise NotFound("Quotation not found.")
    latest = await get_latest_revision(session, quotation)
    clone = await _clone_revision(session, quotation, latest, context.user_id) if latest else None
    if clone is None:
        clone = QuotationRevision(
            quotation_id=quotation.id,
            revision_no=1,
            status="DRAFT",
            quotation_date=date.today(),
            currency_code=data.get("currency") or default_currency,
            created_by_user_id=context.user_id,
        )
        session.add(clone)
        await session.flush()
    quotation.current_revision_no = clone.revision_no
    if latest is not None and latest.status != "DRAFT":
        # Re-quotation reopens the quotation as an editable draft while the
        # original (sent/accepted/converted) revision is preserved for history.
        quotation.status = "DRAFT"
    await session.commit()
    return quotation_record(quotation, clone, quotation.data or {})


async def list_revisions(session: AsyncSession, context: RequestContext, quotation_id: int) -> list[dict[str, Any]]:
    quotation = await session.get(Quotation, quotation_id)
    if quotation is None:
        raise NotFound("Quotation not found.")
    revisions = await QuotationRepository(session).revisions(quotation.id)
    names: dict[int, str] = {}
    user_ids = [row.created_by_user_id for row in revisions if row.created_by_user_id]
    if user_ids:
        from app.modules.auth.models import User

        names = {
            row[0]: row[1]
            for row in (
                await session.execute(select(User.id, User.display_name).where(User.id.in_(user_ids)))
            ).all()
        }
    return [
        {
            "id": str(revision.id),
            "revisionId": str(revision.id),
            "revisionNo": revision.revision_no,
            "status": revision.status.capitalize() if revision.status.isupper() else revision.status,
            "rawStatus": revision.status,
            "quotationDate": revision.quotation_date.isoformat() if revision.quotation_date else None,
            "validUntil": revision.valid_until.isoformat() if revision.valid_until else None,
            "currency": revision.currency_code,
            "total": float(revision.total_amount or 0),
            "createdBy": names.get(revision.created_by_user_id) or revision.created_by_user_id,
            "createdAt": revision.created_at.isoformat() if revision.created_at else None,
            "sentAt": revision.sent_at.isoformat() if revision.sent_at else None,
            "acceptedAt": revision.accepted_at.isoformat() if revision.accepted_at else None,
            "isCurrent": revision.revision_no == quotation.current_revision_no,
        }
        for revision in revisions
    ]


async def _revision_with_quotation(session: AsyncSession, revision_id: int) -> tuple[Quotation, QuotationRevision]:
    revision = await session.get(QuotationRevision, revision_id)
    if revision is None:
        raise NotFound("Quotation revision not found.")
    quotation = await session.get(Quotation, revision.quotation_id)
    if quotation is None:
        raise NotFound("Quotation not found.")
    return quotation, revision


async def revision_status(session: AsyncSession, revision_id: int) -> str | None:
    """Current status of one revision, for the audit trail of a transition."""
    revision = await session.get(QuotationRevision, revision_id)
    return None if revision is None else str(revision.status)


async def send_revision(session: AsyncSession, context: RequestContext, revision_id: int) -> dict:
    quotation, revision = await _revision_with_quotation(session, revision_id)
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
    quotation, revision = await _revision_with_quotation(session, revision_id)
    if revision.status == "SENT":
        return quotation_record(quotation, revision, quotation.data or {})
    if revision.status != "DRAFT":
        raise InvalidState(f"Cannot submit a revision in status {revision.status}.")
    revision.status = "SENT"
    revision.sent_at = revision.sent_at or datetime.now(UTC)
    quotation.status = "SENT"
    await session.commit()
    return quotation_record(quotation, revision, quotation.data or {})


async def accept_revision(session: AsyncSession, context: RequestContext, revision_id: int) -> dict:
    quotation, revision = await _revision_with_quotation(session, revision_id)
    if revision.status == "ACCEPTED":
        return quotation_record(quotation, revision, quotation.data or {})
    if revision.status != "SENT":
        raise InvalidState("Only a sent revision can be accepted.")
    revision.status = "ACCEPTED"
    revision.accepted_at = datetime.now(UTC)
    quotation.status = "ACCEPTED"
    competing = await QuotationRepository(session).competing_revisions(quotation.id, revision.id)
    for other in competing:
        other.status = "SUPERSEDED"
    await session.commit()
    return quotation_record(quotation, revision, quotation.data or {})


async def reject_revision(session: AsyncSession, context: RequestContext, revision_id: int, reason: str | None = None) -> dict:
    """Record a customer rejection instead of silently leaving the revision SENT.

    Rejection is final for that revision: its terms stay frozen and a follow-up
    offer has to be a new revision, which keeps the approval history readable.
    """
    quotation, revision = await _revision_with_quotation(session, revision_id)
    if revision.status == "REJECTED":
        return quotation_record(quotation, revision, quotation.data or {})
    if revision.status not in {"SENT", "DRAFT"}:
        raise InvalidState(f"Cannot reject a revision in status {revision.status}.")
    revision.status = "REJECTED"
    revision.rejected_at = datetime.now(UTC)
    if reason:
        revision.data = jsonable({**(revision.data or {}), "rejectionReason": reason})
    if quotation.current_revision_no == revision.revision_no and not any(
        other.status in {"DRAFT", "SENT", "ACCEPTED"}
        for other in await QuotationRepository(session).revisions(quotation.id)
        if other.id != revision.id
    ):
        # Only reflect the rejection on the header when no other revision can
        # still be accepted, so a rejected revision cannot hide a live offer.
        quotation.status = "REJECTED"
    await session.commit()
    return quotation_record(quotation, revision, quotation.data or {})


async def cancel_revision(session: AsyncSession, context: RequestContext, revision_id: int, reason: str | None = None) -> dict:
    """Withdraw a revision the seller no longer offers.

    Cancelling differs from rejecting: nobody declined the offer, it was pulled
    back before a decision. Only a draft or a sent revision can be withdrawn, and
    the header mirrors it only when no other revision is still live — the same
    rule the rejection path uses, so a cancelled revision cannot hide a live
    offer. The revision's terms stay frozen, exactly as after a rejection.
    """
    quotation, revision = await _revision_with_quotation(session, revision_id)
    if revision.status == "CANCELLED":
        return quotation_record(quotation, revision, quotation.data or {})
    if revision.status not in {"DRAFT", "SENT"}:
        raise InvalidState(f"Cannot cancel a revision in status {revision.status}.")
    revision.status = "CANCELLED"
    if reason:
        revision.data = jsonable({**(revision.data or {}), "cancellationReason": reason})
    if quotation.current_revision_no == revision.revision_no and not any(
        other.status in {"DRAFT", "SENT", "ACCEPTED"}
        for other in await QuotationRepository(session).revisions(quotation.id)
        if other.id != revision.id
    ):
        quotation.status = "CANCELLED"
    await session.commit()
    return quotation_record(quotation, revision, quotation.data or {})


# Fields compared by the revision diff. Ordered so the output reads header-first.
_COMPARE_HEADER_FIELDS: tuple[tuple[str, str], ...] = (
    ("quotationDate", "quotation_date"),
    ("validUntil", "valid_until"),
    ("currency", "currency_code"),
    ("status", "status"),
    ("description", "description"),
    ("notes", "notes"),
    ("subtotal", "subtotal_amount"),
    ("discount", "discount_amount"),
    ("tax", "tax_amount"),
    ("total", "total_amount"),
)


def _comparison_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


async def compare_revisions(
    session: AsyncSession, context: RequestContext, revision_id: int, other_revision_id: int
) -> dict:
    """Diff two revisions of the same quotation without touching either one.

    Only the same quotation can be compared: comparing across quotations would
    imply a commercial relationship that does not exist.
    """
    left = await session.get(QuotationRevision, revision_id)
    if left is None:
        raise NotFound("Quotation revision not found.")
    right = await session.get(QuotationRevision, other_revision_id)
    if right is None:
        raise NotFound("Quotation revision not found.")
    if left.quotation_id != right.quotation_id:
        raise ValidationFailed(
            "Only revisions of the same quotation can be compared.",
            {"revision": "The two revisions belong to different quotations."},
        )

    header_changes = []
    for label, attribute in _COMPARE_HEADER_FIELDS:
        before = _comparison_value(getattr(left, attribute, None))
        after = _comparison_value(getattr(right, attribute, None))
        if before != after:
            header_changes.append({"field": label, "from": before, "to": after})

    def line_key(line: QuotationRevisionLine) -> int:
        return int(line.line_no)

    left_lines = {line_key(line): line for line in await _revision_lines(session, left.id)}
    right_lines = {line_key(line): line for line in await _revision_lines(session, right.id)}
    line_changes = []
    for line_no in sorted(set(left_lines) | set(right_lines)):
        before, after = left_lines.get(line_no), right_lines.get(line_no)
        if before is None or after is None:
            line_changes.append(
                {
                    "lineNo": line_no,
                    "change": "added" if before is None else "removed",
                    "from": _revision_line_payload(before) if before else None,
                    "to": _revision_line_payload(after) if after else None,
                }
            )
            continue
        differences = {}
        for field, attribute in (
            ("description", "service_description"),
            ("quantity", "quantity"),
            ("unitPrice", "unit_price"),
            ("discountRate", "discount_rate"),
            ("taxRate", "tax_rate"),
            ("lineTotal", "line_total"),
        ):
            if _comparison_value(getattr(before, attribute, None)) != _comparison_value(getattr(after, attribute, None)):
                differences[field] = {
                    "from": _comparison_value(getattr(before, attribute, None)),
                    "to": _comparison_value(getattr(after, attribute, None)),
                }
        if differences:
            line_changes.append({"lineNo": line_no, "change": "modified", "fields": differences})

    left_total = _comparison_value(left.total_amount) or 0.0
    right_total = _comparison_value(right.total_amount) or 0.0
    return {
        "quotationId": str(left.quotation_id),
        "from": {"revisionId": str(left.id), "revisionNo": left.revision_no, "status": left.status},
        "to": {"revisionId": str(right.id), "revisionNo": right.revision_no, "status": right.status},
        "headerChanges": header_changes,
        "lineChanges": line_changes,
        "totals": {
            "from": left_total,
            "to": right_total,
            "difference": float(right_total) - float(left_total),
        },
        "changed": bool(header_changes or line_changes),
    }


def _revision_line_payload(line: QuotationRevisionLine | None) -> dict[str, Any] | None:
    if line is None:
        return None
    return {
        "lineNo": line.line_no,
        "description": line.service_description,
        "quantity": float(line.quantity or 0),
        "unitPrice": float(line.unit_price or 0),
        "lineTotal": float(line.line_total or 0),
    }


async def _revision_lines(session: AsyncSession, revision_id: int) -> list[QuotationRevisionLine]:
    return list(
        (
            await session.execute(
                select(QuotationRevisionLine)
                .where(QuotationRevisionLine.quotation_revision_id == revision_id)
                .order_by(QuotationRevisionLine.line_no)
            )
        ).scalars().all()
    )


async def convert_revision(session: AsyncSession, context: RequestContext, revision_id: int) -> dict:
    from app.modules.operations.service import create_service_order_from_quotation

    quotation, revision = await _revision_with_quotation(session, revision_id)
    prior_conversion = await QuotationRepository(session).conversion_for_quotation(quotation.id)
    if prior_conversion is not None:
        raise Conflict("DUPLICATE_CONVERSION", "This quotation was already converted to a service order.")
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
    await cache.bump("reports")
    payload = quotation_record(quotation, revision, quotation.data or {})
    payload["serviceOrderId"] = str(service_order.id)
    payload["serviceOrderNo"] = service_order.service_order_no
    return payload


async def delete_quotations(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    for quotation_id in ids:
        quotation = await session.get(Quotation, quotation_id)
        if quotation is None:
            continue
        conversion = await QuotationRepository(session).conversion_for_quotation(quotation.id)
        if conversion is not None or quotation.status == "CONVERTED":
            # A converted quotation is the audit trail behind a service order.
            raise Conflict(
                "QUOTATION_HAS_SERVICE_ORDER",
                f"{quotation.quotation_no} is linked to a service order and cannot be deleted.",
            )
        await session.delete(quotation)
    await session.commit()

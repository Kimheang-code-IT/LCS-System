from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.context import RequestContext
from app.core.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from app.core.pagination import PageParams, paged
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.core.validation import validate_line_items
from app.modules.master_data.models import BusinessParty, TradeDirection, TransportType
from app.modules.master_data.route_stops import (
    route_stop_payload,
    route_stop_payloads,
    save_route_stops,
)
from app.modules.quotations.models import (
    Quotation,
    QuotationConversion,
    QuotationRevision,
    QuotationRevisionContainer,
    QuotationRevisionLine,
    QuotationRevisionPlace,
)
from app.modules.quotations.repository import QuotationRepository
from app.modules.quotations.schemas import (
    CONTAINER_REQUIREMENT_SCHEMA,
    PRICING_LINE_SCHEMA,
    QUOTATION_WRITE_SCHEMA,
)
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
        # A supplied direction is a choice, not a hint: never silently replace it
        # with the first configured row.
        raise ValidationFailed(
            "The selected trade direction does not exist.",
            {"direction": "Unknown trade direction."},
        )
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


def _money(value: Decimal) -> Decimal:
    """Round a commercial amount the same way the form and the reports do."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
            "sourceServiceOrderId": str(quotation.source_service_order_id) if quotation.source_service_order_id else None,
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


async def revision_route_payloads(session: AsyncSession, revision_id: int) -> list[dict[str, Any]]:
    """The saved route stops of a revision, ordered by sequence."""
    rows = list(
        (
            await session.execute(
                select(QuotationRevisionPlace)
                .where(QuotationRevisionPlace.quotation_revision_id == revision_id)
                .order_by(QuotationRevisionPlace.sequence_no, QuotationRevisionPlace.id)
            )
        ).scalars().all()
    )
    return await route_stop_payloads(session, rows)


async def _resolve_transport_by(session: AsyncSession, value: Any) -> str | None:
    """Resolve a pricing line's Transport Type to its id.

    New lines submit the master-record id. Quotations saved before the select
    was database-driven stored the name; resolve it when a record exists and
    keep the legacy text otherwise so an old quotation stays editable.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.isdigit():
        row = await session.get(TransportType, int(text))
        return str(row.id) if row is not None else None
    row = (
        await session.execute(
            select(TransportType).where(
                or_(TransportType.code == text, TransportType.name == text),
                TransportType.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    return str(row.id) if row is not None else text


async def _save_revision_children(session: AsyncSession, revision: QuotationRevision, data: dict[str, Any]) -> None:
    # Replace a child collection only when the caller supplied it, so a partial
    # save (e.g. editing notes) does not erase containers or priced lines.
    if "containerRequirements" in data:
        data["containerRequirements"] = validate_line_items(
            data.get("containerRequirements"),
            CONTAINER_REQUIREMENT_SCHEMA,
            field="containerRequirements",
        )
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
        # The route editor keeps a trailing blank row for data entry; only rows
        # the operator actually started are validated and persisted. Existing
        # row ids are preserved, so a role deactivated after the fact stays
        # acceptable on the row that already used it.
        data["places"] = await save_route_stops(
            session,
            model=QuotationRevisionPlace,
            parent_field="quotation_revision_id",
            parent_id=revision.id,
            rows=data.get("places"),
        )
    if "pricingLines" in data or "lines" in data:
        from app.modules.master_data.service import resolve_reference_id

        priced = data.get("pricingLines") if "pricingLines" in data else data.get("lines")
        data["pricingLines"] = validate_line_items(priced, PRICING_LINE_SCHEMA, field="pricingLines")
        await session.execute(delete(QuotationRevisionLine).where(QuotationRevisionLine.quotation_revision_id == revision.id))
        priced_subtotal = Decimal("0")
        priced_discount = Decimal("0")
        priced_tax = Decimal("0")
        priced_total = Decimal("0")
        for index, line in enumerate(data.get("pricingLines") or []):
            from app.core.validation import parse_decimal

            unit_value = line.get("unitPrice")
            if unit_value in (None, ""):
                unit_value = line.get("unitAmount")
            quantity = parse_decimal(line.get("quantity"), f"pricingLines.{index}.quantity", Decimal("1"), places=3)
            unit_price = parse_decimal(unit_value, f"pricingLines.{index}.unitPrice", Decimal("0"), places=4)
            discount = _money(parse_decimal(
                line.get("discountAmount") if line.get("discountAmount") is not None else line.get("discount"),
                f"pricingLines.{index}.discount",
                Decimal("0"),
                places=4,
            ))
            subtotal = _money(quantity * unit_price)
            taxable = max(Decimal("0"), subtotal - discount)
            rate_value = line.get("taxRate")
            if rate_value not in (None, ""):
                # A per-line rate (Additional Details) is authoritative: the
                # server derives the tax amount rather than trusting the browser.
                tax_rate = parse_decimal(
                    rate_value, f"pricingLines.{index}.taxRate", Decimal("0"), places=4
                )
                tax = _money(taxable * tax_rate / Decimal("100"))
            else:
                tax = _money(parse_decimal(
                    line.get("taxAmount") if line.get("taxAmount") is not None else line.get("tax"),
                    f"pricingLines.{index}.tax",
                    Decimal("0"),
                    places=4,
                ))
                tax_rate = (tax / taxable * Decimal("100")) if taxable > 0 else Decimal("0")
            transport_by = await _resolve_transport_by(session, line.get("transportBy"))
            line_errors: dict[str, str] = {}
            if quantity <= 0:
                line_errors[f"pricingLines.{index}.quantity"] = "Must be greater than zero."
            if unit_price < 0:
                line_errors[f"pricingLines.{index}.unitPrice"] = "Cannot be negative."
            if discount < 0 or discount > subtotal:
                line_errors[f"pricingLines.{index}.discount"] = "Must be between zero and the line subtotal."
            if tax < 0:
                line_errors[f"pricingLines.{index}.tax"] = "Cannot be negative."
            if tax_rate < 0 or tax_rate > 100:
                line_errors[f"pricingLines.{index}.taxRate"] = "Must be between 0 and 100."
            if line.get("transportBy") not in (None, "") and transport_by is None:
                line_errors[f"pricingLines.{index}.transportBy"] = "Choose a valid transport type."
            if line_errors:
                raise ValidationFailed("Please correct the quotation lines.", line_errors)
            if transport_by is not None:
                # Persist the canonical id so a later rename changes only the label.
                line["transportBy"] = transport_by
            # Commercial totals are derived, not copied from the browser.
            total = _money(subtotal - discount + tax)
            priced_subtotal += subtotal
            priced_discount += discount
            priced_tax += tax
            priced_total += total
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
                    tax_rate=tax_rate,
                    line_subtotal=subtotal,
                    line_discount=discount,
                    line_tax=tax,
                    line_total=total,
                )
            )
        # The revision header is a roll-up of its priced lines. A partial save
        # that did not submit pricing lines keeps the stored totals.
        revision.subtotal_amount = _money(priced_subtotal)
        revision.discount_amount = _money(priced_discount)
        revision.tax_amount = _money(priced_tax)
        revision.total_amount = _money(priced_total)
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
    from app.core.users import user_display_names
    from app.modules.quotations.models import QuotationRevision

    # The list shows who created the quotation (first revision), not who authored
    # the latest revision; an edit must not change creator attribution.
    first_creators = dict(
        (
            await session.execute(
                select(QuotationRevision.quotation_id, QuotationRevision.created_by_user_id)
                .where(
                    QuotationRevision.quotation_id.in_([row.id for row in rows]),
                    QuotationRevision.revision_no == 1,
                )
            )
        ).all()
    )
    creator_names = await user_display_names(session, first_creators.values())
    items = []
    for quotation in rows:
        revision = latest_revisions.get(quotation.id)
        record = quotation_record(quotation, revision, quotation.data or {}, conversions.get(quotation.id))
        if not record.get("customer"):
            record["customer"] = party_names.get(quotation.customer_party_id)
        record["createdBy"] = creator_names.get(first_creators.get(quotation.id))
        items.append(record)
    return paged(items, page, total)


async def get_quotation(session: AsyncSession, context: RequestContext, quotation_id: int) -> dict:
    quotation = await session.get(Quotation, quotation_id)
    if quotation is None:
        raise NotFound("Quotation not found.")
    revision = await get_latest_revision(session, quotation)
    conversions = await _conversions_for(session, [quotation.id])
    record = quotation_record(quotation, revision, quotation.data or {}, conversions.get(quotation.id))
    if revision is not None:
        from sqlalchemy import select as _select

        from app.core.users import user_display_names
        from app.modules.quotations.models import QuotationRevision

        first_creator = (
            await session.execute(
                _select(QuotationRevision.created_by_user_id).where(
                    QuotationRevision.quotation_id == quotation.id,
                    QuotationRevision.revision_no == 1,
                )
            )
        ).scalar_one_or_none()
        names = await user_display_names(session, [first_creator])
        record["createdBy"] = names.get(first_creator)
    if revision is not None:
        route = await revision_route_payloads(session, revision.id)
        if route:
            record["places"] = route
        elif isinstance(record.get("places"), list):
            # A revision saved before route rows existed keeps its route in the
            # JSON copy; normalize the old single date column for the table.
            record["places"] = [
                {**row, "planned": row.get("planned") or row.get("plannedActual") or ""}
                for row in record["places"]
                if isinstance(row, dict)
            ]
    if not record.get("customer") and quotation.customer_party_id:
        party_names = await _party_names(session, [quotation.customer_party_id])
        record["customer"] = party_names.get(quotation.customer_party_id)
    return record


async def save_quotation(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    default_currency = await get_default_currency(session)
    data = QUOTATION_WRITE_SCHEMA.validate(
        data,
        partial=bool(data.get("id") or data.get("quotationId")),
    )
    quotation_id = data.get("id") or data.get("quotationId")
    quotation: Quotation | None = None
    if quotation_id and str(quotation_id).isdigit():
        quotation = await session.get(Quotation, int(quotation_id))

    if quotation is None:
        if _date(data.get("date")) is None and _date(data.get("quotationDate")) is None:
            raise ValidationFailed("A quotation date is required.", {"date": "Required"})
        party_id = data.get("customerPartyId")
        customer_name = str(data.get("customer") or "").strip()
        # A quotation must be attributable. The free-text name is accepted for
        # older clients and resolves/creates a party; neither is optional.
        if party_id in (None, "") and not customer_name:
            raise ValidationFailed(
                "A business party is required.",
                {"customerPartyId": "Required"},
            )
        if not str(data.get("direction") or "").strip():
            raise ValidationFailed(
                "A trade direction is required.",
                {"direction": "Required"},
            )
        party = (
            await resolve_party_by_id(session, party_id)
            if party_id not in (None, "")
            else await resolve_party_by_name(session, customer_name, context)
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
    if latest.valid_until is not None and latest.quotation_date is not None and latest.valid_until < latest.quotation_date:
        raise ValidationFailed(
            "Valid until cannot be earlier than the quotation date.",
            {"validUntil": "Cannot be earlier than the quotation date."},
        )
    await _save_revision_children(session, latest, data)

    payload = {key: value for key, value in data.items() if key not in {"id", "quotationId", "createdAt", "updatedAt"}}
    if "pricingLines" in data or "lines" in data:
        # The roll-up is authoritative; never echo a browser-computed total.
        payload.update({
            "subtotal": float(latest.subtotal_amount or 0),
            "discount": float(latest.discount_amount or 0),
            "tax": float(latest.tax_amount or 0),
            "total": float(latest.total_amount or 0),
            "amount": float(latest.total_amount or 0),
        })
    if party is not None and not str(payload.get("customer") or "").strip():
        # Fall back to the linked party's legal name only when the operator did
        # not type a company name of their own; a hand-entered name is the
        # record and must survive the party lookup.
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
    for place in (
        await session.execute(
            select(QuotationRevisionPlace)
            .where(QuotationRevisionPlace.quotation_revision_id == source.id)
            .order_by(QuotationRevisionPlace.sequence_no, QuotationRevisionPlace.id)
        )
    ).scalars().all():
        session.add(
            QuotationRevisionPlace(
                quotation_revision_id=clone.id,
                place_role_id=place.place_role_id,
                place_role=place.place_role,
                sequence_no=place.sequence_no,
                planned_at=place.planned_at,
                free_text=place.free_text,
                notes=place.notes,
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
    data = QUOTATION_WRITE_SCHEMA.validate(data, partial=True)
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


async def _conversion_by_key(session: AsyncSession, idempotency_key: str) -> QuotationConversion | None:
    return (
        await session.execute(select(QuotationConversion).where(QuotationConversion.idempotency_key == idempotency_key))
    ).scalars().first()


async def _conversion_payload(session: AsyncSession, conversion: QuotationConversion) -> dict:
    """The response a retried conversion returns: the order it already created."""

    from app.modules.operations.models import ServiceOrder

    quotation, revision = await _revision_with_quotation(session, conversion.quotation_revision_id)
    order = await session.get(ServiceOrder, conversion.service_order_id)
    payload = quotation_record(quotation, revision, quotation.data or {})
    payload["serviceOrderId"] = str(conversion.service_order_id)
    payload["serviceOrderNo"] = order.service_order_no if order is not None else ""
    return payload


async def convert_revision(
    session: AsyncSession, context: RequestContext, revision_id: int, idempotency_key: str | None = None
) -> dict:
    from app.modules.operations.service import create_service_order_from_quotation

    if idempotency_key:
        # A retry of the same request is a replay, not a second conversion.
        replay = await _conversion_by_key(session, idempotency_key)
        if replay is not None:
            return await _conversion_payload(session, replay)

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
            idempotency_key=idempotency_key,
        )
    )
    revision.status = "CONVERTED"
    quotation.status = "CONVERTED"
    try:
        await session.commit()
    except IntegrityError:
        # A concurrent request won the unique constraint on the revision, the
        # order or the idempotency key. Roll the whole posting back so no second
        # service order survives. A retry that carries the winning key is a
        # replay and gets the original order; anything else is a real duplicate.
        await session.rollback()
        if idempotency_key:
            replay = await _conversion_by_key(session, idempotency_key)
            if replay is not None:
                return await _conversion_payload(session, replay)
        raise Conflict("DUPLICATE_CONVERSION", "This quotation was already converted to a service order.") from None
    await cache.bump("reports")
    payload = quotation_record(quotation, revision, quotation.data or {})
    payload["serviceOrderId"] = str(service_order.id)
    payload["serviceOrderNo"] = service_order.service_order_no
    return payload


async def create_quotation_from_service_order(
    session: AsyncSession, context: RequestContext, identifier: str | int
) -> dict:
    """Re-quotation: a new draft quotation copied from an existing service order.

    The order is the source only. Nothing on it, on its pricing or on the order
    it was itself converted from is modified, so confirmed prices and posted
    financial history stay untouched. The new quotation records
    ``source_service_order_id`` so the offer traces back to the job.
    """
    from app.modules.operations.models import (
        ServiceOrderContainerRequirement,
        ServiceOrderPlace,
        ServiceOrderPricing,
        ServiceOrderPricingLine,
    )
    from app.modules.operations.service import resolve_order

    order = await resolve_order(session, context, identifier)
    direction = await session.get(TradeDirection, order.trade_direction_id)
    if direction is None:
        raise ValidationFailed("The service order has no trade direction.", {"direction": "Required"})

    pricing = (
        await session.execute(select(ServiceOrderPricing).where(ServiceOrderPricing.service_order_id == order.id))
    ).scalars().first()
    stops = (
        await session.execute(
            select(ServiceOrderPlace)
            .where(ServiceOrderPlace.service_order_id == order.id)
            .order_by(ServiceOrderPlace.sequence_no, ServiceOrderPlace.id)
        )
    ).scalars().all()
    requirements = (
        await session.execute(
            select(ServiceOrderContainerRequirement).where(ServiceOrderContainerRequirement.service_order_id == order.id)
        )
    ).scalars().all()
    priced_lines = []
    if pricing is not None:
        priced_lines = (
            await session.execute(
                select(ServiceOrderPricingLine)
                .where(ServiceOrderPricingLine.service_order_pricing_id == pricing.id)
                .order_by(ServiceOrderPricingLine.line_no, ServiceOrderPricingLine.id)
            )
        ).scalars().all()

    record = await save_quotation(
        session,
        context,
        {
            "customerPartyId": str(order.customer_party_id),
            "direction": direction.code or direction.name,
            "date": date.today().isoformat(),
            "currency": (pricing.currency_code if pricing is not None else order.currency_code)
            or await get_default_currency(session),
            "description": order.description,
            "status": "DRAFT",
            "places": [
                {
                    key: value
                    for key, value in route_stop_payload(
                        sequence=index + 1,
                        place_role_id=stop.place_role_id,
                        place_role=stop.place_role,
                        place=stop.free_text,
                        planned_at=stop.planned_at,
                        notes=stop.notes,
                    ).items()
                    if value not in (None, "")
                }
                for index, stop in enumerate(stops)
            ],
            "containerRequirements": [
                {
                    "containerTypeId": str(requirement.container_type_id),
                    "quantity": str(requirement.quantity or 0),
                    "grossWeightKg": str(requirement.gross_weight_kg)
                    if requirement.gross_weight_kg is not None
                    else None,
                    "remarks": requirement.remarks,
                }
                for requirement in requirements
            ],
            # The stored line discount is an amount; the tax amount is derived
            # from the stored total, so a re-quotation reproduces the same money
            # whether the source line recorded a rate or an amount.
            "pricingLines": [
                {
                    "feeTypeId": str(line.fee_type_id) if line.fee_type_id else None,
                    "description": line.description,
                    "quantity": str(line.quantity or 0),
                    "unit": line.unit_code,
                    "unitPrice": str(line.unit_price or 0),
                    "discount": str(line.discount_rate or 0),
                    "tax": str(max(
                        Decimal("0"),
                        (line.line_total or Decimal("0"))
                        - ((line.quantity or Decimal("0")) * (line.unit_price or Decimal("0")) - (line.discount_rate or Decimal("0"))),
                    )),
                }
                for line in priced_lines
            ],
        },
    )

    quotation = await session.get(Quotation, int(record["id"]))
    if quotation is not None:
        quotation.source_service_order_id = order.id
        await session.commit()
    record["sourceServiceOrderId"] = str(order.id)
    record["sourceServiceOrderNo"] = order.service_order_no
    return record


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

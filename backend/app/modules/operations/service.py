from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
import zipfile
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.config import settings
from app.core.context import RequestContext
from app.core.database import utcnow
from app.core.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, list_sort_orders, paged
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.modules.master_data import config_versions
from app.modules.master_data.models import BusinessParty
from app.modules.master_data.route_stops import (
    route_stop_payloads,
    save_route_stops,
)
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
from app.modules.operations.schemas import (
    CHARGE_DOCUMENT_TYPES,
    CHARGE_LINE_SCHEMA,
    CHARGE_WRITE_SCHEMA,
    CONTAINER_WRITE_SCHEMA,
    MILESTONE_STATUSES,
    MILESTONE_WRITE_SCHEMA,
    MOVEMENT_STATUSES,
    MOVEMENT_WRITE_SCHEMA,
    SERVICE_ORDER_WRITE_SCHEMA,
)
from app.modules.quotations.models import (
    Quotation,
    QuotationConversion,
    QuotationRevision,
    QuotationRevisionContainer,
    QuotationRevisionLine,
    QuotationRevisionPlace,
)
from app.modules.settings.service import get_default_currency

logger = logging.getLogger(__name__)

ORDER_STATUS = {
    "active": "ACTIVE",
    "inactive": "INACTIVE",
    "finished": "FINISHED",
    "completed": "FINISHED",
    "complete": "FINISHED",
}

# Legacy lifecycle statuses from before the Active/Inactive simplification.
_LEGACY_INACTIVE = {"cancelled", "canceled", "closed", "inactive", "voided"}


def _ensure_order_editing(order: ServiceOrder) -> None:
    """Finish locks operational editing; financial settlement continues separately."""
    if order.status == "FINISHED":
        raise Conflict(
            "ORDER_FINISHED",
            "A finished service order is locked. Reopen it before editing operations.",
        )


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
            # "Started" is the creation stamp (set once, never edited); "Ended"
            # is the Finish stamp, empty until the order is finished.
            "startedAt": order.created_at.isoformat() if order.created_at else None,
            "finishedAt": order.finished_at.isoformat() if order.finished_at else None,
            "endedAt": order.finished_at.isoformat() if order.finished_at else None,
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
    order_ids = [row.id for row in rows]
    containers: list[ServiceOrderContainer] = []
    requirements: list[ServiceOrderContainerRequirement] = []
    if order_ids:
        containers = list(
            (
                await session.execute(
                    select(ServiceOrderContainer)
                    .where(ServiceOrderContainer.service_order_id.in_(order_ids))
                    .order_by(ServiceOrderContainer.id)
                )
            ).scalars().all()
        )
        requirements = list(
            (
                await session.execute(
                    select(ServiceOrderContainerRequirement)
                    .where(ServiceOrderContainerRequirement.service_order_id.in_(order_ids))
                    .order_by(ServiceOrderContainerRequirement.id)
                )
            ).scalars().all()
        )
    labels = await _container_type_labels(
        session,
        {int(c.container_type_id) for c in containers} | {int(r.container_type_id) for r in requirements},
    )
    containers_by_order: dict[int, list[dict[str, Any]]] = {}
    for container in containers:
        containers_by_order.setdefault(container.service_order_id, []).append(
            _container_payload(container, labels.get(int(container.container_type_id)))
        )
    requirements_by_order: dict[int, list[dict[str, Any]]] = {}
    for requirement in requirements:
        requirements_by_order.setdefault(requirement.service_order_id, []).append(
            _requirement_payload(requirement, labels.get(int(requirement.container_type_id)))
        )
    links = (
        await session.execute(
            select(Attachment, AttachmentLink.entity_id)
            .join(AttachmentLink, AttachmentLink.attachment_id == Attachment.id)
            .where(
                AttachmentLink.entity_type == "jobs",
                AttachmentLink.entity_id.in_(order_ids),
                Attachment.is_deleted.is_(False),
            )
            .order_by(Attachment.id)
        )
    ).all() if order_ids else []
    files_by_order: dict[int, list[dict[str, Any]]] = {}
    for attachment, order_id in links:
        payload = await _attachment_payload_async(session, attachment)
        files_by_order.setdefault(int(order_id), []).append(payload)
    revision_ids = [row.quotation_revision_id for row in rows if row.quotation_revision_id]
    quotations: dict[int, tuple[str, str]] = {}
    if revision_ids:
        quotations = {
            revision_id: (str(quotation_id), quotation_no)
            for revision_id, quotation_id, quotation_no in (
                await session.execute(
                    select(QuotationRevision.id, Quotation.id, Quotation.quotation_no)
                    .join(Quotation, Quotation.id == QuotationRevision.quotation_id)
                    .where(QuotationRevision.id.in_(revision_ids))
                )
            ).all()
        }
    records = []
    from app.core.users import user_display_names

    creator_names = await user_display_names(session, (row.created_by_user_id for row in rows))
    for row in rows:
        extra: dict[str, Any] = {"createdBy": creator_names.get(row.created_by_user_id)}
        if row.quotation_revision_id:
            quotation = quotations.get(row.quotation_revision_id)
            if quotation:
                extra["quotationId"], extra["quotationNo"] = quotation
        # Database rows win when they exist, but an order created before the rows
        # were exposed keeps its legacy JSON copy instead of appearing empty.
        containers_for_order = containers_by_order.get(row.id)
        if containers_for_order:
            extra["actualContainers"] = containers_for_order
        requirements_for_order = requirements_by_order.get(row.id)
        if requirements_for_order:
            extra["containerRequirements"] = requirements_for_order
        # The Files grid reads the linked uploads, never a payload copy race.
        extra["attachments"] = files_by_order.get(row.id, [])
        records.append(order_record(row, row.data or {}, extra))
    return paged(records, page, total)


async def order_route_payloads(session: AsyncSession, order_id: int) -> list[dict[str, Any]]:
    """The saved route stops of a service order, ordered by sequence."""
    rows = list(
        (
            await session.execute(
                select(ServiceOrderPlace)
                .where(ServiceOrderPlace.service_order_id == order_id)
                .order_by(ServiceOrderPlace.sequence_no, ServiceOrderPlace.id)
            )
        ).scalars().all()
    )
    return await route_stop_payloads(session, rows)


async def get_service_order(session: AsyncSession, context: RequestContext, identifier: str) -> dict:
    order = await resolve_order(session, context, identifier)
    containers, requirements = await OperationsRepository(session).order_containers(order.id)
    route = await order_route_payloads(session, order.id)
    labels = await _container_type_labels(
        session,
        {int(c.container_type_id) for c in containers} | {int(r.container_type_id) for r in requirements},
    )
    container_payloads = [_container_payload(c, labels.get(int(c.container_type_id))) for c in containers]
    extra: dict[str, Any] = {"components": []}
    if container_payloads:
        # Prepared or numbered rows are authoritative once they exist; an order
        # without rows keeps whatever JSON copy it was created with.
        extra["containers"] = container_payloads
        extra["actualContainers"] = container_payloads
    if requirements:
        extra["containerRequirements"] = [
            _requirement_payload(r, labels.get(int(r.container_type_id))) for r in requirements
        ]
    if route:
        extra["places"] = route
    # Linked files are authoritative for the Files grid: they always exist once
    # uploaded (the attachment API links them), while the payload's JSON copy
    # races the save that stores it.
    extra["attachments"] = await list_attachments(session, context, "jobs", str(order.id))
    # The quote link must survive a deep link or refresh: the workspace derives
    # its container payment rows from the source quotation (same as the list).
    if order.quotation_revision_id:
        link = (
            await session.execute(
                select(QuotationRevision.id, Quotation.id, Quotation.quotation_no)
                .join(Quotation, Quotation.id == QuotationRevision.quotation_id)
                .where(QuotationRevision.id == order.quotation_revision_id)
            )
        ).first()
        if link:
            extra["quotationId"], extra["quotationNo"] = str(link[1]), link[2]
    return order_record(order, order.data or {}, extra)


async def _resolve_party(session: AsyncSession, name: str | None, context: RequestContext) -> BusinessParty:
    from app.modules.quotations.service import resolve_party_by_name

    return await resolve_party_by_name(session, name, context)


async def save_service_order(
    session: AsyncSession, context: RequestContext, data: dict[str, Any], idempotency_key: str | None = None
) -> dict:
    default_currency = await get_default_currency(session)
    from app.modules.master_data.currency_rates import assert_currency_code
    from app.modules.quotations.service import resolve_direction

    # A currency is a reference to an active master record, not free text: an
    # archived or malformed code must be refused where the operator can see it.
    if data.get("currency") not in (None, ""):
        data["currency"] = await assert_currency_code(session, data["currency"], "currency")

    date_errors = {
        key: "Enter a valid date."
        for key in ("date", "validUntil", "pickupDate", "deliveryDate")
        if data.get(key) not in (None, "") and _date(data.get(key)) is None
    }
    if date_errors:
        raise ValidationFailed("Please correct the service order dates.", date_errors)
    starts_on = _date(data.get("date"))
    valid_until = _date(data.get("validUntil"))
    if starts_on and valid_until and valid_until < starts_on:
        raise ValidationFailed(
            "The valid-until date cannot precede the order date.",
            {"validUntil": "Cannot be before the order date."},
        )

    identifier = data.get("id") or data.get("serviceOrderId") or data.get("jobNo")
    # Types, lengths and dates first; a partial save only checks the keys it was
    # sent, so an untouched required field is never re-required. The dynamic
    # fields of the Service Order form are intentionally preserved.
    data = SERVICE_ORDER_WRITE_SCHEMA.validate(data, partial=bool(identifier))
    order: ServiceOrder | None = None
    if identifier:
        try:
            order = await resolve_order(session, context, identifier)
        except NotFound:
            order = None
    is_new_order = order is None
    quotation: Quotation | None = None
    if is_new_order:
        # A replayed create request is answered with the order it already made,
        # so a network retry never produces a second copy of the booking.
        quotation_id = data.get("quotationId") or data.get("quotation_id")
        # Manual Service Order creation is retired: every order originates from
        # a quotation, and a create request without one is refused here so the
        # API cannot be used to bypass the conversion workflow.
        if quotation_id in (None, ""):
            raise ValidationFailed(
                "Service Orders must be created from a quotation.",
                {"quotationId": "Convert a quotation to create a Service Order."},
            )
        if idempotency_key:
            replay = (
                await session.execute(
                    select(QuotationConversion).where(QuotationConversion.idempotency_key == idempotency_key)
                )
            ).scalars().first()
            if replay is not None:
                existing = await session.get(ServiceOrder, replay.service_order_id)
                if existing is not None:
                    return order_record(existing, existing.data or {})
        # The quotation prefills the reusable commercial data; anything the
        # caller typed explicitly (party, direction, currency, description)
        # wins below, so the prefilled order form stays editable.
        try:
            numeric_quotation_id = int(str(quotation_id))
        except (TypeError, ValueError) as exc:
            raise ValidationFailed(
                "The selected quotation is invalid.",
                {"quotationId": "Invalid quotation."},
            ) from exc
        quotation = await session.get(Quotation, numeric_quotation_id)
        if quotation is None:
            raise ValidationFailed("The selected quotation does not exist.", {"quotationId": "Unknown quotation."})
        from app.modules.quotations.service import get_latest_revision

        revision = await get_latest_revision(session, quotation)
        if revision is None:
            raise ValidationFailed(
                "The selected quotation has no revision to copy.",
                {"quotationId": "No revision."},
            )
        # Party: an explicit picker id wins, then the quotation's party, then a
        # typed company name. A service order always names one party.
        if data.get("customerPartyId") not in (None, ""):
            from app.modules.quotations.service import resolve_party_by_id

            party_id = (await resolve_party_by_id(session, data.get("customerPartyId"))).id
        elif quotation is not None:
            party_id = quotation.customer_party_id
        elif str(data.get("customer") or "").strip():
            party_id = (await _resolve_party(session, data.get("customer"), context)).id
        else:
            raise ValidationFailed(
                "A business party is required for a service order.",
                {"customerPartyId": "Required"},
            )
        if data.get("direction") not in (None, ""):
            direction_id = (await resolve_direction(session, data.get("direction"))).id
        elif quotation is not None:
            direction_id = quotation.trade_direction_id
        else:
            raise ValidationFailed(
                "A trade direction is required for a service order.",
                {"direction": "Required"},
            )
        number = data.get("jobNo") or data.get("serviceOrderNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, "SERVICE_ORDER")
        order = ServiceOrder(
            service_order_no=str(number),
            quotation_revision_id=revision.id if revision is not None else None,
            customer_party_id=party_id,
            trade_direction_id=direction_id,
            status=normalize_order_status(data.get("status"), "ACTIVE"),
            currency_code=data.get("currency") or (revision.currency_code if revision is not None else None) or default_currency,
            description=data.get("description") or (revision.description if revision is not None else None),
            created_by_user_id=context.user_id,
            data=dict(quotation.data or {}) if quotation is not None else {},
        )
        session.add(order)
        await session.flush()
        if quotation is not None and revision is not None:
            await _attach_quotation_copy(session, order, quotation, revision)
        # Every new order is recorded in the ledger so a retried create is
        # answered with the order it already made.
        session.add(
            QuotationConversion(
                quotation_revision_id=revision.id,
                service_order_id=order.id,
                converted_by_user_id=context.user_id,
                idempotency_key=idempotency_key,
            )
        )
    else:
        _ensure_order_editing(order)
        # Only reassign when the caller actually supplied the field, otherwise a
        # partial save would silently repoint the order at another party/direction.
        if "customer" in data:
            order.customer_party_id = (await _resolve_party(session, data.get("customer"), context)).id
        if "direction" in data:
            order.trade_direction_id = (await resolve_direction(session, data.get("direction"))).id
        order.status = normalize_order_status(data.get("status"), order.status)
        requested_currency = str(data.get("currency") or "").strip().upper()
        if requested_currency and requested_currency != str(order.currency_code or "").upper():
            await _assert_order_currency_changeable(session, order, requested_currency)
            from app.modules.master_data.currency_rates import assert_currency_code

            order.currency_code = await assert_currency_code(session, requested_currency, "currency")

    # A brand-new quotation-based order arrives with the UI's empty route
    # collections; the server-side copy is authoritative, so a blank list must
    # not wipe the stops or payment rows it just generated.
    if quotation is not None:
        if not data.get("places"):
            data.pop("places", None)
        if not data.get("containerPayments"):
            data.pop("containerPayments", None)
    if "places" in data:
        # Route stops are their own collection, not arbitrary header JSON: this
        # keeps them queryable and lets the quotation copy populate them. Row
        # ids are preserved, so an existing row keeps an inactive reference.
        data["places"] = await save_route_stops(
            session,
            model=ServiceOrderPlace,
            parent_field="service_order_id",
            parent_id=order.id,
            rows=data.get("places"),
        )

    payload = {key: value for key, value in data.items() if key not in {"id", "createdAt", "updatedAt", "quotationId", "quotation_id"}}
    # Merge so a partial update does not discard previously stored fields.
    order.data = jsonable({**(order.data or {}), **payload})
    if not str((order.data or {}).get("customer") or "").strip() and order.customer_party_id:
        stored = await session.get(BusinessParty, int(order.customer_party_id))
        if stored is not None:
            order.data = jsonable({**(order.data or {}), "customer": stored.legal_name})
    from app.modules.telegram.producers import service_order_notification

    # Transactional outbox: the notification commits with the order itself, so
    # a Telegram outage can never fail a booking and a replay cannot double-send.
    await service_order_notification(
        session, order,
        "SERVICE_ORDER_CREATED" if is_new_order else "SERVICE_ORDER_UPDATED",
    )
    try:
        await session.commit()
    except IntegrityError:
        # Two racing creates carrying the same idempotency key: the loser rolls
        # back and answers with the winning request's order instead of a 500.
        await session.rollback()
        if idempotency_key:
            replay = (
                await session.execute(
                    select(QuotationConversion).where(QuotationConversion.idempotency_key == idempotency_key)
                )
            ).scalars().first()
            if replay is not None:
                existing = await session.get(ServiceOrder, replay.service_order_id)
                if existing is not None:
                    return order_record(existing, existing.data or {})
        raise
    await cache.bump("reports")
    extra: dict[str, Any] | None = None
    if order.quotation_revision_id:
        link = (
            await session.execute(
                select(QuotationRevision.id, Quotation.id, Quotation.quotation_no)
                .join(Quotation, Quotation.id == QuotationRevision.quotation_id)
                .where(QuotationRevision.id == order.quotation_revision_id)
            )
        ).first()
        if link:
            extra = {"quotationId": str(link[1]), "quotationNo": link[2]}
    return order_record(order, order.data or {}, extra)


async def finish_service_order(session: AsyncSession, context: RequestContext, identifier: str) -> dict:
    """Mark a service order as finished (idempotent).

    Operational editing locks from this point; invoices, payments and the
    accounting trail continue on the order without needing full settlement.
    """
    order = await resolve_order(session, context, identifier)
    if order.status == "INACTIVE":
        raise InvalidState("Cannot finish an inactive service order.")
    if order.status != "FINISHED":
        order.status = "FINISHED"
        order.finished_at = utcnow()
        order.finished_by_user_id = context.user_id
        from app.modules.telegram.producers import service_order_notification

        await service_order_notification(session, order, "SERVICE_ORDER_FINISHED")
        await session.commit()
        await cache.bump("reports")
    payload = order_record(order, order.data or {})
    # Financial drafts belong to the approved Finish workflow, never to an
    # ordinary operational save. A document failure must not undo the finish.
    try:
        from app.modules.finance.order_documents import refresh_service_order_financial_documents

        payload["financialDocuments"] = await refresh_service_order_financial_documents(
            session, context, order
        )
    except Exception as failure:  # noqa: BLE001
        # Leave a clean session for the router's audit/status write.
        await session.rollback()
        payload["financialDocumentWarnings"] = [
            f"Financial drafts were not refreshed: {failure}"
        ]
    return payload


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
    # Leaving FINISHED (reopen) keeps the order editable again but clears the
    # Ended stamp: it is empty while the order is not finished, and a new Finish
    # writes a fresh one.
    if order.status == "FINISHED" and normalize_order_status(status, order.status) != "FINISHED":
        order.finished_at = None
        order.finished_by_user_id = None
    previous = str(order.status)
    next_status = normalize_order_status(status, order.status)
    order.status = next_status
    if previous != next_status:
        from app.modules.telegram.producers import service_order_notification

        await service_order_notification(
            session,
            order,
            "SERVICE_ORDER_CANCELLED" if next_status == "INACTIVE" else "SERVICE_ORDER_STATUS_CHANGED",
        )
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

    if before == "ISSUED":
        # An idempotent re-issue is answered with the same state; only the
        # DRAFT → ISSUED transition leaves one audit event.
        return
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
    # An order that already has financial history stays an auditable record;
    # refusing with a clean conflict here keeps the FK violation out of the 500 path.
    from app.modules.finance.models import FinancialDocument, JournalEntryLine

    financed = (
        await session.execute(
            select(FinancialDocument.service_order_id).where(FinancialDocument.service_order_id.in_(ids)).distinct()
        )
    ).scalars().all()
    if financed:
        raise Conflict(
            "ORDER_HAS_FINANCIAL_DOCUMENTS",
            "Service orders with financial documents cannot be deleted. Delete the documents first.",
        )
    journaled = (
        await session.execute(
            select(JournalEntryLine.service_order_id).where(JournalEntryLine.service_order_id.in_(ids)).distinct()
        )
    ).scalars().all()
    if journaled:
        raise Conflict(
            "ORDER_HAS_JOURNAL_ENTRIES",
            "Service orders with posted journal entries cannot be deleted. Keep the order for audit history.",
        )
    charged = (
        await session.execute(
            select(ServiceOrderCharge.service_order_id).where(ServiceOrderCharge.service_order_id.in_(ids)).distinct()
        )
    ).scalars().all()
    if charged:
        raise Conflict(
            "ORDER_HAS_SERVICE_CHARGES",
            "Service orders with service charges cannot be deleted. Delete the charges first.",
        )
    # The conversion ledger row records which order this quotation revision
    # produced. It is cleared with the order in this same transaction (the
    # quotation itself stays; a deleted order must not leave a dangling
    # conversion row, and the RESTRICT FK then never fires at database level).
    from sqlalchemy import delete as sql_delete

    from app.modules.quotations.models import QuotationConversion

    await session.execute(
        sql_delete(QuotationConversion).where(QuotationConversion.service_order_id.in_(ids))
    )
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
    order = ServiceOrder(
        service_order_no=number,
        quotation_revision_id=revision.id,
        customer_party_id=quotation.customer_party_id,
        trade_direction_id=quotation.trade_direction_id,
        status="ACTIVE",
        currency_code=revision.currency_code or default_currency,
        description=revision.description,
        created_by_user_id=context.user_id,
        data=dict(quotation.data or {}),
    )
    session.add(order)
    await session.flush()
    await _attach_quotation_copy(session, order, quotation, revision)
    return order


async def _assert_order_currency_changeable(
    session: AsyncSession, order: ServiceOrder, requested_currency: str
) -> None:
    """Document currency may only change before anything is priced against it.

    A Service Order inherits its quotation's currency. Once charges or financial
    documents exist they carry their own currency snapshot, so re-denominating
    the order would silently mix currencies in one settlement chain. A correction
    before that point stays allowed and is audited by the normal order update.
    """
    from app.modules.finance.models import FinancialDocument

    charge_count = await session.scalar(
        select(func.count()).select_from(ServiceOrderCharge).where(
            ServiceOrderCharge.service_order_id == order.id
        )
    )
    document_count = await session.scalar(
        select(func.count()).select_from(FinancialDocument).where(
            FinancialDocument.service_order_id == order.id
        )
    )
    if int(charge_count or 0) or int(document_count or 0):
        raise Conflict(
            "DOCUMENT_CURRENCY_LOCKED",
            (
                f"This service order is already priced in {order.currency_code}. "
                f"Remove its charges and financial documents before changing the currency to "
                f"{requested_currency}."
            ),
        )


async def _attach_quotation_copy(
    session: AsyncSession, order: ServiceOrder, quotation: Quotation, revision: QuotationRevision
) -> None:
    """Copy the quotation's reusable data into the order's own independent rows.

    Route stops, container requirements and pricing lines become rows the order
    owns — never shared pointers — so editing either document afterwards cannot
    change the other. Actual container numbers, invoices, payments and journal
    entries belong to this order alone and are never copied.
    """
    data = dict(order.data or {})
    # Pin the order to the configuration published when the quotation converts,
    # so a later publish cannot re-interpret its dynamic component rows.
    await config_versions.stamp_service_order(session, order)

    # Copy the quotation's route stops into the order's own rows. They are rows,
    # not a shared pointer, so both documents remain independently editable after
    # conversion.
    quotation_stops = list(
        (
            await session.execute(
                select(QuotationRevisionPlace)
                .where(QuotationRevisionPlace.quotation_revision_id == revision.id)
                .order_by(QuotationRevisionPlace.sequence_no, QuotationRevisionPlace.id)
            )
        ).scalars().all()
    )
    if quotation_stops:
        created: list[ServiceOrderPlace] = []
        for index, stop in enumerate(quotation_stops):
            row = ServiceOrderPlace(
                service_order_id=order.id,
                place_role_id=stop.place_role_id,
                place_role=stop.place_role,
                sequence_no=index + 1,
                planned_at=stop.planned_at,
                free_text=stop.free_text,
                notes=stop.notes,
            )
            session.add(row)
            created.append(row)
        await session.flush()
        # Prefer the order's own rows (and their ids) over the quotation copy.
        data["places"] = await route_stop_payloads(session, created)
        order.data = jsonable(data)
    else:
        # Legacy quotations predate `quotation_revision_places`; their route was
        # kept in the header keys. Preserve it as sequence-numbered stops.
        sequence = 0
        for role in ("pickup", "border", "delivery"):
            value = data.get(role)
            if value:
                sequence += 1
                session.add(
                    ServiceOrderPlace(
                        service_order_id=order.id,
                        place_role=role.upper(),
                        free_text=str(value),
                        sequence_no=sequence,
                    )
                )

    requirements = (
        await session.execute(
            select(QuotationRevisionContainer).where(QuotationRevisionContainer.quotation_revision_id == revision.id)
        )
    ).scalars().all()
    requirement_by_source: dict[int, ServiceOrderContainerRequirement] = {}
    prepared: list[ServiceOrderContainer] = []
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
        # One pending box per required unit: the number is entered when the box is
        # actually collected, so the row starts with no identifier rather than a
        # fabricated one. Every quotation reuse copies its own freshly prepared
        # rows, so reusing the same quotation never duplicates a box.
        # Pricing-line types and quantities are deliberately never turned into
        # rows here: a line's quantity is a billing unit count, not a box count.
        for _ in range(max(1, int(source.quantity or 1))):
            prepared.append(
                ServiceOrderContainer(
                    service_order_id=order.id,
                    container_requirement_id=requirement.id,
                    container_type_id=source.container_type_id,
                    container_number=None,
                    status="EXPECTED",
                    gross_weight_kg=source.gross_weight_kg,
                    data={
                        "sourceQuotationContainerId": str(source.id),
                        "prepared": True,
                    },
                )
            )
    if prepared:
        session.add_all(prepared)
        await session.flush()

    pricing = ServiceOrderPricing(
        service_order_id=order.id,
        currency_code=revision.currency_code or await get_default_currency(session),
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

    # Container payments: one row per quoted unit, generated once here at
    # conversion. The stored rows are authoritative from now on — page loads,
    # refreshes and later saves never regenerate or append them.
    if lines:
        from app.modules.master_data.models import FeeType

        fee_ids = {line.fee_type_id for line in lines if line.fee_type_id}
        fee_names = dict(
            (await session.execute(select(FeeType.id, FeeType.name).where(FeeType.id.in_(fee_ids)))).all()
        )
        payments = _expanded_container_payment_rows(lines, fee_names)
        if payments:
            order.data = jsonable({**(order.data or {}), "containerPayments": payments})


#: One container-payment row per quoted unit; beyond this a line keeps a single
#: billing-count row instead of exploding the order's JSON payload.
MAX_PAYMENT_ROWS_PER_LINE = 500


def _expanded_container_payment_rows(
    lines: Sequence[QuotationRevisionLine], fee_names: dict[int, str]
) -> list[dict[str, Any]]:
    """Container-payment rows for a converted order: one row per quoted unit.

    A whole-number Qty N becomes N rows of Qty 1 at the line's unit price, so
    the rows' sum equals the line's own subtotal before adjustments (discounts
    and tax stay sheet-level, exactly as the payment sheet applies them). A
    fractional quantity cannot be split into units and keeps the line's own
    single billing-count row — the existing handling for such charges — never
    silently rounded.
    """
    rows: list[dict[str, Any]] = []
    for line in lines:
        quantity = line.quantity or Decimal(0)
        unit_price = line.unit_price or Decimal(0)
        fee_name = fee_names.get(line.fee_type_id)
        base = {
            "feeType": fee_name,
            "containerNo": "",
            "serviceOrderContainerId": "",
            "description": line.service_description or fee_name,
            "unit": line.unit_code or "Container",
            "blNo": "",
            "truckNo": "",
            "note": "",
            # Traceability back to the quoted line; the row itself is the order's.
            "sourceQuotationLineId": str(line.id),
        }
        if quantity > 0 and quantity == quantity.to_integral_value() and quantity <= MAX_PAYMENT_ROWS_PER_LINE:
            unit = float(unit_price)
            for _ in range(int(quantity)):
                rows.append({
                    **base,
                    # One identity per row: a split line must not hand the same
                    # id to every unit, or editing one unit edits them all.
                    "id": uuid4().hex,
                    "quantity": 1,
                    "unitPrice": unit,
                    "discountAmount": 0,
                    "taxRate": 0,
                    "taxAmount": 0,
                    "lineSubtotal": unit,
                    "lineTotal": unit,
                    "amount": unit,
                })
        else:
            rows.append({
                **base,
                "id": uuid4().hex,
                "quantity": float(quantity),
                "unitPrice": float(unit_price),
                "discountAmount": float(line.line_discount or 0),
                "taxRate": float(line.tax_rate or 0),
                "taxAmount": float(line.line_tax or 0),
                "lineSubtotal": float(line.line_subtotal or 0),
                "lineTotal": float(line.line_total or 0),
                "amount": float(line.line_total or 0),
            })
    return rows


def _container_payload(container: ServiceOrderContainer, type_label: str | None = None) -> dict[str, Any]:
    payload = dict(container.data or {})
    payload.update(
        {
            "id": str(container.id),
            "serviceOrderId": str(container.service_order_id),
            "containerRequirementId": str(container.container_requirement_id) if container.container_requirement_id else None,
            "containerType": type_label or str(container.container_type_id),
            "containerTypeId": container.container_type_id,
            "containerNumber": container.container_number or "",
            "containerNo": container.container_number or "",
            "pending": not bool(container.container_number),
            "sealSerial": container.seal_serial,
            "sealNo": container.seal_serial,
            "status": container.status,
            "netWeightKg": float(container.net_weight_kg) if container.net_weight_kg is not None else None,
            "grossWeightKg": float(container.gross_weight_kg) if container.gross_weight_kg is not None else None,
            "pickupDate": container.pickup_date.isoformat() if container.pickup_date else None,
            "returnDate": container.return_date.isoformat() if container.return_date else None,
        }
    )
    return payload


def _requirement_payload(requirement: ServiceOrderContainerRequirement, type_label: str | None = None) -> dict[str, Any]:
    return {
        "id": str(requirement.id),
        "serviceOrderId": str(requirement.service_order_id),
        "containerTypeId": requirement.container_type_id,
        "containerType": type_label or str(requirement.container_type_id),
        "quantity": float(requirement.quantity or 0),
        "grossWeightKg": float(requirement.gross_weight_kg) if requirement.gross_weight_kg is not None else None,
        "description": requirement.description,
        "remarks": requirement.remarks,
    }


async def _container_type_labels(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    """Human label for each container type, so a pending row reads ``40HC`` not ``3``."""
    from app.modules.master_data.models import ContainerType

    if not ids:
        return {}
    rows = (
        await session.execute(select(ContainerType.id, ContainerType.code, ContainerType.name).where(ContainerType.id.in_(ids)))
    ).all()
    return {int(row[0]): str(row[1] or row[2] or row[0]) for row in rows}


async def list_containers(session: AsyncSession, context: RequestContext, identifier: str) -> list[dict]:
    order = await resolve_order(session, context, identifier)
    rows = (
        await session.execute(
            select(ServiceOrderContainer)
            .where(ServiceOrderContainer.service_order_id == order.id)
            .order_by(ServiceOrderContainer.id)
        )
    ).scalars().all()
    labels = await _container_type_labels(session, {int(row.container_type_id) for row in rows})
    return [_container_payload(row, labels.get(int(row.container_type_id))) for row in rows]


def _container_input(data: dict[str, Any], existing: ServiceOrderContainer | None) -> tuple[dict[str, str], str, Any, Any, date | None, date | None]:
    """Parse and validate one container row from add/update payloads.

    Accepts both camelCase form keys and the snake_case keys that survive in
    stored data blobs. Returns ``(errors, container_number, net_weight,
    gross_weight, pickup_date, return_date)``; ``errors`` non-empty aborts the
    caller. Kept separate from persistence so add_container stays readable.
    """
    from app.core.validation import parse_decimal

    errors: dict[str, str] = {}
    # A container identifier is an ISO 6346 code: stored and compared uppercase,
    # so "abcu1234567" and "ABCU1234567" are the same box on the same order.
    container_number = str(data.get("containerNumber") or data.get("container_number") or data.get("containerNo") or "").strip().upper()
    if not container_number:
        # Only a prepared row may stay unnumbered; a manually added box must be identified.
        if existing is None:
            errors["containerNumber"] = "This field is required."
    elif len(container_number) > 32:
        errors["containerNumber"] = "Use at most 32 characters."
    elif not all(char.isalnum() or char in " -_" for char in container_number):
        errors["containerNumber"] = "Use letters, digits, spaces, '-' or '_'."
    net_weight = parse_decimal(data.get("netWeightKg"), "netWeightKg")
    gross_weight = parse_decimal(data.get("grossWeightKg"), "grossWeightKg")
    if net_weight < 0:
        errors["netWeightKg"] = "Cannot be negative."
    if gross_weight < 0:
        errors["grossWeightKg"] = "Cannot be negative."
    if net_weight and gross_weight and gross_weight < net_weight:
        errors["grossWeightKg"] = "Cannot be less than the net weight."
    pickup_date = _date(data.get("pickupDate") or data.get("pickup_date"))
    return_date = _date(data.get("returnDate") or data.get("return_date"))
    if data.get("pickupDate") not in (None, "") and pickup_date is None:
        errors["pickupDate"] = "Enter a valid date."
    if data.get("returnDate") not in (None, "") and return_date is None:
        errors["returnDate"] = "Enter a valid date."
    if pickup_date and return_date and return_date < pickup_date:
        errors["returnDate"] = "Cannot be before the pickup date."
    return errors, container_number, net_weight, gross_weight, pickup_date, return_date


async def add_container(session: AsyncSession, context: RequestContext, identifier: str, data: dict[str, Any]) -> dict:
    """Create a container, or update the prepared row when ``id`` is supplied.

    A row prepared from a quotation requirement starts with no number; supplying
    the number later updates that same row instead of creating a second one.
    """
    order = await resolve_order(session, context, identifier)
    if order.status == "INACTIVE":
        raise InvalidState("Cannot add containers to an inactive service order.")
    _ensure_order_editing(order)
    data = CONTAINER_WRITE_SCHEMA.validate(data, partial=bool(data.get("id")))
    existing: ServiceOrderContainer | None = None
    container_id = _int_or_none(data.get("id"))
    if container_id is not None:
        existing = await session.get(ServiceOrderContainer, container_id)
        if existing is None or existing.service_order_id != order.id:
            raise NotFound("Container not found.")

    errors, container_number, net_weight, gross_weight, pickup_date, return_date = _container_input(data, existing)
    if errors:
        raise ValidationFailed("Please correct the container details.", errors)
    if container_number:
        clash = (
            await session.execute(
                select(ServiceOrderContainer).where(func.upper(ServiceOrderContainer.container_number) == container_number)
            )
        ).scalars().first()
        if clash is not None and (existing is None or clash.id != existing.id):
            raise Conflict("DUPLICATE_NUMBER", "Container number already exists.", {"containerNumber": "Already in use"})
    container_type_id = data.get("containerTypeId") or data.get("container_type_id")
    if not container_type_id and existing is not None:
        container_type_id = existing.container_type_id
    if not container_type_id:
        from app.modules.master_data.service import resolve_or_create_container_type

        container_type_id = await resolve_or_create_container_type(session, data.get("containerType"))
    if not container_type_id:
        raise ValidationFailed("Container type is required.", {"containerType": "Required"})
    from app.modules.master_data.models import ContainerType

    container_type = await session.get(ContainerType, int(container_type_id))
    if container_type is None:
        raise ValidationFailed("Container type is required.", {"containerType": "Choose a container type."})
    if str(container_type.status or "").upper() != "ACTIVE":
        raise ValidationFailed(
            "That container type is inactive.",
            {"containerType": "Choose an active container type."},
        )
    payload_data = jsonable({k: v for k, v in data.items() if k not in {"id"}})
    container = existing or ServiceOrderContainer(
        service_order_id=order.id,
        container_requirement_id=_int_or_none(data.get("containerRequirementId") or data.get("container_requirement_id")),
        container_type_id=int(container_type_id),
        container_number=None,
    )
    if existing is not None:
        # Keep the link to the prepared requirement when the form does not carry it.
        if data.get("containerRequirementId") or data.get("container_requirement_id"):
            container.container_requirement_id = _int_or_none(
                data.get("containerRequirementId") or data.get("container_requirement_id")
            )
        container.data = jsonable({**(existing.data or {}), **payload_data})
    else:
        container.data = payload_data
    container.container_type_id = int(container_type_id)
    container.container_number = container_number or None
    container.seal_serial = data.get("sealSerial") or data.get("seal_serial") or None
    container.status = str(data.get("status") or (existing.status if existing is not None else "EXPECTED"))
    container.net_weight_kg = net_weight if net_weight else None
    container.gross_weight_kg = gross_weight if gross_weight else None
    container.pickup_date = pickup_date
    container.return_date = return_date
    session.add(container)
    await session.commit()
    label = str(container_type.code or container_type.name or container_type_id)
    return _container_payload(container, label)


async def delete_containers(
    session: AsyncSession, context: RequestContext, identifier: str, ids: list[int]
) -> int:
    """Delete containers unless a fee row references them.

    Container payments live in the order's document data (one row per charge),
    so the guard reads the same structure the form writes. A referenced container
    is never silently removed; the caller reports the conflict instead.
    """
    order = await resolve_order(session, context, identifier)
    _ensure_order_editing(order)
    rows = (
        await session.execute(
            select(ServiceOrderContainer).where(
                ServiceOrderContainer.service_order_id == order.id,
                ServiceOrderContainer.id.in_(ids),
            )
        )
    ).scalars().all()
    payments = (order.data or {}).get("containerPayments")
    referenced: set[str] = set()
    if isinstance(payments, list):
        for payment in payments:
            if not isinstance(payment, dict):
                continue
            for key in ("serviceOrderContainerId", "containerNo"):
                value = str(payment.get(key) or "").strip()
                if value:
                    referenced.add(value)
    blocked = [
        row for row in rows
        if row.container_number and (str(row.id) in referenced or row.container_number in referenced)
    ]
    if blocked:
        raise Conflict(
            "CONTAINER_IN_USE",
            "Remove the linked container payment before deleting this container.",
            {"containers": ", ".join(str(row.container_number) for row in blocked)},
        )
    for row in rows:
        await session.delete(row)
    await session.commit()
    return len(rows)


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
            "serviceOrderId": str(charge.service_order_id) if charge.service_order_id else None,
            "customerPartyId": str(charge.customer_party_id) if charge.customer_party_id else None,
            "chargeSide": charge.charge_side or "CUSTOMER",
            "supplierPartyId": str(charge.supplier_party_id) if charge.supplier_party_id else None,
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
            # Optimistic concurrency: the client echoes this back on update so a
            # stale editor cannot silently overwrite a newer save.
            "updatedAt": charge.updated_at.isoformat() if charge.updated_at else None,
        }
    )
    return payload


async def _order_no(session: AsyncSession, order_id: int) -> str | None:
    order = await session.get(ServiceOrder, order_id)
    return order.service_order_no if order else None


async def _charge_with_details(
    session: AsyncSession,
    charge: ServiceOrderCharge,
    creator_name: str | None = None,
) -> dict[str, Any]:
    """Charge payload enriched with its fee lines and, when present, the linked invoice."""
    from app.modules.finance.models import FinancialDocument, FinancialDocumentSource

    payload = charge_record(charge, charge.data or {})
    payload["createdBy"] = creator_name
    payload["jobNo"] = await _order_no(session, charge.service_order_id)
    lines = (
        await session.execute(
            select(ServiceOrderChargeLine)
            .where(ServiceOrderChargeLine.service_order_charge_id == charge.id)
            .order_by(ServiceOrderChargeLine.line_no)
        )
    ).scalars().all()
    from app.modules.master_data.models import BusinessParty, FeeType

    fee_ids = [line.fee_type_id for line in lines if line.fee_type_id]
    fee_names = (
        dict((await session.execute(select(FeeType.id, FeeType.name).where(FeeType.id.in_(fee_ids)))).all())
        if fee_ids else {}
    )
    if charge.supplier_party_id:
        supplier = await session.get(BusinessParty, charge.supplier_party_id)
        payload["supplier"] = (
            (supplier.legal_name or supplier.display_name) if supplier is not None else None
        )
        generated = (
            await session.execute(
                select(FinancialDocument).where(
                    FinancialDocument.generated_key
                    == f"SO:{charge.service_order_id}:SUP:{charge.supplier_party_id}:{charge.currency_code}:SUPPLIER_BILL"
                )
            )
        ).scalars().first()
        if generated is not None:
            payload["supplierDocumentId"] = str(generated.id)
            payload["supplierDocumentNo"] = generated.document_no
    payload["costTotal"] = float(sum((line.cost_amount or 0) for line in lines))
    payload["feeLines"] = [
        {
            "id": str(line.id),
            "lineNo": line.line_no,
            "feeTypeId": line.fee_type_id,
            "feeType": fee_names.get(line.fee_type_id),
            "description": line.description,
            "quantity": float(line.quantity or 0),
            "unit": line.unit_code,
            # `unitPrice` is the API name; `unitAmount` is the form column. The
            # row must round-trip through both consumers without losing its price.
            "unitPrice": float(line.unit_price or 0),
            "unitAmount": float(line.unit_price or 0),
            "costUnitPrice": float(line.cost_unit_price or 0),
            "costAmount": float(line.cost_amount or 0),
            "discount": float(line.discount_amount or 0),
            "taxRate": float(line.tax_rate or 0),
            # `tax` keeps its historical meaning here (the rate); `taxAmount` is
            # the amount the form's inline cell edits and the printer sums.
            "tax": float(line.tax_rate or 0),
            "taxAmount": float(line.tax_amount or 0),
            "amount": float(line.line_amount or 0),
            "total": float(line.line_amount or 0),
        }
        for line in lines
    ]
    # Short description for list views: the first fee line's description, plus
    # how many more lines the charge carries when it has several.
    payload["description"] = (
        f"{lines[0].description} (+{len(lines) - 1} more)"
        if len(lines) > 1 and lines[0].description
        else (lines[0].description if lines else "")
    )
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
    if not payload.get("customer"):
        # The list needs the party even when the charge was created without its
        # own free-text company: its own party first, then the order's.
        party_name = None
        if charge.customer_party_id:
            party_name = (
                await session.execute(
                    select(BusinessParty.display_name, BusinessParty.legal_name).where(
                        BusinessParty.id == charge.customer_party_id
                    )
                )
            ).first()
        else:
            party_name = (
                await session.execute(
                    select(BusinessParty.display_name, BusinessParty.legal_name)
                    .join(ServiceOrder, ServiceOrder.customer_party_id == BusinessParty.id)
                    .where(ServiceOrder.id == charge.service_order_id)
                )
            ).first()
        if party_name is not None:
            payload["customer"] = party_name[0] or party_name[1]
    return payload


async def list_charges(session: AsyncSession, context: RequestContext, page: PageParams, scope: str = "all") -> dict:
    stmt = select(ServiceOrderCharge)
    if scope == "standalone":
        # Explicit standalone scope: top-level charges only; service-order
        # charges live on their parent order's Service Charge tab.
        stmt = stmt.where(ServiceOrderCharge.service_order_id.is_(None))
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
    from app.core.users import user_display_names

    creators = await user_display_names(session, (row.created_by_user_id for row in rows))
    items = [
        await _charge_with_details(session, row, creators.get(row.created_by_user_id))
        for row in rows
    ]
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
    from app.core.users import user_display_names

    creators = await user_display_names(session, (row.created_by_user_id for row in rows))
    return [
        await _charge_with_details(session, row, creators.get(row.created_by_user_id))
        for row in rows
    ]


async def get_charge(session: AsyncSession, context: RequestContext, charge_id: int) -> dict:
    charge = await session.get(ServiceOrderCharge, charge_id)
    if charge is None:
        raise NotFound("Service charge not found.")
    from app.core.users import user_display_names

    creators = await user_display_names(session, [charge.created_by_user_id])
    return await _charge_with_details(session, charge, creators.get(charge.created_by_user_id))


async def save_charge(session: AsyncSession, context: RequestContext, data: dict[str, Any], order_identifier: str | None = None) -> dict:
    data = CHARGE_WRITE_SCHEMA.validate(data, partial=bool(data.get("id")))
    supplied_type = data.get("documentType")
    if supplied_type not in (None, ""):
        document_type = str(supplied_type).strip().upper()
        if document_type not in CHARGE_DOCUMENT_TYPES:
            raise ValidationFailed(
                "Unsupported charge document type.",
                {"documentType": "Choose one of the configured document types."},
            )
        data["documentType"] = document_type
    if data.get("currency") not in (None, ""):
        from app.modules.master_data.currency_rates import assert_currency_code

        data["currency"] = await assert_currency_code(session, data["currency"], "currency")
    if data.get("documentDate") not in (None, "") and _date(data.get("documentDate")) is None:
        raise ValidationFailed("A valid document date is required.", {"documentDate": "Enter a valid date."})
    charge_id = data.get("id")
    charge: ServiceOrderCharge | None = None
    if charge_id and str(charge_id).isdigit():
        charge = await session.get(ServiceOrderCharge, int(charge_id))
    identifier = order_identifier or data.get("jobNo") or data.get("serviceOrderId") or (charge.service_order_id if charge else None)
    order: ServiceOrder | None = None
    supplied_party = data.get("customerPartyId") or data.get("customer_party_id")
    if identifier:
        order = await resolve_order(session, context, str(identifier))
        if order.status == "INACTIVE":
            raise InvalidState("Cannot add charges to an inactive service order.")
        # A linked charge always bills the order's customer: a supplied party
        # that disagrees is a mistake, not an override.
        effective_party_id = order.customer_party_id
    elif charge is not None:
        if supplied_party not in (None, ""):
            from app.modules.quotations.service import resolve_party_by_id

            effective_party_id = (await resolve_party_by_id(session, supplied_party)).id
        else:
            effective_party_id = charge.customer_party_id
    else:
        # Standalone charge: no service order, but a customer is mandatory.
        # The form's picker supplies the party id; older clients may send only
        # the company name, which resolves (or creates) the party like a
        # quotation's would.
        customer_name = str(data.get("customer") or "").strip()
        if supplied_party in (None, "") and not customer_name:
            raise ValidationFailed(
                "A business party is required.",
                {"customerPartyId": "Required"},
            )
        from app.modules.quotations.service import resolve_party_by_id, resolve_party_by_name

        effective_party_id = (await resolve_party_by_id(session, supplied_party)).id \
            if supplied_party not in (None, "") \
            else (await resolve_party_by_name(session, customer_name, context)).id

    # A linked charge inherits the order's currency unless the operator names
    # another one explicitly (a supplier cost may be booked in its own currency;
    # reporting groups by currency and never sums across them).
    # Idempotent create: a retry after a lost response carries the same stable
    # client marker. Adopt the row it already created instead of inserting a
    # second charge (two genuinely different rows have different markers).
    if charge is None and order is not None:
        marker = str(data.get("clientRowId") or "").strip()
        if marker:
            candidates = (
                await session.execute(
                    select(ServiceOrderCharge).where(
                        ServiceOrderCharge.service_order_id == order.id,
                    )
                )
            ).scalars().all()
            charge = next(
                (
                    candidate
                    for candidate in candidates
                    if str((candidate.data or {}).get("clientRowId") or "").strip() == marker
                ),
                None,
            )
    charge_side = str(
        data.get("chargeSide")
        or (charge.charge_side if charge is not None else None)
        or "CUSTOMER"
    ).upper()
    if charge_side not in {"CUSTOMER", "INTERNAL"}:
        raise ValidationFailed("Charge side must be CUSTOMER or INTERNAL.", {"chargeSide": "Invalid charge side"})
    supplier_raw = data.get("supplierPartyId") or data.get("supplier_party_id")
    supplier_party_id: int | None = charge.supplier_party_id if charge is not None else None
    if supplier_raw not in (None, ""):
        from app.modules.quotations.service import resolve_party_by_id

        supplier_party_id = (await resolve_party_by_id(session, supplier_raw)).id
    if charge_side == "INTERNAL" and supplier_party_id is None:
        raise ValidationFailed(
            "An internal charge requires a supplier.",
            {"supplierPartyId": "Required"},
        )
    if charge is not None and charge.status != "DRAFT":
        raise InvalidState("Only draft service charges can be edited.")
    # Optimistic concurrency: a client that loaded the charge sends its
    # `updatedAt`; if the row moved since, the save is refused instead of
    # silently overwriting the other session's edit. A caller that does not
    # send the stamp (import, internal command) keeps the previous behaviour.
    expected_updated_at = data.get("updatedAt")
    if charge is not None and expected_updated_at not in (None, "") and charge.updated_at is not None:
        try:
            expected_dt = datetime.fromisoformat(str(expected_updated_at).replace("Z", "+00:00"))
            current_dt = charge.updated_at
            if current_dt.tzinfo is None:
                current_dt = current_dt.replace(tzinfo=UTC)
            if expected_dt.tzinfo is None:
                expected_dt = expected_dt.replace(tzinfo=UTC)
        except ValueError:
            expected_dt = None
        if expected_dt is not None and current_dt != expected_dt:
            raise Conflict(
                "STALE_CHARGE",
                "This charge was changed by another session. Reload it before saving again.",
            )
    if charge is None:
        number = data.get("chargeNo") or data.get("documentNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, "SERVICE_CHARGE")
        charge = ServiceOrderCharge(
            service_order_id=order.id if order is not None else None,
            customer_party_id=effective_party_id,
            charge_side=charge_side,
            supplier_party_id=supplier_party_id,
            charge_no=str(number),
            document_type=str(data.get("documentType") or "SERVICE_NOTE"),
            document_date=_date(data.get("documentDate")) or date.today(),
            currency_code=data.get("currency") or (order.currency_code if order is not None else None) or await get_default_currency(session),
            status="DRAFT",
            created_by_user_id=context.user_id,
            data={},
        )
        session.add(charge)
        await session.flush()
    elif charge.customer_party_id is None:
        charge.customer_party_id = effective_party_id
    if charge is not None:
        charge.charge_side = charge_side
        charge.supplier_party_id = supplier_party_id
    # Only rebuild priced lines when the caller supplied them; a partial update
    # (e.g. just a status change) must not wipe the existing lines and totals.
    # `feeLines` is the document form's column; the other two spellings keep
    # older API clients working.
    if any(key in data for key in ("lines", "chargeLines", "feeLines")):
        from app.core.validation import validate_line_items
        from app.modules.master_data.service import resolve_reference_id

        line_field = next(key for key in ("lines", "chargeLines", "feeLines") if key in data)
        lines = validate_line_items(
            data.get(line_field) or [],
            CHARGE_LINE_SCHEMA,
            field=line_field,
        )
        subtotal = Decimal("0")
        discount_total = Decimal("0")
        tax_total = Decimal("0")
        await session.execute(delete(ServiceOrderChargeLine).where(ServiceOrderChargeLine.service_order_charge_id == charge.id))
        from app.core.validation import parse_decimal, resolve_line_tax

        for index, line in enumerate(lines):
            if not isinstance(line, dict):
                continue
            # The form's column is `unitAmount`; accept `unitPrice` as the
            # long-standing API spelling so neither client silently saves zero.
            unit_value = line.get("unitPrice")
            if unit_value in (None, ""):
                unit_value = line.get("unitAmount")
            quantity = parse_decimal(line.get("quantity"), f"{line_field}.{index}.quantity", Decimal("1"), places=3) or Decimal("1")
            unit_price = parse_decimal(unit_value, f"{line_field}.{index}.unitPrice", Decimal("0"), places=4)
            cost_value = line.get("costUnitPrice")
            if cost_value in (None, ""):
                cost_value = line.get("cost_unit_price")
            cost_unit_price = (
                parse_decimal(cost_value, f"{line_field}.{index}.costUnitPrice", Decimal("0"), places=4)
                if charge_side == "INTERNAL"
                else Decimal("0")
            )
            cost_amount = quantity * cost_unit_price
            discount = parse_decimal(line.get("discount"), f"{line_field}.{index}.discount", Decimal("0"), places=4)
            base = quantity * unit_price
            if quantity <= 0:
                raise ValidationFailed("Charge quantity must be greater than zero.", {f"{line_field}.{index}.quantity": "Must be positive"})
            if unit_price < 0:
                raise ValidationFailed("Charge unit price cannot be negative.", {f"{line_field}.{index}.unitPrice": "Cannot be negative"})
            if discount < 0 or discount > base:
                raise ValidationFailed(
                    "Charge discount must be between zero and the line subtotal.",
                    {f"{line_field}.{index}.discount": "Invalid discount"},
                )
            # The editor exposes a tax rate; the document-style tax amount is
            # accepted too, and an explicit rate wins when both are present.
            tax_rate_field, tax_amount, tax_rate = resolve_line_tax(line, base - discount, f"{line_field}.{index}")
            if tax_amount < 0:
                raise ValidationFailed(
                    "Charge tax cannot be negative.",
                    {f"{line_field}.{index}.{tax_rate_field}": "Cannot be negative"},
                )
            if tax_rate < 0 or tax_rate > 100:
                raise ValidationFailed(
                    "Charge tax rate must be between 0 and 100.",
                    {f"{line_field}.{index}.{tax_rate_field}": "Invalid tax rate"},
                )
            line_total = base - discount + tax_amount
            container_id = _int_or_none(line.get("containerId") or line.get("serviceOrderContainerId"))
            if container_id is not None:
                container = await session.get(ServiceOrderContainer, container_id)
                if order is None or container is None or container.service_order_id != order.id:
                    raise ValidationFailed(
                        "A charge line container must belong to the service order.",
                        {f"{line_field}.{index}.containerId": "Container does not belong to this service order"},
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
                    cost_unit_price=cost_unit_price,
                    cost_amount=cost_amount,
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
        **{
            key: value
            for key, value in data.items()
            if key not in {"id", "lines", "chargeLines", "feeLines", "createdAt", "updatedAt"}
        },
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
    if (charge.charge_side or "CUSTOMER").upper() == "INTERNAL":
        raise InvalidState("Internal cost charges are billed to suppliers, not issued to the customer.")
    if charge.status not in {"DRAFT", "ISSUED"}:
        raise InvalidState(f"Cannot issue a charge in status {charge.status}.")
    lines = (
        await session.execute(
            select(ServiceOrderChargeLine).where(ServiceOrderChargeLine.service_order_charge_id == charge.id)
        )
    ).scalars().all()
    if not lines or (charge.total_amount or Decimal("0")) <= 0:
        raise ValidationFailed("A service charge must have at least one positive line before it can be issued.")

    # Issuing is an operational/billing state change only (workflows.md §9): the
    # finance draft is created by the separate, finance-authorized convert
    # command and journals follow only its posting.
    charge.status = "ISSUED"
    await session.commit()
    await cache.bump("reports")
    return await _charge_with_details(session, charge)


async def delete_charges(session: AsyncSession, ids: list[int]) -> int:
    charges = await OperationsRepository(session).charges_by_ids(ids)
    # A charge that already produced a finance invoice is the invoice's source
    # of truth; deleting it would orphan that document's traceability.
    from app.modules.finance.models import FinancialDocumentSource

    invoiced = {
        row[0]
        for row in (
            await session.execute(
                select(FinancialDocumentSource.source_id).where(
                    FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE",
                    FinancialDocumentSource.source_id.in_(ids),
                )
            )
        ).all()
    }
    drafts = [charge for charge in charges if charge.status == "DRAFT" and charge.id not in invoiced]
    for charge in drafts:
        await session.delete(charge)
    await session.commit()
    if drafts:
        await cache.bump("reports")
    return len(drafts)


async def charge_to_invoice(
    session: AsyncSession, context: RequestContext, charge_id: int, idempotency_key: str | None = None
) -> dict:
    from app.modules.finance import service as finance_service

    # Lock the source charge so the whole check-and-create conversion is serial
    # per charge on PostgreSQL: a second concurrent convert waits here, then its
    # re-check inside the finance service sees the winner's source link and
    # returns that document instead of drafting a second one.
    charge = (
        await session.execute(
            select(ServiceOrderCharge).where(ServiceOrderCharge.id == charge_id).with_for_update()
        )
    ).scalars().first()
    if charge is None:
        raise NotFound("Service charge not found.")
    document = await finance_service.create_invoice_from_charge(
        session, context, charge, idempotency_key=idempotency_key
    )
    return document


# --- Attachments -------------------------------------------------------------
#: Collections that own uploaded files (source of truth: the frontend module
#: catalog's collections, which is where DocumentView passes `uploadContext`).
#: New collections must be added here deliberately; unknown values are refused
#: so a typo cannot create an attachment link nothing will ever list.
ATTACHMENT_ENTITY_TYPES = frozenset(
    {
        "companies",
        "quotations",
        "jobs",
        "shipments",
        "customs",
        "documents",
        "deliveries",
        "debitNotes",
        "customerPayments",
        "jobCharges",
        "supplierCosts",
        "supplierPayments",
        "receivables",
        "payables",
        "profitability",
        "users",
        "roles",
        "archive",
        "auditLogs",
    }
)

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
    return [await _attachment_payload_async(session, item) for item in links]


async def link_attachment(
    session: AsyncSession,
    attachment_id: int,
    module: str,
    record_no: str,
) -> None:
    """Link an upload to the document that owns it, when the caller supplied one.

    The upload endpoint predated links, so files were stored but never listed
    against their record. The link is optional: a generic upload without a
    module/record stays usable on its own.
    """
    entity_type = str(module or "").strip()[:64]
    entity_id = _int_or_none(record_no)
    if not entity_type or entity_id is None:
        return
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        # Refuse unknown collections instead of silently linking a file that no
        # screen will ever show (typo/forged module value).
        raise ValidationFailed(
            f"Unknown attachment entity type '{entity_type}'.",
            {"module": "Unsupported entity type"},
        )
    existing = (
        await session.execute(
            select(AttachmentLink.id).where(
                AttachmentLink.attachment_id == attachment_id,
                AttachmentLink.entity_type == entity_type,
                AttachmentLink.entity_id == entity_id,
            )
        )
    ).first()
    if existing is not None:
        return
    session.add(
        AttachmentLink(
            attachment_id=attachment_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )
    await session.commit()


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
    from app.modules.storage import service as storage_service

    removed = 0
    for attachment in attachments:
        if attachment.is_deleted:
            continue
        attachment.is_deleted = True
        await session.execute(
            delete(AttachmentLink).where(AttachmentLink.attachment_id == attachment.id)
        )
        try:
            tag = attachment.storage_provider or "local"
            provider: Any = await storage_service.build_provider(session, tag)
            if await asyncio.to_thread(provider.exists, attachment.storage_key):
                await asyncio.to_thread(provider.delete, attachment.storage_key)
        except Exception:  # noqa: BLE001 - the flag is the source of truth, not the object store
            pass
        try:
            from app.modules.storage.models import StorageReplica

            replicas = (
                await session.execute(select(StorageReplica).where(StorageReplica.attachment_id == attachment.id))
            ).scalars().all()
            for replica in replicas:
                await session.delete(replica)
        except Exception:  # noqa: BLE001 - replica cleanup is best-effort
            pass
        removed += 1
    await session.commit()
    return removed


async def _attachment_payload_async(session: AsyncSession, attachment: Attachment) -> dict[str, Any]:
    """Build the API attachment view, resolving URLs from the file's provider."""
    from app.modules.storage import service as storage_service

    tag = attachment.storage_provider or "local"
    url = None
    try:
        provider = await storage_service.build_provider(session, tag)
        url = await asyncio.to_thread(provider.presigned_get, attachment.storage_key, settings.presigned_url_expire_seconds)
    except Exception:  # noqa: BLE001 - an unconfigured provider must not break listing
        url = None
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
        "note": attachment.note,
        "url": url,
    }


ATTACHMENT_NOTE_MAX_LENGTH = 1000


def _attachment_note(value: Any) -> str | None:
    """Normalize the optional note; over-long text is refused, not truncated."""
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > ATTACHMENT_NOTE_MAX_LENGTH:
        raise ValidationFailed(
            f"The note must be {ATTACHMENT_NOTE_MAX_LENGTH} characters or fewer.",
            {"note": "Note is too long"},
        )
    return text


async def update_attachment_note(
    session: AsyncSession, context: RequestContext, attachment_id: int, note: Any
) -> dict:
    """Update only the note. The file and its links are never touched."""
    attachment = await session.get(Attachment, attachment_id)
    if attachment is None or attachment.is_deleted:
        raise NotFound("Attachment not found.")
    attachment.note = _attachment_note(note)
    await session.commit()
    return await _attachment_payload_async(session, attachment)


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
    storage = await _resolve_upload_storage(session)
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
    session: AsyncSession,
    context: RequestContext,
    file_name: str,
    mime_type: str,
    content: bytes,
    storage_key: str | None = None,
    note: str | None = None,
) -> dict:
    storage = await _resolve_upload_storage(session)
    clean_name, extension, content_type = _upload_metadata(file_name, await effective_upload_extensions(session))
    clean_note = _attachment_note(note)
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
    # Providers return the authoritative file id (Drive replaces the caller
    # key with its own fileId); object stores echo the key unchanged.
    stored_key = await asyncio.to_thread(storage.put, key, content, content_type)
    attachment = Attachment(
        file_name=clean_name,
        storage_key=stored_key or key,
        mime_type=content_type,
        file_size_bytes=len(content),
        storage_provider=storage.tag,
        uploaded_by_user_id=context.user_id,
        note=clean_note,
    )
    session.add(attachment)
    await session.commit()
    payload = await _attachment_payload_async(session, attachment)
    # Durable backup scheduling never blocks or fails the upload itself.
    try:
        await _schedule_backup(attachment.id)
    except Exception as exc:  # noqa: BLE001 - backup is asynchronous by design
        logger.warning("Backup scheduling for attachment %s failed: %s", attachment.id, exc)
    return payload


async def _resolve_upload_storage(session: AsyncSession):
    """The destination provider for new uploads, per the Settings configuration."""
    from app.modules.storage import service as storage_service

    return (await storage_service.resolve_upload_target(session))[0]


async def _schedule_backup(attachment_id: int) -> None:
    from app.core.database import SessionLocal
    from app.modules.storage import service as storage_service
    from app.modules.storage.models import StorageReplica

    async with SessionLocal() as session:
        config = await storage_service.load_config(session)
        target = str(config.get("backupProvider") or "").strip()
        if not target or not bool(config.get("backupEnabled")) or target == config.get("primaryProvider"):
            return
        if not storage_service.is_configured(target, (config.get("providers") or {}).get(target) or {}):
            return
        exists = (
            await session.execute(
                select(StorageReplica.id).where(
                    StorageReplica.attachment_id == attachment_id,
                    StorageReplica.backup_provider == target,
                )
            )
        ).scalar_one_or_none()
        if exists:
            return
        session.add(StorageReplica(attachment_id=attachment_id, backup_provider=target, backup_key="-", status="PENDING"))
        await session.commit()


async def read_attachment(storage_key: str, session: AsyncSession | None = None) -> tuple[bytes, str]:
    """Stream the file from the provider it actually lives on (per its metadata)."""
    from app.core.exceptions import NotFound
    from app.modules.storage import service as storage_service

    try:
        return await storage_service.read_file(storage_key, None, session)
    except (FileNotFoundError, OSError, LookupError) as exc:
        # Deleted object or missing provider config → 404, not a raw provider error.
        raise NotFound("File not found.") from exc
    except Exception as exc:  # noqa: BLE001 - provider 404s surface as 404 too
        import googleapiclient.errors  # noqa: PLC0415

        if isinstance(exc, googleapiclient.errors.HttpError) and exc.resp.status == 404:
            raise NotFound("File not found.") from exc
        raise


# --- Movements ---------------------------------------------------------------
# A movement is one leg of the transport chain (origin -> destination, planned
# and actual times). The tables existed but had no service or endpoints, so the
# capability was unreachable from the application.

# Movement statuses are plain values rather than an enum so a new state does not
# need a migration; the shared request schema declares the vocabulary.


def _normalize_movement_status(value: Any, default: str = "PLANNED") -> str:
    if value in (None, ""):
        return default
    candidate = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    return candidate if candidate in MOVEMENT_STATUSES else default


def _as_utc(value: Any, field: str = "date") -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise ValidationFailed(
                "Enter a valid date and time.",
                {field: "Enter a valid date and time."},
            ) from None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _positive_int(value: Any, field: str, default: int | None = None) -> int | None:
    """Parse a whole number, reporting a malformed value on its own field."""
    if value in (None, ""):
        return default
    from app.core.validation import parse_decimal

    number = parse_decimal(value, field)
    if number != number.to_integral_value():
        raise ValidationFailed("Enter a whole number.", {field: "Enter a whole number."})
    return int(number)


def _movement_payload(row: ServiceOrderMovement, *, transport_type: str | None = None) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "serviceOrderId": str(row.service_order_id),
        "sequenceNo": row.sequence_no,
        "transportTypeId": row.transport_type_id,
        "transportType": transport_type,
        "transportAssetId": row.transport_asset_id,
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
    _ensure_order_editing(order)

    data = MOVEMENT_WRITE_SCHEMA.validate(data, partial=bool(data.get("id")))
    movement_id = _int_or_none(data.get("id"))
    movement: ServiceOrderMovement | None = None
    if movement_id is not None:
        movement = await session.get(ServiceOrderMovement, movement_id)
        if movement is None or movement.service_order_id != order.id:
            raise NotFound("Movement not found on this service order.")

    if movement is None:
        if "sequenceNo" in data and data.get("sequenceNo") not in (None, ""):
            sequence_no = _positive_int(data["sequenceNo"], "sequenceNo", 0) or 0
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
        requested = _positive_int(data["sequenceNo"], "sequenceNo", 0) or 0
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
            setattr(movement, attribute, _as_utc(data.get(camel), camel))

    movement.status = _normalize_movement_status(data.get("status"), movement.status or "PLANNED")
    stored = dict(movement.data or {})
    if "notes" in data:
        stored["notes"] = data.get("notes")
    movement.data = jsonable(stored)
    await session.commit()
    return _movement_payload(movement)


async def delete_movements(session: AsyncSession, context: RequestContext, identifier: str, ids: list[int]) -> int:
    order = await resolve_order(session, context, identifier)
    _ensure_order_editing(order)
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
    _ensure_order_editing(order)

    data = MILESTONE_WRITE_SCHEMA.validate(data, partial=bool(data.get("id")))
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
            sequence_no=_positive_int(data.get("sequenceNo"), "sequenceNo", 1) or 1,
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
            milestone.sequence_no = _positive_int(data["sequenceNo"], "sequenceNo", 1) or 1
        milestone.status = _normalize_milestone_status(data.get("status"), milestone.status)
        if "notes" in data:
            milestone.notes = data.get("notes")

    for camel, attribute in (("plannedAt", "planned_at"), ("actualAt", "actual_at")):
        if camel in data:
            setattr(milestone, attribute, _as_utc(data.get(camel), camel))

    await session.commit()
    return _milestone_payload(milestone)


async def delete_milestones(session: AsyncSession, context: RequestContext, identifier: str, ids: list[int]) -> int:
    order = await resolve_order(session, context, identifier)
    _ensure_order_editing(order)
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

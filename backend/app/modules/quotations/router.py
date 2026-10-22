from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.pagination import PageParams, page_params
from app.core.validation import EntityId, validate_id_list
from app.modules.audit.service import write_audit
from app.modules.quotations import service
from app.modules.quotations.schemas import REVISION_REASON_SCHEMA

router = APIRouter()


async def _record_revision_status_change(
    session: AsyncSession,
    context: RequestContext,
    revision_id: int,
    before: str | None,
    record: dict,
    event_type: str,
    action: str,
    reason: str | None = None,
) -> None:
    """Every quotation transition leaves one audit row with both statuses."""
    await write_audit(
        session,
        context,
        event_type=event_type,
        entity_type="quotation_revision",
        entity_id=revision_id,
        action=action,
        before={"status": before} if before else None,
        after={"status": record.get("revisionStatus")},
        reason=reason,
    )
    await session.commit()


@router.get("/quotations")
async def list_quotations(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("quotation.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_quotations(session, context, page)}


@router.post("/quotations", status_code=status.HTTP_201_CREATED)
async def save_quotation(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await service.save_quotation(session, context, payload)
    await session.commit()
    return {"data": record}


@router.delete("/quotations")
async def delete_quotations(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.delete")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = validate_id_list(payload)
    await service.delete_quotations(session, context, ids)
    return {"data": {"removed": len(ids)}}


@router.get("/quotations/{quotation_id}")
async def get_quotation(
    quotation_id: EntityId,
    context: RequestContext = Depends(require_permission("quotation.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_quotation(session, context, quotation_id)}


@router.put("/quotations/{quotation_id}")
async def update_quotation(
    quotation_id: EntityId,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = {**payload, "id": quotation_id}
    record = await service.save_quotation(session, context, payload)
    await session.commit()
    return {"data": record}


@router.post("/quotations/{quotation_id}/revisions", status_code=status.HTTP_201_CREATED)
async def create_revision(
    quotation_id: EntityId,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.revise")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await service.create_revision(session, context, quotation_id, payload)
    return {"data": record}


@router.get("/quotations/{quotation_id}/revisions")
async def list_revisions(
    quotation_id: EntityId,
    context: RequestContext = Depends(require_permission("quotation.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_revisions(session, context, quotation_id)}


@router.post("/quotation-revisions/{revision_id}/send")
async def send_revision(
    revision_id: EntityId,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.send")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    before = await service.revision_status(session, revision_id)
    record = await service.send_revision(session, context, revision_id)
    await _record_revision_status_change(
        session, context, revision_id, before, record, "QUOTATION_SENT", "send",
    )
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/submit")
async def submit_revision(
    revision_id: EntityId,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.submit")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    before = await service.revision_status(session, revision_id)
    record = await service.submit_revision(session, context, revision_id)
    await _record_revision_status_change(
        session, context, revision_id, before, record, "QUOTATION_SENT", "submit",
    )
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/accept")
async def accept_revision(
    revision_id: EntityId,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.accept")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    before = await service.revision_status(session, revision_id)
    record = await service.accept_revision(session, context, revision_id)
    await _record_revision_status_change(
        session, context, revision_id, before, record, "QUOTATION_ACCEPTED", "accept",
    )
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/reject")
async def reject_revision(
    revision_id: EntityId,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.accept")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Rejecting is approval authority: the same role that may accept may reject."""
    reason = REVISION_REASON_SCHEMA.validate(payload).get("reason")
    before = await service.revision_status(session, revision_id)
    record = await service.reject_revision(session, context, revision_id, str(reason) if reason else None)
    await _record_revision_status_change(
        session, context, revision_id, before, record, "QUOTATION_REJECTED", "reject",
        str(reason) if reason else None,
    )
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/cancel")
async def cancel_revision(
    revision_id: EntityId,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Withdrawing an offer is edit authority: no customer decision is involved."""
    reason = REVISION_REASON_SCHEMA.validate(payload).get("reason")
    before = await service.revision_status(session, revision_id)
    record = await service.cancel_revision(session, context, revision_id, str(reason) if reason else None)
    await _record_revision_status_change(
        session, context, revision_id, before, record, "QUOTATION_CANCELLED", "cancel",
        str(reason) if reason else None,
    )
    return {"data": record}


@router.get("/quotation-revisions/{revision_id}/compare/{other_revision_id}")
async def compare_revisions(
    revision_id: EntityId,
    other_revision_id: EntityId,
    context: RequestContext = Depends(require_permission("quotation.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Diff two revisions of one quotation; neither revision is modified."""
    return {"data": await service.compare_revisions(session, context, revision_id, other_revision_id)}


@router.post("/quotation-revisions/{revision_id}/convert", status_code=status.HTTP_201_CREATED)
async def convert_revision(
    revision_id: EntityId,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.convert")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    before = await service.revision_status(session, revision_id)
    record = await service.convert_revision(session, context, revision_id)
    await _record_revision_status_change(
        session, context, revision_id, before, record, "QUOTATION_CONVERTED", "convert",
    )
    return {"data": record}

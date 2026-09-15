from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.pagination import PageParams, page_params
from app.modules.audit.service import write_audit
from app.modules.quotations import service

router = APIRouter()


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
    await write_audit(
        session,
        context,
        event_type="QUOTATION_SAVED",
        entity_type="quotation",
        entity_id=int(record["id"]),
        action="create" if not payload.get("id") else "update",
        after={"quotationNo": record.get("quotationNo"), "status": record.get("status")},
    )
    await session.commit()
    return {"data": record}


@router.delete("/quotations")
async def delete_quotations(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.update_draft")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    await service.delete_quotations(session, context, ids)
    return {"data": {"removed": len(ids)}}


@router.get("/quotations/{quotation_id}")
async def get_quotation(
    quotation_id: str,
    context: RequestContext = Depends(require_permission("quotation.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_quotation(session, context, int(quotation_id))}


@router.put("/quotations/{quotation_id}")
async def update_quotation(
    quotation_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.update_draft")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = {**payload, "id": quotation_id}
    record = await service.save_quotation(session, context, payload)
    await write_audit(
        session,
        context,
        event_type="QUOTATION_UPDATED",
        entity_type="quotation",
        entity_id=int(quotation_id),
        action="update",
        after={"status": record.get("status")},
    )
    await session.commit()
    return {"data": record}


@router.post("/quotations/{quotation_id}/revisions", status_code=status.HTTP_201_CREATED)
async def create_revision(
    quotation_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("quotation.update_draft")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await service.create_revision(session, context, int(quotation_id), payload)
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/send")
async def send_revision(
    revision_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.send")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await service.send_revision(session, context, int(revision_id))
    await write_audit(
        session,
        context,
        event_type="QUOTATION_SENT",
        entity_type="quotation_revision",
        entity_id=int(revision_id),
        action="send",
        after={"status": "SENT", "idempotencyKey": idempotency_key},
    )
    await session.commit()
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/submit")
async def submit_revision(
    revision_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.send")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await service.submit_revision(session, context, int(revision_id))
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/accept")
async def accept_revision(
    revision_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.accept")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await service.accept_revision(session, context, int(revision_id))
    await write_audit(
        session,
        context,
        event_type="QUOTATION_ACCEPTED",
        entity_type="quotation_revision",
        entity_id=int(revision_id),
        action="accept",
        after={"status": "ACCEPTED"},
    )
    await session.commit()
    return {"data": record}


@router.post("/quotation-revisions/{revision_id}/convert", status_code=status.HTTP_201_CREATED)
async def convert_revision(
    revision_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("quotation.convert")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await service.convert_revision(session, context, int(revision_id))
    await write_audit(
        session,
        context,
        event_type="QUOTATION_CONVERTED",
        entity_type="quotation_revision",
        entity_id=int(revision_id),
        action="convert",
        after={"serviceOrderId": record.get("serviceOrderId")},
    )
    await session.commit()
    return {"data": record}

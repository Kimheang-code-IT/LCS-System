from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.pagination import PageParams, page_params
from app.modules.audit import service

router = APIRouter()


@router.get("/audit-events")
async def list_audit_events(
    page: PageParams = Depends(page_params),
    entity_type: str | None = Query(None, max_length=64),
    event_type: str | None = Query(None, max_length=64),
    entity_id: int | None = Query(None, ge=1),
    context: RequestContext = Depends(require_permission("audit_log.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await service.list_events(session, context, page, entity_type, event_type, entity_id)
    return {"data": result}

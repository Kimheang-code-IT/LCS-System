from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.pagination import PageParams, page_params
from app.modules.archive import service

router = APIRouter()


@router.get("/archive/options")
async def get_archive_options(
    context: RequestContext = Depends(require_permission("archive.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.archive_options(session)}


@router.get("/archive")
async def list_archive(
    page: PageParams = Depends(page_params),
    entity_type: str | None = Query(None),
    deleted_by: int | None = Query(None),
    context: RequestContext = Depends(require_permission("archive.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_archived_records(session, page, entity_type=entity_type, deleted_by_id=deleted_by)}


@router.get("/archive/{entity_type}/{entity_id}")
async def get_archive_record(
    entity_type: str,
    entity_id: int,
    context: RequestContext = Depends(require_permission("archive.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_archived_record(session, entity_type, entity_id)}


@router.post("/archive/{entity_type}/{entity_id}/restore")
async def restore_archive_record(
    entity_type: str,
    entity_id: int,
    context: RequestContext = Depends(require_permission("archive.restore")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.restore_record(session, context, entity_type, entity_id)}


@router.delete("/archive/{entity_type}/{entity_id}")
async def hard_delete_archive_record(
    entity_type: str,
    entity_id: int,
    context: RequestContext = Depends(require_permission("archive.hard_delete")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.hard_delete_record(session, context, entity_type, entity_id)}

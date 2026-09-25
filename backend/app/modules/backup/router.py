from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.exceptions import AccessDenied, Conflict, ValidationFailed
from app.core.pagination import PageParams, page_params, paged
from app.modules.backup import service
from app.modules.backup.models import BackupRun
from app.modules.backup.sheets import BackupConfigurationError, SheetsApiError

router = APIRouter()


@router.get("/backup/status")
async def backup_status(
    context: RequestContext = Depends(require_permission("backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service._load_backup_config(session)
    last_run = (
        await session.execute(select(BackupRun).order_by(BackupRun.id.desc()).limit(1))
    ).scalars().first()
    return {
        "data": {
            "config": service.public_config(config),
            "schedule": service.schedule_status(config),
            "activeRunId": service.active_run_id(),
            "lastRun": service.serialize_run(last_run) if last_run else None,
        }
    }


@router.get("/backup/runs")
async def list_runs(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    total = int(await session.scalar(select(func.count()).select_from(BackupRun)) or 0)
    runs = (
        await session.execute(
            select(BackupRun).order_by(BackupRun.id.desc()).limit(page.page_size).offset(page.offset)
        )
    ).scalars().all()
    return {"data": paged([service.serialize_run(run) for run in runs], page, total)}


@router.get("/backup/runs/{run_id}")
async def get_run(
    run_id: int,
    context: RequestContext = Depends(require_permission("backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    run = await service.get_run(session, run_id)
    if run is None:
        raise ValidationFailed("Backup run not found.", {"run_id": "Unknown run."})
    return {"data": run}


@router.post("/backup/run")
async def run_backup(
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        run = await service.start_backup(session, trigger="manual", user_id=context.user_id)
    except BackupConfigurationError as exc:
        raise ValidationFailed(str(exc), {"spreadsheetId": str(exc)}) from exc
    except RuntimeError as exc:
        raise Conflict("BACKUP_RUNNING", str(exc)) from exc
    return {"data": run}


@router.post("/backup/restore")
async def restore_backup(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not context.has_permission("settings.manage") and not context.is_platform_admin:
        raise AccessDenied("Restoring backup data requires the settings.manage permission.")
    confirm = str(payload.get("confirm") or "")
    tables = payload.get("tables") or None
    try:
        result = await service.restore_from_sheets(session, confirm=confirm, tables=tables)
    except BackupConfigurationError as exc:
        raise ValidationFailed(str(exc), {"spreadsheetId": str(exc)}) from exc
    except ValueError as exc:
        raise ValidationFailed(str(exc), {"confirm": str(exc)}) from exc
    except SheetsApiError as exc:
        raise ValidationFailed(f"Google Sheets error: {exc}", {"spreadsheetId": str(exc)}) from exc
    return {"data": result}


@router.post("/backup/test-connection")
async def test_connection(
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service._load_backup_config(session)
    try:
        client = service.build_client(config)
    except BackupConfigurationError as exc:
        raise ValidationFailed(str(exc), {"spreadsheetId": str(exc)}) from exc
    try:
        result = await asyncio.to_thread(client.test_connection)
    except SheetsApiError as exc:
        raise ValidationFailed(f"Google Sheets error: {exc}", {"spreadsheetId": str(exc)}) from exc
    return {"data": {"status": "connected", "message": "Google Sheets connection succeeded.", **result}}

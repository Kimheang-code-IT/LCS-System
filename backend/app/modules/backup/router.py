from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.exceptions import AccessDenied, Conflict, ValidationFailed
from app.core.pagination import PageParams, page_params, paged
from app.modules.backup import service
from app.modules.backup.repository import BackupRunRepository
from app.modules.backup.schemas import RESTORE_BACKUP_SCHEMA
from app.modules.backup.sheets import BackupConfigurationError, SheetsApiError

router = APIRouter()


async def _record_restore_failure(session: AsyncSession, context: RequestContext) -> None:
    from app.modules.audit.service import write_audit

    await session.rollback()
    await write_audit(session, context, event_type="BACKUP_RESTORE_FAILED", entity_type="backup", entity_id=0, action="restore", result="FAILED", reason="Restore execution failed; review authorized backup logs.")
    await session.commit()


@router.get("/backup/status")
async def backup_status(
    context: RequestContext = Depends(require_permission("backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service._load_backup_config(session)
    last_run = await BackupRunRepository(session).latest()
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
    runs, total = await BackupRunRepository(session).page(page)
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
    values = RESTORE_BACKUP_SCHEMA.validate(payload)
    confirm = str(values.get("confirm") or "")
    tables = values.get("tables") or None
    try:
        result = await service.restore_from_sheets(session, confirm=confirm, tables=tables)
    except BackupConfigurationError as exc:
        raise ValidationFailed(str(exc), {"spreadsheetId": str(exc)}) from exc
    except ValueError as exc:
        raise ValidationFailed(str(exc), {"confirm": str(exc)}) from exc
    except SheetsApiError as exc:
        await _record_restore_failure(session, context)
        raise ValidationFailed(f"Google Sheets error: {exc}", {"spreadsheetId": str(exc)}) from exc
    except Exception:
        await _record_restore_failure(session, context)
        raise
    return {"data": result}


@router.post("/backup/full")
async def create_full_backup(
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Manual full DR backup: pg_dump + attachments + manifest (+ object upload)."""
    from datetime import UTC, datetime

    from app.modules.audit.service import write_audit
    from app.modules.backup import dr

    run = await service.create_run(session, trigger="full-manual", user_id=context.user_id, spreadsheet_id=None)
    try:
        manifest = await dr.build_archive(session)
        archive = dr.archive_dir() / manifest["archive"]["file"]
        remote_key = await dr.upload_archive(session, archive)
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        run.message = f"Full backup {manifest['backupId']} stored ({manifest['archive']['bytes']} bytes)."
        run.detail = {"kind": "full", **manifest, "remoteKey": remote_key}
        await write_audit(
            session,
            context,
            event_type="BACKUP_FULL_CREATED",
            entity_type="backup",
            entity_id=int(run.id),
            action="run",
            reason=f"Full backup {manifest['backupId']} created.",
            metadata={
                "backupId": manifest["backupId"],
                "remoteKey": remote_key,
                "encrypted": manifest["encryption"]["algorithm"] != "none",
            },
        )
        await session.commit()
        return {"data": {**manifest, "remoteKey": remote_key}}
    except Exception as exc:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.message = str(exc)[:500]
        run.detail = {"kind": "full"}
        await write_audit(
            session,
            context,
            event_type="BACKUP_FULL_FAILED",
            entity_type="backup",
            entity_id=int(run.id),
            action="run",
            result="FAILED",
            reason="Full backup creation failed.",
        )
        await session.commit()
        raise


@router.get("/backup/full")
async def full_backup_history(
    context: RequestContext = Depends(require_permission("backup.read")),
) -> dict:
    from app.modules.backup import dr

    return {"data": {"items": dr.list_archives()}}


@router.post("/backup/full/verify")
async def verify_full_backup(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("backup.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.audit.service import write_audit
    from app.modules.backup import dr

    report = dr.verify_archive(dr.archive_path_from_name(str(payload.get("file") or "")))
    await write_audit(
        session,
        context,
        event_type="BACKUP_FULL_VERIFIED" if report["ok"] else "BACKUP_FULL_VERIFY_FAILED",
        entity_type="backup",
        entity_id=0,
        action="verify",
        result="SUCCESS" if report["ok"] else "FAILED",
        reason="Full backup integrity verification.",
        metadata={"file": payload.get("file"), "problems": len(report["problems"])},
    )
    await session.commit()
    return {"data": {"ok": report["ok"], "problems": report["problems"]}}


@router.post("/backup/full/restore")
async def restore_full_backup(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Protected DR restore: maintenance mode, typed confirmation, safety backup.

    Refuses to overwrite the live database unless the operator set
    ``FULL_BACKUP_ALLOW_LIVE_RESTORE=1`` (the CLI path targets an isolated DB).
    """
    from app.modules.audit.service import write_audit
    from app.modules.backup import dr
    from app.modules.settings import maintenance

    if not context.has_permission("settings.manage") and not context.is_platform_admin:
        raise AccessDenied("Full restore requires the settings.manage permission.")
    state = await maintenance.load(session)
    if not maintenance.active(state):
        raise Conflict("MAINTENANCE_REQUIRED", "Enable maintenance mode before a full restore.")
    archive = dr.archive_path_from_name(str(payload.get("file") or ""))
    # Safety backup first: never restore without a fresh recoverable copy.
    safety = await dr.build_archive(session)
    result = await asyncio.to_thread(
        dr.restore_archive,
        archive,
        target_dsn=dr.libpq_dsn(),
        confirm=str(payload.get("confirm") or ""),
    )
    await write_audit(
        session,
        context,
        event_type="BACKUP_FULL_RESTORED",
        entity_type="backup",
        entity_id=0,
        action="restore",
        reason=f"Full restore from {archive.name}; safety backup {safety['backupId']}.",
        metadata={"file": archive.name, "safetyBackupId": safety["backupId"]},
    )
    await session.commit()
    return {"data": {**result, "safetyBackupId": safety["backupId"]}}


@router.post("/backup/test-connection")
async def test_connection(
    context: RequestContext = Depends(require_permission("backup.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service._load_backup_config(session)
    if service.r2_configured(config):
        try:
            storage = service.build_r2_storage(config)
            await asyncio.to_thread(storage.test_connection)
        except Exception as exc:  # noqa: BLE001 - do not expose SDK details that may contain credential context
            raise ValidationFailed(
                "Cloudflare R2 connection failed. Verify the endpoint, credentials, bucket, and permissions.",
                {"r2Endpoint": "Could not access the configured R2 bucket."},
            ) from exc
        return {
            "data": {
                "status": "connected",
                "message": "Cloudflare R2 connection succeeded.",
                "bucket": config.get("r2BucketName"),
            }
        }
    try:
        client = service.build_client(config)
    except BackupConfigurationError as exc:
        raise ValidationFailed(str(exc), {"spreadsheetId": str(exc)}) from exc
    try:
        result = await asyncio.to_thread(client.test_connection)
    except SheetsApiError as exc:
        raise ValidationFailed(f"Google Sheets error: {exc}", {"spreadsheetId": str(exc)}) from exc
    return {"data": {"status": "connected", "message": "Google Sheets connection succeeded.", **result}}

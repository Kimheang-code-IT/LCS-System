"""In-process asyncio scheduler for automatic configured backups.

A single background task wakes on an interval, reads the ``backup`` section of
the application config and starts a run when the configured number of hours has
elapsed since the last one. It runs in its own task and session, so it never
touches request transactions. Call :func:`start_scheduler` from the FastAPI
lifespan and :func:`stop_scheduler` on shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.locks import advisory_lock
from app.modules.backup import service

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_stop = asyncio.Event()


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed


def _is_due(last_run_at: str, interval_hours: int, now: datetime) -> bool:
    last = _parse_timestamp(last_run_at)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=now.tzinfo)
    return (now - last).total_seconds() >= max(1, interval_hours) * 3600


async def maybe_run_due() -> None:
    if service.active_run_id() is not None:
        return
    async with SessionLocal() as session:
        from app.modules.settings.maintenance import jobs_paused, tick
        await tick(session)
        if await jobs_paused(session):
            return
        await _maybe_full_backup_due(session)
        config = await service._load_backup_config(session)
        if not config.get("enabled"):
            return
        if not service.sheets_configured(config) and not service.r2_configured(config):
            return
        interval = int(config.get("intervalHours") or 24)
        now = service.utcnow()
        if not _is_due(str(config.get("lastRunAt") or ""), interval, now):
            return
        # PostgreSQL advisory lock: when several API replicas run the scheduler,
        # only the replica that wins the lock performs the scheduled run.
        async with advisory_lock(session, "backup:scheduled") as acquired:
            if not acquired:
                logger.debug("Scheduled backup skipped: another replica holds the lock.")
                return
            try:
                await service.run_now(session, trigger="scheduled")
            except Exception as exc:  # noqa: BLE001 - scheduler must keep running
                logger.warning("Scheduled backup failed: %s", exc)


async def _maybe_full_backup_due(session) -> None:
    """Scheduled full DR backup, opt-in through FULL_BACKUP_INTERVAL_HOURS.

    Default 0 = disabled, so existing deployments keep their current schedule
    until an operator turns disaster-recovery archives on. The last full run is
    read from the backup journal (trigger starts with ``full-``).
    """
    import os

    from sqlalchemy import select

    from app.modules.backup import dr
    from app.modules.backup.models import BackupRun

    try:
        interval = int(os.environ.get("FULL_BACKUP_INTERVAL_HOURS", "0") or 0)
    except ValueError:
        return
    if interval <= 0:
        return
    last = (
        await session.execute(
            select(BackupRun.started_at)
            .where(BackupRun.trigger.like("full-%"), BackupRun.status == "success")
            .order_by(BackupRun.started_at.desc())
            .limit(1)
        )
    ).scalar()
    if not _is_due(last.isoformat() if last else "", interval, service.utcnow()):
        return
    async with advisory_lock(session, "backup:full-scheduled") as acquired:
        if not acquired:
            return
        run = await service.create_run(session, trigger="full-scheduled", user_id=None, spreadsheet_id=None)
        try:
            manifest = await dr.build_archive(session)
            remote_key = await dr.upload_archive(session, dr.archive_dir() / manifest["archive"]["file"])
            run.status = "success"
            run.message = f"Scheduled full backup {manifest['backupId']}."
            run.detail = {"kind": "full", **manifest, "remoteKey": remote_key}
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - scheduler must keep running
            await session.rollback()
            run = await session.get(BackupRun, run.id)
            if run is not None:
                run.status = "failed"
                run.message = str(exc)[:500]
                run.detail = {"kind": "full"}
                await session.commit()
            logger.warning("Scheduled full backup failed: %s", exc)


async def _loop() -> None:
    tick = max(5, int(settings.backup_scheduler_tick_seconds))
    while not _stop.is_set():
        try:
            await maybe_run_due()
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            logger.warning("Backup scheduler tick failed: %s", exc)
        try:
            await asyncio.wait_for(_stop.wait(), timeout=tick)
        except TimeoutError:
            continue


def start_scheduler() -> None:
    global _task
    if not settings.backup_scheduler_enabled or _task is not None:
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())


async def stop_scheduler() -> None:
    global _task
    if _task is None:
        return
    _stop.set()
    try:
        await asyncio.wait_for(_task, timeout=5)
    except (TimeoutError, asyncio.CancelledError):
        _task.cancel()
    _task = None

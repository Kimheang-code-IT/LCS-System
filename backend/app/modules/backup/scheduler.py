"""In-process asyncio scheduler for automatic Google Sheets backups.

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
        config = await service._load_backup_config(session)
        if not config.get("enabled"):
            return
        if not config.get("spreadsheetId") or not config.get("serviceAccountJson"):
            return
        interval = int(config.get("intervalHours") or 24)
        now = service.utcnow()
        if not _is_due(str(config.get("lastRunAt") or ""), interval, now):
            return
        try:
            await service.run_now(session, trigger="scheduled")
        except Exception as exc:  # noqa: BLE001 - scheduler must keep running
            logger.warning("Scheduled backup failed: %s", exc)


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

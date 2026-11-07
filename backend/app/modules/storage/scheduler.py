"""In-process asyncio scheduler for the storage backup/migration workflows.

One background task wakes on a fixed tick and calls
:func:`app.modules.storage.service.reconcile`, which:

* sweeps replication to the configured backup provider,
* resumes jobs a restart left PENDING,
* resets jobs whose RUNNING heartbeat stalled.

It keeps its own DB session (the existing backup-scheduler pattern) and is
guarded by the same PostgreSQL advisory-lock approach, so API replicas never
double-process the same replica.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.locks import advisory_lock

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_stop = asyncio.Event()


async def reconcile_tick() -> None:
    async with SessionLocal() as session:
        from app.modules.settings.maintenance import jobs_paused

        if await jobs_paused(session):
            return
        async with advisory_lock(session, "storage:reconcile") as acquired:
            if not acquired:
                return
            await storage_service_reconcile(session)


async def storage_service_reconcile(session) -> None:  # noqa: ANN001 - session type kept loose for tests
    from app.modules.storage import service

    await service.reconcile(session)


def start_scheduler() -> None:
    global _task
    if _task is not None:
        return
    _stop.clear()
    _task = asyncio.get_running_loop().create_task(_loop())


async def stop_scheduler() -> None:
    global _task
    _stop.set()
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutdown must be quiet
            pass
    _task = None


async def _loop() -> None:
    tick = max(15, int(settings.backup_scheduler_tick_seconds))
    while not _stop.is_set():
        try:
            await asyncio.wait_for(_stop.wait(), timeout=tick)
            return
        except TimeoutError:
            pass
        except asyncio.CancelledError:
            raise
        try:
            await reconcile_tick()
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            logger.warning("Storage reconcile tick failed: %s", exc)

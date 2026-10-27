"""One low-frequency asyncio task in the existing API process, no broker."""

import asyncio
import logging
import time

from sqlalchemy import delete

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.modules.telegram import outbox
from app.modules.telegram.models import TelegramPairing, TelegramUpdate

logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None
_stop = asyncio.Event()
last_tick: float | None = None
last_failure: float | None = None


async def tick() -> None:
    global last_tick
    async with SessionLocal() as session:
        claims = await outbox.claim(session)
    semaphore = asyncio.Semaphore(2)

    async def send(item: tuple[int, str]) -> None:
        async with semaphore:
            await outbox.deliver(*item, session_factory=SessionLocal)

    await asyncio.gather(*(send(item) for item in claims))
    last_tick = time.monotonic()


async def _loop() -> None:
    global last_failure
    from datetime import timedelta

    from app.modules.telegram.monitor import monitor_tick

    next_monitor = 0.0
    next_cleanup = 0.0
    while not _stop.is_set():
        try:
            if time.monotonic() >= next_monitor:
                await monitor_tick()
                next_monitor = time.monotonic() + 60
            await tick()
            if time.monotonic() >= next_cleanup:
                async with SessionLocal() as session:
                    await session.execute(delete(TelegramPairing).where(TelegramPairing.expires_at < utcnow() - timedelta(days=1)))
                    await session.execute(delete(TelegramUpdate).where(TelegramUpdate.received_at < utcnow() - timedelta(days=7)))
                    await session.commit()
                next_cleanup = time.monotonic() + 3600
        except Exception:
            last_failure = time.monotonic()
            logger.warning("Telegram background tick failed; retrying on the next interval.")
        try:
            await asyncio.wait_for(_stop.wait(), timeout=15)
        except TimeoutError:
            pass


def start_worker() -> None:
    global _task
    if not settings.telegram_worker_enabled or _task is not None:
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())


async def stop_worker() -> None:
    global _task
    if _task is None:
        return
    _stop.set()
    try:
        await asyncio.wait_for(_task, timeout=12)
    except (TimeoutError, asyncio.CancelledError):
        _task.cancel()
    _task = None

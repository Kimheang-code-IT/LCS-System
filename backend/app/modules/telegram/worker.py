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
#: Development polling state: the confirmed update offset and the bot it belongs to.
_poll_offset: int | None = None
_poll_bot_id: int | None = None
_poll_failed_at: float | None = None
#: Safe, secret-free worker health exposed through /health and the Settings card.
_state: dict[str, object] = {
    "enabled": bool(settings.telegram_worker_enabled),
    "mode": settings.telegram_update_mode,
    "status": "starting",
    "lastUpdateAt": None,
    "lastError": None,
}


def health() -> dict[str, object]:
    """Worker status for diagnostics; never includes tokens or message content."""
    return dict(_state)


def _set_state(**values: object) -> None:
    _state.update(values)


async def tick() -> None:
    global last_tick
    async with SessionLocal() as session:
        from app.modules.settings.maintenance import tick as maintenance_tick
        await maintenance_tick(session)
        claims = await outbox.claim(session)
    semaphore = asyncio.Semaphore(2)

    async def send(item: tuple[int, str]) -> None:
        async with semaphore:
            await outbox.deliver(*item, session_factory=SessionLocal)

    await asyncio.gather(*(send(item) for item in claims))
    last_tick = time.monotonic()


async def poll_updates() -> None:
    """Development-only update consumer (TELEGRAM_UPDATE_MODE=polling).

    Exactly one poller runs per deployment (advisory lock) and it disables any
    registered webhook first, so polling and webhook delivery never overlap.
    Production keeps webhook mode; the public HTTPS requirement is untouched.
    """
    global _poll_offset, _poll_bot_id, _poll_failed_at
    from sqlalchemy.exc import IntegrityError

    from app.core.locks import advisory_lock
    from app.modules.telegram import service
    from app.modules.telegram.client import TelegramError

    async with SessionLocal() as session:
        async with advisory_lock(session, "telegram:polling") as acquired:
            if not acquired:
                return
            value = await service.config(session)
            # Pairing/chatbot do not depend on the Admin Alerts switch; only the
            # saved bot token is required.
            if not value.get("botToken"):
                _set_state(status="misconfigured", lastError="missing_bot_token")
                return
            try:
                bot = service.bot_client(value)
                bot_id = value.get("botId")
                if bot_id and bot_id != _poll_bot_id:
                    # Never steal another deployment's webhook implicitly.
                    info = await bot.call("getWebhookInfo")
                    registered = info.get("url") if isinstance(info, dict) else ""
                    if registered and not settings.telegram_allow_webhook_delete:
                        _poll_bot_id, _poll_offset = None, None
                        _set_state(status="misconfigured", lastError="webhook_registered_elsewhere")
                        _warn_once("Telegram polling blocked: a webhook is registered for this bot. Use a separate development bot token, or set TELEGRAM_ALLOW_WEBHOOK_DELETE=true if you own that webhook.", "webhook_block")
                        return
                    if registered:
                        await bot.call("deleteWebhook", {"drop_pending_updates": False})
                    _poll_bot_id, _poll_offset = bot_id, None
                payload: dict = {"timeout": 0, "limit": 50, "allowed_updates": ["message"]}
                if _poll_offset is not None:
                    payload["offset"] = _poll_offset
                updates = await bot.call("getUpdates", payload)
                for update in updates or []:
                    if not isinstance(update, dict):
                        continue
                    try:
                        await service.process_update(session, update)
                        await session.commit()
                    except IntegrityError:
                        # A replayed update after a crash is already recorded; the
                        # offset must still advance or it would block the queue.
                        await session.rollback()
                    if isinstance(update.get("update_id"), int):
                        _poll_offset = update["update_id"] + 1
                _poll_failed_at = None
                _set_state(status="polling", lastUpdateAt=utcnow().isoformat(), lastError=None)
            except TelegramError as exc:
                # 409 webhook_active means another consumer owns the updates;
                # drop the cached webhook state so the next tick re-checks it.
                if exc.code in {"webhook_active", "invalid_bot_token"}:
                    _poll_bot_id, _poll_offset = None, None
                _set_state(status="failed", lastError=exc.code)
                now = time.monotonic()
                if _poll_failed_at is None or now - _poll_failed_at > 120:
                    _poll_failed_at = now
                    logger.warning("Telegram polling failed (%s); retrying on the next interval.", exc.code)
            except Exception:  # noqa: BLE001 - a dev poller must never kill the worker
                _set_state(status="failed", lastError="polling_error")
                now = time.monotonic()
                if _poll_failed_at is None or now - _poll_failed_at > 120:
                    _poll_failed_at = now
                    logger.warning("Telegram polling failed; retrying on the next interval.")


_warned: set[str] = set()


def _warn_once(message: str, key: str) -> None:
    if key in _warned:
        return
    _warned.add(key)
    logger.error(message)


async def _loop() -> None:
    global last_failure
    from datetime import timedelta

    from app.modules.telegram.monitor import monitor_tick

    next_monitor = 0.0
    next_cleanup = 0.0
    next_poll = 0.0
    while not _stop.is_set():
        try:
            if time.monotonic() >= next_monitor:
                await monitor_tick()
                next_monitor = time.monotonic() + 60
            if (settings.telegram_update_mode or "").strip().lower() == "polling" and time.monotonic() >= next_poll:
                await poll_updates()
                next_poll = time.monotonic() + 5
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
    mode = (settings.telegram_update_mode or "webhook").strip().lower()
    production = settings.environment.strip().lower() == "production"
    _set_state(enabled=bool(settings.telegram_worker_enabled), mode=mode, status="starting", lastError=None)
    if not settings.telegram_worker_enabled:
        _set_state(status="disabled")
        logger.info("Telegram worker disabled (TELEGRAM_WORKER_ENABLED=false); no update consumer runs.")
        return
    if _task is not None:
        return
    if production and mode == "polling":
        # Defence in depth: production config validation already refuses polling.
        _set_state(status="misconfigured", lastError="polling_not_allowed_in_production")
        logger.error("Telegram worker refused polling in production; set TELEGRAM_UPDATE_MODE=webhook.")
        return
    if mode == "webhook" and not settings.telegram_public_app_url.strip():
        _set_state(status="misconfigured", lastError="missing_public_app_url")
        logger.error(
            "Telegram webhook mode has no public HTTPS origin: set TELEGRAM_PUBLIC_APP_URL and register the webhook. "
            "Messages will not reach the app until then."
        )
    if mode == "polling":
        logger.info("Telegram worker started: mode=polling (development consumer, advisory-locked).")
        _set_state(status="starting", lastError=None)
    else:
        logger.info("Telegram worker started: mode=webhook http_origin=%s (updates arrive via the registered webhook).", "configured" if settings.telegram_public_app_url.strip() else "missing")
        _set_state(status="webhook", lastError=None if settings.telegram_public_app_url.strip() else "missing_public_app_url")
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

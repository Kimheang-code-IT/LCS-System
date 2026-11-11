from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.bootstrap import reset_all_data
from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context, require_any_permission, require_permission
from app.core.exceptions import ValidationFailed
from app.core.rate_limit import enforce_rate_limit
from app.modules.audit.service import write_audit
from app.modules.settings import service
from app.modules.settings.maintenance import DeploymentResult, MaintenanceChange
from app.modules.settings.schemas import (
    APP_CONFIG_WRITE_SCHEMA,
    APP_INFO_WRITE_SCHEMA,
    RESET_DATA_SCHEMA,
    SEARCH_ASK_SCHEMA,
)
from app.modules.telegram.client import TelegramError

router = APIRouter()


@router.get("/maintenance/status")
async def maintenance_status(response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.config import settings
    from app.modules.settings import maintenance
    response.headers["Cache-Control"] = "no-store"
    if settings.force_maintenance:
        return {"data": maintenance.public(maintenance.DEFAULT)}
    try:
        value = await maintenance.load(session)
    except SQLAlchemyError:
        value = {**maintenance.DEFAULT, "enabled": True}
    return {"data": maintenance.public(value)}


@router.get("/settings/maintenance")
async def get_maintenance(
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.settings import maintenance
    value = await maintenance.load(session)
    return {"data": {**value, **maintenance.public(value), "history": await maintenance.history(session)}}


@router.put("/settings/maintenance")
async def set_maintenance(
    payload: MaintenanceChange,
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.settings import maintenance
    return {"data": await maintenance.change(session, context, payload)}


@router.post("/settings/maintenance/deployment")
async def maintenance_deployment(
    payload: DeploymentResult,
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.settings import maintenance
    return {"data": await maintenance.record_deployment(session, context, payload)}


# --- App info (branding) -----------------------------------------------------
@router.get("/settings/app-info")
async def get_app_info(
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_app_info(session, context)}


@router.patch("/settings/app-info")
async def update_app_info(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    values = APP_INFO_WRITE_SCHEMA.validate(payload, partial=True)
    return {"data": await service.update_app_info(session, context, values)}


@router.post("/settings/app-info/reset")
async def reset_app_info(
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.reset_app_info(session, context)}


# --- App config --------------------------------------------------------------
async def _attach_telegram_admin_state(session: AsyncSession, context: RequestContext, payload: dict) -> dict:
    """Read-only Telegram status for the Settings card: recipient count and the
    configured update consumer. Never returns secrets."""
    from app.core.config import settings

    telegram = payload.get("telegram")
    if not isinstance(telegram, dict):
        return payload
    if not context.has_permission("settings.app_config.view") and not context.has_permission("configuration.manage"):
        return payload
    from app.modules.telegram import service as telegram_service
    from app.modules.telegram.worker import health as telegram_worker_health

    value = await telegram_service.config(session)
    telegram["adminRecipientCount"] = await telegram_service.admin_recipient_count(session, value)
    telegram["updateMode"] = (settings.telegram_update_mode or "webhook").strip().lower()
    telegram["workerEnabled"] = bool(settings.telegram_worker_enabled)
    worker = telegram_worker_health()
    telegram["updateStatus"] = worker.get("status", "starting")
    telegram["lastUpdateAt"] = worker.get("lastUpdateAt")
    telegram["lastError"] = worker.get("lastError")
    return payload


@router.get("/settings/app-config")
async def get_app_config(
    # Any authenticated user needs the redacted localization/format config; the
    # Settings page itself is guarded by ``settings.app_config.view``.
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = service.redact_app_config(await service.get_app_config(session, context))
    if not context.has_permission("settings.app_config.view") and not context.has_permission("configuration.manage"):
        result["telegram"] = {"enabled": bool(result.get("telegram", {}).get("enabled"))}
    else:
        result = await _attach_telegram_admin_state(session, context, result)
    return {"data": result}


@router.patch("/settings/app-config")
async def update_app_config(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    values = APP_CONFIG_WRITE_SCHEMA.validate(payload, partial=True)
    if "telegram" in values:
        await enforce_rate_limit(f"telegram:config:{context.user_id}", limit=10, window_seconds=300)
    result = service.redact_app_config(await service.update_app_config(session, context, values))
    return {"data": await _attach_telegram_admin_state(session, context, result)}


@router.post("/settings/app-config/email/test-connection")
async def test_email_connection(
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service.get_app_config(session, context)
    return {"data": service.connection_result(bool(config.get("email", {}).get("enabled")), "Email")}


@router.post("/settings/app-config/email/send-test")
async def send_test_email(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service.get_app_config(session, context)
    return {"data": service.connection_result(bool(config.get("email", {}).get("enabled")), "Email")}


@router.post("/settings/app-config/telegram/test-connection")
async def test_telegram_connection(
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.telegram.service import test_connection

    await enforce_rate_limit(f"telegram:test:{context.user_id}", limit=5, window_seconds=300)
    return {"data": await test_connection(session)}


@router.post("/settings/app-config/telegram/send-test")
async def send_test_telegram(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """A real alert test to every currently eligible verified recipient."""
    from app.modules.telegram import service

    await enforce_rate_limit(f"telegram:send-test:{context.user_id}", limit=3, window_seconds=300)
    value = await service.config(session)
    if not value.get("enabled"):
        raise ValidationFailed("Enable admin alerts first.")
    recipients = await service.admin_recipients(session, value)
    if not recipients:
        raise ValidationFailed("No verified recipient holds the telegram.alerts.receive permission. Grant it to a role and connect the user's Telegram account from their profile.", {"telegram.alerts": "No eligible recipient"})
    bot = service.client(value)
    delivered = 0
    first_error = None
    for link, _user in recipients:
        try:
            await bot.send_message(link.chat_id, "LCS admin alert delivery test (private chat).")
            delivered += 1
        except TelegramError as exc:
            first_error = first_error or exc
    if delivered == 0 and first_error is not None:
        raise ValidationFailed(f"Telegram could not deliver to any verified recipient: {service.describe(first_error)}", {"telegram.alerts": first_error.code}) from first_error
    return {"data": {"status": "connected", "message": f"Telegram accepted the test alert for {delivered} recipient(s)."}}


@router.post("/settings/app-config/telegram/client/test-connection")
async def test_telegram_client_connection(
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.telegram.service import test_client_connection

    await enforce_rate_limit(f"telegram:client-test:{context.user_id}", limit=5, window_seconds=300)
    return {"data": await test_client_connection(session)}


@router.post("/settings/app-config/telegram/client/send-test")
async def send_test_telegram_client(
    context: RequestContext = Depends(require_any_permission("settings.app_config.update", "configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """A real message to the client group only; the admin bot never sees it."""
    from app.modules.telegram.service import client_sender, config, describe

    await enforce_rate_limit(f"telegram:client-send-test:{context.user_id}", limit=3, window_seconds=300)
    value = await config(session)
    sender, chat_id = client_sender(value)
    try:
        await sender.send_message(chat_id, "LCS client-group delivery test.")
    except TelegramError as exc:
        handle = f"@{value.get('clientBotUsername')}" if value.get("clientBotUsername") else "the bot"
        raise ValidationFailed(
            f"Telegram could not deliver to the client group ({describe(exc)}). Add {handle} to the group as a member with permission to post, then retry.",
            {"telegram.clientGroupId": exc.code},
        ) from exc
    return {"data": {"status": "connected", "message": "Telegram accepted the test message."}}


# --- Danger zone: full data reset -------------------------------------------
@router.post("/settings/reset-data")
async def reset_data(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("settings.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    values = RESET_DATA_SCHEMA.validate(payload)
    if str(values["confirm"]).strip().upper() != "RESET":
        raise ValidationFailed("Typed confirmation is required.", {"confirm": "Type RESET to confirm."})
    await reset_all_data(session)
    await write_audit(
        session,
        context,
        event_type="BUSINESS_DATA_RESET",
        entity_type="settings",
        entity_id=0,
        action="reset_business_data",
    )
    await session.commit()
    await cache.bump("master_data", "reports", "auth")
    return {"data": {"reset": True}}


# --- Global search -----------------------------------------------------------
@router.get("/search")
async def global_search(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await enforce_rate_limit(f"search:user:{context.user_id}", limit=120, window_seconds=60)
    return {"data": await service.search(session, context, q, limit)}


@router.post("/search/ask")
async def search_ask(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await enforce_rate_limit(f"search-ask:user:{context.user_id}", limit=60, window_seconds=60)
    values = SEARCH_ASK_SCHEMA.validate(payload)
    return {"data": await service.answer(session, context, str(values.get("q") or ""), values.get("hitIds") or [])}

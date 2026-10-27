from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
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
from app.modules.settings.schemas import (
    APP_CONFIG_WRITE_SCHEMA,
    APP_INFO_WRITE_SCHEMA,
    RESET_DATA_SCHEMA,
    SEARCH_ASK_SCHEMA,
)

router = APIRouter()


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
    return {"data": service.redact_app_config(await service.update_app_config(session, context, values))}


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
    from app.modules.telegram.service import client, config

    await enforce_rate_limit(f"telegram:send-test:{context.user_id}", limit=3, window_seconds=300)
    value = await config(session)
    if not value.get("adminGroupId"):
        raise ValidationFailed("Verify an admin group first.")
    await client(value).send_message(value["adminGroupId"], "LCS admin-group delivery test.")
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

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context, require_permission
from app.modules.settings import service

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
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.update_app_info(session, context, payload)}


@router.post("/settings/app-info/reset")
async def reset_app_info(
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.reset_app_info(session, context)}


# --- App config --------------------------------------------------------------
@router.get("/settings/app-config")
async def get_app_config(
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_app_config(session, context)}


@router.patch("/settings/app-config")
async def update_app_config(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.update_app_config(session, context, payload)}


@router.post("/settings/app-config/email/test-connection")
async def test_email_connection(
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service.get_app_config(session, context)
    return {"data": service.connection_result(bool(config.get("email", {}).get("enabled")), "Email")}


@router.post("/settings/app-config/email/send-test")
async def send_test_email(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service.get_app_config(session, context)
    return {"data": service.connection_result(bool(config.get("email", {}).get("enabled")), "Email")}


@router.post("/settings/app-config/telegram/test-connection")
async def test_telegram_connection(
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service.get_app_config(session, context)
    return {"data": service.connection_result(bool(config.get("telegram", {}).get("enabled")), "Telegram")}


@router.post("/settings/app-config/telegram/send-test")
async def send_test_telegram(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("configuration.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    config = await service.get_app_config(session, context)
    return {"data": service.connection_result(bool(config.get("telegram", {}).get("enabled")), "Telegram")}


# --- Global search -----------------------------------------------------------
@router.get("/search")
async def global_search(
    q: str = Query(default=""),
    limit: int = 20,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.search(session, context, q, limit)}


@router.post("/search/ask")
async def search_ask(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.answer(session, context, str(payload.get("q") or ""), payload.get("hitIds") or [])}

import json
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.database import get_session
from app.core.deps import get_current_context, require_any_permission
from app.core.exceptions import AccessDenied, ValidationFailed
from app.core.rate_limit import enforce_rate_limit
from app.modules.auth.models import PasswordResetToken, User
from app.modules.telegram import service
from app.modules.telegram.models import NotificationOutbox, TelegramLink, TelegramPairing

router = APIRouter()
manage = require_any_permission("settings.app_config.update", "configuration.manage")
view = require_any_permission("settings.app_config.view", "configuration.manage")


class PasswordProof(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(max_length=128)


class Challenge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge: str = Field(min_length=40, max_length=64)


@router.post("/integrations/telegram/webhook")
async def webhook(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    value = await service.config(session)
    expected = decrypt_secret(value.get("webhookSecret") or "")
    actual = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not expected or not actual or len(actual) > 256 or not secrets.compare_digest(actual, expected):
        raise AccessDenied("Invalid webhook secret.")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise ValidationFailed("Telegram update exceeds the supported size.")
    try:
        update = json.loads(raw)
        if not isinstance(update, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        raise ValidationFailed("Invalid Telegram update.") from None
    try:
        await service.process_update(session, update)
        await session.commit()
    except IntegrityError:
        # Duplicate receipt/identity races fail closed and remain idempotent.
        await session.rollback()
    return {"data": {"accepted": True}}


@router.post("/settings/telegram/webhook")
async def register_webhook(context: RequestContext = Depends(manage), session: AsyncSession = Depends(get_session)) -> dict:
    await enforce_rate_limit(f"telegram:webhook:{context.user_id}", limit=3, window_seconds=300)
    value = await service.locked_config(session)
    origin = service.trusted_origin()
    if not value.get("webhookSecret"):
        value["webhookSecret"] = encrypt_secret(secrets.token_urlsafe(32))
    # Persist before the external call: a delivered update can authenticate immediately.
    value["webhookStatus"] = "pending"
    await service.save_internal(session, value, context)
    await session.commit()
    result = await service.client(value).call("setWebhook", {"url": f"{origin}/api/v1/integrations/telegram/webhook", "secret_token": decrypt_secret(value["webhookSecret"]), "allowed_updates": ["message"], "max_connections": 2})
    if result is not True:
        raise ValidationFailed("Telegram did not accept the webhook.")
    info = await service.client(value).call("getWebhookInfo")
    current = await service.locked_config(session)
    if current.get("botToken") != value.get("botToken") or current.get("webhookSecret") != value.get("webhookSecret") or not current.get("enabled"):
        raise ValidationFailed("Telegram configuration changed during webhook verification.")
    current["webhookStatus"] = "registered" if info.get("url") == f"{origin}/api/v1/integrations/telegram/webhook" else "not_verified"
    await service.save_internal(session, current, context)
    await session.commit()
    return {"data": {"status": current["webhookStatus"], "pendingUpdates": info.get("pending_update_count", 0)}}


@router.post("/settings/telegram/group/pair")
async def group_pair(context: RequestContext = Depends(manage), session: AsyncSession = Depends(get_session)) -> dict:
    await enforce_rate_limit(f"telegram:group:{context.user_id}", limit=3, window_seconds=600)
    return {"data": await service.create_pairing(session, context, "GROUP")}


@router.get("/settings/telegram/group/candidate")
async def group_candidate(context: RequestContext = Depends(manage), session: AsyncSession = Depends(get_session)) -> dict:
    row = (await session.execute(select(TelegramPairing).where(TelegramPairing.user_id == context.user_id, TelegramPairing.kind == "GROUP"))).scalar_one_or_none()
    eligible = row and service.aware(row.expires_at) > service.utcnow()
    return {"data": {"name": row.candidate_name if eligible else None, "verified": bool(eligible and row.candidate_id)}}


@router.post("/settings/telegram/group/confirm")
async def group_confirm(payload: Challenge, context: RequestContext = Depends(manage), session: AsyncSession = Depends(get_session)) -> dict:
    await service.confirm_group(session, context, payload.challenge)
    return {"data": {"confirmed": True}}


@router.delete("/settings/telegram/group")
async def group_disconnect(context: RequestContext = Depends(manage), session: AsyncSession = Depends(get_session)) -> dict:
    value = await service.locked_config(session)
    value.update(adminGroupId=None, adminGroupName="", adminGroupVerifiedAt="")
    await service.save_internal(session, value, context)
    await session.commit()
    return {"data": {"disconnected": True}}


@router.get("/auth/me/telegram")
async def my_link(context: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)) -> dict:
    link = await session.get(TelegramLink, context.user_id)
    return {"data": {"connected": bool(link), "displayName": link.display_name if link else None, "verifiedAt": link.verified_at.isoformat() if link else None, "blocked": bool(link and link.blocked_at)}}


@router.post("/auth/me/telegram/pair")
async def private_pair(payload: PasswordProof, context: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)) -> dict:
    await enforce_rate_limit(f"telegram:private:{context.user_id}", limit=3, window_seconds=600)
    await session.execute(select(User.id).where(User.id == context.user_id).with_for_update())
    await service.reauthenticate(session, context.user_id, payload.current_password)
    if await session.get(TelegramLink, context.user_id):
        raise ValidationFailed("Disconnect the current Telegram account before pairing another.")
    return {"data": await service.create_pairing(session, context, "PRIVATE")}


@router.post("/auth/me/telegram/disconnect")
async def private_disconnect(payload: PasswordProof, context: RequestContext = Depends(get_current_context), session: AsyncSession = Depends(get_session)) -> dict:
    await enforce_rate_limit(f"telegram:private:{context.user_id}", limit=3, window_seconds=600)
    await session.execute(select(User.id).where(User.id == context.user_id).with_for_update())
    await service.reauthenticate(session, context.user_id, payload.current_password)
    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == context.user_id, PasswordResetToken.used_at.is_(None)).values(used_at=service.utcnow()))
    pending = (await session.execute(select(NotificationOutbox).where(NotificationOutbox.category == "recovery", NotificationOutbox.status.in_(["PENDING", "PROCESSING"])))).scalars().all()
    for item in pending:
        if item.payload.get("user_id") == context.user_id:
            item.status, item.sensitive_payload, item.claim_token = "CANCELLED", None, None
    link = await session.get(TelegramLink, context.user_id)
    if link:
        from app.modules.telegram.outbox import enqueue_private

        await enqueue_private(session, context.user_id, "TELEGRAM_UNLINKED")
        await session.delete(link)
    await session.execute(delete(TelegramPairing).where(TelegramPairing.user_id == context.user_id))
    await session.commit()
    return {"data": {"disconnected": True}}


@router.get("/settings/telegram/history")
async def history(category: str | None = None, status: str | None = None, destination_type: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), context: RequestContext = Depends(view), session: AsyncSession = Depends(get_session)) -> dict:
    filters = []
    for column, value in ((NotificationOutbox.category, category), (NotificationOutbox.status, status), (NotificationOutbox.destination_type, destination_type)):
        if value:
            filters.append(column == value)
    if date_from:
        filters.append(NotificationOutbox.created_at >= date_from)
    if date_to:
        filters.append(NotificationOutbox.created_at < date_to)
    total = await session.scalar(select(func.count()).select_from(NotificationOutbox).where(*filters))
    rows = (await session.execute(select(NotificationOutbox).where(*filters).order_by(NotificationOutbox.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [{"id": row.id, "createdAt": row.created_at.isoformat(), "category": row.category, "event": row.event_type, "destination": row.destination_type, "status": row.status, "attempts": row.attempts, "error": row.last_error, "canRetry": row.status == "FAILED" and row.category != "recovery" and not row.sensitive_payload and service.aware(row.expires_at) > service.utcnow()} for row in rows]
    sent = await session.scalar(select(func.max(NotificationOutbox.sent_at)))
    failed = await session.scalar(select(func.max(NotificationOutbox.updated_at)).where(NotificationOutbox.status == "FAILED"))
    linked = await session.scalar(select(func.count()).select_from(TelegramLink))
    return {"data": {"items": items, "meta": {"page": page, "page_size": page_size, "total": total}, "lastSentAt": sent.isoformat() if sent else None, "lastFailedAt": failed.isoformat() if failed else None, "linkedUsers": linked}}


@router.post("/settings/telegram/history/{notification_id}/retry")
async def retry(notification_id: int, context: RequestContext = Depends(manage), session: AsyncSession = Depends(get_session)) -> dict:
    await enforce_rate_limit(f"telegram:retry:{context.user_id}", limit=5, window_seconds=300)
    row = (await session.execute(select(NotificationOutbox).where(NotificationOutbox.id == notification_id).with_for_update())).scalar_one_or_none()
    if not row or row.status != "FAILED" or row.category == "recovery" or row.sensitive_payload or service.aware(row.expires_at) <= service.utcnow() or row.updated_at and service.aware(row.updated_at) > service.utcnow() - timedelta(minutes=1):
        raise ValidationFailed("This notification cannot be retried.")
    row.status, row.attempts, row.last_error = "PENDING", 0, None
    row.next_attempt_at = service.utcnow()
    await session.commit()
    return {"data": {"queued": True}}

"""Transactional queue; no network call belongs in a business transaction."""

import json
import secrets
from datetime import timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.database import SessionLocal, utcnow
from app.modules.auth.models import PasswordResetToken, User
from app.modules.telegram import service
from app.modules.telegram.client import TelegramError
from app.modules.telegram.models import NotificationOutbox, TelegramLink

SEVERITY = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}


def policy(value: dict, category: str) -> dict:
    return {**service.DEFAULT_RULES[category], **(value.get("rules", {}).get(category) or {})}


async def enqueue_private(session: AsyncSession, user_id: int, event: str, *, token: str | None = None, reset_id: int | None = None) -> NotificationOutbox | None:
    value = await service.config(session)
    link = await session.get(TelegramLink, user_id)
    if not value.get("enabled") or not link or link.blocked_at or link.bot_id != value.get("botId"):
        return None
    if token and not policy(value, "recovery")["enabled"]:
        return None
    messages = {
        "PASSWORD_RESET_REQUESTED": "LCS password recovery. This link expires in 15 minutes. If you did not request it, ignore this message.",
        "PASSWORD_CHANGED": "Your LCS password was changed. All sessions were revoked. Contact your administrator if this was unexpected.",
        "PASSWORD_RESET_COMPLETED": "Your LCS password was reset. All sessions were revoked. Sign in normally with your new password.",
        "TELEGRAM_LINKED": "This private Telegram account is now linked to your LCS account.",
        "TELEGRAM_UNLINKED": "This Telegram account was disconnected from LCS. It can no longer receive password recovery links.",
        "SESSIONS_REVOKED": "Your LCS sessions were revoked. Sign in again. Contact your administrator if this was unexpected.",
    }
    if event not in messages or (token is not None and event != "PASSWORD_RESET_REQUESTED"):
        raise ValueError("Unsupported private notification")
    text = messages[event]
    sensitive = None
    if token:
        sensitive = encrypt_secret(json.dumps({"text": f"{text}\n{service.trusted_origin()}/auth/reset-password#token={token}"}))
    row = NotificationOutbox(event_type=event, category="recovery" if token else "private", severity="INFO", destination_type="PRIVATE", destination_reference=link.chat_id, payload={"text": "Recovery link (redacted)" if token else text, "user_id": user_id, "bot_id": value.get("botId"), "reset_id": reset_id}, sensitive_payload=sensitive, expires_at=utcnow() + timedelta(minutes=12 if token else 1440), max_attempts=policy(value, "recovery")["maxAttempts"], deduplication_key=f"private:{event}:{user_id}:{reset_id or secrets.token_hex(16)}")
    session.add(row)
    return row


async def enqueue_admin(session: AsyncSession, event: str, category: str, severity: str, *, reference: str, summary: str, dedup: str) -> NotificationOutbox | None:
    value = await service.config(session)
    rule = policy(value, category)
    if not value.get("enabled") or not value.get("adminGroupId") or not rule["enabled"] or SEVERITY[severity] < SEVERITY[rule["minimumSeverity"]]:
        return None
    if await session.scalar(select(NotificationOutbox.id).where(NotificationOutbox.deduplication_key == dedup)):
        return None
    if category in {"security", "backup"} and event != "BACKUP_SUCCEEDED" and event != "BACKUP_FAILED":
        recent = await session.scalar(select(NotificationOutbox.id).where(NotificationOutbox.event_type == event, NotificationOutbox.category == category, NotificationOutbox.created_at > utcnow() - timedelta(minutes=rule["cooldownMinutes"])))
        if recent:
            return None
    # Producers pass controlled summaries, never exceptions, request bodies or credentials.
    row = NotificationOutbox(event_type=event, category=category, severity=severity, destination_type="ADMIN", destination_reference=value["adminGroupId"], payload={"text": f"LCS {category.title()} Alert\nSeverity: {severity}\nEvent: {summary[:600]}\nReference: {reference[:100]}\nTime: {utcnow().isoformat()}", "bot_id": value.get("botId")}, expires_at=utcnow() + timedelta(days=1), max_attempts=rule["maxAttempts"], deduplication_key=dedup)
    session.add(row)
    await session.flush()
    return row


async def claim(session: AsyncSession, *, batch_size: int = 5) -> list[tuple[int, str]]:
    now = utcnow()
    # Purge ciphertext even for terminal rows. Sensitive retries never outlive delivery TTL.
    await session.execute(update(NotificationOutbox).where(NotificationOutbox.expires_at <= now).values(sensitive_payload=None))
    rows = (await session.execute(select(NotificationOutbox).where(or_(and_(NotificationOutbox.status == "PENDING", NotificationOutbox.next_attempt_at <= now), and_(NotificationOutbox.status == "PROCESSING", NotificationOutbox.locked_until <= now))).order_by(NotificationOutbox.next_attempt_at, NotificationOutbox.id).limit(min(batch_size, 10)).with_for_update(skip_locked=True))).scalars().all()
    result = []
    for row in rows:
        if service.aware(row.expires_at) <= now or row.attempts >= row.max_attempts:
            row.status = "CANCELLED" if service.aware(row.expires_at) <= now else "FAILED"
            row.sensitive_payload = None
            row.last_error = "expired" if row.status == "CANCELLED" else "attempt_limit"
            continue
        row.status = "PROCESSING"
        row.attempts += 1
        row.claim_token = secrets.token_hex(16)
        row.locked_until = now + timedelta(minutes=2)
        result.append((row.id, row.claim_token))
    await session.commit()
    return result


async def deliver(row_id: int, claim_token: str, *, session_factory=SessionLocal) -> None:
    async with session_factory() as session:
        row = await session.get(NotificationOutbox, row_id)
        if not row or row.status != "PROCESSING" or row.claim_token != claim_token:
            return
        session.expunge(row)
        value = await service.config(session)
        eligible = value.get("enabled") and value.get("botId") == row.payload.get("bot_id") and service.aware(row.expires_at) > utcnow()
        if row.destination_type == "ADMIN":
            eligible = eligible and value.get("adminGroupId") == row.destination_reference and row.category in service.DEFAULT_RULES and row.category != "recovery" and not row.sensitive_payload and policy(value, row.category)["enabled"]
        else:
            link = await session.get(TelegramLink, row.payload.get("user_id"))
            user = await session.get(User, row.payload.get("user_id"))
            eligible = eligible and user is not None and user.status.upper() == "ACTIVE" and (row.event_type == "TELEGRAM_UNLINKED" or link is not None and not link.blocked_at and link.chat_id == row.destination_reference)
            if row.category == "recovery":
                reset = await session.get(PasswordResetToken, row.payload.get("reset_id"))
                eligible = eligible and policy(value, "recovery")["enabled"] and reset is not None and reset.used_at is None and service.aware(reset.expires_at) > utcnow()
        if not eligible:
            row.status, row.last_error, row.sensitive_payload = "CANCELLED", "destination_ineligible", None
            await session.execute(update(NotificationOutbox).where(NotificationOutbox.id == row_id, NotificationOutbox.claim_token == claim_token, NotificationOutbox.status == "PROCESSING").values(status=row.status, last_error=row.last_error, sensitive_payload=None, claim_token=None, locked_until=None))
            await session.commit()
            return
        try:
            text = json.loads(decrypt_secret(row.sensitive_payload))["text"] if row.sensitive_payload else row.payload["text"]
            # The claim transaction already committed. Delivery has a bounded timeout.
            await service.client(value).send_message(row.destination_reference, text)
            row.status, row.sent_at, row.last_error = "SENT", utcnow(), None
            row.sensitive_payload = None
        except TelegramError as exc:
            row.last_error = exc.code
            delay = max(exc.retry_after, min(30 * 2 ** (row.attempts - 1), 3600))
            next_attempt = utcnow() + timedelta(seconds=delay)
            retry = exc.retryable and row.attempts < row.max_attempts and next_attempt < service.aware(row.expires_at)
            row.status = "PENDING" if retry else "FAILED"
            row.next_attempt_at = next_attempt
            if not retry:
                row.sensitive_payload = None
            if exc.code == "destination_blocked" and row.destination_type == "PRIVATE" and link:
                link.blocked_at = utcnow()
        except Exception:
            # Encryption/configuration faults fail closed without logging sensitive bodies.
            row.status, row.last_error, row.sensitive_payload = "FAILED", "delivery_configuration_error", None
        row.claim_token, row.locked_until = None, None
        # A disconnect or a reclaimed lease must not be overwritten by a stale sender.
        await session.execute(update(NotificationOutbox).where(NotificationOutbox.id == row_id, NotificationOutbox.claim_token == claim_token, NotificationOutbox.status == "PROCESSING").values(status=row.status, sent_at=row.sent_at, last_error=row.last_error, sensitive_payload=row.sensitive_payload, next_attempt_at=row.next_attempt_at, claim_token=None, locked_until=None))
        await session.commit()

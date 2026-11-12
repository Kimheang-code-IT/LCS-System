"""Private-chat chatbot commands. Authorization is resolved per message.

A Telegram link (or a pairing record) never grants access by itself: every
command re-checks the bot identity, the active LCS user and the current
``telegram.chatbot.use`` Casbin permission. Replies contain no business or
account data beyond the caller's own connection state.
"""

from __future__ import annotations

import re

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.modules.audit.service import write_audit
from app.modules.auth.models import PasswordResetToken, User
from app.modules.telegram import service
from app.modules.telegram.models import NotificationOutbox, TelegramLink, TelegramPairing

PUBLIC_START = (
    "LCS Freight Forwarding bot. Generate a verification code in your LCS profile "
    "(Profile → Telegram), then send /verify CODE here."
)
DENIED = "Telegram chatbot access is not enabled for this LCS account. Contact an administrator."
TOO_MANY = "Too many attempts. Wait a few minutes and try again."
INVALID_CODE = "Invalid or expired verification code."
ALLOWED_USERS = "Available commands:\n/help — show this list\n/status — show your Telegram connection status\n/disconnect — unlink this Telegram account"


async def start(session: AsyncSession, value: dict, *, chat: dict, sender: dict, text: str) -> str:
    resolved = await service.chatbot_user(session, value, sender["id"])
    if resolved is None:
        return PUBLIC_START
    user, link = resolved
    return f"Connected to LCS as {user.display_name or user.username}. Send /help to see available commands."


async def help_command(session: AsyncSession, value: dict, *, chat: dict, sender: dict, text: str) -> str:
    resolved = await service.chatbot_user(session, value, sender["id"])
    if resolved is None:
        return PUBLIC_START
    return ALLOWED_USERS


async def verify_command(session: AsyncSession, value: dict, *, chat: dict, sender: dict, text: str) -> str:
    """Consume an LCS-issued 6-digit code from the sender's private chat."""
    parts = text.split()
    if chat.get("type") != "private" or int(chat.get("id") or 0) != int(sender.get("id") or 0):
        return "Verification is only available in a private chat with the bot."
    if len(parts) != 2 or not re.fullmatch(r"\d{6}", parts[1]):
        return "Send /verify followed by the 6-digit code from your LCS profile."
    code = parts[1]
    # Per-Telegram-account and per-code budgets stop guessing at scale; they
    # stay active even when the general rate limiter is disabled.
    if not await service.within_rate_budget(f"telegram:verify:{sender['id']}", limit=5, window_seconds=600):
        return TOO_MANY
    if not await service.within_rate_budget(f"telegram:verify-code:{service.digest(code)}", limit=10, window_seconds=300):
        return TOO_MANY

    from app.core.authorization import service as authorization

    pairing = (await session.execute(select(TelegramPairing).where(TelegramPairing.token_hash == service.digest(code)).with_for_update())).scalar_one_or_none()
    if (
        pairing is None or pairing.kind != "PRIVATE" or pairing.used_at is not None
        or service.aware(pairing.expires_at) <= utcnow() or pairing.bot_id != value.get("botId")
    ):
        return INVALID_CODE
    user = await session.get(User, pairing.user_id)
    if user is None or user.status is None or user.status.upper() != "ACTIVE":
        return "Your LCS account is not active. Contact an administrator."
    if not authorization.can(user.id, service.CHATBOT_PERMISSION):
        return DENIED
    if await session.get(TelegramLink, user.id):
        return "This LCS account already has a connected Telegram account. Disconnect it first."
    existing = (await session.execute(select(TelegramLink).where(TelegramLink.telegram_user_id == sender["id"]))).scalar_one_or_none()
    if existing is not None:
        return "This Telegram account is already linked to another LCS account."
    session.add(TelegramLink(
        user_id=user.id,
        telegram_user_id=sender["id"],
        bot_id=value["botId"],
        chat_id=chat["id"],
        display_name=str(sender.get("username") or sender.get("first_name") or "Telegram")[:255],
    ))
    pairing.used_at = utcnow()
    await session.flush()
    from app.modules.telegram.outbox import enqueue_private

    await enqueue_private(session, user.id, "TELEGRAM_LINKED")
    await write_audit(session, None, event_type="TELEGRAM_VERIFIED", entity_type="user", entity_id=user.id, action="verify", metadata={"bot_id": value["botId"]})
    return "Verification successful. This Telegram account is now connected to LCS. Send /help for commands."


async def status_command(session: AsyncSession, value: dict, *, chat: dict, sender: dict, text: str) -> str:
    resolved = await service.chatbot_user(session, value, sender["id"])
    if resolved is None:
        return DENIED
    user, link = resolved
    stamp = service.aware(link.verified_at).isoformat() if link.verified_at else "unknown"
    bot = value.get("botUsername") or "LCS bot"
    return f"LCS Telegram status\nUser: {user.display_name or user.username}\nBot: @{bot.lstrip('@')}\nVerified: {stamp}\nAccess: enabled"


async def disconnect_command(session: AsyncSession, value: dict, *, chat: dict, sender: dict, text: str) -> str:
    resolved = await service.chatbot_user(session, value, sender["id"])
    if resolved is None:
        return DENIED
    user, link = resolved
    # Revoking from the verified private chat also cancels pending recovery links.
    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=utcnow()))
    pending = (await session.execute(select(NotificationOutbox).where(NotificationOutbox.category == "recovery", NotificationOutbox.status.in_(["PENDING", "PROCESSING"])))).scalars().all()
    for item in pending:
        if item.payload.get("user_id") == user.id:
            item.status, item.sensitive_payload, item.claim_token = "CANCELLED", None, None
    from app.modules.telegram.outbox import enqueue_private

    await enqueue_private(session, user.id, "TELEGRAM_UNLINKED")
    await session.delete(link)
    await session.execute(delete(TelegramPairing).where(TelegramPairing.user_id == user.id))
    await write_audit(session, None, event_type="TELEGRAM_UNLINKED", entity_type="user", entity_id=user.id, action="disconnect", metadata={"via": "chatbot"})
    return "This Telegram account was disconnected from LCS. You can reconnect from your LCS profile."


COMMANDS = {
    "/start": start,
    "/help": help_command,
    "/verify": verify_command,
    "/status": status_command,
    "/disconnect": disconnect_command,
}


async def handle(session: AsyncSession, value: dict, *, chat: dict, sender: dict, text: str) -> str | None:
    """Reply text for a supported command, or None when it is not one of ours."""
    parts = text.split()
    if not parts:
        return None
    command = parts[0].split("@")[0]
    handler = COMMANDS.get(command)
    if handler is None:
        return None
    # Private chat with the bot only; groups and forwarded chats are ignored.
    if chat.get("type") != "private" or chat.get("id") != sender.get("id"):
        return None
    return await handler(session, value, chat=chat, sender=sender, text=text)

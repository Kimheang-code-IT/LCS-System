"""Settings and challenge verification; Telegram never authorizes business changes."""

import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import RequestContext
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.database import utcnow
from app.core.exceptions import AccessDenied, ValidationFailed
from app.core.security import verify_password
from app.modules.audit.service import write_audit
from app.modules.auth.models import User, UserCredential
from app.modules.settings import service as settings_service
from app.modules.settings.models import AppSetting
from app.modules.telegram.client import TelegramClient, TelegramError
from app.modules.telegram.models import NotificationOutbox, TelegramLink, TelegramPairing, TelegramUpdate

READONLY = {"botId", "botDisplayName", "botUsername", "connectionStatus", "lastVerifiedAt", "lastTestedAt", "lastTestMessage", "adminGroupId", "adminGroupName", "adminGroupVerifiedAt", "webhookSecret", "webhookStatus", "webhookUrl", "botTokenConfigured", "destinations",
            "clientBotId", "clientBotUsername", "clientBotDisplayName", "clientConnectionStatus", "clientLastVerifiedAt", "clientLastTestedAt", "clientLastTestMessage", "clientBotTokenConfigured"}
#: The client group's only events are committed Service Order lifecycle actions.
CLIENT_EVENTS = (
    "SERVICE_ORDER_CREATED",
    "SERVICE_ORDER_UPDATED",
    "SERVICE_ORDER_STATUS_CHANGED",
    "SERVICE_ORDER_FINISHED",
    "SERVICE_ORDER_CANCELLED",
)
DEFAULT_RULES = {
    name: {"enabled": False, "destination": "PRIVATE" if name == "recovery" else "ADMIN", "minimumSeverity": "INFO" if name in {"recovery", "backup"} else "WARNING", "cooldownMinutes": 15, "notifyOnRecovery": True, "maxAttempts": 3}
    for name in ("security", "backup", "system", "recovery")
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def trusted_origin() -> str:
    origin = settings.telegram_public_app_url.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise ValidationFailed(
            "Webhook registration needs a public HTTPS application origin. Set TELEGRAM_PUBLIC_APP_URL to the deployed https origin (for example https://lcs.example); localhost cannot receive Telegram webhooks. Saving settings and testing the bot token do not require it."
        )
    return origin


async def config(session: AsyncSession) -> dict:
    stored, _ = await settings_service._current_app_config(session)
    return merged_client_config({**settings_service.DEFAULT_APP_CONFIG["telegram"], **(stored.get("telegram") or {})})


async def locked_config(session: AsyncSession) -> dict:
    row = (await session.execute(select(AppSetting).where(AppSetting.setting_key == "telegram").with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    return merged_client_config({**settings_service.DEFAULT_APP_CONFIG["telegram"], **(row.setting_value if row else {})})


def merged_client_config(value: dict) -> dict:
    """Stored per-event toggles override defaults; unset events stay usable."""
    value = dict(value)
    value["clientEvents"] = {**settings_service.DEFAULT_APP_CONFIG["telegram"]["clientEvents"], **(value.get("clientEvents") or {})}
    return value


async def save_internal(session: AsyncSession, value: dict, context: RequestContext | None = None) -> None:
    if value.get("botToken"):
        value = {**value, "botToken": encrypt_secret(decrypt_secret(value["botToken"]))}
    await settings_service._upsert_setting(session, "telegram", "telegram", value, context, "Telegram configuration; credentials encrypted.")
    stored, _ = await settings_service._current_app_config(session)
    await settings_service._mirror_legacy_settings(session, settings_service.APP_CONFIG_COLLECTION, {**stored, "telegram": value})


def prepare_patch(patch: dict, current: dict) -> dict:
    clean = {key: value for key, value in patch.items() if key not in READONLY}
    if clean.pop("removeBotToken", False):
        clean["botToken"] = ""
        clean["enabled"] = False
    elif clean.get("botToken"):
        # Accept only literal tokens from users; encrypted values are server owned.
        try:
            TelegramClient(str(clean["botToken"]))
        except TelegramError:
            raise ValidationFailed("Invalid Telegram bot token.", {"telegram.botToken": "Enter the BotFather token."}) from None
        clean["botToken"] = encrypt_secret(str(clean["botToken"]))
    else:
        clean.pop("botToken", None)
    if "botToken" in clean and clean["botToken"] != current.get("botToken"):
        clean.update(botId=None, botUsername="", botDisplayName="", connectionStatus="not_tested", lastVerifiedAt="", adminGroupId=None, adminGroupName="", adminGroupVerifiedAt="", webhookSecret=encrypt_secret(secrets.token_urlsafe(32)), webhookStatus="not_registered")
    if clean.get("clientBotToken"):
        # A blank field means "keep the stored token"; a literal client token is
        # validated like the main one and encrypted before it is stored.
        try:
            TelegramClient(str(clean["clientBotToken"]))
        except TelegramError:
            raise ValidationFailed("Invalid Telegram bot token.", {"telegram.clientBotToken": "Enter the BotFather token."}) from None
        clean["clientBotToken"] = encrypt_secret(str(clean["clientBotToken"]))
    else:
        clean.pop("clientBotToken", None)
    if "clientBotToken" in clean and clean["clientBotToken"] != current.get("clientBotToken"):
        clean.update(clientBotId=None, clientBotUsername="", clientBotDisplayName="", clientConnectionStatus="not_tested", clientLastVerifiedAt="", clientLastTestedAt="")
    if "clientGroupId" in clean:
        raw = str(clean.get("clientGroupId") or "").strip().replace(" ", "")
        if raw:
            try:
                chat_id = int(raw)
                assert chat_id < 0 and abs(chat_id) < 2**53 and not raw.startswith(("+", "-0"))
            except (ValueError, AssertionError):
                raise ValidationFailed("Enter the negative numeric Telegram group chat id.", {"telegram.clientGroupId": "Invalid group chat id"}) from None
            clean["clientGroupId"] = str(chat_id)
        else:
            clean["clientGroupId"] = ""
    if "clientEvents" in clean:
        events = clean["clientEvents"]
        if not isinstance(events, dict) or set(events) - set(CLIENT_EVENTS) or any(type(v) is not bool for v in events.values()):
            raise ValidationFailed("Invalid Service Order notification events.", {"telegram.clientEvents": "Invalid events"})
        clean["clientEvents"] = events
    if "rules" in clean:
        rules = clean["rules"]
        if not isinstance(rules, dict) or set(rules) - set(DEFAULT_RULES):
            raise ValidationFailed("Invalid Telegram alert categories.")
        normalized = {}
        for category, rule in rules.items():
            if not isinstance(rule, dict):
                raise ValidationFailed("Invalid Telegram alert rule.")
            rule = {**DEFAULT_RULES[category], **rule}
            if rule["destination"] != DEFAULT_RULES[category]["destination"]:
                raise ValidationFailed("Recovery requires a private verified chat; alerts belong to the admin bot.")
            if rule["minimumSeverity"] not in {"INFO", "WARNING", "CRITICAL"}:
                raise ValidationFailed("Invalid severity.")
            for field, low, high in (("cooldownMinutes", 1, 1440), ("maxAttempts", 1, 5)):
                if type(rule[field]) is not int or not low <= rule[field] <= high:
                    raise ValidationFailed("Invalid Telegram retry or cooldown value.")
            for field in ("enabled", "notifyOnRecovery"):
                if type(rule[field]) is not bool:
                    raise ValidationFailed("Invalid Telegram alert toggle.")
            normalized[category] = rule
        clean["rules"] = normalized
    return clean


def bot_client(value: dict) -> TelegramClient:
    """Transport for pairing and chatbot replies.

    Deliberately independent of the Admin Alerts master switch: connecting a
    profile and answering /start,/help,/status,/disconnect must work before any
    alert routing is enabled. The admin-alert gate stays in ``client()``.
    """
    token = value.get("botToken")
    if not token:
        raise ValidationFailed("Save the shared Telegram bot token first.")
    return TelegramClient(decrypt_secret(token))


def client(value: dict) -> TelegramClient:
    if not value.get("enabled") or not value.get("botToken"):
        raise ValidationFailed("Telegram is disabled or has no bot token.")
    return TelegramClient(decrypt_secret(value["botToken"]))


def client_sender(value: dict) -> tuple[TelegramClient, int]:
    """The client group's bot and chat: a separate token when one is stored,
    otherwise the same credential as the admin bot (shared reference)."""
    if not value.get("clientEnabled"):
        raise ValidationFailed("Client group notifications are disabled.")
    token = value.get("clientBotToken") or value.get("botToken")
    if not token:
        raise ValidationFailed("No bot token is configured for the client group.", {"telegram.clientBotToken": "Required"})
    try:
        chat_id = int(str(value.get("clientGroupId") or ""))
    except (TypeError, ValueError):
        raise ValidationFailed("Configure the client group chat id first.", {"telegram.clientGroupId": "Required"}) from None
    return TelegramClient(decrypt_secret(token)), chat_id


def test_client_sender(value: dict) -> TelegramClient:
    """getMe for the client credential, without requiring a chat id."""
    token = value.get("clientBotToken") or value.get("botToken")
    if not token:
        raise ValidationFailed("No bot token is configured for the client group.", {"telegram.clientBotToken": "Required"})
    return TelegramClient(decrypt_secret(token))


def describe(exc: TelegramError) -> str:
    """Human-readable verification result; never echoes token-bearing details."""
    return {
        "invalid_bot_token": "Telegram rejected the bot token. Copy the current token from BotFather and save it again.",
        "invalid_destination": "Telegram could not find this chat. Start the chat with the bot and check the chat id.",
        "destination_blocked": "The bot was blocked or removed from this chat. Open the chat and start the bot again.",
        "rate_limited": "Telegram is rate limiting requests. Wait a minute and test again.",
        "webhook_active": "A webhook is still registered for this bot. Polling removes it automatically; retry in a few seconds.",
        "transport_unavailable": "Telegram API is unreachable from the server. Check outbound HTTPS connectivity and retry.",
        "telegram_unavailable": "Telegram API is temporarily unavailable. Retry shortly.",
        "invalid_response": "Telegram returned an unexpected response. Retry shortly.",
    }.get(exc.code, "Telegram verification failed. Retry shortly.")


async def test_client_connection(session: AsyncSession) -> dict:
    value = await config(session)
    bot_name = ""
    try:
        sender = test_client_sender(value)
        identity = await sender.get_me()
        bot_name = str(identity.get("username") or "")
        message = "Client bot verified by getMe."
        group_id = str(value.get("clientGroupId") or "").strip()
        if group_id:
            # Only a group chat the bot can actually post into counts as connected.
            chat = await sender.call("getChat", {"chat_id": int(group_id)})
            if chat.get("id") != int(group_id) or chat.get("type") not in {"group", "supergroup"}:
                raise ValidationFailed("The client destination must be a Telegram group the bot can access.", {"telegram.clientGroupId": "Not a group chat"})
            message = "Client bot verified; the group is reachable."
        value.update(
            clientBotId=identity["id"],
            clientBotDisplayName=str(identity.get("first_name", ""))[:255],
            clientBotUsername=bot_name[:100],
            clientConnectionStatus="connected",
            clientLastVerifiedAt=utcnow().isoformat(),
            clientLastTestMessage=message,
        )
        if value.get("clientBotToken"):
            value["clientBotToken"] = encrypt_secret(decrypt_secret(value["clientBotToken"]))
    except ValidationFailed as exc:
        value.update(clientConnectionStatus="failed", clientLastTestMessage=exc.message, clientLastVerifiedAt="", clientBotId=None)
    except TelegramError as exc:
        handle = f"@{bot_name}" if bot_name else "the bot"
        detail = describe(exc)
        if str(value.get("clientGroupId") or "").strip() and exc.code in {"invalid_destination", "chat_not_found", "not_enough_rights_to_send", "destination_blocked"}:
            detail = f"Telegram could not reach this group. Add {handle} to the group as a member with permission to post, send a message there, then test again. Supergroup ids start with -100."
        value.update(clientConnectionStatus="failed", clientLastTestMessage=detail, clientLastVerifiedAt="", clientBotId=None)
    value["clientLastTestedAt"] = utcnow().isoformat()
    current = await locked_config(session)
    stored_token = decrypt_secret(current.get("clientBotToken") or "") if current.get("clientBotToken") else ""
    new_token = decrypt_secret(value.get("clientBotToken") or "") if value.get("clientBotToken") else ""
    if current.get("clientEnabled") is not value.get("clientEnabled") or stored_token != new_token or str(current.get("clientGroupId") or "") != str(value.get("clientGroupId") or ""):
        raise ValidationFailed("Client group configuration changed during verification. Test it again.")
    fields = {key: value[key] for key in ("clientBotId", "clientBotDisplayName", "clientBotUsername", "clientConnectionStatus", "clientLastVerifiedAt", "clientLastTestedAt", "clientLastTestMessage", "clientBotToken") if key in value}
    await save_internal(session, {**current, **fields})
    await session.commit()
    return {"status": value["clientConnectionStatus"], "message": value["clientLastTestMessage"], "lastTestedAt": value["clientLastTestedAt"]}


CHATBOT_PERMISSION = "telegram.chatbot.use"
ALERTS_PERMISSION = "telegram.alerts.receive"


async def verified_link(session: AsyncSession, user_id: int, value: dict) -> TelegramLink | None:
    """The user's verified private link for the current bot, or None."""
    link = await session.get(TelegramLink, user_id)
    if link is None or link.blocked_at or not value.get("botId") or link.bot_id != value.get("botId"):
        return None
    return link


async def chatbot_user(session: AsyncSession, value: dict, telegram_user_id: int) -> tuple[User, TelegramLink] | None:
    """Resolve a Telegram sender to an active, permitted LCS user.

    Every condition is checked per message: a link or a pairing record never
    grants access on its own, and revoking the permission takes effect now.
    """
    from app.core.authorization import service as authorization

    link = (await session.execute(select(TelegramLink).where(TelegramLink.telegram_user_id == telegram_user_id))).scalar_one_or_none()
    if link is None or link.blocked_at or not value.get("botId") or link.bot_id != value.get("botId"):
        return None
    user = await session.get(User, link.user_id)
    if user is None or user.status is None or user.status.upper() != "ACTIVE":
        return None
    if not authorization.can(user.id, CHATBOT_PERMISSION):
        return None
    return user, link


async def admin_recipients(session: AsyncSession, value: dict) -> list[tuple[TelegramLink, User]]:
    """Verified private chats of active users holding ``telegram.alerts.receive``."""
    from app.core.authorization import service as authorization

    if not value.get("botId"):
        return []
    rows = (await session.execute(select(TelegramLink).where(TelegramLink.blocked_at.is_(None), TelegramLink.bot_id == value.get("botId")))).scalars().all()
    recipients: list[tuple[TelegramLink, User]] = []
    for link in rows:
        user = await session.get(User, link.user_id)
        if user is None or user.status is None or user.status.upper() != "ACTIVE":
            continue
        if not authorization.can(user.id, ALERTS_PERMISSION):
            continue
        recipients.append((link, user))
    return recipients


async def admin_recipient_count(session: AsyncSession, value: dict) -> int:
    return len(await admin_recipients(session, value))


def bot_identity(value: dict) -> dict:
    return {"botName": value.get("botDisplayName") or "", "botUsername": value.get("botUsername") or ""}


async def test_connection(session: AsyncSession) -> dict:
    value = await config(session)
    try:
        identity = await client(value).get_me()
        value.update(botId=identity["id"], botDisplayName=str(identity.get("first_name", ""))[:255], botUsername=str(identity.get("username", ""))[:100], connectionStatus="connected", lastVerifiedAt=utcnow().isoformat(), lastTestMessage="Telegram verified by getMe.")
        value["botToken"] = encrypt_secret(decrypt_secret(value["botToken"]))
    except TelegramError as exc:
        value.update(connectionStatus="failed", lastTestMessage=describe(exc), lastVerifiedAt="", botId=None)
    value["lastTestedAt"] = utcnow().isoformat()
    current = await locked_config(session)
    if current.get("enabled") is not value.get("enabled") or decrypt_secret(current.get("botToken") or "") != decrypt_secret(value.get("botToken") or ""):
        raise ValidationFailed("Telegram configuration changed during verification. Test the current configuration again.")
    fields = {key: value[key] for key in ("botId", "botDisplayName", "botUsername", "connectionStatus", "lastVerifiedAt", "lastTestedAt", "lastTestMessage", "botToken") if key in value}
    await save_internal(session, {**current, **fields})
    await session.commit()
    return {"status": value["connectionStatus"], "message": value["lastTestMessage"], "lastTestedAt": value["lastTestedAt"]}


async def encrypt_legacy_credentials(session: AsyncSession) -> None:
    """Migrate previously saved plaintext Telegram credentials in both settings copies."""
    value = await config(session)
    if value.get("botToken") and not value["botToken"].startswith("enc:v1:"):
        await save_internal(session, value)
        await session.commit()


async def reauthenticate(session: AsyncSession, user_id: int, password: str) -> None:
    credential = await session.get(UserCredential, user_id)
    if credential is None or not verify_password(password, credential.password_hash):
        raise AccessDenied("Current password is required to change Telegram linkage.")


async def create_pairing(session: AsyncSession, context: RequestContext, kind: str) -> dict:
    await session.execute(select(User.id).where(User.id == context.user_id).with_for_update())
    value = await config(session)
    if not value.get("botId") or value.get("connectionStatus") != "connected":
        raise ValidationFailed("Verify the bot connection first.")
    # A newly generated challenge invalidates earlier challenges of this kind.
    await session.execute(delete(TelegramPairing).where(TelegramPairing.user_id == context.user_id, TelegramPairing.kind == kind))
    token = secrets.token_urlsafe(32)
    expires = utcnow() + timedelta(minutes=10)
    session.add(TelegramPairing(token_hash=digest(token), user_id=context.user_id, kind=kind, bot_id=value["botId"], expires_at=expires))
    await session.commit()
    return {"challenge": token, "expiresAt": expires.isoformat(), "url": f"https://t.me/{value['botUsername']}?start={token}" if kind == "PRIVATE" else None, "command": f"/lcs_pair {token}" if kind == "GROUP" else None}


VERIFICATION_CODE_TTL = timedelta(minutes=5)


async def within_rate_budget(key: str, *, limit: int, window_seconds: int) -> bool:
    """Attempt budget for verification actions.

    Deliberately independent of ``RATE_LIMIT_ENABLED``: guessing a verification
    code or spamming code creation must be bounded even when the general rate
    limiter is switched off. Redis is used when configured; otherwise the
    process-local window shared with the rate-limit fallback applies.
    """
    from app.core import rate_limit
    from app.core.redis import safe_increment

    count = await safe_increment(f"rate:{key}", window_seconds)
    if count is None:
        now = time.monotonic()
        bucket = rate_limit._fallback[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        bucket.append(now)
        count = len(bucket)
    return count <= limit


async def create_verification_code(session: AsyncSession, context: RequestContext) -> dict:
    """Issue a short-lived 6-digit code; only its hash is stored.

    A new code replaces the user's previous one, so exactly one challenge is
    active per LCS account. The code is bound to the configured bot identity and
    consumed by ``/verify`` from the sender's own private chat.
    """
    await session.execute(select(User.id).where(User.id == context.user_id).with_for_update())
    value = await config(session)
    if not value.get("botId") or value.get("connectionStatus") != "connected":
        raise ValidationFailed("Verify the bot connection in Settings → Telegram before generating a code.")
    if await session.get(TelegramLink, context.user_id):
        raise ValidationFailed("Disconnect the current Telegram account before generating a new verification code.")
    await session.execute(delete(TelegramPairing).where(TelegramPairing.user_id == context.user_id, TelegramPairing.kind == "PRIVATE"))
    code = ""
    for _ in range(8):  # collision with another active code is vanishingly unlikely
        code = f"{secrets.randbelow(1_000_000):06d}"
        if await session.get(TelegramPairing, digest(code)) is None:
            break
    expires = utcnow() + VERIFICATION_CODE_TTL
    session.add(TelegramPairing(token_hash=digest(code), user_id=context.user_id, kind="PRIVATE", bot_id=value["botId"], expires_at=expires))
    await write_audit(session, context, event_type="TELEGRAM_VERIFICATION_CODE_ISSUED", entity_type="user", entity_id=context.user_id, action="generate")
    await session.commit()
    return {"code": code, "expiresAt": expires.isoformat(), "botUsername": value.get("botUsername") or ""}


async def process_update(session: AsyncSession, update: dict) -> None:
    update_id = update.get("update_id")
    if type(update_id) is not int or update_id < 0:
        raise ValidationFailed("Invalid update.")
    if await session.get(TelegramUpdate, update_id):
        return
    session.add(TelegramUpdate(update_id=update_id))
    await session.flush()  # Unique receipt participates in the pairing transaction.
    message = update.get("message") or {}
    if not isinstance(message, dict):
        return
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return
    chat_id, sender_id = chat.get("id"), sender.get("id")
    if type(chat_id) is not int or type(sender_id) is not int or abs(chat_id) >= 2**53 or sender_id <= 0 or sender.get("is_bot"):
        return
    value = await config(session)
    migration = message.get("migrate_to_chat_id")
    if type(migration) is int and chat_id == value.get("adminGroupId"):
        migrated = await client(value).call("getChat", {"chat_id": migration})
        if migrated.get("id") == migration and migrated.get("type") == "supergroup" and not migrated.get("username"):
            await session.execute(update(NotificationOutbox).where(NotificationOutbox.destination_type == "ADMIN", NotificationOutbox.destination_reference == chat_id, NotificationOutbox.status.in_(["PENDING", "FAILED"])).values(destination_reference=migration))
            value["adminGroupId"] = migration
            await save_internal(session, value)
        return
    text = message.get("text", "")
    if not isinstance(text, str) or len(text) > 200:
        return
    parts = text.split()
    command = parts[0].split("@")[0] if parts else ""
    if command in {"/start", "/lcs_pair"} and len(parts) == 2 and len(parts[1]) <= 64:
        pairing = (await session.execute(select(TelegramPairing).where(TelegramPairing.token_hash == digest(parts[1])).with_for_update())).scalar_one_or_none()
        if pairing is not None and not pairing.used_at and aware(pairing.expires_at) > utcnow() and pairing.bot_id == value.get("botId") and value.get("botToken"):
            owner = await session.get(User, pairing.user_id)
            if owner is not None and owner.status.upper() == "ACTIVE":
                from app.core.authorization import service as authorization

                if not authorization.can(owner.id, CHATBOT_PERMISSION):
                    # A revoked permission invalidates an outstanding challenge too.
                    return
                if pairing.kind == "PRIVATE" and command == "/start" and chat.get("type") == "private" and chat_id == sender_id and not await session.get(TelegramLink, pairing.user_id):
                    existing = (await session.execute(select(TelegramLink).where(TelegramLink.telegram_user_id == sender_id))).scalar_one_or_none()
                    if existing is None:
                        # A challenge alone cannot change a password or create an LCS session.
                        session.add(TelegramLink(user_id=pairing.user_id, telegram_user_id=sender_id, bot_id=value["botId"], chat_id=chat_id, display_name=str(sender.get("username") or sender.get("first_name") or "Telegram")[:255]))
                        await session.flush()
                        from app.modules.telegram.outbox import enqueue_private

                        await enqueue_private(session, pairing.user_id, "TELEGRAM_LINKED")
                        pairing.used_at = utcnow()
                        await write_audit(session, None, event_type="TELEGRAM_LINKED", entity_type="user", entity_id=pairing.user_id, action="link", metadata={"bot_id": value["botId"]})
                elif pairing.kind == "GROUP" and command == "/lcs_pair" and chat.get("type") in {"group", "supergroup"}:
                    actual = await bot_client(value).call("getChat", {"chat_id": chat_id})
                    member = await bot_client(value).call("getChatMember", {"chat_id": chat_id, "user_id": sender_id})
                    if actual.get("id") == chat_id and not actual.get("username") and member.get("status") in {"creator", "administrator"}:
                        await bot_client(value).send_message(chat_id, "LCS admin-group pairing candidate verified. Confirm inside authenticated LCS Settings.")
                        pairing.candidate_id = chat_id
                        pairing.candidate_name = str(actual.get("title") or "Admin group")[:255]
                        pairing.used_at = utcnow()
    # Every protected command re-resolves the LCS user, active status, bot
    # identity and the current chatbot permission; replies are best-effort.
    from app.modules.telegram import chatbot

    reply = await chatbot.handle(session, value, chat=chat, sender=sender, text=text)
    if reply:
        try:
            await bot_client(value).send_message(chat_id, reply)
        except Exception:  # noqa: BLE001 - a reply fault must not undo a pairing
            pass


async def confirm_group(session: AsyncSession, context: RequestContext, token: str) -> None:
    pairing = (await session.execute(select(TelegramPairing).where(TelegramPairing.token_hash == digest(token)).with_for_update())).scalar_one_or_none()
    value = await config(session)
    if not pairing or pairing.user_id != context.user_id or pairing.kind != "GROUP" or not pairing.candidate_id or aware(pairing.expires_at) <= utcnow() or pairing.bot_id != value.get("botId"):
        raise ValidationFailed("No eligible verified group candidate.")
    # Recheck eligibility at confirmation; a candidate must still be private.
    actual = await client(value).call("getChat", {"chat_id": pairing.candidate_id})
    if actual.get("username") or actual.get("type") not in {"group", "supergroup"}:
        raise ValidationFailed("The admin destination must be a private group.")
    current = await locked_config(session)
    if current.get("botId") != pairing.bot_id or current.get("botToken") != value.get("botToken") or not current.get("enabled"):
        raise ValidationFailed("Telegram configuration changed. Generate a new pairing challenge.")
    current.update(adminGroupId=pairing.candidate_id, adminGroupName=pairing.candidate_name, adminGroupVerifiedAt=utcnow().isoformat())
    await save_internal(session, current, context)
    await session.delete(pairing)
    await session.commit()

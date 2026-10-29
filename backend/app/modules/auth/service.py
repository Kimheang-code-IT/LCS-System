from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import authorization, cache, deletion
from app.core.bootstrap import provision_admin, requires_setup
from app.core.config import settings
from app.core.context import RequestContext
from app.core.exceptions import AccessDenied, AuthRequired, Conflict, NotFound, ValidationFailed
from app.core.locks import advisory_lock
from app.core.pagination import PageParams, paged
from app.core.permissions import (
    ALL_PERMISSION_CODES,
    PAGE_PERMISSION_CODES,
    PROTECTED_ROLE_CODES,
    SOURCE_PERMISSION_CODES,
    SUPER_ADMIN_ROLE,
    compile_role_permissions,
    resolve_role_codes,
)
from app.core.redis import safe_delete
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
    verify_password_or_dummy,
)
from app.modules.auth.models import (
    PROTECTED_SYSTEM_ADMIN_IDENTITY,
    PasswordResetToken,
    Role,
    UsedRefreshToken,
    User,
    UserCredential,
    UserSession,
)
from app.modules.auth.repository import AuthRepository

# Account lockout policy for privileged/credentialed access. These are the
# defaults; the effective values come from app_settings(`security`) so an
# administrator can tighten them without a deploy. They are clamped to a safe
# range because a policy of "never lock" or "lock after 1" would either remove a
# control or lock everyone out.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
_LOCKOUT_ATTEMPTS_RANGE = (3, 100)
_LOCKOUT_MINUTES_RANGE = (1, 1440)


def _clamped_int(value: Any, default: int, bounds: tuple[int, int]) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    low, high = bounds
    return max(low, min(high, parsed))


async def lockout_policy(session: AsyncSession) -> tuple[int, int]:
    """Effective ``(max_failed_attempts, lockout_minutes)``.

    Reads the stored security settings and falls back to the module defaults when
    they are missing or unusable, so a bad configuration can never silently disable
    the lockout control.
    """
    from app.modules.settings.service import get_app_config

    try:
        config = await get_app_config(session)
    except Exception:  # noqa: BLE001 - a broken settings document must not block login
        return MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES
    security = config.get("security") if isinstance(config, dict) else None
    security = security if isinstance(security, dict) else {}
    return (
        _clamped_int(security.get("maxLoginAttempts"), MAX_FAILED_ATTEMPTS, _LOCKOUT_ATTEMPTS_RANGE),
        _clamped_int(security.get("accountLockMinutes"), LOCKOUT_MINUTES, _LOCKOUT_MINUTES_RANGE),
    )


def _is_protected_system_admin(user: User) -> bool:
    return user.system_identity == PROTECTED_SYSTEM_ADMIN_IDENTITY


async def _user_role_codes(session: AsyncSession, user_id: int) -> list[str]:
    return await authorization.user_role_codes(session, user_id)


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive datetimes so expiry comparisons are safe."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _assert_can_manage_protected_role(context: RequestContext | None, role_code: str | None) -> None:
    """Only a super administrator may touch a protected system role."""
    if role_code in PROTECTED_ROLE_CODES and not (context and context.is_platform_admin):
        raise AccessDenied(f"Only a super administrator can modify the {role_code} role.")


def _assert_can_grant_permissions(context: RequestContext, codes: list[str]) -> None:
    """Prevent delegated role managers from granting capabilities they lack."""
    if context.is_platform_admin:
        return
    # Compare the closed set: granting a page checkbox also grants the API codes
    # behind it, so the actor must hold those too.
    required = set(resolve_role_codes(codes))
    missing = sorted(code for code in required if not context.has_permission(code))
    if missing:
        raise AccessDenied(
            "You cannot grant permissions that you do not hold: " + ", ".join(missing)
        )


async def _assert_can_assign_role(session: AsyncSession, context: RequestContext, role: Role) -> None:
    if context.is_platform_admin:
        return
    _assert_can_grant_permissions(context, await authorization.role_permission_codes(session, role.code))


async def _revoke_all_sessions(session: AsyncSession, user: User) -> None:
    """Invalidate every refresh session and bump the token version so existing
    access tokens stop working immediately."""
    now = datetime.now(UTC)
    records = await AuthRepository(session).active_sessions(user.id)
    for record in records:
        record.revoked_at = now
    user.token_version = int(user.token_version or 0) + 1
    from app.modules.telegram.models import TelegramPairing

    await session.execute(delete(TelegramPairing).where(TelegramPairing.user_id == user.id))
    await safe_delete(f"revoked:{user.id}")


async def must_change_password(session: AsyncSession, user_id: int) -> bool:
    """Whether the current password was chosen by somebody other than its owner."""
    credential = await AuthRepository(session).credential_for_user(user_id)
    return bool(credential and credential.must_change_password)


async def get_user_by_login(session: AsyncSession, login: str) -> User | None:
    return await AuthRepository(session).user_by_login(login)


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await AuthRepository(session).user(user_id)
    if user is None:
        raise NotFound("User not found.")
    return user


async def authenticate(session: AsyncSession, login: str, password: str) -> User:
    from app.modules.audit.service import write_audit

    user = await get_user_by_login(session, login)
    if user is None:
        verify_password_or_dummy(password, None)
        await write_audit(session, None, event_type="LOGIN_FAILED", entity_type="user", entity_id=0, action="login", result="REJECTED")
        await session.commit()
        raise AuthRequired("Invalid username or password.")
    credential = await AuthRepository(session).credential_for_user(user.id)
    now = datetime.now(UTC)
    locked_until = credential.locked_until if credential is not None else None
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    if locked_until is not None and locked_until > now:
        raise AuthRequired("Account is temporarily locked. Try again later.")
    if credential is None or not verify_password(password, credential.password_hash):
        if credential is not None:
            max_attempts, lockout_minutes = await lockout_policy(session)
            credential.failed_attempt_count = (credential.failed_attempt_count or 0) + 1
            if credential.failed_attempt_count >= max_attempts:
                credential.locked_until = now + timedelta(minutes=lockout_minutes)
                credential.failed_attempt_count = 0
                await write_audit(session, None, event_type="ACCOUNT_LOCKED", entity_type="user", entity_id=user.id, action="lock", result="REJECTED")
            await write_audit(session, None, event_type="LOGIN_FAILED", entity_type="user", entity_id=user.id, action="login", result="REJECTED")
            await session.commit()
        raise AuthRequired("Invalid username or password.")
    if str(user.status or "").upper() not in {"ACTIVE"}:
        raise AuthRequired("This account is not active.")
    credential.failed_attempt_count = 0
    credential.locked_until = None
    await session.commit()
    return user


def resolve_page_keys(permissions: set[str], is_platform_admin: bool) -> tuple[list[str], list[str]]:
    """Split a user's effective codes into API capabilities and page keys.

    Both halves come from Casbin: a role stores the page code *and* the API codes
    that page needs (compiled when the role is saved), so nothing is implied at
    read time.
    """
    if is_platform_admin or "*" in permissions:
        return ["ALL_PAGES"], ["ALL_PAGES"]
    source = sorted(code for code in permissions if code in SOURCE_PERMISSION_CODES)
    pages = sorted(code for code in permissions if code in PAGE_PERMISSION_CODES)
    return source, pages


async def build_context(
    session: AsyncSession,
    user: User,
    *,
    request_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RequestContext:
    # Every authenticated request and every login/refresh reaches a context, so
    # this is the one place that guarantees the policy copy is current before any
    # decision (and before the identity snapshot is cached).
    await authorization.ensure_current(session)
    permissions, role_codes, avatar = await resolve_identity(session, user)
    is_platform_admin = authorization.is_super_admin(user.id) or "*" in permissions

    return RequestContext(
        user_id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        permissions=permissions | ({"ALL_PAGES"} if is_platform_admin else set()),
        is_platform_admin=is_platform_admin,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        avatar=avatar,
        roles=role_codes,
    )


async def resolve_identity(session: AsyncSession, user: User) -> tuple[set[str], list[str], str | None]:
    """Effective permissions, role codes and avatar for one user.

    The codes come from the Casbin enforcer, which is synchronized before any
    request is authorized. The result is cached read-through with version-based
    invalidation: the key includes the user's ``token_version`` so session
    revocation invalidates it, and every policy mutation bumps the ``auth``
    namespace. Enforcement never reads this cache — ``RequestContext`` asks
    Casbin for each decision.
    """
    parts = ("identity", user.id, int(user.token_version or 0))
    cached = await cache.get_json("auth", *parts)
    if isinstance(cached, dict) and "permissions" in cached:
        try:
            return set(cached["permissions"]), list(cached.get("roles") or []), cached.get("avatar")
        except (TypeError, ValueError):
            pass
    permissions = set(authorization.effective_codes(user.id))
    role_codes = await authorization.user_role_codes(session, user.id)
    avatar = await get_user_avatar(session, user.id)
    if authorization.is_loaded():
        # Never memoize a snapshot taken while the policy copy was unavailable:
        # it would keep an empty permission set for the whole TTL.
        await cache.set_json(
            "auth", *parts,
            value={"permissions": sorted(permissions), "roles": role_codes, "avatar": avatar},
            ttl_seconds=settings.cache_ttl_permissions_seconds,
        )
    return permissions, role_codes, avatar


def build_auth_user(
    ctx: RequestContext,
    role_label: str,
    *,
    must_change_password: bool = False,
    roles: list[str] | None = None,
) -> dict:
    source_permissions, page_access = resolve_page_keys(ctx.permissions, ctx.is_platform_admin)
    return {
        "id": ctx.user_id,
        "name": ctx.display_name,
        "email": ctx.email,
        "role": role_label,
        "roles": roles if roles is not None else [role_label],
        "avatar": ctx.avatar,
        "permissions": page_access,
        "pageAccess": page_access,
        "sourcePermissions": list(source_permissions),
        # Tells the SPA to send this session to the change-password screen before
        # anything else. The API enforces the same rule server-side.
        "mustChangePassword": must_change_password,
    }


async def _session_access(session: AsyncSession, user: User, record: UserSession) -> str:
    from app.modules.settings.service import get_access_policy

    policy = await get_access_policy(session)
    return create_access_token(
        user.id, int(user.token_version or 0), session_id=record.id,
        lifetime_minutes=policy["accessTokenMinutes"],
        must_change_password=await must_change_password(session, user.id),
    )


async def validate_session(session: AsyncSession, record: UserSession | None, user_id: int) -> UserSession:
    from app.modules.settings.service import get_access_policy

    if record is None or record.user_id != user_id or record.revoked_at is not None:
        raise AuthRequired("Session has been revoked. Please sign in again.", code="SESSION_REVOKED")
    policy = await get_access_policy(session)
    now = datetime.now(UTC)
    absolute = min(_as_utc(record.expires_at), _as_utc(record.created_at) + timedelta(minutes=policy["sessionAbsoluteMinutes"]))
    activity = _as_utc(record.last_activity_at or record.created_at)
    if now >= absolute or now >= activity + timedelta(minutes=policy["sessionTimeoutMinutes"]):
        raise AuthRequired("Session has expired. Please sign in again.", code="SESSION_EXPIRED")
    return record


async def create_session(
    session: AsyncSession, user: User, *, ip: str | None, user_agent: str | None, remember_me: bool = False,
) -> tuple[str, str]:
    from app.modules.settings.service import get_access_policy

    now = datetime.now(UTC)
    policy = await get_access_policy(session)
    refresh = create_refresh_token(user.id)
    record = UserSession(
        user_id=user.id, refresh_token_hash=hash_token(refresh),
        expires_at=now + timedelta(minutes=policy["sessionAbsoluteMinutes"]),
        created_at=now, last_activity_at=now, remember_me=remember_me,
    )
    session.add(record)
    await session.flush()
    access = await _session_access(session, user, record)
    user.last_login_at = now
    await session.commit()
    return access, refresh


async def _refresh_record(session: AsyncSession, token: str) -> tuple[UserSession | None, UsedRefreshToken | None]:
    token_hash = hash_token(token)
    # History is immutable. Lock the stable session before inspecting its current
    # hash again: a waiter must observe the winning rotation after the lock.
    record = await session.scalar(select(UserSession).where(UserSession.refresh_token_hash == token_hash).with_for_update())
    if record is not None:
        return record, None
    used = await session.get(UsedRefreshToken, token_hash)
    if used is None:
        return None, None
    record = await session.scalar(select(UserSession).where(UserSession.id == used.session_id).with_for_update())
    return record, used


async def rotate_refresh_token(
    session: AsyncSession, refresh_token: str, *, ip: str | None, user_agent: str | None,
) -> tuple[User, str, str, bool]:
    record, used = await _refresh_record(session, refresh_token)
    if record is None:
        raise AuthRequired("Invalid refresh token.", code="SESSION_INVALID")
    now = datetime.now(UTC)
    if used is not None:
        if record.revoked_at is None and now - _as_utc(used.used_at) <= timedelta(seconds=5):
            # An overlapping request receives no credential and cannot rotate.
            # No cookies are changed; its tab can retry using the winning cookie.
            raise Conflict("REFRESH_CONFLICT", "Another request renewed this session. Retry using the current cookie.")
        if record.revoked_at is None:
            from app.modules.audit.service import write_audit

            record.revoked_at = now
            await write_audit(session, None, event_type="REFRESH_REPLAY", entity_type="user_session",
                              entity_id=record.id, action="revoke", reason="Consumed refresh credential reused")
            await session.commit()
        raise AuthRequired("Session revoked after refresh-token reuse.", code="SESSION_REVOKED")
    user = await session.get(User, record.user_id)
    if user is None or str(user.status).upper() != "ACTIVE":
        raise AuthRequired("This account is not active.", code="SESSION_REVOKED")
    await validate_session(session, record, user.id)
    session.add(UsedRefreshToken(token_hash=record.refresh_token_hash, session_id=record.id, used_at=now))
    new_refresh = create_refresh_token(user.id)
    record.refresh_token_hash = hash_token(new_refresh)
    record.last_used_at = now
    access = await _session_access(session, user, record)
    await session.commit()
    return user, access, new_refresh, bool(record.remember_me)


async def revoke_session(session: AsyncSession, user_id: int | None, refresh_token: str | None, *, session_id: int | None = None) -> int | None:
    now = datetime.now(UTC)
    if refresh_token:
        record, _ = await _refresh_record(session, refresh_token)
        if record is not None:
            record.revoked_at = now
            user_id = record.user_id
        await session.commit()
        return user_id
    if user_id is None:
        return None
    if session_id is not None:
        record = await session.scalar(select(UserSession).where(UserSession.id == session_id).with_for_update())
        if record is not None and record.user_id == user_id:
            record.revoked_at = now
            await session.commit()
        return user_id
    records = await AuthRepository(session).active_sessions(user_id)
    for record in records:
        record.revoked_at = now
    await session.commit()
    return user_id


async def request_password_reset(session: AsyncSession, email: str) -> None:
    import secrets

    from app.modules.telegram import service as telegram
    from app.modules.telegram.models import TelegramLink
    from app.modules.telegram.outbox import enqueue_private, policy

    value = await telegram.config(session)
    if not value.get("enabled") or not policy(value, "recovery")["enabled"]:
        return
    try:
        telegram.trusted_origin()
    except ValidationFailed:
        return
    user = await AuthRepository(session).user_by_login(email.strip())
    if user is None or user.status.upper() != "ACTIVE":
        return
    # Serialize issuance and consumption per account, including simultaneous requests.
    user = (await session.execute(select(User).where(User.id == user.id).with_for_update())).scalar_one()
    link = await session.get(TelegramLink, user.id)
    if not link or link.blocked_at or link.bot_id != value.get("botId"):
        return
    now = datetime.now(UTC)
    recent = await session.scalar(select(PasswordResetToken.id).where(PasswordResetToken.user_id == user.id, PasswordResetToken.created_at > now - timedelta(minutes=policy(value, "recovery")["cooldownMinutes"])))
    if recent:
        return
    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=now))
    token = secrets.token_urlsafe(32)
    record = PasswordResetToken(user_id=user.id, email=user.email, code_hash=hash_token(token), expires_at=now + timedelta(minutes=15))
    session.add(record)
    await session.flush()
    await enqueue_private(session, user.id, "PASSWORD_RESET_REQUESTED", token=token, reset_id=record.id)
    await session.commit()


async def verify_reset_code(session: AsyncSession, email: str, code: str) -> bool:
    # email is retained as a compatibility argument; identity is derived only from the token.
    if not 40 <= len(code) <= 128:
        return False
    record = await session.scalar(select(PasswordResetToken.id).where(PasswordResetToken.code_hash == hash_token(code), PasswordResetToken.used_at.is_(None), PasswordResetToken.expires_at > datetime.now(UTC)))
    return record is not None


async def reset_password(session: AsyncSession, email: str, code: str, password: str) -> None:
    from app.modules.audit.service import write_audit
    from app.modules.telegram import service as telegram
    from app.modules.telegram.models import TelegramLink
    from app.modules.telegram.outbox import enqueue_private, policy

    password_errors = validate_password_strength(password)
    if password_errors:
        raise ValidationFailed(password_errors[0], {"password": password_errors[0]})
    if not 40 <= len(code) <= 128:
        raise Conflict("INVALID_RESET_CODE", "The recovery link is invalid or has expired.")
    record = (await session.execute(select(PasswordResetToken).where(PasswordResetToken.code_hash == hash_token(code)))).scalar_one_or_none()
    if record is None:
        raise Conflict("INVALID_RESET_CODE", "The recovery link is invalid or has expired.")
    user = (await session.execute(select(User).where(User.id == record.user_id).with_for_update())).scalar_one_or_none()
    if user is None or user.status.upper() != "ACTIVE":
        raise Conflict("INVALID_RESET_CODE", "The recovery link is invalid or has expired.")
    value = await telegram.config(session)
    link = await session.get(TelegramLink, user.id)
    if not value.get("enabled") or not policy(value, "recovery")["enabled"] or not link or link.blocked_at or link.bot_id != value.get("botId"):
        raise Conflict("INVALID_RESET_CODE", "The recovery link is invalid or has expired.")
    now = datetime.now(UTC)
    # Atomic conditional consumption is required even when the caller preverified the link.
    consumed = await session.execute(update(PasswordResetToken).where(PasswordResetToken.id == record.id, PasswordResetToken.used_at.is_(None), PasswordResetToken.expires_at > now).values(used_at=now).returning(PasswordResetToken.id).execution_options(synchronize_session=False))
    if consumed.scalar_one_or_none() is None:
        raise Conflict("INVALID_RESET_CODE", "The recovery link is invalid or has expired.")
    credential = await AuthRepository(session).credential_for_user(user.id)
    if credential is None:
        credential = UserCredential(user_id=user.id, password_hash=hash_password(password))
        session.add(credential)
    else:
        credential.password_hash = hash_password(password)
    credential.password_changed_at = now
    credential.must_change_password = False
    credential.failed_attempt_count = 0
    credential.locked_until = None
    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=now))
    await _revoke_all_sessions(session, user)
    await enqueue_private(session, user.id, "PASSWORD_RESET_COMPLETED")
    await write_audit(session, None, event_type="PASSWORD_RESET_COMPLETED", entity_type="user", entity_id=user.id, action="reset_password")
    await session.commit()


async def change_password(session: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    from app.modules.telegram.outbox import enqueue_private

    credential = await AuthRepository(session).credential_for_user(user.id)
    if credential is None or not verify_password(current_password, credential.password_hash):
        raise AuthRequired("Current password is incorrect.")
    password_errors = validate_password_strength(new_password)
    if password_errors:
        raise ValidationFailed(password_errors[0], {"password": password_errors[0]})
    credential.password_hash = hash_password(new_password)
    credential.password_changed_at = datetime.now(UTC)
    # The user chose this password, so it is no longer temporary. Clearing the
    # flag and revoking sessions together means the next token has no "must
    # change" claim and every other device has to sign in again.
    credential.must_change_password = False
    # Changing the password signs out every device, including the current one.
    await _revoke_all_sessions(session, user)
    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=datetime.now(UTC)))
    await enqueue_private(session, user.id, "PASSWORD_CHANGED")
    await session.commit()


async def set_user_password(
    session: AsyncSession,
    context: RequestContext,
    user_id: int,
    password: str,
    *,
    must_change: bool = True,
) -> User:
    """Administrator-set password for another account.

    Creating a user already means choosing that user's password, so this grants
    no capability an administrator did not already hold and needs no permission
    of its own beyond ``user.manage``. What it does add is a recovery path for a
    user who cannot receive the self-service reset email.

    The password is never returned: it is hashed here and the caller is told only
    that the account changed. Existing sessions are revoked, because a credential
    change that left other devices signed in would not be a reset.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    target_roles = await authorization.user_role_codes(session, user.id)
    _assert_can_manage_protected_role(
        context, SUPER_ADMIN_ROLE if SUPER_ADMIN_ROLE in target_roles else None
    )
    errors = validate_password_strength(password)
    if errors:
        raise ValidationFailed(errors[0], {"password": errors[0]})
    credential = await AuthRepository(session).credential_for_user(user.id)
    if credential is None:
        credential = UserCredential(user_id=user.id, password_hash=hash_password(password))
        session.add(credential)
    else:
        credential.password_hash = hash_password(password)
    credential.password_changed_at = datetime.now(UTC)
    credential.must_change_password = must_change
    # A reset that leaves the account locked out would be useless, and a stale
    # failure count would lock it again on the next typo.
    credential.failed_attempt_count = 0
    credential.locked_until = None
    await _revoke_all_sessions(session, user)
    from app.modules.telegram.outbox import enqueue_private

    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=datetime.now(UTC)))
    await enqueue_private(session, user.id, "PASSWORD_CHANGED")
    await session.commit()
    return user


async def force_logout_user(session: AsyncSession, user_id: int) -> None:
    """Administrative forced sign-out: revoke all sessions and bump the version."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    await _revoke_all_sessions(session, user)
    from app.modules.telegram.outbox import enqueue_private

    await enqueue_private(session, user.id, "SESSIONS_REVOKED")
    await session.commit()


async def list_users(session: AsyncSession, page: PageParams | None = None) -> list[dict]:
    """Users with their role codes.

    Returns a bare list: ``GET /users`` has always answered that way and the SPA
    consumes it directly. ``page`` still bounds the query, it just does not add a
    ``meta`` envelope the clients do not read.
    """
    rows, _total = await AuthRepository(session).users_with_role_codes(page)
    from app.core.users import creator_names_from_audit

    creators = await creator_names_from_audit(
        session, "user", "USER_CREATED", (user.id for user, _assignments in rows)
    )
    output = []
    for user, role_codes in rows:
        output.append(
            {
                "id": user.id,
                "userCode": user.user_code,
                "username": user.username,
                "email": user.email,
                "displayName": user.display_name,
                "status": user.status,
                "role": role_codes[0] if role_codes else None,
                "roles": list(role_codes),
                "lastLogin": user.last_login_at.isoformat() if user.last_login_at else None,
                "createdBy": creators.get(user.id),
                "createdAt": user.created_at.isoformat() if user.created_at else None,
                "isProtectedSystemAccount": _is_protected_system_admin(user),
            }
        )
    return output


def _requested_role_codes(data: dict) -> list[str] | None:
    """The single role code requested by a user create/update payload.

    Returns ``None`` when the payload mentions no role (leave the assignment
    alone) and ``[]`` when it explicitly clears it. A user holds exactly one
    role, so the value is one code; multi-role payloads are refused by the
    request schemas.
    """
    for key in ("role_code", "roleCode", "role"):
        if data.get(key) is not None:
            value = str(data[key]).strip()
            return [value] if value else []
    return None


async def _load_roles(session: AsyncSession, codes: list[str]) -> list[Role]:
    """Resolve role codes to active role rows, refusing unknown or inactive ones."""
    unique = list(dict.fromkeys(codes))
    if not unique:
        return []
    roles = (await session.execute(select(Role).where(Role.code.in_(unique)))).scalars().all()
    by_code = {role.code: role for role in roles}
    unknown = [code for code in unique if code not in by_code]
    if unknown:
        raise ValidationFailed(f"Unknown role: {', '.join(unknown)}.", {"roles": "Unknown role"})
    inactive = [role.code for role in roles if str(role.status or "").upper() != "ACTIVE"]
    if inactive:
        raise ValidationFailed(
            "The selected role is not active.", {"roles": "Inactive role: " + ", ".join(inactive)}
        )
    return [by_code[code] for code in unique]


async def _apply_user_roles(session: AsyncSession, user_id: int, role_codes: list[str]) -> None:
    """Store a user's role set in Casbin, the only role-assignment store."""
    # Serialize per user so two concurrent edits cannot interleave their writes.
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    await authorization.set_user_roles(session, user_id, role_codes)


def _assert_can_touch_super_admin(context: RequestContext, current: list[str], requested: list[str] | None) -> None:
    if context.is_platform_admin:
        return
    if SUPER_ADMIN_ROLE in current or (requested and SUPER_ADMIN_ROLE in requested):
        raise AccessDenied("Only a super administrator can change a Super Administrator assignment.")


async def _assert_super_admin_remains(session: AsyncSession, user_id: int, new_codes: list[str]) -> None:
    """Block removing the last remaining super administrator assignment."""
    if SUPER_ADMIN_ROLE in new_codes:
        return
    # Serialize the check so two concurrent requests cannot each see the other.
    await session.execute(select(Role.id).where(Role.code == SUPER_ADMIN_ROLE).with_for_update())
    current = await authorization.user_role_codes(session, user_id)
    if SUPER_ADMIN_ROLE not in current:
        return
    others = 0
    for other_id in await authorization.users_with_role(session, SUPER_ADMIN_ROLE):
        if other_id == user_id:
            continue
        other = await session.get(User, other_id)
        if other is not None and str(other.status or "").upper() == "ACTIVE":
            others += 1
    if not others:
        raise ValidationFailed("At least one Super Administrator must remain.", {"roles": "Required"})


async def create_user(session: AsyncSession, data: dict, context: RequestContext) -> User:
    if (await session.execute(select(User).where(User.email == data["email"]))).scalars().first():
        raise Conflict("DUPLICATE_EMAIL", "A user with this email already exists.", {"email": "Already in use"})
    if (await session.execute(select(User).where(User.username == data["username"]))).scalars().first():
        raise Conflict("DUPLICATE_USERNAME", "A user with this username already exists.", {"username": "Already in use"})
    user_code = str(data.get("user_code") or data["username"].upper()).strip()
    if (await session.execute(select(User).where(User.user_code == user_code))).scalars().first():
        raise Conflict("DUPLICATE_USER_CODE", "A user with this code already exists.", {"userCode": "Already in use"})
    role_codes = _requested_role_codes(data)
    if not role_codes:
        raise ValidationFailed("At least one role is required.", {"roles": "Required"})
    for code in role_codes:
        _assert_can_manage_protected_role(context, code)
    for role in await _load_roles(session, role_codes):
        await _assert_can_assign_role(session, context, role)
    password = str(data.get("password") or "")
    password_errors = validate_password_strength(password)
    if password_errors:
        raise ValidationFailed(password_errors[0], {"password": password_errors[0]})
    user = User(
        user_code=user_code,
        username=data["username"],
        email=data["email"],
        display_name=data["display_name"],
        status=str(data.get("status") or "ACTIVE").upper(),
    )
    session.add(user)
    await session.flush()
    session.add(
        UserCredential(
            user_id=user.id,
            password_hash=hash_password(password),
            password_changed_at=datetime.now(UTC),
        )
    )
    await _apply_user_roles(session, user.id, role_codes)
    await session.commit()
    await authorization.refresh(session)
    return user


async def update_user(session: AsyncSession, user_id: int, data: dict, context: RequestContext) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    requested = _requested_role_codes(data)
    current_roles = await authorization.user_role_codes(session, user_id)
    if _is_protected_system_admin(user):
        if requested is not None and requested != [SUPER_ADMIN_ROLE]:
            raise AccessDenied("The built-in System Administrator role cannot be changed.")
        if data.get("status") is not None and str(data["status"]).upper() != "ACTIVE":
            raise AccessDenied("The built-in System Administrator cannot be deactivated.")
    for key, column in (
        ("email", "email"),
        ("display_name", "display_name"),
        ("displayName", "display_name"),
        ("locale", "locale"),
        ("timezone", "timezone"),
    ):
        if data.get(key) is not None:
            setattr(user, column, data[key])

    new_code = data.get("user_code") or data.get("userCode")
    if new_code is not None and str(new_code).strip():
        new_code = str(new_code).strip()
        duplicate = (
            await session.execute(select(User).where(User.user_code == new_code, User.id != user_id))
        ).scalars().first()
        if duplicate:
            raise Conflict("DUPLICATE_USER_CODE", "A user with this code already exists.", {"userCode": "Already in use"})
        user.user_code = new_code

    if requested is not None:
        if set(requested) != set(current_roles):
            if context.user_id == user_id:
                raise AccessDenied("You cannot change your own roles.")
            _assert_can_touch_super_admin(context, current_roles, requested)
            for code in requested:
                _assert_can_manage_protected_role(context, code)
            for role in await _load_roles(session, requested):
                await _assert_can_assign_role(session, context, role)
            await _assert_super_admin_remains(session, user_id, requested)
            await _apply_user_roles(session, user_id, requested)

    if data.get("status") is not None:
        new_status = str(data["status"]).upper()
        if context.user_id == user_id and new_status != "ACTIVE":
            raise AccessDenied("You cannot deactivate your own account.")
        if new_status != "ACTIVE":
            _assert_can_touch_super_admin(context, current_roles, None)
            # The last active Super Administrator cannot be deactivated.
            await _assert_super_admin_remains(session, user_id, [])
        user.status = new_status
        if new_status != "ACTIVE":
            await _revoke_all_sessions(session, user)
    await session.commit()
    await authorization.refresh(session)
    return user


async def user_payload(session: AsyncSession, user: User) -> dict:
    roles = await authorization.user_role_codes(session, user.id)
    effective = authorization.effective_codes(user.id)
    return {
        "id": user.id,
        "userCode": user.user_code,
        "username": user.username,
        "email": user.email,
        "displayName": user.display_name,
        "status": str(user.status or "").upper(),
        "role": roles[0] if roles else None,
        "roles": roles,
        # The pages this account can open. Display only: the server re-checks
        # every request against Casbin, and the full code list is on
        # ``GET /users/{id}/effective-permissions``.
        "pagePermissions": sorted(code for code in effective if code in PAGE_PERMISSION_CODES),
        "lastLogin": user.last_login_at.isoformat() if user.last_login_at else None,
        "isProtectedSystemAccount": _is_protected_system_admin(user),
    }


async def list_role_assignments(session: AsyncSession, user_id: int) -> list[dict]:
    """Return the roles currently assigned to the user, in Casbin."""
    codes = await authorization.user_role_codes(session, user_id)
    if not codes:
        return []
    rows = (await session.execute(select(Role).where(Role.code.in_(codes)))).scalars().all()
    by_code = {role.code: role for role in rows}
    return [
        {
            "userId": user_id,
            "roleId": getattr(by_code.get(code), "id", None),
            "roleCode": code,
            "roleName": getattr(by_code.get(code), "name", code),
        }
        for code in codes
    ]


async def effective_permissions(session: AsyncSession, user_id: int) -> dict:
    """Every code the user holds through its assigned role, resolved by Casbin."""
    user = await get_user(session, user_id)
    roles = await authorization.user_role_codes(session, user_id)
    codes = sorted(authorization.effective_codes(user_id))
    source = [code for code in codes if code in SOURCE_PERMISSION_CODES]
    pages = [code for code in codes if code in PAGE_PERMISSION_CODES]
    return {
        "userId": user.id,
        "username": user.username,
        "roles": roles,
        "isSuperAdmin": authorization.is_super_admin(user_id) or "*" in codes,
        "permissions": codes,
        "sourcePermissions": source,
        "pagePermissions": pages,
    }


async def assign_role(session: AsyncSession, user_id: int, data: dict, context: RequestContext) -> dict:
    """Replace the user's assigned role: a user holds exactly one role."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    role = None
    if data.get("role_id"):
        role = await session.get(Role, data["role_id"])
    elif data.get("role_code"):
        role = (await session.execute(select(Role).where(Role.code == data["role_code"]))).scalars().first()
    if role is None:
        raise NotFound("Role not found.")
    if str(role.status or "").upper() != "ACTIVE":
        raise ValidationFailed("The selected role is not active.", {"role": "Role is inactive"})
    current = await authorization.user_role_codes(session, user_id)
    if _is_protected_system_admin(user) and role.code != SUPER_ADMIN_ROLE:
        raise AccessDenied("The built-in System Administrator role cannot be changed.")
    _assert_can_manage_protected_role(context, role.code)
    if role.code not in current:
        if context.user_id == user_id:
            raise AccessDenied("You cannot change your own roles.")
        _assert_can_touch_super_admin(context, current, [role.code])
        await _assert_can_assign_role(session, context, role)
        # The new role replaces the old one, so the previous assignment's
        # removal must not leave the system without a super administrator.
        await _assert_super_admin_remains(session, user_id, [role.code])
        await _apply_user_roles(session, user_id, [role.code])
    await session.commit()
    await authorization.refresh(session)
    return {"userId": user_id, "roleId": role.id, "roleCode": role.code}


async def remove_role(session: AsyncSession, user_id: int, role_code: str, context: RequestContext) -> dict:
    """Remove the user's assigned role; the user then holds no permissions."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    current = await authorization.user_role_codes(session, user_id)
    if role_code not in current:
        raise NotFound("Role assignment not found.")
    if _is_protected_system_admin(user):
        raise AccessDenied("The built-in System Administrator role cannot be changed.")
    if context.user_id == user_id:
        raise AccessDenied("You cannot change your own roles.")
    _assert_can_touch_super_admin(context, current, [])
    remaining = [code for code in current if code != role_code]
    await _assert_super_admin_remains(session, user_id, remaining)
    await _apply_user_roles(session, user_id, remaining)
    await session.commit()
    await authorization.refresh(session)
    return {"userId": user_id, "roleCode": role_code, "roles": remaining}


async def list_roles(
    session: AsyncSession, page: PageParams | None = None, *, q: str | None = None, status: str | None = None
) -> dict:
    roles, total = await AuthRepository(session).roles_with_permissions(page, q=q, status=status)
    from app.core.users import creator_names_from_audit

    creators = await creator_names_from_audit(
        session, "role", "ROLE_CREATED", (role.id for role, _perms in roles)
    )
    counts = await authorization.user_counts_by_role(session)
    output = []
    for role, perms in roles:
        output.append(
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "description": role.description,
                "isSystemRole": role.is_system_role,
                "isProtected": role.code in PROTECTED_ROLE_CODES,
                "status": role.status,
                "permissions": list(perms),
                "permissionCount": len(perms),
                "userCount": counts.get(role.code, 0),
                "createdBy": creators.get(role.id),
                "createdAt": role.created_at.isoformat() if role.created_at else None,
            }
        )
    effective_page = page or PageParams(page=1, page_size=max(total, 1))
    return paged(output, effective_page, total)


def _derive_role_code(name: str, existing: set[str]) -> str:
    """Build a stable uppercase role code from the role name."""
    base = re.sub(r"[^A-Za-z0-9]+", "_", str(name or "")).strip("_").upper()[:48] or "ROLE"
    code = base
    suffix = 2
    while code in existing:
        suffix_token = f"_{suffix}"
        code = f"{base[: 64 - len(suffix_token)]}{suffix_token}"
        suffix += 1
    return code


def _validate_permission_codes(codes: list[str]) -> None:
    """Refuse codes the backend does not define.

    The catalog is code-defined (``app/core/permissions.py``) because a new
    endpoint ships with its guard; accepting an arbitrary string would create a
    grant nothing can ever check.
    """
    if not codes:
        return
    unknown = sorted({code for code in codes if code not in ALL_PERMISSION_CODES and code != "*"})
    if unknown:
        raise ValidationFailed(
            f"Unknown permission(s): {', '.join(unknown)}.", {"permissions": "Unknown permission"}
        )


async def create_role(session: AsyncSession, data: dict, context: RequestContext) -> Role:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValidationFailed("A role name is required.", {"name": "Required"})
    code = str(data.get("code") or "").strip()
    if not code:
        existing = set((await session.execute(select(Role.code))).scalars().all())
        code = _derive_role_code(name, existing)
    code = code.upper()
    _assert_can_manage_protected_role(context, code)
    if (await session.execute(select(Role).where(Role.code == code))).scalars().first():
        raise Conflict("DUPLICATE_ROLE", "A role with this code already exists.", {"code": "Already in use"})
    permissions = [str(value) for value in data.get("permissions") or []]
    _validate_permission_codes(permissions)
    _assert_can_grant_permissions(context, permissions)
    role = Role(code=code, name=name, description=data.get("description"), status="ACTIVE")
    session.add(role)
    await session.flush()
    await sync_role_permissions(session, code, permissions)
    await session.commit()
    await authorization.refresh(session)
    return role


async def update_role(session: AsyncSession, role_id: int, data: dict, context: RequestContext) -> Role:
    role = (
        await session.execute(select(Role).where(Role.id == role_id).with_for_update())
    ).scalars().first()
    if role is None:
        raise NotFound("Role not found.")
    _assert_can_manage_protected_role(context, role.code)
    if role.code in PROTECTED_ROLE_CODES:
        if data.get("status") is not None and str(data["status"]).upper() != "ACTIVE":
            raise AccessDenied(f"The protected {role.code} role cannot be deactivated.")
        if data.get("permissions") is not None and "*" not in {str(value) for value in data["permissions"]}:
            raise AccessDenied("The protected super administrator grant cannot be removed.")
    if data.get("status") is not None and str(data["status"]).upper() != "ACTIVE":
        active_users = 0
        for user_id in await authorization.users_with_role(session, role.code):
            member = await session.get(User, user_id)
            if member is not None and str(member.status or "").upper() == "ACTIVE":
                active_users += 1
        if active_users:
            raise Conflict(
                "ROLE_IN_USE",
                "Reassign active users before deactivating this role.",
            )
    for key in ("name", "description", "status"):
        if data.get(key) is not None:
            setattr(role, key, str(data[key]).upper() if key == "status" else data[key])
    if data.get("permissions") is not None:
        permissions = [str(value) for value in data["permissions"]]
        _validate_permission_codes(permissions)
        _assert_can_grant_permissions(context, permissions)
        await sync_role_permissions(session, role.code, permissions)
    await session.commit()
    await authorization.refresh(session)
    return role


async def sync_role_permissions(session: AsyncSession, role_code: str, codes: list[str]) -> None:
    """Replace a role's grants in Casbin, closing page codes over their API codes."""
    _validate_permission_codes(codes)
    role = (await session.execute(select(Role).where(Role.code == role_code))).scalars().first()
    if role is not None and role.code in PROTECTED_ROLE_CODES:
        if "*" not in codes:
            raise AccessDenied("The protected super administrator grant cannot be removed.")
    resolved = sorted(resolve_role_codes(codes)) if "*" not in codes else ["*"]
    await authorization.set_role_permissions(session, role_code, resolved)


def role_label(role_codes: list[str]) -> str:
    if SUPER_ADMIN_ROLE in role_codes:
        return "SuperAdmin"
    if role_codes:
        return role_codes[0]
    return "User"


async def role_payload(session: AsyncSession, role: Role) -> dict:
    perms = await authorization.role_permission_codes(session, role.code)
    assigned_users = []
    for user_id in await authorization.users_with_role(session, role.code):
        member = await session.get(User, user_id)
        if member is not None:
            assigned_users.append(
                {
                    "id": member.id,
                    "username": member.username,
                    "displayName": member.display_name,
                    "email": member.email,
                    "status": member.status,
                }
            )
    assigned_users.sort(key=lambda item: (item["displayName"] or "", item["id"]))
    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "isSystemRole": role.is_system_role,
        "isProtected": role.code in PROTECTED_ROLE_CODES,
        "status": role.status,
        "permissions": list(perms),
        "permissionCount": len(perms),
        "userCount": len(assigned_users),
        "assignedUsers": assigned_users,
        "assignedUsersSummary": ", ".join(user["displayName"] for user in assigned_users),
    }


async def duplicate_role(
    session: AsyncSession, role_id: int, data: dict, context: RequestContext
) -> Role:
    source = await session.get(Role, role_id)
    if source is None:
        raise NotFound("Role not found.")
    permissions = await authorization.role_permission_codes(session, source.code)
    _assert_can_grant_permissions(context, permissions)
    name = str(data.get("name") or f"{source.name} Copy").strip()
    requested_code = str(data.get("code") or "").strip()
    return await create_role(
        session,
        {
            "name": name,
            "code": requested_code or None,
            "description": source.description,
            "permissions": permissions,
        },
        context,
    )


async def get_role(session: AsyncSession, role_id: int) -> dict:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFound("Role not found.")
    return await role_payload(session, role)


async def permission_catalog(session: AsyncSession) -> dict:
    """Matrix metadata the Roles & Permissions screen renders.

    Pages, their actions and the label keys come from the backend so the UI can
    never drift from what a guard checks.
    """
    from app.core.permissions import MATRIX_PAGES, permission_name

    roles = (await session.execute(select(Role).order_by(Role.code))).scalars().all()
    grouped: dict[str, list[dict]] = {}
    for code in ALL_PERMISSION_CODES:
        module, _, action = code.rpartition(".")
        grouped.setdefault(module, []).append(
            {"code": code, "module": module, "action": action, "name": permission_name(code)}
        )
    return {
        "pages": [
            {
                "value": value,
                "group": group,
                "prefix": prefix,
                "labelKey": label_key,
                "actions": list(actions),
                "permissions": [f"{prefix}.{action}" for action in actions],
            }
            for value, group, prefix, label_key, actions in MATRIX_PAGES
        ],
        "roles": [
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "description": role.description,
                "status": role.status,
                "isProtected": role.code in PROTECTED_ROLE_CODES,
            }
            for role in roles
        ],
        "modules": [
            {"module": module, "permissions": entries} for module, entries in sorted(grouped.items())
        ],
    }


async def _locked_role(session: AsyncSession, role_id: int, context: RequestContext) -> Role:
    role = (
        await session.execute(select(Role).where(Role.id == role_id).with_for_update())
    ).scalars().first()
    if role is None:
        raise NotFound("Role not found.")
    _assert_can_manage_protected_role(context, role.code)
    return role


async def replace_role_permissions(
    session: AsyncSession, role_id: int, codes: list[str], context: RequestContext
) -> dict:
    """Set a role's grants to exactly ``codes``."""
    role = await _locked_role(session, role_id, context)
    _validate_permission_codes(codes)
    _assert_can_grant_permissions(context, codes)
    await sync_role_permissions(session, role.code, codes)
    await session.commit()
    await authorization.refresh(session)
    return await role_payload(session, role)


async def grant_role_permissions(
    session: AsyncSession, role_id: int, codes: list[str], context: RequestContext
) -> dict:
    role = await _locked_role(session, role_id, context)
    _validate_permission_codes(codes)
    _assert_can_grant_permissions(context, codes)
    current = await authorization.role_permission_codes(session, role.code)
    await sync_role_permissions(session, role.code, sorted(set(current) | set(codes)))
    await session.commit()
    await authorization.refresh(session)
    return await role_payload(session, role)


async def revoke_role_permissions(
    session: AsyncSession, role_id: int, codes: list[str], context: RequestContext
) -> dict:
    role = await _locked_role(session, role_id, context)
    if role.code in PROTECTED_ROLE_CODES:
        raise AccessDenied("The protected super administrator grant cannot be removed.")
    current = await authorization.role_permission_codes(session, role.code)
    # Revoking a page also revokes the capabilities that page uniquely supplied,
    # otherwise the compiler would simply re-derive them from the capability that
    # is still in the set.
    targets: set[str] = set()
    for code in codes:
        value = str(code).strip()
        targets.add(value)
        targets.update(compile_role_permissions([value]))
    remaining = sorted(set(current) - targets)
    await sync_role_permissions(session, role.code, remaining)
    await session.commit()
    await authorization.refresh(session)
    return await role_payload(session, role)


async def delete_roles(session: AsyncSession, ids: list[int]) -> None:
    roles = [await session.get(Role, role_id) for role_id in set(ids)]
    if any(role is not None and role.code in PROTECTED_ROLE_CODES for role in roles):
        raise AccessDenied("The protected super administrator role cannot be deleted.")
    for role in roles:
        if role is not None:
            await deletion.require_inactive(role.status, label="role")
    assigned_role_ids = {role.id for role in roles if role is not None and await authorization.users_with_role(session, role.code)}
    if assigned_role_ids:
        raise Conflict(
            "ROLE_IN_USE",
            "A role assigned to a user cannot be deleted. Reassign its users first.",
        )
    for role_id in ids:
        role = await session.get(Role, role_id)
        if role is None:
            continue
        await authorization.delete_role_policies(session, role.code)
        await session.delete(role)
    await session.commit()
    await authorization.refresh(session)


async def delete_users(session: AsyncSession, ids: list[int], context: RequestContext | None = None) -> None:
    users = [await session.get(User, user_id) for user_id in set(ids)]
    users = [user for user in users if user is not None]
    if any(_is_protected_system_admin(user) for user in users):
        raise AccessDenied("The built-in System Administrator account cannot be deleted.")
    if context is not None and context.user_id in ids:
        raise AccessDenied("You cannot delete your own account.")

    # Guard: the last Super Administrator cannot be deleted.
    target_ids = [user.id for user in users]
    super_admins = set(await authorization.users_with_role(session, SUPER_ADMIN_ROLE))
    deleting_admins = super_admins & set(target_ids)
    if deleting_admins:
        active_super_admins = 0
        for other_id in super_admins - deleting_admins:
            other = await session.get(User, other_id)
            if other is not None and str(other.status or "").upper() == "ACTIVE":
                active_super_admins += 1
        if not active_super_admins:
            raise ValidationFailed("At least one Super Administrator must remain.")

    for user in users:
        await deletion.require_inactive(user.status, label="user")

    for user in users:
        await session.execute(delete(UserCredential).where(UserCredential.user_id == user.id))
        await authorization.delete_user_policies(session, user.id)
        await session.execute(delete(UserSession).where(UserSession.user_id == user.id))
        await session.delete(user)
    # Deleting every account would make `requires_setup` true again and expose the
    # public first-run setup endpoint; refuse to remove the last user.
    await session.flush()
    if not await session.scalar(select(func.count()).select_from(User)):
        await session.rollback()
        raise ValidationFailed("At least one user account must remain.")
    await session.commit()
    await authorization.refresh(session)


# --- Profile avatar (stored as a generic module record) ----------------------
USER_AVATAR_COLLECTION = "__user_avatar__"


async def _avatar_record(session: AsyncSession, user_id: int):
    from app.modules.master_data.models import ModuleRecord

    return (
        await session.execute(
            select(ModuleRecord).where(
                ModuleRecord.collection == USER_AVATAR_COLLECTION,
                ModuleRecord.record_no == str(user_id),
            )
        )
    ).scalars().first()


async def get_user_avatar(session: AsyncSession, user_id: int) -> str | None:
    record = await _avatar_record(session, user_id)
    if record is None or not isinstance(record.data, dict):
        return None
    avatar = record.data.get("avatar")
    return str(avatar) if avatar else None


async def set_user_avatar(session: AsyncSession, context: RequestContext, avatar: str | None) -> str | None:
    from app.modules.master_data.models import ModuleRecord

    record = await _avatar_record(session, context.user_id)
    if record is None:
        record = ModuleRecord(
            collection=USER_AVATAR_COLLECTION,
            record_no=str(context.user_id),
            data={"avatar": avatar},
        )
        session.add(record)
    else:
        record.data = {**(record.data or {}), "avatar": avatar}
    await session.commit()
    await cache.bump("auth")
    return avatar


async def clear_user_avatar(session: AsyncSession, context: RequestContext) -> None:
    record = await _avatar_record(session, context.user_id)
    if record is not None:
        await session.delete(record)
        await session.commit()
        await cache.bump("auth")


async def setup_status(session: AsyncSession) -> dict[str, bool]:
    """Public first-run probe: true while no user account exists."""
    return {"requiresSetup": await requires_setup(session)}


async def setup_initialize(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    errors: dict[str, str] = {}
    if "@" not in email:
        errors["email"] = "A valid email address is required."
    password_errors = validate_password_strength(password)
    if password_errors:
        errors["password"] = password_errors[0]
    if errors:
        raise ValidationFailed("The submitted data is invalid.", errors)

    async with advisory_lock(session, "auth:setup-initialize") as acquired:
        if not acquired or not await requires_setup(session):
            raise Conflict("SETUP_COMPLETED", "Setup has already been completed or is in progress.")
        try:
            return await provision_admin(
                session,
                email=email,
                password=password,
                username=str(payload.get("username") or "").strip() or None,
                name=str(payload.get("name") or "").strip() or None,
            )
        except ValueError as error:
            raise ValidationFailed(str(error), {"role": str(error)}) from error

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.bootstrap import provision_admin, requires_setup
from app.core.config import settings
from app.core.context import RequestContext
from app.core.exceptions import AccessDenied, AuthRequired, Conflict, NotFound, ValidationFailed
from app.core.locks import advisory_lock
from app.core.pagination import PageParams, paged
from app.core.permissions import PAGE_PERMISSION_SOURCE_CODES, ROLE_DEFINITIONS, SOURCE_PERMISSIONS
from app.core.redis import safe_delete, safe_get, safe_set
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_code,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
    verify_password_or_dummy,
)
from app.modules.auth.models import (
    PROTECTED_SYSTEM_ADMIN_IDENTITY,
    PasswordResetToken,
    Permission,
    Role,
    RolePermission,
    User,
    UserCredential,
    UserRoleAssignment,
    UserSession,
)
from app.modules.auth.repository import AuthRepository

# Map source permissions to frontend page keys (mirrors the Nuxt contract).
# Page keys come from the Roles & Permissions matrix catalog; a few source codes
# double as page keys for backwards compatibility.
PAGE_KEYS_BY_SOURCE: dict[str, tuple[str, ...]] = {
    "user.read": ("admin.users.view",),
    "user.manage": ("admin.users.view", "admin.users.create", "admin.users.edit", "admin.users.delete"),
    "role.read": ("admin.roles.view",),
    "role.manage": ("admin.roles.view", "admin.roles.create", "admin.roles.edit", "admin.roles.delete"),
    "quotation.read": ("sales.quotations.view",),
    "quotation.create": ("sales.quotations.create",),
    "quotation.update_draft": ("sales.quotations.edit",),
    "quotation.send": ("sales.quotations.edit",),
    "quotation.accept": ("sales.quotations.edit",),
    "quotation.convert": ("sales.quotations.edit", "operations.service_orders.view"),
    "service_order.read": ("operations.service_orders.view",),
    "service_order.create": ("operations.service_orders.create",),
    "service_order.update": ("operations.service_orders.edit", "configuration.view", "configuration.manage"),
    "service_order.complete": ("operations.service_orders.edit",),
    "service_order_config.view": ("operations.service_orders.view",),
    "service_order_config.create": ("operations.service_orders.create", "operations.service_orders.edit"),
    "service_order_config.update": ("operations.service_orders.edit",),
    "service_order_config.delete": ("operations.service_orders.delete",),
    "service_charge.read": ("finance.service_charges.view",),
    "service_charge.create": ("finance.service_charges.create",),
    "service_charge.issue": ("finance.service_charges.edit",),
    "service_charge.convert_to_invoice": ("finance.service_charges.edit",),
    "financial_document.read": ("finance.financial_documents.view",),
    "financial_document.create": ("finance.financial_documents.create",),
    "financial_document.update_draft": ("finance.financial_documents.edit",),
    "financial_document.post": ("finance.financial_documents.edit",),
    "financial_document.reverse": ("finance.financial_documents.edit",),
    "financial_document.allocate": ("finance.financial_documents.edit",),
    "journal_entry.read": ("finance.accounting.view",),
    "journal_entry.create": ("finance.accounting.create",),
    "journal_entry.post": ("finance.accounting.edit",),
    "accounting_period.read": ("finance.accounting.view",),
    "accounting_period.close": ("finance.accounting.edit",),
    "chart_of_accounts.manage": ("finance.accounting.edit",),
    "posting_rule.read": ("finance.posting_rules.view",),
    "posting_rule.manage": (
        "finance.posting_rules.view",
        "finance.posting_rules.create",
        "finance.posting_rules.edit",
        "finance.posting_rules.delete",
    ),
    "audit_log.read": ("admin.audit_logs.view",),
    "archive.view": ("archive.view", "admin.archive.view"),
    "archive.restore": ("admin.archive.edit",),
    "archive.hard_delete": ("admin.archive.delete",),
    "report.read": (
        "operations.reports.view",
        "finance.reports.view",
        "reports.view",
        "finance.accounts_receivable.view",
        "finance.accounts_payable.view",
        "finance.job_profitability.view",
    ),
    "report.export": ("operations.reports.export", "finance.reports.export"),
    "attachment.read": (
        "sales.quotations.view",
        "operations.service_orders.view",
        "finance.financial_documents.view",
    ),
    "attachment.upload": (
        "sales.quotations.edit",
        "operations.service_orders.edit",
        "finance.financial_documents.edit",
    ),
    "attachment.delete": ("finance.financial_documents.edit",),
    "customs_credential.retrieve": ("master.reference.edit",),
    "master.reference.view": (
        "master.reference.view",
        "sales.companies.view",
        "operations.jobs.view",
        "operations.shipments.view",
        "operations.customs.view",
        "operations.documents.view",
        "operations.deliveries.view",
        "finance.debit_notes.view",
        "finance.customer_payments.view",
        "finance.job_charges.view",
        "finance.supplier_costs.view",
        "finance.supplier_payments.view",
    ),
    "master.reference.manage": ("master.reference.create", "master.reference.edit", "master.reference.delete"),
    # Publishing a configuration version changes the live Service Order form for
    # every user, so the Roles screen grants it through the same page key as the
    # rest of the configuration screens.
    "service_order_config.publish": ("configuration.edit",),
    "configuration.manage": (
        "configuration.view",
        "configuration.create",
        "configuration.edit",
        "configuration.delete",
        "configuration.manage",
        "admin.document_sequences.view",
        "admin.document_sequences.create",
        "admin.document_sequences.edit",
        "admin.document_sequences.delete",
        "settings.app_config.view",
        "settings.app_config.edit",
    ),
    "configuration.configure": ("configuration.edit", "configuration.configure"),
    "settings.manage": (
        "settings.app_config.view",
        "settings.app_config.edit",
        "settings.backup.view",
        "settings.backup.edit",
        "settings.manage",
    ),
    "backup.read": ("settings.backup.view",),
    "backup.manage": ("settings.backup.edit",),
    "finance.view": ("finance.accounting.view", "finance.view"),
}

SOURCE_PERMISSION_CODES = {code for code, _, _ in SOURCE_PERMISSIONS}

# Account lockout policy for privileged/credentialed access. These are the
# defaults; the effective values come from app_settings(`security`) so an
# administrator can tighten them without a deploy. They are clamped to a safe
# range because a policy of "never lock" or "lock after 1" would either remove a
# control or lock everyone out.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
_LOCKOUT_ATTEMPTS_RANGE = (3, 100)
_LOCKOUT_MINUTES_RANGE = (1, 1440)
PLATFORM_ADMIN_ROLE = "PLATFORM_ADMIN"


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


async def _active_role_code(session: AsyncSession, user_id: int) -> str | None:
    return await AuthRepository(session).active_role_code(user_id)


def _is_active_assignment(expires_at: datetime | None, now: datetime) -> bool:
    """True when a role assignment is currently active (tz-safe for SQLite)."""
    if expires_at is None:
        return True
    return _as_utc(expires_at) > now


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive datetimes so expiry comparisons are safe."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _refresh_session_lifetime(remember_me: bool) -> timedelta:
    if remember_me:
        return timedelta(days=settings.refresh_token_expire_days)
    return timedelta(hours=settings.session_refresh_token_expire_hours)


def _assert_can_manage_platform_admin(context: RequestContext | None, role_code: str | None) -> None:
    """Only a platform administrator may touch the super-admin role."""
    if role_code == PLATFORM_ADMIN_ROLE and not (context and context.is_platform_admin):
        raise AccessDenied("Only a platform administrator can modify the Platform Administrator role.")


def _assert_can_grant_permissions(context: RequestContext, codes: list[str]) -> None:
    """Prevent delegated role managers from granting capabilities they lack."""
    if context.is_platform_admin:
        return
    required: set[str] = set()
    for code in codes:
        if code in PAGE_PERMISSION_SOURCE_CODES:
            required.update(PAGE_PERMISSION_SOURCE_CODES[code])
        else:
            required.add(code)
    missing = sorted(code for code in required if not context.has_permission(code))
    if missing:
        raise AccessDenied(
            "You cannot grant permissions that you do not hold: " + ", ".join(missing)
        )


async def _assert_can_assign_role(session: AsyncSession, context: RequestContext, role: Role) -> None:
    if context.is_platform_admin:
        return
    codes = list(
        (
            await session.execute(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            )
        ).scalars().all()
    )
    _assert_can_grant_permissions(context, codes)


async def _revoke_all_sessions(session: AsyncSession, user: User) -> None:
    """Invalidate every refresh session and bump the token version so existing
    access tokens stop working immediately."""
    now = datetime.now(UTC)
    records = await AuthRepository(session).active_sessions(user.id)
    for record in records:
        record.revoked_at = now
    user.token_version = int(user.token_version or 0) + 1
    await safe_delete(f"revoked:{user.id}")


async def must_change_password(session: AsyncSession, user_id: int) -> bool:
    """Whether the current password was chosen by somebody other than its owner."""
    credential = await AuthRepository(session).credential_for_user(user_id)
    return bool(credential and credential.must_change_password)


def expand_source_permissions(permissions: set[str]) -> set[str]:
    """Expand stored page permissions into the source/API permissions they imply."""
    expanded = set(permissions)
    for code in permissions:
        expanded.update(PAGE_PERMISSION_SOURCE_CODES.get(code, ()))
    return expanded


async def get_user_by_login(session: AsyncSession, login: str) -> User | None:
    return await AuthRepository(session).user_by_login(login)


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await AuthRepository(session).user(user_id)
    if user is None:
        raise NotFound("User not found.")
    return user


async def authenticate(session: AsyncSession, login: str, password: str) -> User:
    user = await get_user_by_login(session, login)
    if user is None:
        verify_password_or_dummy(password, None)
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
            await session.commit()
        raise AuthRequired("Invalid username or password.")
    if str(user.status or "").upper() not in {"ACTIVE"}:
        raise AuthRequired("This account is not active.")
    credential.failed_attempt_count = 0
    credential.locked_until = None
    await session.commit()
    return user


async def resolve_permissions(session: AsyncSession, user_id: int) -> tuple[set[str], list[str]]:
    now = datetime.now(UTC)
    assignments = (
        await session.execute(select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id))
    ).scalars().all()
    role_ids = {a.role_id for a in assignments if _is_active_assignment(a.expires_at, now)}
    role_codes: list[str] = []
    permissions: set[str] = set()
    if role_ids:
        active_roles = (
            await session.execute(
                select(Role.id, Role.code).where(Role.id.in_(role_ids), Role.status == "ACTIVE")
            )
        ).all()
        active_role_ids = [role_id for role_id, _ in active_roles]
        role_codes = [code for _, code in active_roles]
        if active_role_ids:
            permissions = set(
                (
                    await session.execute(
                        select(Permission.code)
                        .join(RolePermission, RolePermission.permission_id == Permission.id)
                        .where(RolePermission.role_id.in_(active_role_ids))
                    )
                )
                .scalars()
                .all()
            )
    # A role may store matrix page permissions; expand them to the API-level
    # source permissions they imply so enforcement keeps working.
    return expand_source_permissions(permissions), role_codes


def resolve_page_keys(permissions: set[str], is_platform_admin: bool) -> tuple[list[str], list[str]]:
    if is_platform_admin or "ALL_PAGES" in permissions:
        return ["ALL_PAGES"], ["ALL_PAGES"]
    source = sorted(code for code in permissions if code in SOURCE_PERMISSION_CODES)
    pages: set[str] = {"dashboard.view"}
    for code in permissions:
        # Page-level codes (configuration.manage, master.reference.view, …) are
        # also mapped so they grant the finer-grained matrix pages.
        if code in SOURCE_PERMISSION_CODES or code in PAGE_KEYS_BY_SOURCE:
            pages.update(PAGE_KEYS_BY_SOURCE.get(code, ()))
        if code not in SOURCE_PERMISSION_CODES and "." in code:
            pages.add(code)
    return source, sorted(pages)


async def build_context(
    session: AsyncSession,
    user: User,
    *,
    request_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RequestContext:
    permissions, role_codes, avatar = await resolve_identity(session, user)
    is_platform_admin = "PLATFORM_ADMIN" in role_codes or "*" in permissions

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
    )


async def resolve_identity(session: AsyncSession, user: User) -> tuple[set[str], list[str], str | None]:
    """Effective permissions, role codes and avatar for one user.

    Cached read-through with version-based invalidation. The cache key includes
    the user's ``token_version`` so session revocation invalidates it, and role
    or permission changes bump the ``auth`` namespace immediately (see the
    mutations in this module). Backend authorization remains authoritative:
    every request still verifies the user row and token version first.
    """
    parts = ("identity", user.id, int(user.token_version or 0))
    cached = await cache.get_json("auth", *parts)
    if isinstance(cached, dict) and "permissions" in cached:
        try:
            return set(cached["permissions"]), list(cached.get("roles") or []), cached.get("avatar")
        except (TypeError, ValueError):
            pass
    permissions, role_codes = await resolve_permissions(session, user.id)
    avatar = await get_user_avatar(session, user.id)
    await cache.set_json(
        "auth", *parts,
        value={"permissions": sorted(permissions), "roles": role_codes, "avatar": avatar},
        ttl_seconds=settings.cache_ttl_permissions_seconds,
    )
    return permissions, role_codes, avatar


def build_auth_user(ctx: RequestContext, role_label: str, *, must_change_password: bool = False) -> dict:
    source_permissions, page_access = resolve_page_keys(ctx.permissions, ctx.is_platform_admin)
    return {
        "id": ctx.user_id,
        "name": ctx.display_name,
        "email": ctx.email,
        "role": role_label,
        "avatar": ctx.avatar,
        "permissions": page_access,
        "pageAccess": page_access,
        "sourcePermissions": list(source_permissions),
        # Tells the SPA to send this session to the change-password screen before
        # anything else. The API enforces the same rule server-side.
        "mustChangePassword": must_change_password,
    }


async def create_session(
    session: AsyncSession,
    user: User,
    *,
    ip: str | None,
    user_agent: str | None,
    remember_me: bool = False,
) -> tuple[str, str]:
    now = datetime.now(UTC)
    lifetime = _refresh_session_lifetime(remember_me)
    refresh = create_refresh_token(user.id, expires_delta=lifetime)
    record = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh),
        ip_address=ip,
        user_agent=user_agent,
        expires_at=now + lifetime,
        remember_me=remember_me,
    )
    session.add(record)
    await session.flush()
    access = create_access_token(
        user.id,
        int(user.token_version or 0),
        must_change_password=await must_change_password(session, user.id),
    )
    user.last_login_at = now
    await session.commit()
    return access, refresh


async def rotate_refresh_token(
    session: AsyncSession, refresh_token: str, *, ip: str | None, user_agent: str | None
) -> tuple[User, str, str, bool]:
    """Rotate a refresh token and return ``(user, access, refresh, remember_me)``.

    The replacement session inherits the original absolute ``expires_at`` so
    rotation never extends the server-side session lifetime.
    """
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise AuthRequired("Invalid refresh token.") from exc
    if payload.get("type") != "refresh":
        raise AuthRequired("Invalid token type.")
    token_hash = hash_token(refresh_token)
    record = await AuthRepository(session).session_by_refresh_hash(token_hash)
    if record is None or record.revoked_at is not None:
        raise AuthRequired("Session is no longer valid.")
    now = datetime.now(UTC)
    expires_at = _as_utc(record.expires_at)
    if expires_at <= now:
        raise AuthRequired("Session has expired.")
    user = await session.get(User, record.user_id)
    if user is None:
        raise AuthRequired("User not found.")
    record.revoked_at = now
    record.last_used_at = now
    remember_me = bool(record.remember_me)
    new_refresh = create_refresh_token(user.id, expires_delta=expires_at - now)
    # Rotation issues a brand-new session row. Reusing the now-revoked row would
    # make the fresh token fail the revoked check on the very next refresh.
    session.add(
        UserSession(
            user_id=user.id,
            refresh_token_hash=hash_token(new_refresh),
            ip_address=ip,
            user_agent=user_agent,
            expires_at=expires_at,
            remember_me=remember_me,
        )
    )
    await session.commit()
    # Carries the "must change" claim too: refreshing must not be a way to
    # escape the forced change.
    access = create_access_token(
        user.id,
        int(user.token_version or 0),
        must_change_password=await must_change_password(session, user.id),
    )
    return user, access, new_refresh, remember_me


async def revoke_session(session: AsyncSession, user_id: int | None, refresh_token: str | None) -> int | None:
    """Revoke the session identified by ``refresh_token`` (or every active
    session of ``user_id``). Returns the owner id when one was resolved."""
    now = datetime.now(UTC)
    if refresh_token:
        token_hash = hash_token(refresh_token)
        record = await AuthRepository(session).session_by_refresh_hash(token_hash)
        if record is not None:
            record.revoked_at = now
            user_id = record.user_id
        await session.commit()
        if user_id is not None:
            await safe_delete(f"revoked:{user_id}")
        return user_id
    if user_id is None:
        return None
    records = await AuthRepository(session).active_sessions(user_id)
    for record in records:
        record.revoked_at = now
    await session.commit()
    await safe_delete(f"revoked:{user_id}")
    return user_id


async def request_password_reset(session: AsyncSession, email: str) -> None:
    user = await AuthRepository(session).user_by_email(email)
    if user is None:
        return
    code = generate_reset_code()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            email=email,
            code_hash=hash_token(code),
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_code_expire_minutes),
        )
    )
    await session.commit()
    await safe_set(f"reset:{email}", code, ex=settings.password_reset_code_expire_minutes * 60)


async def verify_reset_code(session: AsyncSession, email: str, code: str) -> bool:
    record = (
        await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.email == email, PasswordResetToken.used_at.is_(None))
            .order_by(PasswordResetToken.id.desc())
        )
    ).scalars().first()
    if record is not None and record.expires_at >= datetime.now(UTC) and record.code_hash == hash_token(code):
        return True
    cached = await safe_get(f"reset:{email}")
    return cached is not None and cached == code


async def reset_password(session: AsyncSession, email: str, code: str, password: str) -> None:
    password_errors = validate_password_strength(password)
    if password_errors:
        raise ValidationFailed(password_errors[0], {"password": password_errors[0]})
    if not await verify_reset_code(session, email, code):
        raise Conflict("INVALID_RESET_CODE", "The reset code is invalid or has expired.")
    user = await AuthRepository(session).user_by_email(email)
    if user is None:
        raise NotFound("User not found.")
    credential = await AuthRepository(session).credential_for_user(user.id)
    if credential is None:
        session.add(UserCredential(user_id=user.id, password_hash=hash_password(password), password_changed_at=datetime.now(UTC)))
    else:
        credential.password_hash = hash_password(password)
        credential.password_changed_at = datetime.now(UTC)
    records = (
        await session.execute(select(PasswordResetToken).where(PasswordResetToken.email == email, PasswordResetToken.used_at.is_(None)))
    ).scalars().all()
    for record in records:
        record.used_at = datetime.now(UTC)
    # A password reset invalidates every existing session for the account.
    await _revoke_all_sessions(session, user)
    await session.commit()
    await safe_delete(f"reset:{email}")


async def change_password(session: AsyncSession, user: User, current_password: str, new_password: str) -> None:
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
    _assert_can_manage_platform_admin(context, await _active_role_code(session, user.id))
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
    await session.commit()
    return user


async def force_logout_user(session: AsyncSession, user_id: int) -> None:
    """Administrative forced sign-out: revoke all sessions and bump the version."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    await _revoke_all_sessions(session, user)
    await session.commit()


async def list_users(session: AsyncSession, page: PageParams | None = None) -> list[dict]:
    rows = await AuthRepository(session).users_with_role_codes(page)
    output = []
    for user, assignments in rows:
        output.append(
            {
                "id": user.id,
                "userCode": user.user_code,
                "username": user.username,
                "email": user.email,
                "displayName": user.display_name,
                "status": user.status,
                "roles": list(assignments),
                "isProtectedSystemAccount": _is_protected_system_admin(user),
            }
        )
    return output


def _requested_role_code(data: dict) -> str | None:
    """Resolve the single role requested by a user create/update payload.

    Single-Role RBAC: a user has exactly one role. Accepts the ``role`` /
    ``role_code`` / ``roleCode`` aliases and the legacy ``roles`` list, but a
    list with more than one entry is rejected.

    Returns ``None`` when the payload does not mention any role (leave the
    current assignment unchanged), ``""`` when the payload explicitly clears the
    role, or the role code otherwise.
    """
    roles = data.get("roles")
    if roles is not None:
        codes = [roles] if isinstance(roles, str) else list(roles)
        codes = [str(code).strip() for code in codes if str(code).strip()]
        if len(codes) > 1:
            raise ValidationFailed(
                "A user can only have one role.", {"role": "Only one role is allowed"}
            )
        return codes[0] if codes else ""

    legacy = data.get("role_code") or data.get("roleCode") or data.get("role")
    if legacy:
        return str(legacy).strip()

    mentioned = any(
        key in data and data.get(key) is not None
        for key in ("role_code", "roleCode", "role")
    )
    return "" if mentioned else None


async def _sync_user_role(
    session: AsyncSession, user_id: int, role_code: str, context: RequestContext | None
) -> None:
    """Replace a user's active role with ``role_code``.

    The previous active assignment is expired (never deleted) so history is
    preserved and the partial unique index still allows exactly one active row.
    ``role_code`` must reference an existing active role.
    """
    # Serialize role replacement per user. PostgreSQL enforces the partial
    # unique index as the final backstop; SQLite safely ignores FOR UPDATE.
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    role = (
        await session.execute(select(Role).where(Role.code == role_code))
    ).scalars().first()
    if role is None:
        raise ValidationFailed(f"Unknown role: {role_code}.", {"role": "Unknown role"})
    if str(role.status or "").upper() != "ACTIVE":
        raise ValidationFailed("The selected role is not active.", {"role": "Role is inactive"})

    now = datetime.now(UTC)
    active = (
        await session.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.expires_at.is_(None),
            )
        )
    ).scalars().all()
    for assignment in active:
        assignment.expires_at = now
    # Flush the expiry before inserting so the partial unique index is satisfied.
    await session.flush()
    session.add(
        UserRoleAssignment(
            user_id=user_id,
            role_id=role.id,
            assigned_by_user_id=context.user_id if context else None,
        )
    )
    await session.flush()


async def _assert_platform_admin_remains(session: AsyncSession, user_id: int, new_role_code: str | None) -> None:
    """Block removing the last remaining Platform Administrator assignment."""
    if new_role_code == PLATFORM_ADMIN_ROLE:
        return
    # Serialize all changes that could remove a platform administrator so two
    # concurrent requests cannot each observe the other administrator.
    await session.execute(
        select(Role.id).where(Role.code == PLATFORM_ADMIN_ROLE).with_for_update()
    )
    assignment = (
        await session.execute(
            select(UserRoleAssignment.id)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.expires_at.is_(None),
                Role.code == PLATFORM_ADMIN_ROLE,
            )
        )
    ).scalars().first()
    if assignment is None:
        return
    others = await session.scalar(
        select(func.count())
        .select_from(UserRoleAssignment)
        .join(Role, Role.id == UserRoleAssignment.role_id)
        .where(
            Role.code == PLATFORM_ADMIN_ROLE,
            UserRoleAssignment.user_id != user_id,
            UserRoleAssignment.expires_at.is_(None),
        )
    )
    if not others:
        raise ValidationFailed(
            "At least one Platform Administrator must remain.", {"roles": "Required"}
        )


async def create_user(session: AsyncSession, data: dict, context: RequestContext) -> User:
    if (await session.execute(select(User).where(User.email == data["email"]))).scalars().first():
        raise Conflict("DUPLICATE_EMAIL", "A user with this email already exists.", {"email": "Already in use"})
    if (await session.execute(select(User).where(User.username == data["username"]))).scalars().first():
        raise Conflict("DUPLICATE_USERNAME", "A user with this username already exists.", {"username": "Already in use"})
    user_code = str(data.get("user_code") or data["username"].upper()).strip()
    if (await session.execute(select(User).where(User.user_code == user_code))).scalars().first():
        raise Conflict("DUPLICATE_USER_CODE", "A user with this code already exists.", {"userCode": "Already in use"})
    role_code = _requested_role_code(data)
    if not role_code:
        raise ValidationFailed("A role is required.", {"role": "Required"})
    _assert_can_manage_platform_admin(context, role_code)
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
    await _sync_user_role(session, user.id, role_code, context)
    await session.commit()
    return user


async def update_user(session: AsyncSession, user_id: int, data: dict, context: RequestContext) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    role_code = _requested_role_code(data)
    if _is_protected_system_admin(user):
        if role_code is not None and role_code != PLATFORM_ADMIN_ROLE:
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

    if role_code is not None:
        if not role_code:
            raise ValidationFailed("A user must have exactly one role.", {"role": "Required"})
        current_role_code = await _active_role_code(session, user_id)
        if role_code != current_role_code:
            if context.user_id == user_id:
                raise AccessDenied("You cannot change your own role.")
            _assert_can_manage_platform_admin(context, role_code)
            target_role = (
                await session.execute(select(Role).where(Role.code == role_code))
            ).scalars().first()
            if target_role is None:
                raise ValidationFailed(f"Unknown role: {role_code}.", {"role": "Unknown role"})
            await _assert_can_assign_role(session, context, target_role)
            await _assert_platform_admin_remains(session, user_id, role_code)
            await _sync_user_role(session, user_id, role_code, context)

    if data.get("status") is not None:
        new_status = str(data["status"]).upper()
        if context.user_id == user_id and new_status != "ACTIVE":
            raise AccessDenied("You cannot deactivate your own account.")
        if new_status != "ACTIVE":
            # The last active Platform Administrator cannot be deactivated.
            await _assert_platform_admin_remains(session, user_id, None)
        user.status = new_status
        if new_status != "ACTIVE":
            await _revoke_all_sessions(session, user)
    await session.commit()
    await cache.bump("auth")
    return user


async def user_payload(session: AsyncSession, user: User) -> dict:
    assignments = await list_role_assignments(session, user.id)
    roles = [item["roleCode"] for item in assignments if item.get("roleCode")]
    return {
        "id": user.id,
        "userCode": user.user_code,
        "username": user.username,
        "email": user.email,
        "displayName": user.display_name,
        "status": str(user.status or "").upper(),
        "role": roles[0] if roles else None,
        "roles": roles,
        "lastLogin": user.last_login_at.isoformat() if user.last_login_at else None,
        "isProtectedSystemAccount": _is_protected_system_admin(user),
    }


async def list_role_assignments(session: AsyncSession, user_id: int) -> list[dict]:
    """Return the user's *active* role assignment(s).

    Single-Role RBAC means at most one row. Expired rows are kept for history
    but excluded here so callers always see the current role.
    """
    now = datetime.now(UTC)
    rows = await AuthRepository(session).assignment_rows(user_id)
    return [
        {
            "id": assignment.id,
            "userId": assignment.user_id,
            "roleId": assignment.role_id,
            "roleCode": code,
            "expiresAt": assignment.expires_at.isoformat() if assignment.expires_at else None,
        }
        for assignment, code in rows
        if _is_active_assignment(assignment.expires_at, now)
    ]


async def assign_role(session: AsyncSession, user_id: int, data: dict, context: RequestContext) -> UserRoleAssignment:
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
    if _is_protected_system_admin(user) and role.code != PLATFORM_ADMIN_ROLE:
        raise AccessDenied("The built-in System Administrator role cannot be changed.")
    _assert_can_manage_platform_admin(context, role.code)
    current_role_code = await _active_role_code(session, user_id)
    if role.code != current_role_code:
        if context.user_id == user_id:
            raise AccessDenied("You cannot change your own role.")
        await _assert_can_assign_role(session, context, role)
        await _assert_platform_admin_remains(session, user_id, role.code)
        # Single-Role RBAC: assigning a role replaces the previous active role.
        await _sync_user_role(session, user_id, role.code, context)
    await session.commit()
    await cache.bump("auth")
    assignment = (
        await session.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.expires_at.is_(None),
            )
        )
    ).scalars().first()
    return assignment


async def list_roles(
    session: AsyncSession, page: PageParams | None = None, *, q: str | None = None, status: str | None = None
) -> dict:
    roles, total = await AuthRepository(session).roles_with_permissions(page, q=q, status=status)
    output = []
    for role, perms in roles:
        user_count = int(
            await session.scalar(
                select(func.count())
                .select_from(UserRoleAssignment)
                .where(
                    UserRoleAssignment.role_id == role.id,
                    UserRoleAssignment.expires_at.is_(None),
                )
            )
            or 0
        )
        output.append(
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "description": role.description,
                "isSystemRole": role.is_system_role,
                "status": role.status,
                "permissions": list(perms),
                "permissionCount": len(perms),
                "userCount": user_count,
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


async def _validate_permission_codes(session: AsyncSession, codes: list[str]) -> None:
    if not codes:
        return
    found = set(
        (await session.execute(select(Permission.code).where(Permission.code.in_(codes)))).scalars().all()
    )
    unknown = sorted(set(codes) - found)
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
        existing = set(
            (await session.execute(select(Role.code))).scalars().all()
        )
        code = _derive_role_code(name, existing)
    _assert_can_manage_platform_admin(context, code)
    if (await session.execute(select(Role).where(Role.code == code))).scalars().first():
        raise Conflict("DUPLICATE_ROLE", "A role with this code already exists.", {"code": "Already in use"})
    permissions = [str(value) for value in data.get("permissions") or []]
    await _validate_permission_codes(session, permissions)
    _assert_can_grant_permissions(context, permissions)
    role = Role(code=code, name=name, description=data.get("description"), status="ACTIVE")
    session.add(role)
    await session.flush()
    await sync_role_permissions(session, role.id, permissions)
    await session.commit()
    return role


async def update_role(session: AsyncSession, role_id: int, data: dict, context: RequestContext) -> Role:
    role = (
        await session.execute(select(Role).where(Role.id == role_id).with_for_update())
    ).scalars().first()
    if role is None:
        raise NotFound("Role not found.")
    _assert_can_manage_platform_admin(context, role.code)
    if role.is_system_role and role.code == PLATFORM_ADMIN_ROLE:
        if data.get("status") is not None and str(data["status"]).upper() != "ACTIVE":
            raise AccessDenied("The built-in Platform Administrator role cannot be deactivated.")
        if data.get("permissions") is not None:
            required = set(ROLE_DEFINITIONS[PLATFORM_ADMIN_ROLE]["permissions"])
            requested = {str(value) for value in data["permissions"]}
            if not required.issubset(requested):
                raise AccessDenied("Critical permissions cannot be removed from the built-in administrator role.")
    if data.get("status") is not None and str(data["status"]).upper() != "ACTIVE":
        active_users = int(
            await session.scalar(
                select(func.count())
                .select_from(UserRoleAssignment)
                .join(User, User.id == UserRoleAssignment.user_id)
                .where(
                    UserRoleAssignment.role_id == role.id,
                    UserRoleAssignment.expires_at.is_(None),
                    User.status == "ACTIVE",
                )
            )
            or 0
        )
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
        _assert_can_grant_permissions(context, permissions)
        await sync_role_permissions(session, role.id, permissions)
    await session.commit()
    await cache.bump("auth")
    return role


async def sync_role_permissions(session: AsyncSession, role_id: int, codes: list[str]) -> None:
    await _validate_permission_codes(session, codes)
    role = await session.get(Role, role_id)
    if role is not None and role.is_system_role and role.code == PLATFORM_ADMIN_ROLE:
        required = set(ROLE_DEFINITIONS[PLATFORM_ADMIN_ROLE]["permissions"])
        if not required.issubset(codes):
            raise AccessDenied("Critical permissions cannot be removed from the built-in administrator role.")
    await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    await session.flush()
    if not codes:
        return
    ids = (
        await session.execute(select(Permission.id).where(Permission.code.in_(codes)))
    ).scalars().all()
    for pid in ids:
        session.add(RolePermission(role_id=role_id, permission_id=pid))


def role_label(role_codes: list[str]) -> str:
    if "PLATFORM_ADMIN" in role_codes:
        return "SuperAdmin"
    if role_codes:
        return role_codes[0]
    return "User"


async def role_payload(session: AsyncSession, role: Role) -> dict:
    perms = (
        await session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )
    ).scalars().all()
    assigned_users = (
        await session.execute(
            select(User.id, User.username, User.display_name, User.email, User.status)
            .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
            .where(
                UserRoleAssignment.role_id == role.id,
                UserRoleAssignment.expires_at.is_(None),
            )
            .order_by(User.display_name, User.id)
        )
    ).all()
    users = [
        {"id": row.id, "username": row.username, "displayName": row.display_name, "email": row.email, "status": row.status}
        for row in assigned_users
    ]
    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "isSystemRole": role.is_system_role,
        "status": role.status,
        "permissions": list(perms),
        "permissionCount": len(perms),
        "userCount": len(users),
        "assignedUsers": users,
        "assignedUsersSummary": ", ".join(user["displayName"] for user in users),
    }


async def duplicate_role(
    session: AsyncSession, role_id: int, data: dict, context: RequestContext
) -> Role:
    source = await session.get(Role, role_id)
    if source is None:
        raise NotFound("Role not found.")
    permissions = list(
        (
            await session.execute(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == source.id)
            )
        ).scalars().all()
    )
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


async def delete_roles(session: AsyncSession, ids: list[int]) -> None:
    roles = [await session.get(Role, role_id) for role_id in set(ids)]
    if any(role is not None and role.is_system_role for role in roles):
        raise AccessDenied("Built-in system roles cannot be deleted.")
    assigned_role_ids = {
        role.id
        for role in roles
        if role is not None
        and await session.scalar(
            select(func.count()).select_from(UserRoleAssignment).where(UserRoleAssignment.role_id == role.id)
        )
    }
    if assigned_role_ids:
        raise Conflict(
            "ROLE_IN_USE",
            "A role assigned to a user cannot be deleted. Reassign its users first.",
        )
    for role_id in ids:
        role = await session.get(Role, role_id)
        if role is None:
            continue
        await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        await session.delete(role)
    await session.commit()
    await cache.bump("auth")


async def delete_users(session: AsyncSession, ids: list[int], context: RequestContext | None = None) -> None:
    users = [await session.get(User, user_id) for user_id in set(ids)]
    users = [user for user in users if user is not None]
    if any(_is_protected_system_admin(user) for user in users):
        raise AccessDenied("The built-in System Administrator account cannot be deleted.")
    if context is not None and context.user_id in ids:
        raise AccessDenied("You cannot delete your own account.")

    # Guard: the last Platform Administrator cannot be deleted.
    admin_role_id = (
        await session.execute(select(Role.id).where(Role.code == PLATFORM_ADMIN_ROLE))
    ).scalars().first()
    target_ids = [user.id for user in users]
    if admin_role_id is not None and target_ids:
        deleting_admins = await session.scalar(
            select(func.count())
            .select_from(UserRoleAssignment)
            .where(
                UserRoleAssignment.role_id == admin_role_id,
                UserRoleAssignment.user_id.in_(target_ids),
                UserRoleAssignment.expires_at.is_(None),
            )
        )
        if deleting_admins:
            total_admins = await session.scalar(
                select(func.count())
                .select_from(UserRoleAssignment)
                .where(
                    UserRoleAssignment.role_id == admin_role_id,
                    UserRoleAssignment.expires_at.is_(None),
                )
            )
            if (total_admins or 0) - deleting_admins < 1:
                raise ValidationFailed("At least one Platform Administrator must remain.")

    for user in users:
        await session.execute(delete(UserCredential).where(UserCredential.user_id == user.id))
        await session.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id))
        await session.execute(delete(UserSession).where(UserSession.user_id == user.id))
        await session.delete(user)
    # Deleting every account would make `requires_setup` true again and expose the
    # public first-run setup endpoint; refuse to remove the last user.
    await session.flush()
    if not await session.scalar(select(func.count()).select_from(User)):
        await session.rollback()
        raise ValidationFailed("At least one user account must remain.")
    await session.commit()


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

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.context import RequestContext
from app.core.exceptions import AuthRequired, Conflict, NotFound
from app.core.permissions import PAGE_PERMISSION_SOURCE_CODES, SOURCE_PERMISSIONS
from app.core.redis import safe_delete, safe_get, safe_set
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_code,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.auth.models import (
    PasswordResetToken,
    Permission,
    Role,
    RolePermission,
    User,
    UserCredential,
    UserRoleAssignment,
    UserSession,
)

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
    "service_charge.create": ("finance.service_charges.view", "finance.service_charges.create"),
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
    "audit_log.read": ("admin.audit_logs.view",),
    "report.read": ("operations.reports.view", "finance.reports.view", "reports.view"),
    "report.export": ("operations.reports.export", "finance.reports.export"),
    "master.reference.view": ("master.reference.view",),
    "master.reference.manage": ("master.reference.create", "master.reference.edit", "master.reference.delete"),
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


def expand_source_permissions(permissions: set[str]) -> set[str]:
    """Expand stored page permissions into the source/API permissions they imply."""
    expanded = set(permissions)
    for code in permissions:
        expanded.update(PAGE_PERMISSION_SOURCE_CODES.get(code, ()))
    return expanded


async def get_user_by_login(session: AsyncSession, login: str) -> User | None:
    stmt = select(User).where((User.username == login) | (User.email == login))
    return (await session.execute(stmt)).scalars().first()


async def authenticate(session: AsyncSession, login: str, password: str) -> User:
    user = await get_user_by_login(session, login)
    if user is None:
        raise AuthRequired("Invalid username or password.")
    credential = (
        await session.execute(select(UserCredential).where(UserCredential.user_id == user.id))
    ).scalars().first()
    if credential is None or not verify_password(password, credential.password_hash):
        raise AuthRequired("Invalid username or password.")
    if user.status not in {"ACTIVE"}:
        raise AuthRequired("This account is not active.")
    await session.commit()
    return user


async def resolve_permissions(session: AsyncSession, user_id: int) -> tuple[set[str], list[str]]:
    now = datetime.now(UTC)
    assignments = (
        await session.execute(select(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id))
    ).scalars().all()
    role_ids = {a.role_id for a in assignments if a.expires_at is None or a.expires_at > now}
    role_codes: list[str] = []
    permissions: set[str] = set()
    if role_ids:
        role_codes = list(
            (await session.execute(select(Role.code).where(Role.id.in_(role_ids)))).scalars().all()
        )
        permissions = set(
            (
                await session.execute(
                    select(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id.in_(role_ids))
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
    permissions, role_codes = await resolve_permissions(session, user.id)
    is_platform_admin = "PLATFORM_ADMIN" in role_codes or "*" in permissions
    avatar = await get_user_avatar(session, user.id)

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


def build_auth_user(ctx: RequestContext, role_label: str) -> dict:
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
    }


async def create_session(session: AsyncSession, user: User, *, ip: str | None, user_agent: str | None) -> tuple[str, str]:
    refresh = create_refresh_token(user.id)
    record = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh),
        ip_address=ip,
        user_agent=user_agent,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(record)
    await session.flush()
    access = create_access_token(user.id)
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return access, refresh


async def rotate_refresh_token(session: AsyncSession, refresh_token: str, *, ip: str | None, user_agent: str | None) -> tuple[User, str, str]:
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise AuthRequired("Invalid refresh token.") from exc
    if payload.get("type") != "refresh":
        raise AuthRequired("Invalid token type.")
    token_hash = hash_token(refresh_token)
    record = (
        await session.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash))
    ).scalars().first()
    if record is None or record.revoked_at is not None:
        raise AuthRequired("Session is no longer valid.")
    if record.expires_at < datetime.now(UTC):
        raise AuthRequired("Session has expired.")
    user = await session.get(User, record.user_id)
    if user is None:
        raise AuthRequired("User not found.")
    record.revoked_at = datetime.now(UTC)
    new_refresh = create_refresh_token(user.id)
    record.refresh_token_hash = hash_token(new_refresh)
    record.last_used_at = datetime.now(UTC)
    record.expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    await session.commit()
    access = create_access_token(user.id)
    return user, access, new_refresh


async def revoke_session(session: AsyncSession, user_id: int, refresh_token: str | None) -> None:
    if refresh_token:
        token_hash = hash_token(refresh_token)
        record = (
            await session.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash))
        ).scalars().first()
        if record is not None:
            record.revoked_at = datetime.now(UTC)
    else:
        records = (await session.execute(select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None)))).scalars().all()
        for record in records:
            record.revoked_at = datetime.now(UTC)
    await session.commit()
    await safe_delete(f"revoked:{user_id}")


async def request_password_reset(session: AsyncSession, email: str) -> None:
    user = (await session.execute(select(User).where(User.email == email))).scalars().first()
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
    if not await verify_reset_code(session, email, code):
        raise Conflict("INVALID_RESET_CODE", "The reset code is invalid or has expired.")
    user = (await session.execute(select(User).where(User.email == email))).scalars().first()
    if user is None:
        raise NotFound("User not found.")
    credential = (await session.execute(select(UserCredential).where(UserCredential.user_id == user.id))).scalars().first()
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
    await session.commit()
    await safe_delete(f"reset:{email}")


async def change_password(session: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    credential = (await session.execute(select(UserCredential).where(UserCredential.user_id == user.id))).scalars().first()
    if credential is None or not verify_password(current_password, credential.password_hash):
        raise AuthRequired("Current password is incorrect.")
    credential.password_hash = hash_password(new_password)
    credential.password_changed_at = datetime.now(UTC)
    await session.commit()


async def list_users(session: AsyncSession) -> list[dict]:
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    output = []
    for user in users:
        assignments = (
            await session.execute(
                select(Role.code)
                .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
                .where(UserRoleAssignment.user_id == user.id)
            )
        ).scalars().all()
        output.append(
            {
                "id": user.id,
                "userCode": user.user_code,
                "username": user.username,
                "email": user.email,
                "displayName": user.display_name,
                "phone": user.phone,
                "status": user.status,
                "roles": list(assignments),
            }
        )
    return output


async def create_user(session: AsyncSession, data: dict, context: RequestContext) -> User:
    if (await session.execute(select(User).where(User.email == data["email"]))).scalars().first():
        raise Conflict("DUPLICATE_EMAIL", "A user with this email already exists.", {"email": "Already in use"})
    if (await session.execute(select(User).where(User.username == data["username"]))).scalars().first():
        raise Conflict("DUPLICATE_USERNAME", "A user with this username already exists.", {"username": "Already in use"})
    user = User(
        user_code=data.get("user_code") or data["username"].upper(),
        username=data["username"],
        email=data["email"],
        display_name=data["display_name"],
        phone=data.get("phone"),
        status=data.get("status", "ACTIVE"),
    )
    session.add(user)
    await session.flush()
    session.add(
        UserCredential(
            user_id=user.id,
            password_hash=hash_password(data.get("password") or "changeme123"),
            password_changed_at=datetime.now(UTC),
        )
    )
    role_code = data.get("role_code")
    if role_code:
        role = (await session.execute(select(Role).where(Role.code == role_code))).scalars().first()
        if role is not None:
            session.add(
                UserRoleAssignment(
                    user_id=user.id,
                    role_id=role.id,
                    assigned_by_user_id=context.user_id,
                )
            )
    await session.commit()
    return user


async def update_user(session: AsyncSession, user_id: int, data: dict) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    for key, column in (
        ("email", "email"),
        ("display_name", "display_name"),
        ("displayName", "display_name"),
        ("phone", "phone"),
        ("status", "status"),
        ("locale", "locale"),
        ("timezone", "timezone"),
    ):
        if data.get(key) is not None:
            setattr(user, column, data[key])
    await session.commit()
    return user


async def list_role_assignments(session: AsyncSession, user_id: int) -> list[dict]:
    rows = (
        await session.execute(
            select(UserRoleAssignment, Role.code)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(UserRoleAssignment.user_id == user_id)
        )
    ).all()
    return [
        {
            "id": assignment.id,
            "userId": assignment.user_id,
            "roleId": assignment.role_id,
            "roleCode": code,
            "expiresAt": assignment.expires_at.isoformat() if assignment.expires_at else None,
        }
        for assignment, code in rows
    ]


async def assign_role(session: AsyncSession, user_id: int, data: dict, context: RequestContext) -> UserRoleAssignment:
    role = None
    if data.get("role_id"):
        role = await session.get(Role, data["role_id"])
    elif data.get("role_code"):
        role = (await session.execute(select(Role).where(Role.code == data["role_code"]))).scalars().first()
    if role is None:
        raise NotFound("Role not found.")
    assignment = UserRoleAssignment(
        user_id=user_id,
        role_id=role.id,
        assigned_by_user_id=context.user_id,
        expires_at=data.get("expires_at"),
    )
    session.add(assignment)
    await session.commit()
    return assignment


async def list_roles(session: AsyncSession) -> list[dict]:
    roles = (await session.execute(select(Role).order_by(Role.id))).scalars().all()
    output = []
    for role in roles:
        perms = (
            await session.execute(
                select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id).where(RolePermission.role_id == role.id)
            )
        ).scalars().all()
        output.append(
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "description": role.description,
                "isSystemRole": role.is_system_role,
                "status": role.status,
                "permissions": list(perms),
            }
        )
    return output


async def create_role(session: AsyncSession, data: dict) -> Role:
    if (await session.execute(select(Role).where(Role.code == data["code"]))).scalars().first():
        raise Conflict("DUPLICATE_ROLE", "A role with this code already exists.")
    role = Role(code=data["code"], name=data["name"], description=data.get("description"), status="ACTIVE")
    session.add(role)
    await session.flush()
    await sync_role_permissions(session, role.id, data.get("permissions") or [])
    await session.commit()
    return role


async def update_role(session: AsyncSession, role_id: int, data: dict) -> Role:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFound("Role not found.")
    for key in ("name", "description", "status"):
        if data.get(key) is not None:
            setattr(role, key, data[key])
    if data.get("permissions") is not None:
        await sync_role_permissions(session, role.id, data["permissions"])
    await session.commit()
    return role


async def sync_role_permissions(session: AsyncSession, role_id: int, codes: list[str]) -> None:
    await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    await session.flush()
    if not codes:
        return
    ids = (
        await session.execute(select(Permission.id).where(Permission.code.in_(codes)))
    ).scalars().all()
    for pid in ids:
        session.add(RolePermission(role_id=role_id, permission_id=pid))


async def user_with_credential(session: AsyncSession, user_id: int) -> User | None:
    return (
        await session.execute(select(User).options(selectinload(User.credential)).where(User.id == user_id))
    ).scalars().first()


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
    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "isSystemRole": role.is_system_role,
        "status": role.status,
        "permissions": list(perms),
    }


async def get_role(session: AsyncSession, role_id: int) -> dict:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFound("Role not found.")
    return await role_payload(session, role)


async def delete_roles(session: AsyncSession, ids: list[int]) -> None:
    for role_id in ids:
        role = await session.get(Role, role_id)
        if role is None or role.is_system_role:
            continue
        await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        await session.execute(delete(UserRoleAssignment).where(UserRoleAssignment.role_id == role_id))
        await session.delete(role)
    await session.commit()


async def delete_users(session: AsyncSession, ids: list[int]) -> None:
    for user_id in ids:
        user = await session.get(User, user_id)
        if user is None:
            continue
        await session.execute(delete(UserCredential).where(UserCredential.user_id == user_id))
        await session.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user_id))
        await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
        await session.delete(user)
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
    return avatar


async def clear_user_avatar(session: AsyncSession, context: RequestContext) -> None:
    record = await _avatar_record(session, context.user_id)
    if record is not None:
        await session.delete(record)
        await session.commit()

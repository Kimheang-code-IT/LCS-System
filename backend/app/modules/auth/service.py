from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.context import RequestContext
from app.core.exceptions import AuthRequired, Conflict, NotFound
from app.core.permissions import SOURCE_PERMISSIONS
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
    Branch,
    Organization,
    PasswordResetToken,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranchAssignment,
    UserCredential,
    UserRoleAssignment,
    UserSession,
)

# Map source permissions to frontend page keys (mirrors the Nuxt contract).
PAGE_KEYS_BY_SOURCE: dict[str, tuple[str, ...]] = {
    "organization.read": ("admin.organization.view", "master.reference.view"),
    "organization.update": ("admin.organization.view",),
    "branch.read": ("admin.organization.view", "master.reference.view"),
    "branch.manage": ("admin.organization.view",),
    "user.read": ("admin.users.view",),
    "user.manage": ("admin.users.view",),
    "role.read": ("admin.roles.view",),
    "role.manage": ("admin.roles.view",),
    "quotation.read": ("sales.quotations.view", "sales.companies.view"),
    "quotation.create": ("sales.quotations.create",),
    "quotation.update_draft": ("sales.quotations.edit",),
    "quotation.send": ("sales.quotations.edit",),
    "quotation.accept": ("sales.quotations.edit",),
    "quotation.convert": ("sales.quotations.edit", "operations.service_orders.create"),
    "service_order.read": ("operations.service_orders.view", "operations.jobs.view"),
    "service_order.create": ("operations.service_orders.create",),
    "service_order.update": ("operations.service_orders.edit", "configuration.manage"),
    "service_order.complete": ("operations.service_orders.edit",),
    "service_charge.create": ("finance.service_charges.view", "finance.service_charges.create"),
    "service_charge.issue": ("finance.service_charges.edit",),
    "financial_document.read": ("finance.financial_documents.view", "finance.debit_notes.view"),
    "financial_document.create": ("finance.financial_documents.create", "finance.debit_notes.create"),
    "financial_document.post": ("finance.financial_documents.edit",),
    "journal_entry.read": ("finance.accounting.view", "finance.journals.view"),
    "journal_entry.create": ("finance.journals.create",),
    "accounting_period.read": ("finance.accounting.view", "finance.accounting_periods.view"),
    "accounting_period.close": ("finance.accounting_periods.edit",),
    "audit_log.read": ("admin.audit_logs.view",),
    "report.read": ("dashboard.view", "reports.view"),
    "master.reference.view": ("master.reference.view",),
    "configuration.manage": ("configuration.manage",),
}


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


async def resolve_permissions(session: AsyncSession, user_id: int, organization_id: int) -> tuple[set[str], str, list[int], list[str]]:
    now = datetime.now(UTC)
    assignments = (
        await session.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.organization_id == organization_id,
            )
        )
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
    scope = "ORGANIZATION" if any(a.branch_id is None for a in assignments) else ("BRANCH" if assignments else "NONE")
    branch_rows = (
        await session.execute(
            select(UserBranchAssignment.branch_id).where(
                UserBranchAssignment.user_id == user_id,
                UserBranchAssignment.organization_id == organization_id,
            )
        )
    ).scalars().all()
    assigned_branch_ids = list(branch_rows)
    return permissions, scope, assigned_branch_ids, role_codes


def resolve_page_keys(permissions: set[str], is_platform_admin: bool) -> tuple[list[str], list[str]]:
    source = [code for code, _, _ in SOURCE_PERMISSIONS if code in permissions]
    if is_platform_admin or "ALL_PAGES" in permissions:
        return ["ALL_PAGES"], ["ALL_PAGES"]
    pages: set[str] = {"dashboard.view"}
    for code in source:
        pages.update(PAGE_KEYS_BY_SOURCE.get(code, ()))
    for code in permissions:
        if "." in code and code not in source:
            pages.add(code)
    return sorted(source), sorted(pages)


async def build_context(
    session: AsyncSession,
    user: User,
    *,
    request_id: str,
    organization_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RequestContext:
    if organization_id is None:
        organization_id = (
            await session.execute(
                select(UserBranchAssignment.organization_id)
                .where(UserBranchAssignment.user_id == user.id)
                .limit(1)
            )
        ).scalar()
    if organization_id is None:
        organization_id = (
            await session.execute(select(UserRoleAssignment.organization_id).where(UserRoleAssignment.user_id == user.id).limit(1))
        ).scalar()
    org = await session.get(Organization, organization_id) if organization_id else None
    if org is None:
        raise AuthRequired("No organization is assigned to this account.")

    permissions, scope, assigned_branch_ids, role_codes = await resolve_permissions(session, user.id, org.id)
    is_platform_admin = "PLATFORM_ADMIN" in role_codes or "*" in permissions

    branch_id = None
    branch_name = None
    default_branch = (
        await session.execute(
            select(Branch)
            .join(UserBranchAssignment, UserBranchAssignment.branch_id == Branch.id)
            .where(
                UserBranchAssignment.user_id == user.id,
                UserBranchAssignment.organization_id == org.id,
                UserBranchAssignment.is_default.is_(True),
            )
            .limit(1)
        )
    ).scalars().first()
    if default_branch is None and assigned_branch_ids:
        default_branch = await session.get(Branch, assigned_branch_ids[0])
    if default_branch is not None:
        branch_id = default_branch.id
        branch_name = default_branch.name

    return RequestContext(
        user_id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        organization_id=org.id,
        organization_code=org.organization_code,
        organization_name=org.display_name or org.legal_name,
        branch_id=branch_id,
        branch_name=branch_name,
        assigned_branch_ids=assigned_branch_ids,
        permissions=permissions | ({"ALL_PAGES"} if is_platform_admin else set()),
        permission_scope="ORGANIZATION" if is_platform_admin else scope,
        is_platform_admin=is_platform_admin,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def build_auth_user(ctx: RequestContext, role_label: str) -> dict:
    source_permissions, page_access = resolve_page_keys(ctx.permissions, ctx.is_platform_admin)
    return {
        "id": ctx.user_id,
        "name": ctx.display_name,
        "email": ctx.email,
        "role": role_label,
        "permissions": page_access,
        "pageAccess": page_access,
        "organizationId": ctx.organization_id,
        "organizationCode": ctx.organization_code,
        "organizationName": ctx.organization_name,
        "branchId": ctx.branch_id,
        "branchName": ctx.branch_name,
        "assignedBranchIds": ctx.assigned_branch_ids,
        "permissionScope": ctx.permission_scope,
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
    access = create_access_token(user.id, {"org": None})
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


async def list_users(session: AsyncSession, organization_id: int) -> list[dict]:
    users = (
        await session.execute(
            select(User)
            .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
            .where(UserRoleAssignment.organization_id == organization_id)
            .distinct()
            .order_by(User.id)
        )
    ).scalars().all()
    output = []
    for user in users:
        assignments = (
            await session.execute(
                select(Role.code)
                .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
                .where(UserRoleAssignment.user_id == user.id, UserRoleAssignment.organization_id == organization_id)
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
                    organization_id=data.get("organization_id") or context.organization_id,
                    branch_id=data.get("branch_id"),
                )
            )
    await session.commit()
    return user


async def update_user(session: AsyncSession, user_id: int, data: dict) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    for key in ("email", "display_name", "phone", "status", "locale", "timezone"):
        if data.get(key) is not None:
            setattr(user, key, data[key])
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
            "organizationId": assignment.organization_id,
            "branchId": assignment.branch_id,
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
        organization_id=data.get("organization_id") or context.organization_id,
        branch_id=data.get("branch_id"),
        assigned_by_user_id=context.user_id,
        expires_at=data.get("expires_at"),
    )
    session.add(assignment)
    await session.commit()
    return assignment


async def list_roles(session: AsyncSession, organization_id: int) -> list[dict]:
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


async def list_organizations(session: AsyncSession) -> list[Organization]:
    return list((await session.execute(select(Organization).order_by(Organization.id))).scalars().all())


async def list_branches(session: AsyncSession, organization_id: int) -> list[Branch]:
    return list(
        (await session.execute(select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.id))).scalars().all()
    )


async def create_organization(session: AsyncSession, data: dict) -> Organization:
    org = Organization(
        organization_code=data["organization_code"],
        legal_name=data["legal_name"],
        display_name=data.get("display_name"),
        default_currency_code=data.get("default_currency_code", "USD"),
        timezone=data.get("timezone", "UTC"),
        status="ACTIVE",
    )
    session.add(org)
    await session.commit()
    return org


async def create_branch(session: AsyncSession, organization_id: int, data: dict) -> Branch:
    branch = Branch(
        organization_id=organization_id,
        branch_code=data["branch_code"],
        name=data["name"],
        place_id=data.get("place_id"),
        address=data.get("address"),
        is_head_office=bool(data.get("is_head_office", False)),
        status="ACTIVE",
    )
    session.add(branch)
    await session.commit()
    return branch


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

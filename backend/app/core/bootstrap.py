"""Baseline provisioning shared by the setup API, the CLI and the test harness.

The database ships empty. ``provision_admin`` creates the first administrator
account with its role assignment and seeds the default configuration: document
sequences for the current year and the default app info/config records. No
business or finance data (accounts, periods, parties, documents) is seeded —
every record is entered manually. ``reset_all_data`` returns the database to
that pristine, "setup required" state.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.permissions import (
    BUILTIN_ROLE_CODES,
    PERMISSION_CATALOG,
    ROLE_DEFINITIONS,
    permission_name,
)
from app.core.security import hash_password, validate_password_strength
from app.modules.auth.models import (
    PROTECTED_SYSTEM_ADMIN_IDENTITY,
    Permission,
    Role,
    RolePermission,
    User,
    UserCredential,
    UserRoleAssignment,
)

DEFAULT_ROLES = ", ".join(BUILTIN_ROLE_CODES)


async def ensure_permission_catalog(
    session: AsyncSession,
    *,
    role_codes: Iterable[str] | None = None,
) -> None:
    """Create missing permissions, roles and role → permission mappings.

    Only the built-in roles (PLATFORM_ADMIN) are provisioned by default; every
    other role is created manually from the Roles & Permissions page. Pass
    ``role_codes`` to provision additional defined roles (used by tests).
    """
    existing = {code for (code,) in (await session.execute(select(Permission.code))).all()}
    for code, resource, action in PERMISSION_CATALOG:
        if code not in existing:
            session.add(Permission(code=code, name=permission_name(code), resource=resource, action=action))
    await session.flush()

    permission_ids = {code: pid for pid, code in (await session.execute(select(Permission.id, Permission.code))).all()}
    roles = {role.code: role for role in (await session.execute(select(Role))).scalars().all()}
    for code in tuple(BUILTIN_ROLE_CODES if role_codes is None else role_codes):
        definition = ROLE_DEFINITIONS.get(code)
        if definition is None:
            continue
        role = roles.get(code)
        if role is None:
            role = Role(
                code=code,
                name=str(definition["name"]),
                description=str(definition["description"]),
                is_system_role=True,
            )
            session.add(role)
            await session.flush()
            roles[code] = role
        else:
            role.is_system_role = True
            role.status = "ACTIVE"
        current = set(
            (
                await session.execute(
                    select(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == role.id)
                )
            )
            .scalars()
            .all()
        )
        for code_to_add in set(definition["permissions"]) - current:  # type: ignore[arg-type]
            pid = permission_ids.get(code_to_add)
            if pid is not None:
                session.add(RolePermission(role_id=role.id, permission_id=pid))

    protected_user = (
        await session.execute(
            select(User).where(User.system_identity == PROTECTED_SYSTEM_ADMIN_IDENTITY)
        )
    ).scalars().first()
    platform_role = roles.get("PLATFORM_ADMIN")
    if protected_user is not None and platform_role is not None:
        protected_user.status = "ACTIVE"
        active_assignments = (
            await session.execute(
                select(UserRoleAssignment).where(
                    UserRoleAssignment.user_id == protected_user.id,
                    UserRoleAssignment.expires_at.is_(None),
                )
            )
        ).scalars().all()
        if not any(assignment.role_id == platform_role.id for assignment in active_assignments):
            now = datetime.now(UTC)
            for assignment in active_assignments:
                assignment.expires_at = now
            await session.flush()
            session.add(UserRoleAssignment(user_id=protected_user.id, role_id=platform_role.id))
    await session.commit()


async def requires_setup(session: AsyncSession) -> bool:
    """True while the database has no user account (fresh migration or reset)."""
    total = await session.scalar(select(func.count()).select_from(User))
    return not total


async def provision_baseline(session: AsyncSession) -> None:
    """Seed default configuration.

    Idempotent — existing rows are left untouched. Business/finance data
    (accounts, periods, parties, documents) is never seeded. What is seeded is
    configuration the application cannot invent at runtime:

    * document-number sequences for the current year;
    * the currency master (so every configured currency resolves to a row);
    * the default app info/config, both in ``app_settings`` (the system of
      record) and mirrored into the legacy ``module_records`` payload.
    """
    from copy import deepcopy

    from app.core.localization import SUPPORTED_CURRENCIES
    from app.core.sequences import DEFAULT_PREFIXES
    from app.modules.finance.models import DocumentSequence
    from app.modules.master_data.models import Currency, ModuleRecord
    from app.modules.settings.models import AppSetting
    from app.modules.settings.service import (
        APP_CONFIG_COLLECTION,
        APP_INFO_COLLECTION,
        APP_INFO_GROUP,
        APP_INFO_KEY,
        DEFAULT_APP_CONFIG,
        DEFAULT_APP_INFO,
        SETTINGS_RECORD_NO,
    )

    year = datetime.now(UTC).year

    existing_types = set(
        (
            await session.execute(
                select(DocumentSequence.document_type).where(DocumentSequence.period_year == year)
            )
        )
        .scalars()
        .all()
    )
    for document_type, prefix in DEFAULT_PREFIXES.items():
        if document_type not in existing_types:
            session.add(
                DocumentSequence(
                    document_type=document_type,
                    period_year=year,
                    prefix=prefix,
                    last_value=0,
                    padding_length=6,
                    status="ACTIVE",
                )
            )

    existing_currencies = set(
        (await session.execute(select(Currency.code).where(Currency.deleted_at.is_(None)))).scalars().all()
    )
    for code in SUPPORTED_CURRENCIES:
        if code not in existing_currencies:
            session.add(Currency(code=code, name=code, symbol=None, status="ACTIVE"))

    existing_settings = set((await session.execute(select(AppSetting.setting_key))).scalars().all())
    if APP_INFO_KEY not in existing_settings:
        session.add(
            AppSetting(
                setting_key=APP_INFO_KEY,
                setting_group=APP_INFO_GROUP,
                setting_value=deepcopy(DEFAULT_APP_INFO),
                description="Application identity, branding and support contacts.",
            )
        )
    for group, defaults in DEFAULT_APP_CONFIG.items():
        if group not in existing_settings:
            session.add(
                AppSetting(
                    setting_key=group,
                    setting_group=group,
                    setting_value=deepcopy(defaults),
                    description=f"Application settings group '{group}'.",
                )
            )

    # Transitional mirror so an application rollback still reads the settings an
    # administrator last saved. Safe to drop once the mirror is no longer needed.
    for collection, defaults in (
        (APP_INFO_COLLECTION, DEFAULT_APP_INFO),
        (APP_CONFIG_COLLECTION, DEFAULT_APP_CONFIG),
    ):
        exists = (
            await session.execute(
                select(ModuleRecord.id).where(
                    ModuleRecord.collection == collection,
                    ModuleRecord.record_no == SETTINGS_RECORD_NO,
                )
            )
        ).scalars().first()
        if exists is None:
            session.add(ModuleRecord(collection=collection, record_no=SETTINGS_RECORD_NO, data=deepcopy(defaults)))

    await session.flush()


async def provision_admin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    username: str | None = None,
    name: str | None = None,
    user_code: str | None = None,
    role_code: str = "PLATFORM_ADMIN",
) -> dict[str, Any]:
    """Create/refresh the baseline admin. Raises ``ValueError`` on invalid input."""
    password_errors = validate_password_strength(password)
    if password_errors:
        raise ValueError(password_errors[0])
    username = username or email.split("@")[0]
    user_code = user_code or username.upper().replace(".", "-")[:50]
    display_name = name or username.replace(".", " ").title()

    await ensure_permission_catalog(session)

    role = (await session.execute(select(Role).where(Role.code == role_code))).scalars().first()
    if role is None:
        raise ValueError(f"Unknown role '{role_code}'. Known roles: {DEFAULT_ROLES}.")

    user = (
        await session.execute(select(User).where((User.email == email) | (User.username == username)))
    ).scalars().first()
    protected_exists = await session.scalar(
        select(func.count()).select_from(User).where(
            User.system_identity == PROTECTED_SYSTEM_ADMIN_IDENTITY,
        )
    )
    if user is None:
        user = User(
            user_code=user_code,
            username=username,
            email=email,
            display_name=display_name,
            status="ACTIVE",
            system_identity=PROTECTED_SYSTEM_ADMIN_IDENTITY if not protected_exists else None,
        )
        session.add(user)
        await session.flush()
        user_created = True
    else:
        user_created = False
        if not protected_exists:
            user.system_identity = PROTECTED_SYSTEM_ADMIN_IDENTITY

    credential = (await session.execute(select(UserCredential).where(UserCredential.user_id == user.id))).scalars().first()
    if credential is None:
        session.add(UserCredential(user_id=user.id, password_hash=hash_password(password)))
    else:
        credential.password_hash = hash_password(password)

    assignment = (
        await session.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.role_id == role.id,
            )
        )
    ).scalars().first()
    if assignment is None:
        session.add(UserRoleAssignment(user_id=user.id, role_id=role.id))

    await provision_baseline(session)
    await session.commit()

    return {
        "email": user.email,
        "username": user.username,
        "role": role.code,
        "user": "created" if user_created else "updated",
    }


async def reset_all_data(session: AsyncSession) -> None:
    """Reset business data while preserving identities and security history.

    Authentication/RBAC tables are deliberately excluded: an administrative
    reset must never delete the protected System Administrator or reopen the
    unauthenticated first-run setup flow.
    """
    # Importing the model modules guarantees Base.metadata sees every table.
    import app.modules.archive.models  # noqa: F401
    import app.modules.audit.models  # noqa: F401
    import app.modules.master_data.models  # noqa: F401
    import app.modules.operations.models  # noqa: F401
    import app.modules.quotations.models  # noqa: F401
    import app.modules.settings.models  # noqa: F401

    preserved_tables = {
        "users",
        "user_credentials",
        "user_sessions",
        "roles",
        "permissions",
        "role_permissions",
        "user_role_assignments",
        "audit_events",
    }
    # PostgreSQL guards make posted journals and their lines immutable and audit
    # events append-only. An administrative reset is the one operation allowed to
    # clear them, so it opens the transaction-scoped escape hatch that the guard
    # functions check. SET LOCAL cannot leak past this transaction.
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(text("SET LOCAL lcs.allow_financial_purge = 'on'"))
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in preserved_tables:
            continue
        await session.execute(delete(table))
    await provision_baseline(session)
    await session.commit()

"""Baseline provisioning shared by the setup API, the CLI and the test harness.

The database ships empty. ``provision_admin`` creates the first administrator
account with its role assignment and seeds the default configuration: document
sequences for the current year and the default app info/config records. No
business or finance data (accounts, periods, parties, documents) is seeded —
every record is entered manually. ``reset_all_data`` returns the database to
that pristine, "setup required" state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.permissions import PERMISSION_CATALOG, ROLE_DEFINITIONS, permission_name
from app.core.security import hash_password
from app.modules.auth.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserCredential,
    UserRoleAssignment,
)

DEFAULT_ROLES = ", ".join(ROLE_DEFINITIONS.keys())


async def ensure_permission_catalog(session: AsyncSession) -> None:
    """Create missing permissions, roles and role → permission mappings."""
    existing = {code for (code,) in (await session.execute(select(Permission.code))).all()}
    for code, resource, action in PERMISSION_CATALOG:
        if code not in existing:
            session.add(Permission(code=code, name=permission_name(code), resource=resource, action=action))
    await session.flush()

    permission_ids = {code: pid for pid, code in (await session.execute(select(Permission.id, Permission.code))).all()}
    roles = {role.code: role for role in (await session.execute(select(Role))).scalars().all()}
    for code, definition in ROLE_DEFINITIONS.items():
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
    await session.commit()


async def requires_setup(session: AsyncSession) -> bool:
    """True while the database has no user account (fresh migration or reset)."""
    total = await session.scalar(select(func.count()).select_from(User))
    return not total


async def provision_baseline(session: AsyncSession) -> None:
    """Seed default configuration: document sequences and app info/config.

    Idempotent — existing rows are left untouched. Business/finance data
    (accounts, periods, parties, documents) is never seeded.
    """
    from copy import deepcopy

    from app.core.sequences import DEFAULT_PREFIXES
    from app.modules.finance.models import DocumentSequence
    from app.modules.master_data.models import ModuleRecord
    from app.modules.settings.service import (
        APP_CONFIG_COLLECTION,
        APP_INFO_COLLECTION,
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
    """Create/refresh the baseline admin. Raises ``ValueError`` on unknown role."""
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
    if user is None:
        user = User(user_code=user_code, username=username, email=email, display_name=display_name, status="ACTIVE")
        session.add(user)
        await session.flush()
        user_created = True
    else:
        user_created = False

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
    """Delete every row (business data, users, config) — back to setup-required."""
    # Importing the model modules guarantees Base.metadata sees every table.
    import app.modules.audit.models  # noqa: F401
    import app.modules.master_data.models  # noqa: F401
    import app.modules.operations.models  # noqa: F401
    import app.modules.quotations.models  # noqa: F401

    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(delete(table))
    await session.commit()

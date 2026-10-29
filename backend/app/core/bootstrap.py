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

from app.core import authorization
from app.core.database import Base
from app.core.permissions import (
    BUILTIN_ROLE_CODES,
    PERMISSION_CATALOG,
    ROLE_DEFINITIONS,
    SUPER_ADMIN_ROLE,
    compile_role_permissions,
    permission_module,
    permission_name,
)
from app.core.security import hash_password, validate_password_strength
from app.modules.auth.models import (
    PROTECTED_SYSTEM_ADMIN_IDENTITY,
    Permission,
    Role,
    User,
    UserCredential,
)

DEFAULT_ROLES = ", ".join(BUILTIN_ROLE_CODES)

#: Starting place roles. Configuration owners edit, reorder, deactivate or add to
#: this list through Master Data; the codes are only the seed identity.
DEFAULT_PLACE_ROLES: tuple[tuple[str, str, str], ...] = (
    ("PICKUP", "Pickup", "Goods are collected at this location."),
    ("DROPOFF", "Drop-off", "Goods are handed over at this location."),
    ("ORIGIN", "Origin", "Start of the commercial transport route."),
    ("DESTINATION", "Destination", "End of the commercial transport route."),
    ("LOADING", "Loading", "Goods or containers are loaded here."),
    ("UNLOADING", "Unloading", "Goods or containers are unloaded here."),
    ("TRANSIT", "Transit", "An intermediate or border crossing point."),
    ("CUSTOMS", "Customs Clearance", "A customs office or clearance location."),
    ("DELIVERY", "Delivery", "Final delivery location."),
    ("RETURN", "Return Location", "Empty containers or equipment are returned here."),
)

#: Starting business-party roles; formerly the hardcoded Customer/Supplier/Company
#: options. Administrators rename, deactivate or extend them through Master Data.
DEFAULT_PARTY_ROLES: tuple[tuple[str, str, str], ...] = (
    ("CUSTOMER", "Customer", "Buys the freight service."),
    ("SUPPLIER", "Supplier", "Provides a service or cost to the shipment."),
    ("COMPANY", "Company", "Internal or group company acting as a party."),
)


async def ensure_permission_catalog(
    session: AsyncSession,
    *,
    role_codes: Iterable[str] | None = None,
) -> None:
    """Create missing permissions, seed roles and synchronize their Casbin grants.

    Idempotent and additive: an existing role only gains the grants it is missing,
    so an administrator's customization survives a restart. ``SUPER_ADMIN`` keeps
    its protected ``*, *`` policy. Pass ``role_codes`` to provision a subset.
    """
    existing = {code for (code,) in (await session.execute(select(Permission.code))).all()}
    for code, resource, action in PERMISSION_CATALOG:
        if code not in existing:
            session.add(
                Permission(
                    code=code,
                    name=permission_name(code),
                    module=permission_module(code),
                    resource=resource,
                    action=action,
                )
            )
    await session.flush()

    roles = {role.code: role for role in (await session.execute(select(Role))).scalars().all()}
    wanted = tuple(BUILTIN_ROLE_CODES if role_codes is None else role_codes)
    for code in wanted:
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

    await session.flush()

    for code in wanted:
        definition = ROLE_DEFINITIONS.get(code)
        if definition is None or code not in roles:
            continue
        current = set(await authorization.role_permission_codes(session, code))
        if code == SUPER_ADMIN_ROLE:
            desired = current | {"*"}
        else:
            desired = current | set(
                compile_role_permissions(definition["permissions"])  # type: ignore[arg-type]
            )
        if desired != current:
            await authorization.set_role_permissions(session, code, desired)

    protected_user = (
        await session.execute(
            select(User).where(User.system_identity == PROTECTED_SYSTEM_ADMIN_IDENTITY)
        )
    ).scalars().first()
    if protected_user is not None and SUPER_ADMIN_ROLE in roles:
        protected_user.status = "ACTIVE"
        assigned = await authorization.user_role_codes(session, protected_user.id)
        if SUPER_ADMIN_ROLE not in assigned:
            await authorization.set_user_roles(session, protected_user.id, [*assigned, SUPER_ADMIN_ROLE])

    await session.commit()
    # Reload immediately so a deploy applies the new grants without waiting for
    # the reload interval, and publish the change to every other worker.
    await authorization.refresh(session)


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
    from app.modules.master_data.models import Currency, ModuleRecord, PartyRole, PlaceRole
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

    # The route-stop vocabulary is configuration: these are starting records an
    # administrator may rename, reorder, deactivate or extend. They are seeded as
    # data rather than shipped as a code-owned dropdown, and only missing codes
    # are inserted so a rename survives a restart.
    existing_roles = set(
        (await session.execute(select(PlaceRole.code).where(PlaceRole.deleted_at.is_(None)))).scalars().all()
    )
    for index, (code, role_name, role_description) in enumerate(DEFAULT_PLACE_ROLES):
        if code not in existing_roles:
            session.add(
                PlaceRole(
                    code=code,
                    name=role_name,
                    description=role_description,
                    sort_order=(index + 1) * 10,
                    status="ACTIVE",
                )
            )

    # The business-party vocabulary, formerly a hardcoded dropdown.
    existing_party_roles = set(
        (await session.execute(select(PartyRole.code).where(PartyRole.deleted_at.is_(None)))).scalars().all()
    )
    for code, role_name, role_description in DEFAULT_PARTY_ROLES:
        if code not in existing_party_roles:
            session.add(
                PartyRole(
                    code=code,
                    name=role_name,
                    description=role_description,
                    status="ACTIVE",
                )
            )

    # The transport-asset identity vocabulary (License Plate, IMO Number, …) was
    # a hardcoded dropdown; it is seeded as configuration like the roles above.
    # Transport types themselves are administrator data, so a fresh database
    # seeds unlinked identity types (offered for every type) until the
    # administrator links them from the Asset Identity Types master.
    from app.modules.master_data.service import seed_capacity_units, seed_transport_asset_identity_types

    await seed_transport_asset_identity_types(session)

    # The capacity-unit list (KG, CBM, Pallets, …) backs the asset capacity
    # select; seeded like the vocabulary above.
    await seed_capacity_units(session)

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
    role_code: str = SUPER_ADMIN_ROLE,
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

    assignment = await authorization.user_role_codes(session, user.id)
    if role.code not in assignment:
        await authorization.set_user_roles(session, user.id, [*assignment, role.code])

    await provision_baseline(session)
    await session.commit()
    await authorization.refresh(session)

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
    import app.modules.excel_io.models  # noqa: F401
    import app.modules.master_data.models  # noqa: F401
    import app.modules.operations.models  # noqa: F401
    import app.modules.quotations.models  # noqa: F401
    import app.modules.settings.models  # noqa: F401
    import app.modules.telegram.models  # noqa: F401

    preserved_tables = {
        "users",
        "user_credentials",
        "used_refresh_tokens",
        "user_sessions",
        "roles",
        "permissions",
        "casbin_rule",
        "audit_events",
        "import_jobs",
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

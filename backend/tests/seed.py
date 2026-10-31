"""Test-only fixtures.

This module is NOT used by the application — production ships with an empty
database and every record is entered manually. These helpers only exist so the
test-suite has a deterministic starting point.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import authorization
from app.core.bootstrap import ensure_permission_catalog
from app.core.permissions import ROLE_DEFINITIONS
from app.core.security import hash_password
from app.modules.auth.models import (
    PROTECTED_SYSTEM_ADMIN_IDENTITY,
    Role,
    User,
    UserCredential,
)
from app.modules.finance.models import (
    AccountingPeriod,
    ChartOfAccount,
    DocumentSequence,
    FinancialAccount,
    PostingRule,
)
from app.modules.master_data.models import (
    BusinessParty,
    BusinessPartyRole,
    ComponentAttribute,
    ComponentGroup,
    ComponentGroupAttribute,
    ComponentTab,
    ComponentTabGroup,
    ContainerType,
    FeeType,
    PartyRole,
    PlaceRole,
    TradeDirection,
    TransportType,
)
from app.modules.master_data.service import seed_capacity_units, seed_transport_asset_identity_types

DEMO_USERS = [
    ("ADMIN-001", "admin", "admin@example.test", "Demo Administrator", "SUPER_ADMIN", "ADMIN"),
    ("OPS-PP-001", "ops.pp", "ops.pp@example.test", "Phnom Penh Operations", "OPERATIONS", "OPS"),
    ("FIN-001", "finance", "finance@example.test", "Finance Officer", "ACCOUNTANT", "FIN"),
    ("SALES-001", "sales", "sales@example.test", "Sales Officer", "SALES", "SALES"),
]

DEFAULT_PASSWORD = "Passw0rd!"

COA_SEED = [
    ("1010", "Cash on Hand", "ASSET", "DEBIT"),
    ("1020", "Bank Account", "ASSET", "DEBIT"),
    ("1100", "Accounts Receivable", "ASSET", "DEBIT"),
    ("1200", "Prepayments", "ASSET", "DEBIT"),
    ("2010", "Accounts Payable", "LIABILITY", "CREDIT"),
    ("3010", "Owner Equity", "EQUITY", "CREDIT"),
    ("4010", "Service Revenue", "REVENUE", "CREDIT"),
    ("4020", "Other Income", "REVENUE", "CREDIT"),
    ("5010", "Transport Expense", "EXPENSE", "DEBIT"),
    ("5020", "Customs Expense", "EXPENSE", "DEBIT"),
    ("5030", "Office Expense", "EXPENSE", "DEBIT"),
    ("5040", "Bank Charges", "EXPENSE", "DEBIT"),
]

POSTING_RULES = [
    ("CUSTOMER_INVOICE", "1100", "4010"),
    ("SUPPLIER_BILL", "5010", "2010"),
    ("CUSTOMER_RECEIPT", "1020", "1100"),
    ("SUPPLIER_PAYMENT", "2010", "1020"),
    ("OTHER_INCOME", "1020", "4020"),
    ("OTHER_EXPENSE", "5030", "1020"),
]

DOCUMENT_SEQUENCES = [
    ("QUOTATION", "Q"),
    ("SERVICE_ORDER", "SO"),
    ("SERVICE_CHARGE", "SC"),
    ("CUSTOMER_INVOICE", "INV"),
    ("SUPPLIER_BILL", "BILL"),
    ("CUSTOMER_RECEIPT", "REC"),
    ("SUPPLIER_PAYMENT", "PAY"),
    ("JOURNAL", "JE"),
]

async def ensure_seed_data(session: AsyncSession) -> None:
    """Idempotently seed permissions, roles and default role mappings.

    Unlike production, tests provision every defined role so the demo users can
    log in with their assigned permissions.
    """
    await ensure_permission_catalog(session, role_codes=ROLE_DEFINITIONS.keys())


async def _get_or_create(session: AsyncSession, model: type, defaults: dict, **filters):
    instance = (await session.execute(select(model).filter_by(**filters))).scalars().first()
    if instance is not None:
        return instance
    instance = model(**filters, **defaults)
    session.add(instance)
    await session.flush()
    return instance


async def _ensure_finance_baseline(session: AsyncSession) -> None:
    today = date.today()

    for offset in range(0, 3):
        month = today.month - offset
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        start = date(year, month, 1)
        end = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        await _get_or_create(
            session, AccountingPeriod,
            {"start_date": start, "end_date": end, "status": "OPEN"},
            period_year=year, period_month=month,
        )

    for document_type, prefix in DOCUMENT_SEQUENCES:
        await _get_or_create(
            session, DocumentSequence,
            {"prefix": prefix, "padding_length": 6},
            document_type=document_type, period_year=today.year,
        )

    for code, name, account_type, normal_balance in COA_SEED:
        await _get_or_create(
            session, ChartOfAccount,
            {"account_name": name, "account_type": account_type, "normal_balance": normal_balance, "is_postable": True},
            account_code=code,
        )
    await session.flush()

    accounts = {
        account.account_code: account
        for account in (await session.execute(select(ChartOfAccount))).scalars().all()
    }
    for account_name, account_type, bank_name, masked in [
        ("Bank Account", "BANK", "ABA Bank", "****1234"),
        ("Cash on Hand", "CASH", None, None),
    ]:
        ledger = accounts.get("1020" if account_type == "BANK" else "1010")
        if ledger is None:
            continue
        await _get_or_create(
            session, FinancialAccount,
            {"account_name": account_name, "account_type": account_type, "currency_code": "USD", "bank_name": bank_name, "account_number_masked": masked},
            account_id=ledger.id,
        )

    for document_type, debit_code, credit_code in POSTING_RULES:
        debit = accounts.get(debit_code)
        credit = accounts.get(credit_code)
        if debit is None or credit is None:
            continue
        await _get_or_create(
            session, PostingRule,
            {"debit_account_id": debit.id, "credit_account_id": credit.id, "status": "ACTIVE"},
            document_type=document_type, fee_type_id=None,
        )
    await session.flush()


async def seed_demo_data(session: AsyncSession) -> None:
    for index, (code, name, description) in enumerate([
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
    ]):
        await _get_or_create(
            session,
            PlaceRole,
            {"name": name, "description": description, "sort_order": (index + 1) * 10, "status": "ACTIVE"},
            code=code,
        )

    for code, name, description in [
        ("IMPORT", "Import", "Goods enter the country"),
        ("EXPORT", "Export", "Goods leave the country"),
        ("TRANSIT", "Transit", "Goods pass through the country"),
        ("RE_EXPORT", "Re-export", "Previously imported goods leave the country"),
    ]:
        await _get_or_create(session, TradeDirection, {"name": name, "description": description}, code=code)

    for code, name in [("TRUCK", "Truck"), ("VESSEL", "Vessel"), ("AIR", "Air"), ("RAIL", "Rail"), ("MULTIMODAL", "Multimodal")]:
        await _get_or_create(session, TransportType, {"name": name}, code=code)

    # The transport-asset identity vocabulary (License Plate, IMO Number, …) is
    # master data; seed it here so the rows link to the types above.
    await seed_transport_asset_identity_types(session, (await session.execute(select(TransportType))).scalars().all())
    # Capacity units (KG, CBM, Pallets, ...) back the capacity select the same way.
    await seed_capacity_units(session)
    # Attributing the seeded vocabulary mirrors production provisioning: the
    # lists' creator column shows "System" for these rows.
    from app.modules.master_data.service import ensure_vocabulary_creation_audit

    await ensure_vocabulary_creation_audit(session)

    for code, name, size, kind, iso_code, length in [
        ("20DV", "20-foot Dry Van", "20FT", "DRY", "22G1", 20),
        ("40DV", "40-foot Dry Van", "40FT", "DRY", "42G1", 40),
        ("40HC", "40-foot High Cube", "40FT", "HIGH_CUBE", "45G1", 40),
        ("40RF", "40-foot Reefer", "40FT", "REEFER", "45R1", 40),
    ]:
        await _get_or_create(
            session, ContainerType,
            {"name": name, "container_size": size, "container_kind": kind, "iso_code": iso_code, "length_feet": length},
            code=code,
        )

    for code, name in [
        ("CUSTOMS_CLEARANCE", "Customs Clearance"),
        ("INLAND_TRANSPORT", "Inland Transport"),
        ("BORDER_HANDLING", "Border Handling"),
        ("DOCUMENTATION", "Documentation"),
        ("STORAGE", "Storage"),
        ("PORT_HANDLING", "Port Handling"),
        ("OTHER", "Other"),
    ]:
        await _get_or_create(session, FeeType, {"name": name}, code=code)

    attribute_defs = [
        ("declaration_no", "Declaration Number", "text", True, 10),
        ("clearance_date", "Clearance Date", "date", False, 20),
        ("duty_amount", "Duty Amount", "number", False, 30),
    ]
    attributes: dict[str, ComponentAttribute] = {}
    for code, label, data_type, required, _order in attribute_defs:
        attributes[code] = await _get_or_create(
            session, ComponentAttribute, {"label": label, "data_type": data_type, "is_required": required}, code=code
        )

    group = await _get_or_create(
        session, ComponentGroup, {"name": "Customs", "render_mode": "table", "display_order": 10}, code="CUSTOMS"
    )
    existing_memberships = (
        await session.execute(select(ComponentGroupAttribute).where(ComponentGroupAttribute.group_id == group.id))
    ).scalars().all()
    if not existing_memberships:
        for code, _label, _data_type, _required, order in attribute_defs:
            session.add(
                ComponentGroupAttribute(
                    group_id=group.id, attribute_id=attributes[code].id, display_order=order, status="ACTIVE"
                )
            )
        await session.flush()

    import_direction = (await session.execute(select(TradeDirection).where(TradeDirection.code == "IMPORT"))).scalars().first()
    tab = await _get_or_create(
        session,
        ComponentTab,
        {
            "name": "Customs",
            "display_order": 10,
            "trade_direction_id": import_direction.id if import_direction else None,
        },
        code="CUSTOMS",
    )
    tab_group = (
        await session.execute(
            select(ComponentTabGroup).where(ComponentTabGroup.tab_id == tab.id, ComponentTabGroup.group_id == group.id)
        )
    ).scalars().first()
    if tab_group is None:
        session.add(ComponentTabGroup(tab_id=tab.id, group_id=group.id, display_order=10, status="ACTIVE"))
    await session.flush()

    customers = [
        ("CUST-001", "ABC Manufacturing Co., Ltd.", "CUSTOMER"),
        ("CUST-002", "Mekong Trading Co., Ltd.", "CUSTOMER"),
    ]
    party_roles = {
        code: await _get_or_create(session, PartyRole, {"name": name.title(), "status": "ACTIVE"}, code=code)
        for code, name in (("CUSTOMER", "customer"), ("SUPPLIER", "supplier"), ("COMPANY", "company"))
    }
    for code, name, role in customers:
        party = await _get_or_create(
            session, BusinessParty,
            {"legal_name": name, "display_name": name, "roles": [role.title()], "status": "ACTIVE"},
            party_code=code,
        )
        exists = (
            await session.execute(
                select(BusinessPartyRole).where(
                    BusinessPartyRole.business_party_id == party.id,
                    BusinessPartyRole.party_role_id == party_roles[role].id,
                )
            )
        ).scalars().first()
        if exists is None:
            session.add(BusinessPartyRole(business_party_id=party.id, party_role_id=party_roles[role].id))
    await session.flush()

    roles = {role.code: role for role in (await session.execute(select(Role))).scalars().all()}
    for user_code, username, email, display_name, role_code, _ in DEMO_USERS:
        user = await _get_or_create(
            session, User,
            {
                "username": username,
                "email": email,
                "display_name": display_name,
                "status": "ACTIVE",
                "system_identity": PROTECTED_SYSTEM_ADMIN_IDENTITY if role_code == "SUPER_ADMIN" else None,
            },
            user_code=user_code,
        )
        credential = (await session.execute(select(UserCredential).where(UserCredential.user_id == user.id))).scalars().first()
        if credential is None:
            session.add(UserCredential(user_id=user.id, password_hash=hash_password(DEFAULT_PASSWORD)))
        if role_code in roles:
            assigned = await authorization.user_role_codes(session, user.id)
            if role_code not in assigned:
                await authorization.set_user_roles(session, user.id, [*assigned, role_code])
    await session.flush()
    # The fixture commits after this call, so publish the policies now: the
    # enforcer is a snapshot and the first request must already see these roles.
    await authorization.refresh(session)

    await _ensure_finance_baseline(session)
    await session.flush()

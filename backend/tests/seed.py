from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERMISSION_CATALOG, ROLE_DEFINITIONS, permission_name
from app.core.security import hash_password
from app.modules.auth.models import (
    Branch,
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserBranchAssignment,
    UserCredential,
    UserRoleAssignment,
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
    ComponentGroup,
    ComponentTemplate,
    ContainerType,
    FeeType,
    PartyRole,
    Place,
    TemplateAttribute,
    TradeDirection,
    TradeDirectionComponent,
    TransportType,
)
from app.modules.master_data.service_order_tabs import seed_service_order_tabs

DEMO_USERS = [
    ("ADMIN-001", "admin", "admin@example.test", "Demo Administrator", "PLATFORM_ADMIN", "ADMIN"),
    ("OPS-PP-001", "ops.pp", "ops.pp@example.test", "Phnom Penh Operations", "OPERATIONS_OFFICER", "OPS"),
    ("FIN-001", "finance", "finance@example.test", "Finance Officer", "FINANCE_OFFICER", "FIN"),
    ("SALES-001", "sales", "sales@example.test", "Sales Officer", "SALES_OFFICER", "SALES"),
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


async def ensure_seed_data(session: AsyncSession) -> None:
    """Idempotently seed permissions, roles and default role mappings."""
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
        wanted = set(definition["permissions"])  # type: ignore[arg-type]
        for code_to_add in wanted - current:
            pid = permission_ids.get(code_to_add)
            if pid is not None:
                session.add(RolePermission(role_id=role.id, permission_id=pid))
    await session.commit()


async def _get_or_create(session: AsyncSession, model: type, defaults: dict, **filters):
    instance = (await session.execute(select(model).filter_by(**filters))).scalars().first()
    if instance is not None:
        return instance
    instance = model(**filters, **defaults)
    session.add(instance)
    await session.flush()
    return instance


async def seed_demo_data(session: AsyncSession) -> None:
    org = await _get_or_create(
        session,
        Organization,
        {
            "legal_name": "Demo Freight Forwarding Co., Ltd.",
            "display_name": "Demo Freight",
            "country_code": "KH",
            "default_currency_code": "USD",
            "timezone": "Asia/Phnom_Penh",
        },
        organization_code="DEMO",
    )

    place_defs = [
        ("PP", "Phnom Penh", "City", "KH"),
        ("BV", "Bavet", "Border Checkpoint", "KH"),
        ("PP_PORT", "Phnom Penh Port", "Port", "KH"),
        ("SEZ", "Special Economic Zone", "SEZ", "KH"),
    ]
    places: dict[str, Place] = {}
    for code, name, category, country in place_defs:
        places[code] = await _get_or_create(
            session, Place, {"name": name, "place_category": category, "country_code": country}, code=code
        )

    pp_branch = await _get_or_create(
        session,
        Branch,
        {"name": "Phnom Penh Branch", "place_id": places["PP"].id, "address": "Phnom Penh", "is_head_office": True},
        organization_id=org.id,
        branch_code="PP",
    )
    await _get_or_create(
        session,
        Branch,
        {"name": "Bavet Branch", "place_id": places["BV"].id, "address": "Bavet", "is_head_office": False},
        organization_id=org.id,
        branch_code="BV",
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

    for code, name, size, kind, iso_code, length in [
        ("20DV", "20-foot Dry Van", "20FT", "DRY", "22G1", 20),
        ("40DV", "40-foot Dry Van", "40FT", "DRY", "42G1", 40),
        ("40HC", "40-foot High Cube", "40FT", "HIGH_CUBE", "45G1", 40),
        ("40RF", "40-foot Reefer", "40FT", "REEFER", "45R1", 40),
    ]:
        await _get_or_create(
            session,
            ContainerType,
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

    group_defs = [
        ("CARGO", "Cargo", 10),
        ("TRANSPORT", "Transport", 20),
        ("CUSTOMS", "Customs", 30),
        ("SHIPPING_DOCUMENTS", "Shipping Documents", 40),
        ("MILESTONES", "Milestones", 50),
        ("FINANCE", "Finance", 60),
    ]
    groups: dict[str, ComponentGroup] = {}
    for code, name, order in group_defs:
        groups[code] = await _get_or_create(session, ComponentGroup, {"name": name, "display_order": order}, code=code)

    template = await _get_or_create(
        session,
        ComponentTemplate,
        {
            "name": "Customs Clearance",
            "description": "Customs clearance task",
            "category": groups["CUSTOMS"].code,
            "instance_mode": "SINGLE",
        },
        code="CUSTOMS_CLEARANCE",
        version=1,
    )
    existing_attrs = (
        await session.execute(select(TemplateAttribute).where(TemplateAttribute.template_id == template.id))
    ).scalars().all()
    if not existing_attrs:
        session.add_all(
            [
                TemplateAttribute(
                    template_id=template.id,
                    code="declaration_no",
                    label="Declaration Number",
                    data_type="text",
                    display_order=1,
                ),
                TemplateAttribute(
                    template_id=template.id,
                    code="clearance_date",
                    label="Clearance Date",
                    data_type="date",
                    display_order=2,
                ),
                TemplateAttribute(
                    template_id=template.id,
                    code="duty_amount",
                    label="Duty Amount",
                    data_type="number",
                    display_order=3,
                ),
            ]
        )
        await session.flush()

    import_direction = (await session.execute(select(TradeDirection).where(TradeDirection.code == "IMPORT"))).scalars().first()
    export_direction = (await session.execute(select(TradeDirection).where(TradeDirection.code == "EXPORT"))).scalars().first()
    for direction in (import_direction, export_direction):
        if direction is None:
            continue
        exists = (
            await session.execute(
                select(TradeDirectionComponent).where(
                    TradeDirectionComponent.trade_direction_id == direction.id,
                    TradeDirectionComponent.component_template_id == template.id,
                )
            )
        ).scalars().first()
        if exists is None:
            session.add(
                TradeDirectionComponent(
                    trade_direction_id=direction.id,
                    component_group_id=groups["CUSTOMS"].id,
                    component_template_id=template.id,
                    display_order=10,
                    is_required=False,
                    instance_mode_override="INHERIT",
                )
            )
    await session.flush()

    # Business parties
    customers = [
        ("CUST-001", "ABC Manufacturing Co., Ltd.", "CUSTOMER"),
        ("CUST-002", "Mekong Trading Co., Ltd.", "CUSTOMER"),
    ]
    for code, name, role in customers:
        party = await _get_or_create(
            session,
            BusinessParty,
            {"legal_name": name, "display_name": name, "country_code": "KH", "status": "ACTIVE"},
            party_code=code,
        )
        role_exists = (
            await session.execute(select(PartyRole).where(PartyRole.party_id == party.id, PartyRole.role_type == role))
        ).scalars().first()
        if role_exists is None:
            session.add(PartyRole(party_id=party.id, role_type=role, is_primary=True))
    await session.flush()

    # Users
    roles = {role.code: role for role in (await session.execute(select(Role))).scalars().all()}
    for user_code, username, email, display_name, role_code, _ in DEMO_USERS:
        user = await _get_or_create(
            session,
            User,
            {"username": username, "email": email, "display_name": display_name, "status": "ACTIVE"},
            user_code=user_code,
        )
        credential = (await session.execute(select(UserCredential).where(UserCredential.user_id == user.id))).scalars().first()
        if credential is None:
            session.add(UserCredential(user_id=user.id, password_hash=hash_password(DEFAULT_PASSWORD)))
        role = roles.get(role_code)
        if role is not None:
            assignment = (
                await session.execute(
                    select(UserRoleAssignment).where(
                        UserRoleAssignment.user_id == user.id,
                        UserRoleAssignment.role_id == role.id,
                        UserRoleAssignment.organization_id == org.id,
                    )
                )
            ).scalars().first()
            if assignment is None:
                session.add(
                    UserRoleAssignment(
                        user_id=user.id,
                        role_id=role.id,
                        organization_id=org.id,
                        branch_id=pp_branch.id,
                    )
                )
        branch_assignment = (
            await session.execute(
                select(UserBranchAssignment).where(
                    UserBranchAssignment.user_id == user.id,
                    UserBranchAssignment.organization_id == org.id,
                    UserBranchAssignment.branch_id == pp_branch.id,
                )
            )
        ).scalars().first()
        if branch_assignment is None:
            session.add(
                UserBranchAssignment(
                    user_id=user.id, organization_id=org.id, branch_id=pp_branch.id, is_default=True
                )
            )
    await session.flush()

    # Accounting periods for the current year
    today = date.today()
    for offset in range(0, 3):
        month = today.month - offset
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        start = date(year, month, 1)
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        await _get_or_create(
            session,
            AccountingPeriod,
            {"start_date": start, "end_date": end, "status": "OPEN"},
            organization_id=org.id,
            period_year=year,
            period_month=month,
        )

    for document_type, prefix in [
        ("QUOTATION", "Q"),
        ("SERVICE_ORDER", "SO"),
        ("SERVICE_CHARGE", "SC"),
        ("CUSTOMER_INVOICE", "INV"),
        ("SUPPLIER_BILL", "BILL"),
        ("CUSTOMER_RECEIPT", "REC"),
        ("SUPPLIER_PAYMENT", "PAY"),
        ("JOURNAL", "JE"),
    ]:
        await _get_or_create(
            session,
            DocumentSequence,
            {"prefix": prefix, "padding_length": 6},
            organization_id=org.id,
            document_type=document_type,
            period_year=today.year,
        )

    for code, name, account_type, normal_balance in COA_SEED:
        await _get_or_create(
            session,
            ChartOfAccount,
            {"account_name": name, "account_type": account_type, "normal_balance": normal_balance, "is_postable": True},
            organization_id=org.id,
            account_code=code,
        )
    await session.flush()

    accounts = {
        account.account_code: account
        for account in (
            await session.execute(select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id))
        ).scalars().all()
    }
    for account_name, account_type, bank_name, masked in [
        ("Bank Account", "BANK", "ABA Bank", "****1234"),
        ("Cash on Hand", "CASH", None, None),
    ]:
        ledger = accounts.get("1020" if account_type == "BANK" else "1010")
        if ledger is None:
            continue
        await _get_or_create(
            session,
            FinancialAccount,
            {
                "account_name": account_name,
                "account_type": account_type,
                "currency_code": "USD",
                "bank_name": bank_name,
                "account_number_masked": masked,
            },
            organization_id=org.id,
            account_id=ledger.id,
        )

    for document_type, debit_code, credit_code in [
        ("CUSTOMER_INVOICE", "1100", "4010"),
        ("SUPPLIER_BILL", "5010", "2010"),
        ("CUSTOMER_RECEIPT", "1020", "1100"),
        ("SUPPLIER_PAYMENT", "2010", "1020"),
        ("OTHER_INCOME", "1020", "4020"),
        ("OTHER_EXPENSE", "5030", "1020"),
    ]:
        debit = accounts.get(debit_code)
        credit = accounts.get(credit_code)
        if debit is None or credit is None:
            continue
        exists = (
            await session.execute(
                select(PostingRule).where(
                    PostingRule.organization_id == org.id,
                    PostingRule.document_type == document_type,
                    PostingRule.fee_type_id.is_(None),
                )
            )
        ).scalars().first()
        if exists is None:
            session.add(
                PostingRule(
                    organization_id=org.id,
                    document_type=document_type,
                    debit_account_id=debit.id,
                    credit_account_id=credit.id,
                    status="ACTIVE",
                )
            )
    await seed_service_order_tabs(session, org.id)
    await session.flush()

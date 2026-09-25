"""Test-only fixtures.

This module is NOT used by the application — production ships with an empty
database and every record is entered manually. These helpers only exist so the
test-suite has a deterministic starting point.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bootstrap import ensure_permission_catalog
from app.core.security import hash_password
from app.modules.auth.models import (
    Role,
    User,
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
    ServiceOrderColumnConfig,
    ServiceOrderTabConfig,
    TemplateAttribute,
    TradeDirection,
    TradeDirectionComponent,
    TransportType,
)

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

TAB_SEED: list[dict[str, Any]] = [
    {
        "code": "invoice",
        "name": "Invoice",
        "icon": "i-lucide-file-text",
        "sort_order": 10,
        "columns": [
            {"field_key": "invoice_no", "label": "Invoice No.", "field_type": "text", "is_required": True, "sort_order": 10, "width": "160px"},
            {"field_key": "invoice_date", "label": "Invoice Date", "field_type": "date", "is_required": True, "sort_order": 20},
            {"field_key": "seller", "label": "Seller", "field_type": "reference", "reference_type": "business_party", "sort_order": 30},
            {"field_key": "invoice_amount", "label": "Invoice Amount", "field_type": "money", "sort_order": 40},
            {"field_key": "currency", "label": "Currency", "field_type": "currency", "sort_order": 50, "options": ["USD", "KHR", "VND"]},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 60, "options": ["Pending", "Approved", "Paid", "Cancelled"]},
            {"field_key": "remark", "label": "Remark", "field_type": "text", "sort_order": 70},
        ],
    },
    {
        "code": "packing-list",
        "name": "Packing List",
        "icon": "i-lucide-list",
        "sort_order": 20,
        "columns": [
            {"field_key": "packing_list_no", "label": "Packing List No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "date", "label": "Date", "field_type": "date", "sort_order": 20},
            {"field_key": "package_type", "label": "Package Type", "field_type": "text", "sort_order": 30},
            {"field_key": "quantity", "label": "Quantity", "field_type": "number", "sort_order": 40},
            {"field_key": "gross_weight", "label": "Gross Weight (kg)", "field_type": "decimal", "sort_order": 50},
            {"field_key": "net_weight", "label": "Net Weight (kg)", "field_type": "decimal", "sort_order": 60},
            {"field_key": "remark", "label": "Remark", "field_type": "textarea", "sort_order": 70},
        ],
    },
    {
        "code": "shipment-registration",
        "name": "Shipment Registration No.",
        "icon": "i-lucide-clipboard-list",
        "sort_order": 30,
        "columns": [
            {"field_key": "registration_no", "label": "Registration No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "registration_date", "label": "Registration Date", "field_type": "date", "sort_order": 20},
            {"field_key": "authority", "label": "Authority", "field_type": "text", "sort_order": 30},
            {"field_key": "reference", "label": "Reference", "field_type": "text", "sort_order": 40},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 50, "options": ["Draft", "Submitted", "Registered", "Cancelled"]},
            {"field_key": "remark", "label": "Remark", "field_type": "text", "sort_order": 60},
        ],
    },
    {
        "code": "bill",
        "name": "Bill",
        "icon": "i-lucide-receipt",
        "sort_order": 40,
        "columns": [
            {"field_key": "bill_no", "label": "Bill No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "bill_date", "label": "Bill Date", "field_type": "date", "sort_order": 20},
            {"field_key": "party", "label": "Party", "field_type": "reference", "reference_type": "business_party", "sort_order": 30},
            {"field_key": "description", "label": "Description", "field_type": "text", "sort_order": 40},
            {"field_key": "amount", "label": "Amount", "field_type": "money", "sort_order": 50},
            {"field_key": "currency", "label": "Currency", "field_type": "currency", "sort_order": 60, "options": ["USD", "KHR", "VND"]},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 70, "options": ["Pending", "Approved", "Paid", "Overdue", "Cancelled"]},
        ],
    },
    {
        "code": "customs",
        "name": "Customs",
        "icon": "i-lucide-landmark",
        "sort_order": 50,
        "columns": [
            {"field_key": "declaration_no", "label": "Declaration No.", "field_type": "text", "is_required": True, "sort_order": 10},
            {"field_key": "declaration_date", "label": "Declaration Date", "field_type": "date", "sort_order": 20},
            {"field_key": "checkpoint", "label": "Checkpoint", "field_type": "reference", "reference_type": "place", "sort_order": 30},
            {"field_key": "broker", "label": "Broker", "field_type": "reference", "reference_type": "business_party", "sort_order": 40},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 50, "options": ["Preparing", "Submitted", "Processing", "On Hold", "Cleared"]},
            {"field_key": "clearance_date", "label": "Clearance Date", "field_type": "date", "sort_order": 60},
            {"field_key": "remark", "label": "Remark", "field_type": "text", "sort_order": 70},
        ],
    },
    {
        "code": "transport",
        "name": "Transport",
        "icon": "i-lucide-truck",
        "sort_order": 60,
        "columns": [
            {"field_key": "transport_type", "label": "Transport Type", "field_type": "reference", "reference_type": "transport_type", "sort_order": 10},
            {"field_key": "vehicle", "label": "Vehicle", "field_type": "reference", "reference_type": "transport_asset", "sort_order": 20},
            {"field_key": "driver", "label": "Driver", "field_type": "text", "sort_order": 30},
            {"field_key": "origin", "label": "Origin", "field_type": "reference", "reference_type": "place", "sort_order": 40},
            {"field_key": "destination", "label": "Destination", "field_type": "reference", "reference_type": "place", "sort_order": 50},
            {"field_key": "departure", "label": "Departure", "field_type": "datetime", "sort_order": 60},
            {"field_key": "arrival", "label": "Arrival", "field_type": "datetime", "sort_order": 70},
            {"field_key": "status", "label": "Status", "field_type": "select", "sort_order": 80, "options": ["Planned", "Loading", "In Transit", "Arrived", "Delivered", "Cancelled"]},
        ],
    },
]


async def ensure_seed_data(session: AsyncSession) -> None:
    """Idempotently seed permissions, roles and default role mappings."""
    await ensure_permission_catalog(session)


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


async def _seed_service_order_tabs(session: AsyncSession) -> None:
    for tab_seed in TAB_SEED:
        tab = (
            await session.execute(select(ServiceOrderTabConfig).where(ServiceOrderTabConfig.code == tab_seed["code"]))
        ).scalars().first()
        if tab is None:
            tab = ServiceOrderTabConfig(
                code=tab_seed["code"],
                name=tab_seed["name"],
                icon=tab_seed.get("icon"),
                sort_order=tab_seed.get("sort_order", 0),
                is_active=True,
                allow_multiple_rows=True,
            )
            session.add(tab)
            await session.flush()
        for column_seed in tab_seed["columns"]:
            exists = (
                await session.execute(
                    select(ServiceOrderColumnConfig).where(
                        ServiceOrderColumnConfig.tab_id == tab.id,
                        ServiceOrderColumnConfig.field_key == column_seed["field_key"],
                    )
                )
            ).scalars().first()
            if exists is not None:
                continue
            session.add(
                ServiceOrderColumnConfig(
                    tab_id=tab.id,
                    field_key=column_seed["field_key"],
                    label=column_seed["label"],
                    field_type=column_seed["field_type"],
                    reference_type=column_seed.get("reference_type"),
                    is_required=bool(column_seed.get("is_required", False)),
                    is_active=True,
                    sort_order=column_seed.get("sort_order", 0),
                    width=column_seed.get("width"),
                    options=column_seed.get("options") or [],
                )
            )
    await session.flush()


async def seed_demo_data(session: AsyncSession) -> None:
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
        session, ComponentTemplate,
        {"name": "Customs Clearance", "description": "Customs clearance task", "category": groups["CUSTOMS"].code, "instance_mode": "SINGLE"},
        code="CUSTOMS_CLEARANCE", version=1,
    )
    existing_attrs = (
        await session.execute(select(TemplateAttribute).where(TemplateAttribute.template_id == template.id))
    ).scalars().all()
    if not existing_attrs:
        session.add_all(
            [
                TemplateAttribute(template_id=template.id, code="declaration_no", label="Declaration Number", data_type="text", display_order=1),
                TemplateAttribute(template_id=template.id, code="clearance_date", label="Clearance Date", data_type="date", display_order=2),
                TemplateAttribute(template_id=template.id, code="duty_amount", label="Duty Amount", data_type="number", display_order=3),
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

    customers = [
        ("CUST-001", "ABC Manufacturing Co., Ltd.", "CUSTOMER"),
        ("CUST-002", "Mekong Trading Co., Ltd.", "CUSTOMER"),
    ]
    for code, name, role in customers:
        party = await _get_or_create(
            session, BusinessParty,
            {"legal_name": name, "display_name": name, "country_code": "KH", "status": "ACTIVE"},
            party_code=code,
        )
        role_exists = (
            await session.execute(select(PartyRole).where(PartyRole.party_id == party.id, PartyRole.role_type == role))
        ).scalars().first()
        if role_exists is None:
            session.add(PartyRole(party_id=party.id, role_type=role, is_primary=True))
    await session.flush()

    roles = {role.code: role for role in (await session.execute(select(Role))).scalars().all()}
    for user_code, username, email, display_name, role_code, _ in DEMO_USERS:
        user = await _get_or_create(
            session, User,
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
                    )
                )
            ).scalars().first()
            if assignment is None:
                session.add(UserRoleAssignment(user_id=user.id, role_id=role.id))
    await session.flush()

    await _ensure_finance_baseline(session)
    await _seed_service_order_tabs(session)
    await session.flush()

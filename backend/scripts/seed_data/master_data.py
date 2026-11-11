"""Seed data for the Master Data reference collections.

Register-style data only: codes, names and the verified metadata the seed can
prove (ISO container type codes, ISO 4217 currency details). Business parties
and rate values stay administrator-managed/entered. Transport-assets rows are
clearly-marked DEMO fixtures for practice environments: they reference only
seeded vocabularies (transport types, identity types, capacity units) and are
insert-missing, like everything else here.

A ``plan`` entry is one row: ``{model-attr: value}`` matched by the module's
match key. Existing rows are never rewritten (see ``scripts/seed.py``).
"""

from __future__ import annotations

from decimal import Decimal

from app.core.bootstrap import DEFAULT_PARTY_ROLES, DEFAULT_PLACE_ROLES
from app.modules.master_data.models import (
    CapacityUnit,
    ContainerType,
    Currency,
    DocumentType,
    FeeType,
    PartyRole,
    PlaceRole,
    TradeDirection,
    TransportAssetIdentityType,
    TransportType,
)

# --- Trade directions --------------------------------------------------------
# The four standard directions plus Re-export, which the demo/test workflows
# already use. Quotations and Service Orders read this table; no direction is
# invented that would create a workflow the application cannot run.
TRADE_DIRECTIONS = (
    {"code": "IMPORT", "name": "Import", "description": "Goods enter the country", "status": "ACTIVE"},
    {"code": "EXPORT", "name": "Export", "description": "Goods leave the country", "status": "ACTIVE"},
    {"code": "TRANSIT", "name": "Transit", "description": "Goods pass through the country", "status": "ACTIVE"},
    {"code": "DOMESTIC", "name": "Domestic", "description": "Movement inside the country", "status": "ACTIVE"},
    {"code": "RE_EXPORT", "name": "Re-export", "description": "Previously imported goods leave the country", "status": "ACTIVE"},
)

# --- Party roles -------------------------------------------------------------
# The bootstrap trio (Customer/Supplier/Company) plus the roles a freight
# forwarder records on parties. Resolve by name like the API does; no allowlist
# changes. Shipper/Consignee/Agent etc. are distinct industry roles, not
# duplicates of the trio.
PARTY_ROLES = (
    *[{"code": code, "name": name, "description": description, "status": "ACTIVE"} for code, name, description in DEFAULT_PARTY_ROLES],
    {"code": "SHIPPER", "name": "Shipper", "description": "Hands the goods over for carriage.", "status": "ACTIVE"},
    {"code": "CONSIGNEE", "name": "Consignee", "description": "Receives the goods at destination.", "status": "ACTIVE"},
    {"code": "NOTIFY_PARTY", "name": "Notify Party", "description": "Notified of the shipment's arrival.", "status": "ACTIVE"},
    {"code": "CARRIER", "name": "Carrier", "description": "Contracts to carry the goods.", "status": "ACTIVE"},
    {"code": "SHIPPING_LINE", "name": "Shipping Line", "description": "Operates the ocean vessel.", "status": "ACTIVE"},
    {"code": "FREIGHT_FORWARDER", "name": "Freight Forwarder", "description": "Arranges the carriage.", "status": "ACTIVE"},
    {"code": "CUSTOMS_BROKER", "name": "Customs Broker", "description": "Clears the goods with customs.", "status": "ACTIVE"},
    {"code": "TRANSPORT_PROVIDER", "name": "Transport Provider", "description": "Runs the inland leg.", "status": "ACTIVE"},
    {"code": "AGENT", "name": "Agent", "description": "Acts for another party in a location.", "status": "ACTIVE"},
)

# --- Place roles -------------------------------------------------------------
# The app's own starting vocabulary. Port-of-loading/port-of-discharge style
# roles are semantic duplicates of LOADING/UNLOADING/etc. — the admin renames,
# the code list is not extended to avoid two names for one meaning.
PLACE_ROLE_FIELDS = ("code", "name", "description", "sort_order", "status")
PLACE_ROLES = [
    dict(zip(PLACE_ROLE_FIELDS, (*entry, (index + 1) * 10, "ACTIVE"), strict=True))
    for index, entry in enumerate(DEFAULT_PLACE_ROLES)
]

# --- Container types ---------------------------------------------------------
# Verified ISO 6346 type codes (22xx = 20 ft, 42xx/45xx = 40 ft; G = general
# purpose, R = reefer, U = open top, B = flat rack). Only code/name/size/kind/
# ISO code and length feet are seeded; weights and mm dimensions are left null —
# no unverified technical figures.
CONTAINER_TYPES = (
    {"code": "20GP", "name": "20-foot General Purpose", "container_size": "20FT", "container_kind": "DRY", "iso_code": "22G1", "length_feet": Decimal(20), "status": "ACTIVE"},
    {"code": "40GP", "name": "40-foot General Purpose", "container_size": "40FT", "container_kind": "DRY", "iso_code": "42G1", "length_feet": Decimal(40), "status": "ACTIVE"},
    {"code": "40HC", "name": "40-foot High Cube", "container_size": "40FT", "container_kind": "HIGH_CUBE", "iso_code": "45G1", "length_feet": Decimal(40), "status": "ACTIVE"},
    {"code": "20RF", "name": "20-foot Reefer", "container_size": "20FT", "container_kind": "REEFER", "iso_code": "22R1", "length_feet": Decimal(20), "status": "ACTIVE"},
    {"code": "40RF", "name": "40-foot Reefer", "container_size": "40FT", "container_kind": "REEFER", "iso_code": "42R1", "length_feet": Decimal(40), "status": "ACTIVE"},
    {"code": "40RFHC", "name": "40-foot High Cube Reefer", "container_size": "40FT", "container_kind": "REEFER", "iso_code": "45R1", "length_feet": Decimal(40), "status": "ACTIVE"},
    {"code": "20OT", "name": "20-foot Open Top", "container_size": "20FT", "container_kind": "OPEN_TOP", "iso_code": "22U1", "length_feet": Decimal(20), "status": "ACTIVE"},
    {"code": "40OT", "name": "40-foot Open Top", "container_size": "40FT", "container_kind": "OPEN_TOP", "iso_code": "42U1", "length_feet": Decimal(40), "status": "ACTIVE"},
    {"code": "20FR", "name": "20-foot Flat Rack", "container_size": "20FT", "container_kind": "FLAT_RACK", "iso_code": "22B1", "length_feet": Decimal(20), "status": "ACTIVE"},
    {"code": "40FR", "name": "40-foot Flat Rack", "container_size": "40FT", "container_kind": "FLAT_RACK", "iso_code": "42B1", "length_feet": Decimal(40), "status": "ACTIVE"},
)

# --- Transport types ---------------------------------------------------------
# The codes the identity-type seeding matches on (TRUCK -> license plates,
# VESSEL -> IMO numbers, RAIL -> rail vehicle numbers). Multimodal is included
# because the demo workflows already use it.
TRANSPORT_TYPES = (
    {"code": "TRUCK", "name": "Truck", "status": "ACTIVE"},
    {"code": "VESSEL", "name": "Vessel", "status": "ACTIVE"},
    {"code": "AIR", "name": "Air", "status": "ACTIVE"},
    {"code": "RAIL", "name": "Rail", "status": "ACTIVE"},
    {"code": "MULTIMODAL", "name": "Multimodal", "status": "ACTIVE"},
)

# --- Fee types ---------------------------------------------------------------
# The demo/workflow fee classifications plus the standard freight-forwarding
# charges. Classification only: no journals or financial transactions are
# created here.
FEE_TYPES = (
    {"code": "CUSTOMS_CLEARANCE", "name": "Customs Clearance", "status": "ACTIVE"},
    {"code": "INLAND_TRANSPORT", "name": "Inland Transport", "status": "ACTIVE"},
    {"code": "BORDER_HANDLING", "name": "Border Handling", "status": "ACTIVE"},
    {"code": "DOCUMENTATION", "name": "Documentation", "status": "ACTIVE"},
    {"code": "STORAGE", "name": "Storage", "status": "ACTIVE"},
    {"code": "PORT_HANDLING", "name": "Port Handling", "status": "ACTIVE"},
    {"code": "OTHER", "name": "Other", "status": "ACTIVE"},
    {"code": "OCEAN_FREIGHT", "name": "Ocean Freight", "status": "ACTIVE"},
    {"code": "AIR_FREIGHT", "name": "Air Freight", "status": "ACTIVE"},
    {"code": "TERMINAL_HANDLING", "name": "Terminal Handling", "status": "ACTIVE"},
    {"code": "DEMURRAGE", "name": "Demurrage", "status": "ACTIVE"},
    {"code": "DETENTION", "name": "Detention", "status": "ACTIVE"},
    {"code": "DELIVERY", "name": "Delivery", "status": "ACTIVE"},
)

# --- Currencies --------------------------------------------------------------
# Verified ISO 4217 names, symbols, numeric codes and minor units. KHR, VND and
# JPY carry zero decimals (the Currency docstring says JPY/KHR are configured
# 0 rather than forced into two). Existing rows are never overwritten: a currency
# the /auth-setup baseline seeded as `name=code` keeps its user-visible state.
CURRENCIES = (
    {"code": "USD", "name": "US Dollar", "symbol": "$", "numeric_code": "840", "decimal_places": 2},
    {"code": "KHR", "name": "Cambodian Riel", "symbol": "៛", "numeric_code": "116", "decimal_places": 0},
    {"code": "THB", "name": "Thai Baht", "symbol": "฿", "numeric_code": "764", "decimal_places": 2},
    {"code": "VND", "name": "Vietnamese Dong", "symbol": "₫", "numeric_code": "704", "decimal_places": 0},
    {"code": "SGD", "name": "Singapore Dollar", "symbol": "$", "numeric_code": "702", "decimal_places": 2},
    {"code": "EUR", "name": "Euro", "symbol": "€", "numeric_code": "978", "decimal_places": 2},
    {"code": "GBP", "name": "Pound Sterling", "symbol": "£", "numeric_code": "826", "decimal_places": 2},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "numeric_code": "392", "decimal_places": 0},
    {"code": "CNY", "name": "Yuan Renminbi", "symbol": "¥", "numeric_code": "156", "decimal_places": 2},
)

# --- Document types ----------------------------------------------------------
# The canonical financial types, copied from alembic revision f0b1c2d3e4f5 (and
# consistent with CANONICAL_DOCUMENT_BEHAVIORS). The migration seeds them on a
# fresh database; this plan only covers a database where they are missing, and
# inserts nothing for codes the user deleted or renamed.
_FINANCE_MODULES = ["financial_documents", "service_order_finance", "posting_rules"]
DOCUMENT_TYPES = (
    *[
        {"code": code, "name": name, "category": "FINANCE", "accounting_behavior": code, "posting_required": True, "available_in": _FINANCE_MODULES, "status": "ACTIVE"}
        for code, name in (
            ("CUSTOMER_INVOICE", "Customer Invoice"),
            ("CREDIT_NOTE", "Customer Credit Note"),
            ("SUPPLIER_BILL", "Supplier Bill"),
            ("SUPPLIER_CREDIT_NOTE", "Supplier Credit Note"),
            ("CUSTOMER_RECEIPT", "Customer Receipt"),
            ("SUPPLIER_PAYMENT", "Supplier Payment"),
            ("OTHER_INCOME", "Other Income"),
            ("OTHER_EXPENSE", "Other Expense"),
        )
    ],
    {"code": "TRANSFER", "name": "Transfer", "category": "FINANCE", "accounting_behavior": "TRANSFER", "posting_required": True, "available_in": ["financial_documents", "posting_rules"], "status": "ACTIVE"},
    {"code": "ADJUSTMENT", "name": "Adjustment", "category": "FINANCE", "accounting_behavior": "ADJUSTMENT", "posting_required": True, "available_in": ["financial_documents", "posting_rules"], "status": "ACTIVE"},
)

# --- Transport assets (DEMO fixtures) ----------------------------------------# Practice data only, inserted by scripts/seed.py with the transport type
# resolved from its seeded code. Identity types match the seeded identity
# vocabulary (license plates for trucks, IMO numbers for vessels, tail numbers
# for air, rail vehicle numbers), and capacity units are seeded codes.
# `owner_party_id`/`operator_party_id` stay unset: parties are real business
# data an administrator owns, so the demo assets work without them.
TRANSPORT_ASSETS = (
    {"asset_code": "TRK-001", "transport_type_code": "TRUCK", "identity": "1KH-2345", "identity_type": "License Plate", "asset_name": "Isuzu NPR green", "capacity_value": Decimal("3.5"), "capacity_unit": "T", "status": "ACTIVE"},
    {"asset_code": "TRK-002", "transport_type_code": "TRUCK", "identity": "2AB-6789", "identity_type": "License Plate", "asset_name": "Hino 500 blue", "capacity_value": Decimal("8"), "capacity_unit": "T", "status": "ACTIVE"},
    {"asset_code": "TRK-003", "transport_type_code": "TRUCK", "identity": "3CD-9012", "identity_type": "License Plate", "asset_name": "Hino 700 trailer head", "capacity_value": Decimal("20"), "capacity_unit": "T", "status": "ACTIVE"},
    {"asset_code": "VES-001", "transport_type_code": "VESSEL", "identity": "9321483", "identity_type": "IMO Number", "asset_name": "MV Phnom Ocean", "capacity_value": Decimal("1200"), "capacity_unit": "CBM", "status": "ACTIVE"},
    {"asset_code": "VES-002", "transport_type_code": "VESSEL", "identity": "9456123", "identity_type": "IMO Number", "asset_name": "MV Mekong Star", "capacity_value": Decimal("900"), "capacity_unit": "CBM", "status": "ACTIVE"},
    {"asset_code": "RAI-001", "transport_type_code": "RAIL", "identity": "RF-TH-0012", "identity_type": "Rail Vehicle Number", "asset_name": "Freight wagon set 12", "capacity_value": Decimal("60"), "capacity_unit": "T", "status": "ACTIVE"},
    {"asset_code": "AIR-001", "transport_type_code": "AIR", "identity": "XU-LCS1", "identity_type": "Aircraft Registration", "asset_name": "ATR 72 freighter", "capacity_value": Decimal("8.5"), "capacity_unit": "T", "status": "ACTIVE"},
    {"asset_code": "MUL-001", "transport_type_code": "MULTIMODAL", "identity": "MM-SET-001", "identity_type": "Other", "asset_name": "Road-rail demo set", "capacity_value": Decimal("40"), "capacity_unit": "T", "status": "ACTIVE"},
)

# --- Business parties (DEMO fixtures, --demo only) ---------------------------
# Five sample parties so every Master Data table starts with usable rows.
# Insert-missing by party_code; the party-role links are resolved from the
# seeded role vocabulary by code. Contact details are obviously fictional.
DEMO_BUSINESS_PARTIES = (
    {"party_code": "DEMO-CUST-01", "legal_name": "Demo Customer One Co., Ltd.", "display_name": "Demo Customer One", "contact_person": "Sok Dara", "phone": "+855 10 000 001", "email": "one@demo.lcs", "role_codes": ("CUSTOMER",), "status": "ACTIVE"},
    {"party_code": "DEMO-CUST-02", "legal_name": "Demo Customer Two Co., Ltd.", "display_name": "Demo Customer Two", "contact_person": "Chan Sopheak", "phone": "+855 10 000 002", "email": "two@demo.lcs", "role_codes": ("CUSTOMER", "CONSIGNEE"), "status": "ACTIVE"},
    {"party_code": "DEMO-SUP-01", "legal_name": "Demo Supplier One Co., Ltd.", "display_name": "Demo Supplier One", "contact_person": "Kim Lina", "phone": "+855 10 000 003", "email": "supplier.one@demo.lcs", "role_codes": ("SUPPLIER",), "status": "ACTIVE"},
    {"party_code": "DEMO-SUP-02", "legal_name": "Demo Shipping Line Co., Ltd.", "display_name": "Demo Shipping Line", "contact_person": "Ly Vannak", "phone": "+855 10 000 004", "email": "line@demo.lcs", "role_codes": ("SUPPLIER", "SHIPPING_LINE"), "status": "ACTIVE"},
    {"party_code": "DEMO-COMP-01", "legal_name": "Demo Group Company Co., Ltd.", "display_name": "Demo Group Company", "contact_person": "Pich Sreyneang", "phone": "+855 10 000 005", "email": "group@demo.lcs", "role_codes": ("COMPANY",), "status": "ACTIVE"},
)

#: Seed module name → (model, match-key column, rows). Configuration is separate
#: (``seed_data/configuration.py``). "asset-identity-types" and "capacity-units"
#: are service-backed; they are dispatched in ``scripts/seed.py``.
MASTER_PLANS: dict[str, tuple[type, str, tuple[dict, ...] | list[dict]]] = {
    "trade-directions": (TradeDirection, "code", TRADE_DIRECTIONS),
    "party-roles": (PartyRole, "code", PARTY_ROLES),
    "place-roles": (PlaceRole, "code", PLACE_ROLES),
    "container-types": (ContainerType, "code", CONTAINER_TYPES),
    "transport-types": (TransportType, "code", TRANSPORT_TYPES),
    "fee-types": (FeeType, "code", FEE_TYPES),
    "currencies": (Currency, "code", CURRENCIES),
    "document-types": (DocumentType, "code", DOCUMENT_TYPES),
    "capacity-units": (CapacityUnit, "code", ()),
    "asset-identity-types": (TransportAssetIdentityType, "name", ()),
}

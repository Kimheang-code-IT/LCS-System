"""Seed data for the Configuration module (Attributes → Groups → Tabs).

The minimum practical setup, mirroring the configuration the demo/test
workflows use. Publishing an active ConfigurationVersion stays an explicit
administrator action; this seed never creates or publishes a version, so the
live Service Order configuration is only extended, never replaced.
"""

from __future__ import annotations

from app.modules.master_data.models import (
    ComponentAttribute,
    ComponentGroup,
    ComponentTab,
)

# Reused where the Service Order customs flow already expects these keys.
COMPONENT_ATTRIBUTES = (
    {"code": "declaration_no", "label": "Declaration Number", "data_type": "text", "is_required": True, "display_order": 10, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "clearance_date", "label": "Clearance Date", "data_type": "date", "is_required": False, "display_order": 20, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "duty_amount", "label": "Duty Amount", "data_type": "number", "is_required": False, "display_order": 30, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    # Practice catalog: attributes an administrator can wire into any group.
    # They are NOT linked to a Service Order tab by this seed, so the live
    # dynamic form is unchanged; links are an explicit configuration action.
    {"code": "booking_no", "label": "Booking Number", "data_type": "text", "is_required": False, "display_order": 40, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "bl_no", "label": "Bill of Lading Number", "data_type": "text", "is_required": False, "display_order": 50, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "vessel_name", "label": "Vessel Name", "data_type": "text", "is_required": False, "display_order": 60, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "voyage_no", "label": "Voyage Number", "data_type": "text", "is_required": False, "display_order": 70, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "port_of_loading", "label": "Port of Loading", "data_type": "text", "is_required": False, "display_order": 80, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "port_of_discharge", "label": "Port of Discharge", "data_type": "text", "is_required": False, "display_order": 90, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "etd", "label": "ETD", "data_type": "date", "is_required": False, "display_order": 100, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "eta", "label": "ETA", "data_type": "date", "is_required": False, "display_order": 110, "options": [], "validation_rules": {}, "status": "ACTIVE"},
    {"code": "container_count", "label": "Container Count", "data_type": "number", "is_required": False, "display_order": 120, "options": [], "validation_rules": {}, "status": "ACTIVE"},
)

COMPONENT_GROUPS = (
    {"code": "CUSTOMS", "name": "Customs", "render_mode": "table", "display_order": 10, "is_active": True, "is_archived": False},
    {"code": "SHIPMENT_DETAILS", "name": "Shipment Details", "render_mode": "table", "display_order": 20, "is_active": True, "is_archived": False},
    {"code": "DELIVERY_TRACKING", "name": "Delivery Tracking", "render_mode": "table", "display_order": 30, "is_active": True, "is_archived": False},
)

#: (group code, attribute code, display order) — dependency-safe: the seed
#: resolves both sides by their unique code before inserting the membership.
GROUP_MEMBERSHIPS = (
    ("CUSTOMS", "declaration_no", 10),
    ("CUSTOMS", "clearance_date", 20),
    ("CUSTOMS", "duty_amount", 30),
    ("SHIPMENT_DETAILS", "booking_no", 10),
    ("SHIPMENT_DETAILS", "bl_no", 20),
    ("SHIPMENT_DETAILS", "vessel_name", 30),
    ("SHIPMENT_DETAILS", "voyage_no", 40),
    ("SHIPMENT_DETAILS", "port_of_loading", 50),
    ("SHIPMENT_DETAILS", "port_of_discharge", 60),
    ("SHIPMENT_DETAILS", "etd", 70),
    ("SHIPMENT_DETAILS", "eta", 80),
    ("DELIVERY_TRACKING", "container_count", 10),
    ("DELIVERY_TRACKING", "etd", 20),
    ("DELIVERY_TRACKING", "eta", 30),
)

#: Tab uses the IMPORT trade direction, resolved by code at seed time.
COMPONENT_TABS = (
    {"code": "CUSTOMS", "name": "Customs", "display_order": 10, "is_active": True, "is_archived": False, "trade_direction_code": "IMPORT"},
)

#: (tab code, group code, display order)
TAB_GROUPS = (
    ("CUSTOMS", "CUSTOMS", 10),
)

CONFIGURATION_PLANS: dict[str, tuple[type, str, tuple | list]] = {
    "component-attributes": (ComponentAttribute, "code", COMPONENT_ATTRIBUTES),
    "component-groups": (ComponentGroup, "code", COMPONENT_GROUPS),
    "component-tabs": (ComponentTab, "code", COMPONENT_TABS),
}

# --- DEMO configuration rows (``--demo`` only) -------------------------------
# Top-ups so every Configuration table starts with five rows. They reuse the
# seeded attribute vocabulary and are linked only to the IMPORT direction, and
# ``--all`` never inserts them: publishing what the operator sees stays an
# explicit decision.
DEMO_COMPONENT_GROUPS = (
    {"code": "WAREHOUSE", "name": "Warehouse", "render_mode": "table", "display_order": 40, "is_active": True, "is_archived": False},
    {"code": "INSURANCE", "name": "Insurance", "render_mode": "table", "display_order": 50, "is_active": True, "is_archived": False},
)

DEMO_COMPONENT_TABS = (
    {"code": "WAREHOUSE", "name": "Warehouse", "display_order": 20, "is_active": True, "is_archived": False, "trade_direction_code": "IMPORT"},
    {"code": "INSURANCE", "name": "Insurance", "display_order": 30, "is_active": True, "is_archived": False, "trade_direction_code": "IMPORT"},
    {"code": "SHIPMENT", "name": "Shipment", "display_order": 40, "is_active": True, "is_archived": False, "trade_direction_code": "IMPORT"},
    {"code": "TRACKING", "name": "Tracking", "display_order": 50, "is_active": True, "is_archived": False, "trade_direction_code": "IMPORT"},
)

#: (group code, attribute code, display order) — demo groups reuse seeded attributes.
DEMO_GROUP_MEMBERSHIPS = (
    ("WAREHOUSE", "booking_no", 10),
    ("INSURANCE", "container_count", 10),
)

#: (tab code, group code, display order) — demo tabs reuse existing groups.
DEMO_TAB_GROUPS = (
    ("WAREHOUSE", "WAREHOUSE", 10),
    ("INSURANCE", "INSURANCE", 10),
    ("SHIPMENT", "SHIPMENT_DETAILS", 10),
    ("TRACKING", "DELIVERY_TRACKING", 10),
)


"""Generate 10-row sample import workbooks for every Master Data page.

Output: one .xlsx per collection in ``../../import-data/`` (numbered so files
with references — transportAssets needs transportTypes and businessParties —
are imported last). Each workbook carries the required ``Instructions`` and
``Data`` sheets; headers come straight from the excel_io registry, so they
always match the backend template exactly.

Run from backend/ :  .venv\\Scripts\\python.exe scripts\\generate_import_workbooks.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.modules.excel_io.registry import REGISTRY

OUT = Path(__file__).resolve().parents[2] / "import-data"

# (registry key, filename order prefix). Dependencies first: transportAssets
# resolves transportType/ownerParty/operatorParty against earlier sheets.
COLLECTIONS = [
    "partyRoles",
    "placeRoles",
    "tradeDirections",
    "transportTypes",
    "containerTypes",
    "currencies",
    "capacityUnits",
    "transportAssetIdentityTypes",
    "feeTypes",
    "documentTypes",
    "businessParties",
    "transportAssets",
]

ROWS: dict[str, list[dict[str, str]]] = {
    "partyRoles": [
        {"code": "CARRIER", "name": "Carrier", "description": "Vessel or airline carrying the goods", "status": "ACTIVE"},
        {"code": "CONSOL", "name": "Consolidator", "description": "Groups LCL shipments into full containers", "status": "ACTIVE"},
        {"code": "CUSTOMS_BROKER", "name": "Customs Broker", "description": "Files customs declarations", "status": "ACTIVE"},
        {"code": "FREIGHT_FORWARDER", "name": "Freight Forwarder", "description": "Arranges the end-to-end transport", "status": "ACTIVE"},
        {"code": "SHIPPER", "name": "Shipper", "description": "Party that exports the goods", "status": "ACTIVE"},
        {"code": "CONSIGNEE", "name": "Consignee", "description": "Party that receives the goods", "status": "ACTIVE"},
        {"code": "WAREHOUSE", "name": "Warehouse Operator", "description": "Stores and handles cargo", "status": "ACTIVE"},
        {"code": "TRUCKING", "name": "Trucking Company", "description": "Performs road haulage", "status": "ACTIVE"},
        {"code": "AGENT", "name": "Overseas Agent", "description": "Correspondent agent at a foreign port", "status": "ACTIVE"},
        {"code": "DEPOT", "name": "Depot Operator", "description": "Empty container depot; kept INACTIVE as an example", "status": "INACTIVE"},
    ],
    "placeRoles": [
        {"code": "PORT_LOADING", "name": "Port of Loading", "description": "Where cargo is loaded onto the vessel", "sortOrder": "10", "status": "ACTIVE"},
        {"code": "PORT_DISCHARGE", "name": "Port of Discharge", "description": "Where cargo is unloaded", "sortOrder": "20", "status": "ACTIVE"},
        {"code": "TRANSIT_STOP", "name": "Transit Stop", "description": "Intermediate stop on the route", "sortOrder": "30", "status": "ACTIVE"},
        {"code": "DELIVERY", "name": "Delivery", "description": "Final handover point", "sortOrder": "40", "status": "ACTIVE"},
        {"code": "CFS", "name": "Container Freight Station", "description": "LCL cargo is devanned here", "sortOrder": "50", "status": "ACTIVE"},
        {"code": "CONTAINER_YARD", "name": "Container Yard", "description": "Full container storage yard", "sortOrder": "60", "status": "ACTIVE"},
        {"code": "BONDED_WH", "name": "Bonded Warehouse", "description": "Customs-bonded storage", "sortOrder": "70", "status": "ACTIVE"},
        {"code": "WAREHOUSE_IN", "name": "Inbound Warehouse", "description": "Receiving warehouse", "sortOrder": "80", "status": "ACTIVE"},
        {"code": "WAREHOUSE_OUT", "name": "Outbound Warehouse", "description": "Dispatch warehouse", "sortOrder": "90", "status": "ACTIVE"},
        {"code": "DOCS_CENTER", "name": "Document Center", "description": "Where originals are exchanged; an INACTIVE example", "sortOrder": "100", "status": "INACTIVE"},
    ],
    "tradeDirections": [
        {"code": "SEA_EXP", "name": "Sea Export", "description": "Outbound ocean shipment", "status": "ACTIVE"},
        {"code": "SEA_IMP", "name": "Sea Import", "description": "Inbound ocean shipment", "status": "ACTIVE"},
        {"code": "AIR_EXP", "name": "Air Export", "description": "Outbound air shipment", "status": "ACTIVE"},
        {"code": "AIR_IMP", "name": "Air Import", "description": "Inbound air shipment", "status": "ACTIVE"},
        {"code": "ROAD_EXP", "name": "Road Export", "description": "Outbound cross-border trucking", "status": "ACTIVE"},
        {"code": "ROAD_IMP", "name": "Road Import", "description": "Inbound cross-border trucking", "status": "ACTIVE"},
        {"code": "RAIL_EXP", "name": "Rail Export", "description": "Outbound rail shipment", "status": "ACTIVE"},
        {"code": "RAIL_IMP", "name": "Rail Import", "description": "Inbound rail shipment", "status": "ACTIVE"},
        {"code": "CABOTAGE", "name": "Cabotage / Coastal", "description": "Domestic coastal movement", "status": "ACTIVE"},
        {"code": "TRANSIT", "name": "Cross-border Transit", "description": "Goods passing through a third country; an INACTIVE example", "status": "INACTIVE"},
    ],
    "transportTypes": [
        {"code": "SEA", "name": "Ocean Freight", "description": "Container and break-bulk by vessel", "status": "ACTIVE"},
        {"code": "AIR", "name": "Air Freight", "description": "Scheduled and charter air cargo", "status": "ACTIVE"},
        {"code": "ROAD", "name": "Road Freight", "description": "Truck and trailer haulage", "status": "ACTIVE"},
        {"code": "RAIL", "name": "Rail Freight", "description": "Wagon and intermodal rail", "status": "ACTIVE"},
        {"code": "BARGE", "name": "Inland Waterway", "description": "Barge movement on rivers", "status": "ACTIVE"},
        {"code": "MULTIMODAL", "name": "Multimodal / Combined", "description": "Bill covers more than one mode", "status": "ACTIVE"},
        {"code": "COURIER", "name": "Courier / Express", "description": "Parcel express service", "status": "ACTIVE"},
        {"code": "LCL_SEA", "name": "Sea LCL", "description": "Less-than-container ocean cargo", "status": "ACTIVE"},
        {"code": "FCL_SEA", "name": "Sea FCL", "description": "Full container ocean cargo", "status": "ACTIVE"},
        {"code": "CHARTER_AIR", "name": "Air Charter", "description": "Whole-aircraft charter; marked INACTIVE as an example", "status": "INACTIVE"},
    ],
    "containerTypes": [
        {"code": "20GP", "name": "20' General Purpose", "size": "20", "kind": "GP", "isoCode": "22G1", "lengthFeet": "20", "widthMillimeter": "2352", "heightMillimeter": "2390", "maxGrossWeightKg": "30480", "description": "Standard 20ft dry container", "status": "ACTIVE"},
        {"code": "40GP", "name": "40' General Purpose", "size": "40", "kind": "GP", "isoCode": "42G1", "lengthFeet": "40", "widthMillimeter": "2352", "heightMillimeter": "2390", "maxGrossWeightKg": "30480", "description": "Standard 40ft dry container", "status": "ACTIVE"},
        {"code": "40HC", "name": "40' High Cube", "size": "40", "kind": "HC", "isoCode": "45G1", "lengthFeet": "40", "widthMillimeter": "2352", "heightMillimeter": "2698", "maxGrossWeightKg": "32500", "description": "High-cube 40ft dry container", "status": "ACTIVE"},
        {"code": "20RF", "name": "20' Reefer", "size": "20", "kind": "RF", "isoCode": "22R1", "lengthFeet": "20", "widthMillimeter": "2352", "heightMillimeter": "2390", "maxGrossWeightKg": "30480", "description": "20ft reefer, -25C to +25C", "status": "ACTIVE"},
        {"code": "40RF", "name": "40' Reefer", "size": "40", "kind": "RF", "isoCode": "42R1", "lengthFeet": "40", "widthMillimeter": "2352", "heightMillimeter": "2590", "maxGrossWeightKg": "34000", "description": "40ft reefer for chilled or frozen cargo", "status": "ACTIVE"},
        {"code": "20OT", "name": "20' Open Top", "size": "20", "kind": "OT", "isoCode": "22U1", "lengthFeet": "20", "widthMillimeter": "2352", "heightMillimeter": "2390", "maxGrossWeightKg": "30480", "description": "Open-top for over-height cargo", "status": "ACTIVE"},
        {"code": "40OT", "name": "40' Open Top", "size": "40", "kind": "OT", "isoCode": "42U1", "lengthFeet": "40", "widthMillimeter": "2352", "heightMillimeter": "2390", "maxGrossWeightKg": "30480", "description": "40ft open-top with tarpaulin", "status": "ACTIVE"},
        {"code": "20FR", "name": "20' Flat Rack", "size": "20", "kind": "FR", "isoCode": "22P1", "lengthFeet": "20", "widthMillimeter": "2400", "heightMillimeter": "2210", "maxGrossWeightKg": "30480", "description": "Flat rack for OOG project cargo", "status": "ACTIVE"},
        {"code": "40FR", "name": "40' Flat Rack", "size": "40", "kind": "FR", "isoCode": "42P1", "lengthFeet": "40", "widthMillimeter": "2400", "heightMillimeter": "2055", "maxGrossWeightKg": "30480", "description": "40ft flat rack", "status": "ACTIVE"},
        {"code": "40NOR", "name": "40' Nor Dry", "size": "40", "kind": "GP", "isoCode": "45G1", "lengthFeet": "40", "widthMillimeter": "2352", "heightMillimeter": "2698", "maxGrossWeightKg": "32500", "description": "Natural-air-reefer used as dry; an INACTIVE example", "status": "INACTIVE"},
    ],
    "currencies": [
        {"code": "EUR", "name": "Euro", "symbol": "EUR", "numericCode": "978", "decimalPlaces": "2", "description": "", "status": "ACTIVE"},
        {"code": "JPY", "name": "Japanese Yen", "symbol": "JPY", "numericCode": "392", "decimalPlaces": "0", "description": "", "status": "ACTIVE"},
        {"code": "CNY", "name": "Chinese Yuan", "symbol": "CNY", "numericCode": "156", "decimalPlaces": "2", "description": "", "status": "ACTIVE"},
        {"code": "THB", "name": "Thai Baht", "symbol": "THB", "numericCode": "764", "decimalPlaces": "2", "description": "", "status": "ACTIVE"},
        {"code": "VND", "name": "Vietnamese Dong", "symbol": "VND", "numericCode": "704", "decimalPlaces": "0", "description": "", "status": "ACTIVE"},
        {"code": "SGD", "name": "Singapore Dollar", "symbol": "SGD", "numericCode": "702", "decimalPlaces": "2", "description": "", "status": "ACTIVE"},
        {"code": "KRW", "name": "South Korean Won", "symbol": "KRW", "numericCode": "410", "decimalPlaces": "0", "description": "", "status": "ACTIVE"},
        {"code": "HKD", "name": "Hong Kong Dollar", "symbol": "HKD", "numericCode": "344", "decimalPlaces": "2", "description": "", "status": "ACTIVE"},
        {"code": "GBP", "name": "Pound Sterling", "symbol": "GBP", "numericCode": "826", "decimalPlaces": "2", "description": "", "status": "ACTIVE"},
        {"code": "AUD", "name": "Australian Dollar", "symbol": "AUD", "numericCode": "036", "decimalPlaces": "2", "description": "AUD is an example row you may set INACTIVE", "status": "INACTIVE"},
    ],
    "capacityUnits": [
        {"code": "MT", "name": "Metric Tonne", "status": "ACTIVE"},
        {"code": "LTR", "name": "Litre", "status": "ACTIVE"},
        {"code": "SQM", "name": "Square Metre", "status": "ACTIVE"},
        {"code": "ROLL", "name": "Roll", "status": "ACTIVE"},
        {"code": "SET", "name": "Set", "status": "ACTIVE"},
        {"code": "PKG", "name": "Package", "status": "ACTIVE"},
        {"code": "BOX", "name": "Box", "status": "ACTIVE"},
        {"code": "UNIT", "name": "Unit", "status": "ACTIVE"},
        {"code": "HR", "name": "Hour", "status": "ACTIVE"},
        {"code": "TONKM", "name": "Tonne-Kilometre", "status": "ACTIVE"},
    ],
    "transportAssetIdentityTypes": [
        {"name": "Registration Plate", "identityLabel": "Plate number", "identityPlaceholder": "e.g. PPH-12345", "validationPattern": r"^[A-Z0-9][A-Z0-9-]{2,15}$", "status": "ACTIVE", "transportType": ""},
        {"name": "Serial Number", "identityLabel": "Serial number", "identityPlaceholder": "e.g. MSCU1234567", "validationPattern": r"^[A-Z]{4}[0-9]{7}$", "status": "ACTIVE", "transportType": ""},
        {"name": "IMO Number", "identityLabel": "IMO number", "identityPlaceholder": "e.g. IMO9123456", "validationPattern": r"^IMO[0-9]{7}$", "status": "ACTIVE", "transportType": ""},
        {"name": "VIN Number", "identityLabel": "VIN", "identityPlaceholder": "17 characters", "validationPattern": r"^[A-HJ-NPR-Z0-9]{17}$", "status": "ACTIVE", "transportType": ""},
        {"name": "Engine Number", "identityLabel": "Engine number", "identityPlaceholder": "e.g. EN-88123", "validationPattern": "", "status": "ACTIVE", "transportType": ""},
        {"name": "Fleet Number", "identityLabel": "Fleet number", "identityPlaceholder": "e.g. F-0012", "validationPattern": r"^F-[0-9]{4}$", "status": "ACTIVE", "transportType": ""},
        {"name": "Chassis Number", "identityLabel": "Chassis number", "identityPlaceholder": "e.g. CH-00901", "validationPattern": "", "status": "ACTIVE", "transportType": ""},
        {"name": "Hull Number", "identityLabel": "Hull number", "identityPlaceholder": "e.g. H-00021", "validationPattern": "", "status": "ACTIVE", "transportType": ""},
        {"name": "Tail Number", "identityLabel": "Aircraft registration", "identityPlaceholder": "e.g. XU-123", "validationPattern": r"^[A-Z]{2}-[0-9]{1,4}[A-Z]?$", "status": "ACTIVE", "transportType": ""},
        {"name": "Wagon Number", "identityLabel": "Wagon number", "identityPlaceholder": "e.g. RW-0007", "validationPattern": "", "status": "ACTIVE", "transportType": ""},
    ],
    "feeTypes": [
        {"code": "OCEAN_FREIGHT", "name": "Ocean Freight", "description": "Base sea freight", "status": "ACTIVE"},
        {"code": "AIR_FREIGHT", "name": "Air Freight", "description": "Base air freight", "status": "ACTIVE"},
        {"code": "THC", "name": "Terminal Handling Charge", "description": "Terminal loading/unloading", "status": "ACTIVE"},
        {"code": "DOC_FEE", "name": "Documentation Fee", "description": "BL / AWB issuance", "status": "ACTIVE"},
        {"code": "CUSTOMS", "name": "Customs Clearance Fee", "description": "Declaration processing", "status": "ACTIVE"},
        {"code": "TRUCKING", "name": "Trucking Fee", "description": "Road haulage", "status": "ACTIVE"},
        {"code": "SURCHARGE", "name": "Surcharge", "description": "BAF / PSS and similar", "status": "ACTIVE"},
        {"code": "INSURANCE", "name": "Cargo Insurance", "description": "All-risk marine insurance", "status": "ACTIVE"},
        {"code": "LSS", "name": "Low Sulfur Surcharge", "description": "IMO 2020 fuel surcharge", "status": "ACTIVE"},
        {"code": "SEAL_FEE", "name": "Seal Fee", "description": "Container seal; marked INACTIVE as an example", "status": "INACTIVE"},
    ],
    "documentTypes": [
        {"code": "COMM_INVOICE", "name": "Commercial Invoice", "category": "FINANCE", "description": "", "accountingBehavior": "CUSTOMER_INVOICE", "postingRequired": "TRUE", "availableIn": "financial_documents", "status": "ACTIVE"},
        {"code": "CREDIT_MEMO", "name": "Credit Memo", "category": "FINANCE", "description": "", "accountingBehavior": "CREDIT_NOTE", "postingRequired": "TRUE", "availableIn": "financial_documents", "status": "ACTIVE"},
        {"code": "VENDOR_BILL", "name": "Vendor Bill Copy", "category": "FINANCE", "description": "", "accountingBehavior": "SUPPLIER_BILL", "postingRequired": "TRUE", "availableIn": "financial_documents", "status": "ACTIVE"},
        {"code": "RECEIPT_COPY", "name": "Customer Receipt Copy", "category": "FINANCE", "description": "", "accountingBehavior": "CUSTOMER_RECEIPT", "postingRequired": "FALSE", "availableIn": "financial_documents", "status": "ACTIVE"},
        {"code": "EXPENSE_VOUCHER", "name": "Expense Voucher", "category": "FINANCE", "description": "", "accountingBehavior": "OTHER_EXPENSE", "postingRequired": "TRUE", "availableIn": "financial_documents", "status": "ACTIVE"},
        {"code": "PACKING_LIST", "name": "Packing List", "category": "OPERATIONS", "description": "", "accountingBehavior": "OTHER_EXPENSE", "postingRequired": "FALSE", "availableIn": "operations_documents", "status": "ACTIVE"},
        {"code": "BILL_OF_LADING", "name": "Bill of Lading", "category": "OPERATIONS", "description": "", "accountingBehavior": "TRANSFER", "postingRequired": "FALSE", "availableIn": "operations_documents", "status": "ACTIVE"},
        {"code": "AIRWAY_BILL", "name": "Airway Bill", "category": "OPERATIONS", "description": "", "accountingBehavior": "TRANSFER", "postingRequired": "FALSE", "availableIn": "operations_documents", "status": "ACTIVE"},
        {"code": "CUSTOMS_DECL", "name": "Customs Declaration", "category": "CUSTOMS", "description": "", "accountingBehavior": "OTHER_EXPENSE", "postingRequired": "FALSE", "availableIn": "operations_documents", "status": "ACTIVE"},
        {"code": "JOB_TICKET", "name": "Job Ticket", "category": "SUPPORTING", "description": "", "accountingBehavior": "OTHER_EXPENSE", "postingRequired": "FALSE", "availableIn": "attachments", "status": "ACTIVE"},
    ],
    "businessParties": [
        {"partyCode": "MAER-001", "legalName": "Maersk Line Limited", "displayName": "Maersk", "contactPerson": "Sok Dara", "phone": "+855-12-345-678", "email": "ops@maersk-branch.example.com", "address": "88 Preah Sihanouk Blvd, Phnom Penh", "status": "ACTIVE", "taxIdentifier": "KH001100001"},
        {"partyCode": "COSCO-01", "legalName": "COSCO Shipping_lines Cambodia", "displayName": "COSCO", "contactPerson": "Chan Sophea", "phone": "+855-11-234-567", "email": "cosco.ops@example.com", "address": "Sihanoukville Autonomous Port", "status": "ACTIVE", "taxIdentifier": "KH001100002"},
        {"partyCode": "EMIRAT-1", "legalName": "Emirates SkyCargo Agent", "displayName": "Emirates SkyCargo", "contactPerson": "Vong Chanly", "phone": "+855-23-987-654", "email": "cargo@emirates-agent.example.com", "address": "Phnom Penh International Airport", "status": "ACTIVE", "taxIdentifier": "KH001100003"},
        {"partyCode": "BROKER-A", "legalName": "Angkor Customs Broker Co Ltd", "displayName": "Angkor Broker", "contactPerson": "Pheap Sokun", "phone": "+855-92-111-222", "email": "clearance@angkorbroker.example.com", "address": "Sihanoukville, Street 108", "status": "ACTIVE", "taxIdentifier": "KH001100004"},
        {"partyCode": "TRUCK-01", "legalName": "Mekong Transport & Logistics", "displayName": "Mekong Transport", "contactPerson": "Kong Visal", "phone": "+855-10-555-333", "email": "dispatch@mekongtransport.example.com", "address": "Kandal Province, NR1 Km 15", "status": "ACTIVE", "taxIdentifier": "KH001100005"},
        {"partyCode": "CUST-A01", "legalName": "Golden Rice Export Co Ltd", "displayName": "Golden Rice", "contactPerson": "San Vichea", "phone": "+855-17-444-555", "email": "export@goldenrice.example.com", "address": "Battambang Province", "status": "ACTIVE", "taxIdentifier": "KH001100006"},
        {"partyCode": "CUST-A02", "legalName": "Evergreen Garments Manufacturing", "displayName": "Evergreen Garments", "contactPerson": "Toul Sambo", "phone": "+855-67-222-888", "email": "shipping@evergreengarments.example.com", "address": "Phnom Penh SEZ, KG Industrial Park", "status": "ACTIVE", "taxIdentifier": "KH001100007"},
        {"partyCode": "CONSOL-01", "legalName": "Dragon Freight Consolidator Ltd", "displayName": "Dragon Freight", "contactPerson": "Lay Pisey", "phone": "+855-96-777-999", "email": "lcl@dragonfreight.example.com", "address": "Poipet, Banteay Meanchey", "status": "ACTIVE", "taxIdentifier": "KH001100008"},
        {"partyCode": "WAREH-01", "legalName": "Phnom Penh Bonded Storage", "displayName": "PP Bonded Storage", "contactPerson": "Mom Chanthy", "phone": "+855-12-900-111", "email": "wh@ppbonded.example.com", "address": "Khan Chbar Ampov, Phnom Penh", "status": "ACTIVE", "taxIdentifier": "KH001100009"},
        {"partyCode": "AGENT-BKK", "legalName": "Bangkok Overseas Agent Partners", "displayName": "BKK Overseas Agent", "contactPerson": "Nop Rattanak", "phone": "+855-81-300-222", "email": "bkk@overseasagent.example.com", "address": "Vat Phnom, Phnom Penh", "status": "ACTIVE", "taxIdentifier": ""},
    ],
    "transportAssets": [
        {"assetCode": "TA-TRK-001", "assetName": "Container Truck T-001", "identity": "PPH-12345", "identityType": "Registration Plate", "capacityValue": "24", "capacityUnit": "MT", "description": "Head truck with 40ft trailer", "status": "ACTIVE", "transportType": "ROAD", "ownerParty": "TRUCK-01", "operatorParty": "TRUCK-01"},
        {"assetCode": "TA-TRK-002", "assetName": "Container Truck T-002", "identity": "PPH-23456", "identityType": "Registration Plate", "capacityValue": "24", "capacityUnit": "MT", "description": "Head truck, 20-40ft compatible", "status": "ACTIVE", "transportType": "ROAD", "ownerParty": "TRUCK-01", "operatorParty": "TRUCK-01"},
        {"assetCode": "TA-TLR-001", "assetName": "Flatbed Trailer TL-001", "identity": "RC-87654", "identityType": "Registration Plate", "capacityValue": "30", "capacityUnit": "MT", "description": "20/40ft flatbed trailer", "status": "ACTIVE", "transportType": "ROAD", "ownerParty": "TRUCK-01", "operatorParty": "TRUCK-01"},
        {"assetCode": "TA-VES-001", "assetName": "MV Freight Star", "identity": "IMO9123456", "identityType": "IMO Number", "capacityValue": "25000", "capacityUnit": "MT", "description": "Feeder vessel, 1200 TEU", "status": "ACTIVE", "transportType": "SEA", "ownerParty": "MAER-001", "operatorParty": "MAER-001"},
        {"assetCode": "TA-VES-002", "assetName": "MV Harbour Star", "identity": "IMO9234567", "identityType": "IMO Number", "capacityValue": "18000", "capacityUnit": "MT", "description": "General cargo vessel", "status": "ACTIVE", "transportType": "SEA", "ownerParty": "COSCO-01", "operatorParty": "COSCO-01"},
        {"assetCode": "TA-CNT-001", "assetName": "40HC Container MSCU1234567", "identity": "MSCU1234567", "identityType": "Serial Number", "capacityValue": "32.5", "capacityUnit": "MT", "description": "Carrier-owned 40HC", "status": "ACTIVE", "transportType": "SEA", "ownerParty": "MAER-001", "operatorParty": "MAER-001"},
        {"assetCode": "TA-CNT-002", "assetName": "20GP Container TCLU7654321", "identity": "TCLU7654321", "identityType": "Serial Number", "capacityValue": "30", "capacityUnit": "MT", "description": "Carrier-owned 20GP", "status": "ACTIVE", "transportType": "SEA", "ownerParty": "COSCO-01", "operatorParty": "COSCO-01"},
        {"assetCode": "TA-AC-001", "assetName": "Freighter A320F", "identity": "XU-123", "identityType": "Tail Number", "capacityValue": "18000", "capacityUnit": "KG", "description": "Combi freighter on regional routes", "status": "ACTIVE", "transportType": "AIR", "ownerParty": "EMIRAT-1", "operatorParty": "EMIRAT-1"},
        {"assetCode": "TA-WGN-001", "assetName": "Rail Wagon RW-001", "identity": "RW-0007", "identityType": "Wagon Number", "capacityValue": "60", "capacityUnit": "MT", "description": "Flat wagon, Cambodia-Vietnam line", "status": "ACTIVE", "transportType": "RAIL", "ownerParty": "TRUCK-01", "operatorParty": "TRUCK-01"},
        {"assetCode": "TA-TRK-003", "assetName": "Container Truck T-003", "identity": "PPH-34567", "identityType": "Registration Plate", "capacityValue": "24", "capacityUnit": "MT", "description": "Under scheduled maintenance; an example of the MAINTENANCE status", "status": "MAINTENANCE", "transportType": "ROAD", "ownerParty": "TRUCK-01", "operatorParty": "TRUCK-01"},
    ],
}

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
REQUIRED_FONT = Font(color="FFFF00", bold=True)


def build_workbook(module_key: str) -> Workbook:
    module = REGISTRY[module_key]
    headers = [column.key for column in module.columns]
    rows = ROWS[module_key]

    workbook = Workbook()
    instructions = workbook.active
    assert instructions is not None
    instructions.title = "Instructions"
    instructions["A1"] = "TEMPLATE_VERSION"
    instructions["B1"] = module.template_version
    instructions["A2"] = "Module"
    instructions["B2"] = module.name
    instructions["A3"] = "Note"
    instructions["B3"] = (
        "Sample data. Import via the page's Import button. Match keys: "
        + " + ".join(module.match_key)
        + ". References resolve by name or code."
    )

    data = workbook.create_sheet("Data")
    data.append(headers)
    for index, column in enumerate(module.columns, start=1):
        cell = data.cell(row=1, column=index)
        cell.fill = HEADER_FILL
        cell.font = REQUIRED_FONT if column.required else Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
        data.column_dimensions[get_column_letter(index)].width = max(14, min(38, len(column.key) + 8))
    data.freeze_panes = "A2"

    known = set(headers)
    for position, row in enumerate(rows, start=2):
        unknown = set(row) - known
        if unknown:
            raise SystemExit(f"{module_key} row {position}: unknown columns {sorted(unknown)}")
        data.append([row.get(header, "") for header in headers])
    for column in module.columns:
        values = [row.get(column.key) for row in rows]
        if column.required and any(value in (None, "") for value in values):
            raise SystemExit(f"{module_key}: required column {column.key} is blank in some row")
    return workbook


def main() -> None:
    OUT.mkdir(exist_ok=True)
    written = []
    for position, key in enumerate(COLLECTIONS, start=1):
        path = OUT / f"{position:02d}-{key}.xlsx"
        build_workbook(key).save(path)
        written.append(path.name)
    print(f"{len(written)} workbooks written to {OUT}")
    for name in written:
        print(f"  {name}")


if __name__ == "__main__":
    main()

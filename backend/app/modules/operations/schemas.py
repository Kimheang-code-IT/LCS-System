"""Request schemas for operations: service orders, containers, charges, routes.

The service order header is partly an open document: the UI stores user-defined
fields in ``service_orders.data`` and the form sends them back on every save.
That collection therefore validates the known fields and deliberately accepts
the remaining keys. The child resources (container, movement, milestone) and the
charge header have a closed contract, so an unsupported key is refused there
instead of being silently ignored.

Database-dependent rules stay in ``service.py``: whether a container type or
Place Role is active, sequence uniqueness, line totals and the posting/issue
workflow all need a round-trip.
"""

from __future__ import annotations

from app.core.validation import FieldSpec, RecordSchema

# Canonical vocabularies shared with the service normalisers. Declared here so a
# schema and the value it accepts cannot drift apart.
ORDER_STATUSES = ("ACTIVE", "INACTIVE", "FINISHED")
CHARGE_DOCUMENT_TYPES = ("SERVICE_NOTE", "DEBIT_NOTE", "PRO_FORMA")
MOVEMENT_STATUSES = ("PLANNED", "IN_TRANSIT", "ARRIVED", "COMPLETED", "CANCELLED")
MILESTONE_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED")

_STATUS_READONLY = ("id", "serviceOrderId", "createdAt", "updatedAt", "rawStatus", "configurationVersionId")


SERVICE_ORDER_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("jobNo", max_length=50, aliases=("job_no", "serviceOrderNo", "service_order_no")),
        FieldSpec("customer", max_length=255),
        FieldSpec("customerPartyId", kind="reference", aliases=("customer_party_id",)),
        FieldSpec("direction", max_length=64),
        FieldSpec("currency", min_length=3, max_length=3),
        FieldSpec("status", max_length=20),
        FieldSpec("date", kind="date"),
        FieldSpec("validUntil", kind="date", aliases=("valid_until",)),
        FieldSpec("pickupDate", kind="date", aliases=("pickup_date",)),
        FieldSpec("deliveryDate", kind="date", aliases=("delivery_date",)),
        FieldSpec("description", max_length=10_000),
    ),
    readonly=_STATUS_READONLY,
)

CONTAINER_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec(
            "containerNumber",
            required=True,
            min_length=1,
            max_length=32,
            aliases=("container_number", "containerNo"),
        ),
        FieldSpec("containerType", kind="reference", max_length=64),
        FieldSpec("containerTypeId", kind="reference", aliases=("container_type_id",)),
        FieldSpec(
            "containerRequirementId",
            kind="reference",
            aliases=("container_requirement_id",),
        ),
        FieldSpec("sealSerial", max_length=64, aliases=("seal_serial",)),
        FieldSpec("status", max_length=32),
        FieldSpec("netWeightKg", kind="decimal", minimum=0, decimal_places=3, aliases=("net_weight_kg",)),
        FieldSpec("grossWeightKg", kind="decimal", minimum=0, decimal_places=3, aliases=("gross_weight_kg",)),
        FieldSpec("pickupDate", kind="date", aliases=("pickup_date",)),
        FieldSpec("returnDate", kind="date", aliases=("return_date",)),
        FieldSpec("description", max_length=2_000),
    ),
    readonly=("id", "serviceOrderId", "createdAt", "updatedAt"),
    reject_unknown=True,
)

MOVEMENT_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("sequenceNo", kind="integer", minimum=1, aliases=("sequence_no",)),
        FieldSpec("transportTypeId", kind="reference", aliases=("transport_type_id",)),
        FieldSpec("transportType", kind="reference", max_length=255),
        FieldSpec("transportAssetId", kind="reference", aliases=("transport_asset_id",)),
        FieldSpec("plannedDeparture", kind="datetime", aliases=("planned_departure",)),
        FieldSpec("actualDeparture", kind="datetime", aliases=("actual_departure",)),
        FieldSpec("plannedArrival", kind="datetime", aliases=("planned_arrival",)),
        FieldSpec("actualArrival", kind="datetime", aliases=("actual_arrival",)),
        # An unrecognised status is normalised by the service (the historic
        # contract); the schema only bounds the stored text.
        FieldSpec("status", max_length=32),
        FieldSpec("notes", max_length=5_000),
    ),
    readonly=("id", "serviceOrderId", "createdAt", "updatedAt"),
    reject_unknown=True,
)

MILESTONE_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec(
            "milestoneCode",
            required=True,
            min_length=1,
            max_length=64,
            aliases=("milestone_code",),
        ),
        FieldSpec("milestoneName", max_length=255, aliases=("milestone_name",)),
        FieldSpec("sequenceNo", kind="integer", minimum=1, aliases=("sequence_no",)),
        FieldSpec("plannedAt", kind="datetime", aliases=("planned_at",)),
        FieldSpec("actualAt", kind="datetime", aliases=("actual_at",)),
        # See MOVEMENT_WRITE_SCHEMA: an unknown status falls back to PENDING.
        FieldSpec("status", max_length=20),
        FieldSpec("notes", max_length=5_000),
    ),
    readonly=("id", "serviceOrderId", "createdAt", "updatedAt"),
    reject_unknown=True,
)

CHARGE_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("jobNo", max_length=64, aliases=("job_no",)),
        FieldSpec("serviceOrderId", kind="reference", aliases=("service_order_id",)),
        FieldSpec("chargeNo", max_length=50, aliases=("charge_no", "documentNo", "document_no")),
        FieldSpec("documentType", choices=CHARGE_DOCUMENT_TYPES, max_length=32, aliases=("document_type",)),
        FieldSpec("documentDate", kind="date", aliases=("document_date",)),
        FieldSpec("currency", min_length=3, max_length=3),
        FieldSpec("remark", max_length=5_000),
    ),
    readonly=("id", "createdAt", "updatedAt", "status", "subtotal", "discount", "tax", "total"),
)

CHARGE_LINE_SCHEMA = RecordSchema(
    (
        FieldSpec("description", max_length=1_000),
        FieldSpec("feeTypeId", kind="reference", aliases=("fee_type_id",)),
        FieldSpec("feeType", kind="reference", max_length=255, aliases=("fee_type",)),
        FieldSpec("quantity", kind="decimal", minimum=0, decimal_places=3),
        FieldSpec("unitPrice", kind="decimal", aliases=("unit_price",)),
        FieldSpec(
            "unitAmount",
            kind="decimal",
            aliases=("unit_amount",),
        ),
        FieldSpec("discount", kind="decimal", minimum=0),
        FieldSpec("taxRate", kind="decimal", minimum=0, maximum=100, aliases=("tax_rate",)),
        FieldSpec("tax", kind="decimal", minimum=0, maximum=100),
        FieldSpec("taxAmount", kind="decimal", minimum=0, aliases=("tax_amount",)),
        FieldSpec("unit", max_length=32, aliases=("unitCode", "unit_code")),
        FieldSpec("containerId", kind="reference", aliases=("container_id",)),
        FieldSpec("serviceOrderContainerId", kind="reference", aliases=("service_order_container_id",)),
    ),
    readonly=("id", "amount", "total", "lineNo", "line_no"),
)

ATTACHMENT_PRESIGN_SCHEMA = RecordSchema(
    (
        FieldSpec("fileName", required=True, min_length=1, max_length=512, aliases=("file_name",)),
        FieldSpec("mimeType", max_length=128, aliases=("mime_type",)),
    ),
    reject_unknown=True,
)

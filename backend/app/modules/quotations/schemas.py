"""Request schemas for quotations and their revision children.

The quotation header and its repeatable children used to reach the service as
untyped dictionaries: a malformed date, an over-long note or a text value in a
numeric cell failed late (or silently became zero). These schemas normalise the
values the service writes and report each violation against the input that owns
it, including ``pricingLines.2.quantity`` for a table cell.

Status transitions, customer existence, container-type creation and revision
immutability remain service rules: they need the database or the aggregate's
current state.
"""

from __future__ import annotations

from app.core.validation import FieldSpec, RecordSchema

#: Header keys the client may write. ``amount`` and its aliases are accepted
#: because the form echoes them, but totals are recomputed from the lines: they
#: are listed as writable numbers so a non-numeric echo is still refused.
REVISION_REASON_SCHEMA = RecordSchema(
    (
        FieldSpec("reason", max_length=2_000, aliases=("notes", "note")),
    ),
    reject_unknown=True,
)

QUOTATION_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("quotationNo", max_length=50, aliases=("quotation_no",)),
        FieldSpec("customerPartyId", kind="reference", aliases=("customer_party_id",)),
        FieldSpec("customer", max_length=255),
        FieldSpec("direction", max_length=64),
        FieldSpec("status", max_length=20),
        FieldSpec("date", kind="date"),
        FieldSpec("quotationDate", kind="date", aliases=("quotation_date",)),
        FieldSpec("validUntil", kind="date", aliases=("valid_until",)),
        FieldSpec("currency", min_length=3, max_length=3),
        FieldSpec("description", max_length=10_000),
        FieldSpec("notes", max_length=10_000),
        FieldSpec("amount", kind="decimal"),
        FieldSpec("totalSelling", kind="decimal", aliases=("total_selling",)),
        FieldSpec("totalAmount", kind="decimal", aliases=("total_amount",)),
        FieldSpec("total", kind="decimal"),
    ),
    readonly=(
        "id",
        "quotationId",
        "revisionId",
        "revisionNo",
        "rawStatus",
        "createdAt",
        "updatedAt",
    ),
)

CONTAINER_REQUIREMENT_SCHEMA = RecordSchema(
    (
        FieldSpec("containerTypeId", kind="reference", aliases=("container_type_id",)),
        FieldSpec("containerType", kind="reference", max_length=64),
        FieldSpec("quantity", kind="decimal", minimum=0, decimal_places=3, aliases=("qty",)),
        FieldSpec("grossWeightKg", kind="decimal", minimum=0, decimal_places=3, aliases=("gross_weight_kg",)),
        FieldSpec("description", max_length=2_000),
        FieldSpec("remarks", max_length=2_000),
    ),
    readonly=("id", "createdAt", "updatedAt"),
)

PRICING_LINE_SCHEMA = RecordSchema(
    (
        FieldSpec("feeTypeId", kind="reference", aliases=("fee_type_id",)),
        FieldSpec("feeType", kind="reference", max_length=255, aliases=("fee_type",)),
        # New lines carry the Transport Type id; a legacy quotation may still
        # carry the name, which the service resolves without rewriting unknown
        # values, so an old line stays editable.
        FieldSpec("transportBy", kind="reference", max_length=255, aliases=("transport_by", "transportTypeId", "transport_type_id")),
        FieldSpec("description", max_length=1_000, aliases=("serviceDescription", "service_description")),
        FieldSpec("quantity", kind="decimal", minimum=0, decimal_places=3),
        FieldSpec("unitPrice", kind="decimal", aliases=("unit_price", "unitAmount", "unit_amount")),
        # These are amounts on a quotation line, not rates (the service derives
        # the total from them), so they are not capped at 100.
        FieldSpec("discount", kind="decimal", minimum=0, aliases=("discountAmount", "discount_amount")),
        FieldSpec("tax", kind="decimal", minimum=0, aliases=("taxAmount", "tax_amount")),
        # Optional per-line rate from the Additional Details dialog; when present
        # the service derives the tax amount from it (0–100).
        FieldSpec("taxRate", kind="decimal", minimum=0, maximum=100, aliases=("tax_rate",)),
        FieldSpec("unit", max_length=32, aliases=("unitCode", "unit_code")),
    ),
    readonly=("id", "lineNo", "line_no", "subtotal", "total", "amount", "createdAt", "updatedAt"),
)

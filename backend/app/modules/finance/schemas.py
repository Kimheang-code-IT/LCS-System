"""Request schemas for finance write APIs.

These schemas enforce the shape the database can store (type, length, decimal
scale, date, closed vocabulary) and normalise values before a service touches
them. They deliberately do **not** decide:

* whether an account is postable or exists,
* whether a period is open,
* whether debit equals credit,
* whether a document may be edited or reversed.

Those are accounting rules and stay in ``service.py`` / ``posting.py``, where
they run inside the transaction that writes the journal.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.validation import FieldSpec, RecordSchema

ACCOUNT_TYPES = ("ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE")
NORMAL_BALANCES = ("DEBIT", "CREDIT")
ACTIVE_STATUSES = ("ACTIVE", "INACTIVE")
FINANCIAL_ACCOUNT_TYPES = ("BANK", "CASH")
PERIOD_STATUSES = ("OPEN", "CLOSED")

ACCOUNT_SCHEMA = RecordSchema(
    (
        FieldSpec(
            "accountCode",
            required=True,
            min_length=1,
            max_length=32,
            aliases=("account_code",),
            # A code is a human identifier used in reports and posting rules; the
            # characters that would break a URL, a sort or a printed statement
            # are refused up front rather than stored.
            pattern=r"[A-Za-z0-9][A-Za-z0-9._-]*",
            label="Account code",
        ),
        FieldSpec(
            "accountName",
            required=True,
            min_length=1,
            max_length=255,
            aliases=("account_name",),
            label="Account name",
        ),
        FieldSpec("accountType", choices=ACCOUNT_TYPES, max_length=20, aliases=("account_type",), label="Account type"),
        FieldSpec(
            "normalBalance",
            choices=NORMAL_BALANCES,
            max_length=10,
            aliases=("normal_balance",),
            label="Normal balance",
        ),
        FieldSpec("parentCode", max_length=32, aliases=("parent_code",), label="Parent account"),
        FieldSpec("postable", kind="boolean", label="Is postable"),
        FieldSpec("status", choices=ACTIVE_STATUSES, max_length=20, label="Status"),
    )
)

FINANCIAL_ACCOUNT_SCHEMA = RecordSchema(
    (
        FieldSpec("ledgerCode", required=True, min_length=1, max_length=32, aliases=("ledger_code",), label="Ledger account"),
        FieldSpec(
            "accountName",
            required=True,
            min_length=1,
            max_length=255,
            aliases=("account_name",),
            label="Account name",
        ),
        FieldSpec(
            "accountType",
            choices=FINANCIAL_ACCOUNT_TYPES,
            max_length=32,
            aliases=("account_type",),
            label="Account type",
        ),
        FieldSpec("currency", min_length=3, max_length=3),
        FieldSpec("bankName", max_length=255, aliases=("bank_name",), label="Bank name"),
        FieldSpec(
            "accountNumberMasked",
            max_length=64,
            aliases=("account_number_masked",),
            label="Masked account number",
        ),
        FieldSpec("status", choices=ACTIVE_STATUSES, max_length=20, label="Status"),
    )
)

PERIOD_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("status", choices=PERIOD_STATUSES, max_length=20),
        FieldSpec("reason", max_length=2_000, aliases=("note",)),
    ),
    reject_unknown=True,
)

SEQUENCE_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("documentType", required=True, min_length=1, max_length=64, aliases=("document_type",)),
        FieldSpec("year", kind="integer", minimum=Decimal("2000"), maximum=Decimal("2200")),
        FieldSpec("prefix", max_length=16),
        FieldSpec("lastValue", kind="integer", minimum=0, aliases=("last_value",)),
        FieldSpec("paddingLength", kind="integer", minimum=1, maximum=12, aliases=("padding_length",)),
        FieldSpec("status", choices=ACTIVE_STATUSES, max_length=20),
    ),
    readonly=("id", "nextNumberPreview", "createdAt", "updatedAt"),
)

DOCUMENT_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("documentNo", max_length=50, aliases=("document_no", "debitNoteNo", "debit_note_no")),
        FieldSpec("documentType", max_length=32, aliases=("document_type",)),
        FieldSpec("date", kind="date"),
        FieldSpec("documentDate", kind="date", aliases=("document_date",)),
        FieldSpec("postingDate", kind="date", aliases=("posting_date",)),
        FieldSpec("dueDate", kind="date", aliases=("due_date",)),
        FieldSpec("valueDate", kind="date", aliases=("value_date",)),
        FieldSpec("currency", min_length=3, max_length=3),
        FieldSpec("exchangeRate", kind="decimal", minimum=0, decimal_places=8, aliases=("exchange_rate",)),
        FieldSpec("baseCurrency", min_length=3, max_length=3, aliases=("base_currency",)),
        FieldSpec("partyId", kind="reference", aliases=("party_id",)),
        FieldSpec("serviceOrderId", kind="reference", aliases=("service_order_id",)),
        FieldSpec("referenceNumber", max_length=128, aliases=("reference_number", "referenceNo")),
        FieldSpec("remark", max_length=10_000),
        FieldSpec("description", max_length=10_000),
        FieldSpec("paymentMethod", max_length=64, aliases=("payment_method",)),
        FieldSpec("financialAccountId", kind="reference", aliases=("financial_account_id",)),
    ),
    readonly=(
        "id",
        "status",
        "subtotal",
        "discount",
        "tax",
        "total",
        "paidAmount",
        "outstanding",
        "baseTotal",
        "createdAt",
        "updatedAt",
    ),
)

DOCUMENT_LINE_SCHEMA = RecordSchema(
    (
        FieldSpec("description", max_length=1_000),
        FieldSpec("feeTypeId", kind="reference", aliases=("fee_type_id",)),
        FieldSpec("feeType", kind="reference", max_length=255, aliases=("fee_type",)),
        FieldSpec("quantity", kind="decimal", minimum=0, decimal_places=3),
        FieldSpec("unitPrice", kind="decimal", aliases=("unit_price", "unitAmount", "unit_amount")),
        FieldSpec("discount", kind="decimal", minimum=0, aliases=("discountAmount", "discount_amount")),
        FieldSpec("taxRate", kind="decimal", minimum=0, maximum=100, aliases=("tax_rate", "tax")),
        FieldSpec("taxAmount", kind="decimal", minimum=0, aliases=("tax_amount",)),
        FieldSpec("unit", max_length=32, aliases=("unitCode", "unit_code")),
        FieldSpec("accountCode", kind="reference", max_length=32, aliases=("account_code",)),
        FieldSpec("accountId", kind="reference", aliases=("account_id",)),
        FieldSpec("serviceOrderId", kind="reference", aliases=("service_order_id",)),
        FieldSpec(
            "serviceOrderContainerId",
            kind="reference",
            aliases=("service_order_container_id", "containerId"),
        ),
    ),
    readonly=("id", "lineNo", "line_no", "amount", "total", "createdAt", "updatedAt"),
)

JOURNAL_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("entryNo", max_length=50, aliases=("entry_no",)),
        FieldSpec("entryType", max_length=64, aliases=("entry_type",)),
        FieldSpec("entryDate", kind="date", aliases=("entry_date",)),
        FieldSpec("postingDate", kind="date", aliases=("posting_date",)),
        FieldSpec("description", max_length=10_000),
    ),
    readonly=("id", "status", "debitTotal", "creditTotal", "createdAt", "updatedAt"),
)

JOURNAL_LINE_SCHEMA = RecordSchema(
    (
        FieldSpec("accountId", kind="reference", aliases=("account_id",)),
        FieldSpec("accountCode", kind="reference", max_length=32, aliases=("account_code",)),
        FieldSpec("debitAmount", kind="decimal", decimal_places=4, aliases=("debit_amount",)),
        FieldSpec("creditAmount", kind="decimal", decimal_places=4, aliases=("credit_amount",)),
        FieldSpec("exchangeRate", kind="decimal", minimum=0, decimal_places=8, aliases=("exchange_rate",)),
        FieldSpec("currency", min_length=3, max_length=3),
        FieldSpec("description", max_length=1_000),
        FieldSpec("party", kind="reference", aliases=("partyId", "party_id")),
        FieldSpec("serviceOrder", kind="reference", aliases=("serviceOrderId", "service_order_id")),
    ),
    readonly=("id", "lineNo", "line_no", "baseDebit", "baseCredit", "createdAt", "updatedAt"),
)

ALLOCATION_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec(
            "targetDocumentId",
            kind="reference",
            aliases=("target_document_id",),
        ),
        FieldSpec(
            "amount",
            kind="decimal",
            minimum=Decimal("0.0001"),
            decimal_places=4,
            aliases=("allocated_amount", "allocatedAmount"),
        ),
    ),
    readonly=("id", "allocatedCurrencyCode", "exchangeRate", "paymentBaseAmount", "targetBaseAmount"),
)

REVERSAL_WRITE_SCHEMA = RecordSchema(
    (
        FieldSpec("reason", max_length=2_000, aliases=("note",)),
    ),
    reject_unknown=True,
)

POSTING_RULE_WRITE_SCHEMA = RecordSchema(
    (
        # Required-ness, the account vocabulary and the priority/status
        # messages stay with `_posting_rule_data`, which can keep the existing
        # field-specific wording ("Select the debit account.", "Priority cannot
        # be negative."). The schema still bounds the text and refuses unknown
        # keys.
        FieldSpec("documentType", min_length=1, max_length=32, aliases=("document_type",)),
        FieldSpec("feeTypeId", kind="reference", aliases=("fee_type_id",)),
        FieldSpec("debitAccount", min_length=1, max_length=64, aliases=("debit_account",)),
        FieldSpec("creditAccount", min_length=1, max_length=64, aliases=("credit_account",)),
        FieldSpec("taxAccount", max_length=64, aliases=("tax_account",)),
        FieldSpec("status", max_length=20),
        FieldSpec("priority", kind="json"),
        FieldSpec("description", max_length=2_000),
    ),
    reject_unknown=True,
)

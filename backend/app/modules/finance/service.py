from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache, deletion, fx
from app.core.context import RequestContext
from app.core.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, list_sort_orders, paged
from app.core.sequences import allocate_number
from app.core.serialization import jsonable
from app.modules.finance.models import (
    AccountingPeriod,
    ChartOfAccount,
    DocumentSequence,
    FinancialAccount,
    FinancialDocument,
    FinancialDocumentAllocation,
    FinancialDocumentLine,
    FinancialDocumentPosting,
    FinancialDocumentSource,
    JournalEntry,
    JournalEntryLine,
    PostingRule,
)
from app.modules.finance.posting import (
    ALLOCATABLE_TYPES,
    STRATEGIES,
    AccountingPostingService,
    DocumentLineInput,
)
from app.modules.finance.posting_rules import (
    POSTING_RULE_ACTIVE,
    PostingRuleResolver,
    validate_postable,
)
from app.modules.finance.repository import FinanceRepository
from app.modules.master_data.currency_rates import (
    assert_currency_code,
    currency_precision,
    resolve_document_rate,
)
from app.modules.master_data.models import BusinessParty, Currency, FeeType
from app.modules.operations.models import ServiceOrder, ServiceOrderCharge, ServiceOrderChargeLine
from app.modules.settings.service import get_default_currency

# The document types a posting rule can be configured for, with the accounting
# meaning each one carries. The strategy table decides how a type posts; this
# catalogue decides what an administrator may choose, so the two are declared
# together and a type cannot be selectable without a posting meaning.
DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "CUSTOMER_INVOICE": "Customer invoice",
    "CREDIT_NOTE": "Customer credit note",
    "SUPPLIER_BILL": "Supplier bill",
    "SUPPLIER_CREDIT_NOTE": "Supplier credit note",
    "CUSTOMER_RECEIPT": "Customer payment received",
    "SUPPLIER_PAYMENT": "Supplier payment made",
    "OTHER_INCOME": "Other income",
    "OTHER_EXPENSE": "Other expense",
    "TRANSFER": "Transfer between own accounts",
    "ADJUSTMENT": "Adjustment",
}
KNOWN_DOCUMENT_TYPES = frozenset(DOCUMENT_TYPE_LABELS) | frozenset(STRATEGIES)

DEFAULT_ACCOUNTS: dict[str, tuple[str, str]] = {
    "CUSTOMER_INVOICE": ("1100", "4010"),
    "SUPPLIER_BILL": ("5010", "2010"),
    "CUSTOMER_RECEIPT": ("1020", "1100"),
    "SUPPLIER_PAYMENT": ("2010", "1020"),
    "OTHER_INCOME": ("1020", "4020"),
    "OTHER_EXPENSE": ("5030", "1020"),
    "TRANSFER": ("1020", "1010"),
    "ADJUSTMENT": ("5030", "1020"),
    # A credit note mirrors its originating document, so its fallback is the
    # mirror of the invoice's.
    "CREDIT_NOTE": ("4010", "1100"),
    "SUPPLIER_CREDIT_NOTE": ("2010", "5010"),
}
PAYMENT_TYPES = {"CUSTOMER_RECEIPT", "SUPPLIER_PAYMENT"}
# Allocation targets are defined once, next to the posting strategies, so the two
# cannot drift apart.
INVOICE_TYPES = set(ALLOCATABLE_TYPES)


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return default


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# --- Chart of accounts / financial accounts / periods / sequences ------------
def account_payload(account: ChartOfAccount, parent_code: str | None = None) -> dict[str, Any]:
    return {
        "id": str(account.id),
        "accountCode": account.account_code,
        "accountName": account.account_name,
        "accountType": account.account_type.capitalize() if account.account_type.isupper() else account.account_type,
        "parentCode": parent_code,
        "parentAccountId": account.parent_account_id,
        "normalBalance": account.normal_balance.capitalize() if account.normal_balance.isupper() else account.normal_balance,
        "postable": account.is_postable,
        "status": account.status.capitalize() if account.status.isupper() else account.status,
    }


async def list_accounts(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    rows, total = await FinanceRepository(session).account_page(page)
    codes = {row.id: row.account_code for row in rows}
    items = [account_payload(row, codes.get(row.parent_account_id)) for row in rows]
    return paged(items, page, total)


async def create_account(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    account = ChartOfAccount(
        account_code=str(data.get("accountCode") or data.get("account_code")),
        account_name=str(data.get("accountName") or data.get("account_name")),
        account_type=str(data.get("accountType") or "ASSET").upper(),
        normal_balance=str(data.get("normalBalance") or "DEBIT").upper(),
        is_postable=bool(data.get("postable", True)),
        status=str(data.get("status") or "ACTIVE").upper(),
    )
    session.add(account)
    await session.commit()
    return account_payload(account)


async def update_account(session: AsyncSession, context: RequestContext, account_id: int, data: dict[str, Any]) -> dict:
    account = await session.get(ChartOfAccount, account_id)
    if account is None:
        raise NotFound("Account not found.")
    for key, column in (("accountCode", "account_code"), ("accountName", "account_name"), ("accountType", "account_type"), ("normalBalance", "normal_balance")):
        if data.get(key) is not None:
            setattr(account, column, str(data[key]))
    if data.get("postable") is not None:
        account.is_postable = bool(data["postable"])
    if data.get("status") is not None:
        account.status = str(data["status"]).upper()
    await session.commit()
    return account_payload(account)


async def financial_account_payload(session: AsyncSession, account: FinancialAccount) -> dict[str, Any]:
    ledger = await session.get(ChartOfAccount, account.account_id) if account.account_id else None
    balance = await session.scalar(
        select(
            func.coalesce(func.sum(JournalEntryLine.base_debit_amount - JournalEntryLine.base_credit_amount), 0)
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            JournalEntryLine.account_id == account.account_id,
            JournalEntry.status == "POSTED",
        )
    )
    return {
        "id": str(account.id),
        "accountName": account.account_name,
        "ledgerCode": ledger.account_code if ledger else None,
        "ledgerAccountId": account.account_id,
        "accountType": account.account_type,
        "currency": account.currency_code,
        "bankName": account.bank_name,
        "accountNumberMasked": account.account_number_masked,
        "balance": float(balance or 0),
        "status": account.status,
    }


async def list_financial_accounts(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    repository = FinanceRepository(session)
    rows, total = await repository.financial_account_page(page)
    ledgers, balances = await repository.financial_account_details(rows)
    items = [
        {
            "id": str(row.id),
            "accountName": row.account_name,
            "ledgerCode": ledgers[row.account_id].account_code if row.account_id in ledgers else None,
            "ledgerAccountId": row.account_id,
            "accountType": row.account_type,
            "currency": row.currency_code,
            "bankName": row.bank_name,
            "accountNumberMasked": row.account_number_masked,
            "balance": float(balances.get(row.account_id, 0) or 0),
            "status": row.status,
        }
        for row in rows
    ]
    return paged(items, page, total)


async def create_financial_account(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    default_currency = await get_default_currency(session)
    ledger_code = data.get("ledgerCode")
    ledger = (
        await session.execute(
            select(ChartOfAccount).where(ChartOfAccount.account_code == ledger_code)
        )
    ).scalars().first()
    if ledger is None:
        raise ValidationFailed("Ledger account not found.", {"ledgerCode": "Unknown account"})
    account = FinancialAccount(
        account_id=ledger.id,
        account_name=str(data.get("accountName") or ledger.account_name),
        account_type=str(data.get("accountType") or "Bank").upper(),
        currency_code=str(data.get("currency") or default_currency),
        bank_name=data.get("bankName"),
        account_number_masked=data.get("accountNumberMasked"),
        status=str(data.get("status") or "ACTIVE").upper(),
    )
    session.add(account)
    await session.commit()
    return await financial_account_payload(session, account)


def period_payload(period: AccountingPeriod, closed_by: str | None = None, posting_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(period.id),
        "name": f"{period.period_year}-{str(period.period_month).zfill(2)}",
        "year": period.period_year,
        "month": period.period_month,
        "startDate": period.start_date.isoformat(),
        "endDate": period.end_date.isoformat(),
        "status": period.status,
        "postingCount": posting_count,
        "closedBy": closed_by,
        "closedAt": period.closed_at.isoformat() if period.closed_at else None,
    }


async def list_periods(
    session: AsyncSession,
    context: RequestContext,
    page: PageParams | None = None,
) -> list[dict]:
    default_order = (AccountingPeriod.period_year.desc(), AccountingPeriod.period_month.desc())
    aliases = {"startDate": "start_date", "endDate": "end_date"}
    orders = list_sort_orders(AccountingPeriod, page, *default_order, aliases=aliases) if page else list(default_order)
    rows = (await session.execute(select(AccountingPeriod).order_by(*orders))).scalars().all()
    return [period_payload(row) for row in rows]


async def resolve_period(session: AsyncSession, posting_date: date) -> AccountingPeriod:
    period = (
        await session.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.start_date <= posting_date,
                AccountingPeriod.end_date >= posting_date,
            )
        )
    ).scalars().first()
    if period is None:
        # Periods cover a full calendar month so a later posting date in the same
        # month reuses this row instead of trying to create a duplicate (which
        # would violate the (year, month) unique constraint).
        if posting_date.month == 12:
            end_date = date(posting_date.year, 12, 31)
        else:
            end_date = date(posting_date.year, posting_date.month + 1, 1) - timedelta(days=1)
        period = AccountingPeriod(
            period_year=posting_date.year,
            period_month=posting_date.month,
            start_date=posting_date.replace(day=1),
            end_date=end_date,
            status="OPEN",
        )
        session.add(period)
        await session.flush()
    return period


async def update_period(session: AsyncSession, context: RequestContext, period_id: int, data: dict[str, Any]) -> dict:
    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise NotFound("Accounting period not found.")
    status_value = data.get("status")
    if status_value is not None:
        period.status = str(status_value).upper()
        if period.status == "OPEN":
            period.closed_at = None
            period.closed_by_user_id = None
    await session.commit()
    return period_payload(period)


async def close_period(session: AsyncSession, context: RequestContext, period_id: int) -> dict:
    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise NotFound("Accounting period not found.")
    period.status = "CLOSED"
    period.closed_at = datetime.now(UTC)
    period.closed_by_user_id = context.user_id
    await session.commit()
    return period_payload(period)


async def reopen_period(session: AsyncSession, context: RequestContext, period_id: int) -> dict:
    """Reopen a closed period so new postings are accepted again.

    Stores ``OPEN`` and clears the closure stamp. The previous frontend path
    wrote ``REOPENED``, which the posting checks treat as open but which left
    ``closed_at``/``closed_by_user_id`` attributed to the closing user.
    """
    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise NotFound("Accounting period not found.")
    period.status = "OPEN"
    period.closed_at = None
    period.closed_by_user_id = None
    await session.commit()
    return period_payload(period)


def sequence_payload(sequence: DocumentSequence) -> dict[str, Any]:
    preview = f"{sequence.prefix}{sequence.period_year}-{str(sequence.last_value + 1).zfill(sequence.padding_length)}"
    return {
        "id": str(sequence.id),
        "documentType": sequence.document_type,
        "year": sequence.period_year,
        "prefix": sequence.prefix,
        "lastValue": sequence.last_value,
        "paddingLength": sequence.padding_length,
        "nextNumberPreview": preview,
        "status": sequence.status.capitalize() if sequence.status.isupper() else sequence.status,
    }


async def list_sequences(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(DocumentSequence)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(DocumentSequence, page, DocumentSequence.id))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    return paged([sequence_payload(row) for row in rows], page, total)


async def upsert_sequence(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    year = int(data.get("year") or datetime.now(UTC).year)
    document_type = str(data.get("documentType") or "").upper()
    sequence = (
        await session.execute(
            select(DocumentSequence).where(
                DocumentSequence.document_type == document_type,
                DocumentSequence.period_year == year,
            )
        )
    ).scalars().first()
    if sequence is None:
        sequence = DocumentSequence(
            document_type=document_type,
            period_year=year,
            prefix=str(data.get("prefix") or document_type[:2]),
            last_value=int(data.get("lastValue") or 0),
            padding_length=int(data.get("paddingLength") or 6),
            status=str(data.get("status") or "ACTIVE").upper(),
        )
        session.add(sequence)
    else:
        sequence.prefix = str(data.get("prefix") or sequence.prefix)
        sequence.last_value = int(data.get("lastValue") if data.get("lastValue") is not None else sequence.last_value)
        sequence.padding_length = int(data.get("paddingLength") or sequence.padding_length)
        sequence.status = str(data.get("status") or sequence.status).upper()
    await session.commit()
    return sequence_payload(sequence)


# --- Financial documents -----------------------------------------------------
def document_payload(
    document: FinancialDocument,
    data: dict[str, Any],
    lines: list[FinancialDocumentLine] | None = None,
    extra: dict[str, Any] | None = None,
    line_accounts: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Serialise one financial document.

    ``extra`` carries what the caller resolved in bulk (party name, service-order
    number, financial account, posted journal, allocations), so this stays a pure
    formatter. The keys the form and the list columns read — ``date``, ``customer``,
    ``jobNo``, ``outstanding``, ``vat``, ``referenceNo`` — are emitted next to the
    canonical ones, because a document created by the API (an invoice generated from
    a service charge, for instance) has none of them echoed in ``data``.
    ``line_accounts`` maps a line id to the account code it will post to.
    """
    total = document.total_amount or Decimal("0")
    paid = document.paid_amount or Decimal("0")
    payload = dict(data or {})
    payload.update(
        {
            "id": str(document.id),
            "documentNo": document.document_no,
            "debitNoteNo": document.document_no,
            "documentType": document.document_type,
            "documentDate": document.document_date.isoformat() if document.document_date else None,
            "date": document.document_date.isoformat() if document.document_date else None,
            "postingDate": document.posting_date.isoformat() if document.posting_date else None,
            "dueDate": document.due_date.isoformat() if document.due_date else None,
            "valueDate": document.value_date.isoformat() if document.value_date else None,
            "status": document.status.capitalize() if document.status.isupper() else document.status,
            "rawStatus": document.status,
            "currency": document.currency_code,
            "exchangeRate": float(document.exchange_rate or 1),
            "subtotal": float(document.subtotal_amount or 0),
            "discount": float(document.discount_amount or 0),
            "tax": float(document.tax_amount or 0),
            "vat": float(document.tax_amount or 0),
            "total": float(total),
            "amount": float(total),
            "paidAmount": float(paid),
            "balance": float(total - paid),
            "outstanding": float(total - paid),
            "partyId": str(document.party_id) if document.party_id else None,
            "serviceOrderId": str(document.service_order_id) if document.service_order_id else None,
            "referenceNumber": document.reference_number,
            "referenceNo": document.reference_number,
            "paymentMethod": document.payment_method_code,
            # The conversion the document was booked at: its own currency and rate,
            # the base currency it converts into, and the converted amounts. All
            # four are stored on the row, so a posted document keeps saying what it
            # was posted against even after the rate store changes.
            "baseCurrency": document.base_currency_code,
            "baseSubtotalAmount": float(document.base_subtotal_amount or 0),
            "baseDiscountAmount": float(document.base_discount_amount or 0),
            "baseTaxAmount": float(document.base_tax_amount or 0),
            "baseTotalAmount": float(document.base_total_amount or 0),
            # Reference ids travel as strings: the form's Master Data selects are
            # keyed by the string id their options carry.
            "financialAccountId": str(document.financial_account_id) if document.financial_account_id else None,
            "remark": document.description,
            "description": document.description,
            "createdAt": document.created_at.isoformat() if document.created_at else None,
        }
    )
    if extra:
        payload.update(extra)
    if lines is not None:
        payload["lines"] = [
            _line_payload(line, (line_accounts or {}).get(line.id)) for line in lines
        ]
    return payload


def _line_payload(line: FinancialDocumentLine, account_code: str | None = None) -> dict[str, Any]:
    return {
        "id": str(line.id),
        "description": line.description,
        "feeTypeId": line.fee_type_id,
        "quantity": float(line.quantity or 0),
        "unitPrice": float(line.unit_price or 0),
        "discount": float(line.discount_amount or 0),
        "taxRate": float(line.tax_rate or 0),
        "tax": float(line.tax_amount or 0),
        "amount": float(line.line_amount or 0),
        "accountId": line.account_id,
        # Derived from the posting rules when the line names no account of its own.
        "accountCode": account_code,
        "serviceOrderId": str(line.service_order_id) if line.service_order_id else None,
    }


async def _document_lines(session: AsyncSession, document_id: int) -> list[FinancialDocumentLine]:
    return (await FinanceRepository(session).document_lines([document_id])).get(document_id, [])


async def _line_account_codes(
    session: AsyncSession,
    document_type: str,
    lines: list[FinancialDocumentLine],
) -> dict[int, str]:
    """The account code each line posts to, resolved through the posting rules.

    Only the detail endpoint asks for this: it costs one rule lookup per line, and
    the list endpoint must not pay that per row. A line that names its own account
    keeps it; otherwise the code is the one ``post_document`` will resolve.
    """
    if not lines:
        return {}
    posting = posting_service(session)
    codes: dict[int, str] = {}
    for line in lines:
        code = await posting.detail_account_code(
            document_type,
            DocumentLineInput(
                description=line.description or "",
                amount=line.line_amount or Decimal("0"),
                tax=line.tax_amount or Decimal("0"),
                fee_type_id=line.fee_type_id,
                account_id=line.account_id,
            ),
        )
        if code:
            codes[line.id] = code
    return codes


async def _document_names(
    session: AsyncSession,
    documents: list[FinancialDocument],
) -> dict[int, dict[str, Any]]:
    """Names for the foreign keys on a page of documents, fetched in bulk.

    One query per reference table keeps the list endpoint's query count flat
    instead of paying a lookup per row.
    """
    party_ids = {document.party_id for document in documents if document.party_id}
    order_ids = {document.service_order_id for document in documents if document.service_order_id}
    account_ids = {document.financial_account_id for document in documents if document.financial_account_id}
    parties: dict[int, str] = {}
    if party_ids:
        parties = {
            row.id: row.legal_name
            for row in (await session.execute(
                select(BusinessParty).where(BusinessParty.id.in_(party_ids))
            )).scalars()
        }
    orders: dict[int, str] = {}
    if order_ids:
        orders = dict((await session.execute(
            select(ServiceOrder.id, ServiceOrder.service_order_no).where(ServiceOrder.id.in_(order_ids))
        )).all())
    accounts: dict[int, str] = {}
    if account_ids:
        accounts = dict((await session.execute(
            select(FinancialAccount.id, FinancialAccount.account_name).where(FinancialAccount.id.in_(account_ids))
        )).all())
    # The precision the converted amounts were rounded with, so the form can
    # round its live preview exactly the way the server stored the document.
    codes = {document.currency_code for document in documents if document.currency_code}
    precisions: dict[str, int] = {}
    if codes:
        precisions = {
            row[0]: fx.currency_precision(row[1])
            for row in (await session.execute(
                select(Currency.code, Currency.decimal_places).where(Currency.code.in_(codes))
            )).all()
        }
    return {
        document.id: {
            # A legacy record may only carry the typed name inside its stored payload.
            "customer": parties.get(document.party_id) or (document.data or {}).get("customer"),
            "jobNo": orders.get(document.service_order_id),
            "financialAccount": accounts.get(document.financial_account_id),
            "currencyPrecision": precisions.get(document.currency_code, fx.DEFAULT_CURRENCY_PRECISION),
        }
        for document in documents
    }


async def _document_detail_extras(session: AsyncSession, document: FinancialDocument) -> dict[str, Any]:
    """The posted journal and the allocations of one document.

    Neither is stored on the document: the journal comes from
    ``financial_document_postings`` and an allocation is a payment ⇄ invoice link,
    shown from whichever side the document is on.
    """
    extras: dict[str, Any] = {}

    journal = (await session.execute(
        select(JournalEntry)
        .join(FinancialDocumentPosting, FinancialDocumentPosting.journal_entry_id == JournalEntry.id)
        .where(FinancialDocumentPosting.financial_document_id == document.id)
        .order_by(JournalEntry.id.desc())
        .limit(1)
    )).scalars().first()
    if journal is not None:
        extras["journalId"] = str(journal.id)
        extras["journalNo"] = journal.entry_no
        extras["journalEntries"] = [
            {
                "id": str(line.id),
                "account": account_code,
                "description": line.description,
                "debit": float(line.debit_amount or 0),
                "credit": float(line.credit_amount or 0),
            }
            for line, account_code in (await session.execute(
                select(JournalEntryLine, ChartOfAccount.account_code)
                .join(ChartOfAccount, ChartOfAccount.id == JournalEntryLine.account_id)
                .where(JournalEntryLine.journal_entry_id == journal.id)
                .order_by(JournalEntryLine.line_no)
            )).all()
        ]

    allocations = (await session.execute(
        select(FinancialDocumentAllocation)
        .where(or_(
            FinancialDocumentAllocation.payment_document_id == document.id,
            FinancialDocumentAllocation.target_document_id == document.id,
        ))
        .order_by(FinancialDocumentAllocation.id)
    )).scalars().all()
    counterparts: dict[int, FinancialDocument] = {}
    counterpart_ids = {
        allocation.target_document_id if allocation.payment_document_id == document.id else allocation.payment_document_id
        for allocation in allocations
    }
    if counterpart_ids:
        counterparts = {
            row.id: row
            for row in (await session.execute(
                select(FinancialDocument).where(FinancialDocument.id.in_(counterpart_ids))
            )).scalars()
        }
    names = await _document_names(session, list(counterparts.values()))
    # Every allocation of one document shares its currency (the allocation guard
    # requires the payment and the target to match), so the precision is looked up
    # once rather than per row.
    allocation_precision = await currency_precision(session, document.currency_code)
    rows: list[dict[str, Any]] = []
    for allocation in allocations:
        counterpart_id = (
            allocation.target_document_id
            if allocation.payment_document_id == document.id
            else allocation.payment_document_id
        )
        counterpart = counterparts.get(counterpart_id)
        counterpart_total = (counterpart.total_amount or Decimal("0")) if counterpart else Decimal("0")
        counterpart_paid = (counterpart.paid_amount or Decimal("0")) if counterpart else Decimal("0")
        # The same allocated amount is worth a different base amount on each side
        # when the two documents were booked at different rates. The difference is
        # the exchange gain or loss the settlement realises; the stored
        # `allocation.exchange_rate` is the payment's rate at allocation time.
        viewed_is_payment = allocation.payment_document_id == document.id
        counterpart_rate = counterpart.exchange_rate if counterpart else None
        payment_rate = allocation.exchange_rate if viewed_is_payment else counterpart_rate
        invoice_rate = counterpart_rate if viewed_is_payment else document.exchange_rate
        payment_base, invoice_base, exchange_difference = _allocation_fx(
            allocation.allocated_amount or Decimal("0"), payment_rate, invoice_rate, allocation_precision
        )
        rows.append({
            "id": str(allocation.id),
            "targetDocumentId": str(counterpart_id),
            "targetDocumentNo": counterpart.document_no if counterpart else "",
            "party": names.get(counterpart_id, {}).get("customer"),
            "originalAmount": float(counterpart_total),
            "amount": float(allocation.allocated_amount or 0),
            "targetOutstanding": float(counterpart_total - counterpart_paid),
            "currency": allocation.allocated_currency_code,
            "paymentBaseAmount": float(payment_base),
            "invoiceBaseAmount": float(invoice_base),
            "exchangeDifference": float(exchange_difference),
            "allocatedAt": allocation.allocated_at.isoformat() if allocation.allocated_at else None,
        })
    extras["allocations"] = rows
    return extras


async def list_documents(
    session: AsyncSession,
    context: RequestContext,
    page: PageParams,
    document_type: str | None = None,
    party_id: int | None = None,
) -> dict:
    repository = FinanceRepository(session)
    rows, total = await repository.document_page(page, document_type=document_type, party_id=party_id)
    lines = await repository.document_lines([row.id for row in rows])
    names = await _document_names(session, rows)
    return paged(
        [
            document_payload(row, row.data or {}, lines.get(row.id, []), names.get(row.id))
            for row in rows
        ],
        page,
        total,
    )


async def get_document(session: AsyncSession, context: RequestContext, document_id: int) -> dict:
    document, lines = await FinanceRepository(session).document_with_lines(document_id)
    if document is None:
        raise NotFound("Financial document not found.")
    extras = {
        **(await _document_names(session, [document])).get(document.id, {}),
        **await _document_detail_extras(session, document),
    }
    return document_payload(
        document,
        document.data or {},
        lines,
        extras,
        await _line_account_codes(session, document.document_type, lines),
    )


async def delete_draft_documents(session: AsyncSession, ids: list[int]) -> int:
    documents = await FinanceRepository(session).documents_by_ids(ids)
    drafts = [document for document in documents if document.status == "DRAFT"]
    for document in drafts:
        await session.delete(document)
    await session.commit()
    return len(drafts)


def _document_columns(data: dict[str, Any], document_type: str, default_currency: str) -> dict[str, Any]:
    """Column values a create and an update both apply.

    Payment method, financial account and value date describe a settlement, and a
    due date describes credit terms, so each is read only for the document types
    that carry one. A stale client value therefore cannot land on a document it does
    not belong to, whatever the caller sends.
    """
    columns: dict[str, Any] = {
        "party_id": _int_or_none(data.get("partyId")),
        "service_order_id": _int_or_none(data.get("serviceOrderId")),
        "description": data.get("remark") if data.get("remark") is not None else data.get("description"),
        # The form posts `referenceNo`; `referenceNumber` is the canonical spelling.
        "reference_number": data.get("referenceNumber") or data.get("referenceNo"),
        "posting_date": _date(data.get("postingDate")),
        # The form posts `date`; `documentDate` is the canonical API spelling.
        "document_date": _date(data.get("documentDate") or data.get("date")),
    }
    if document_type in PAYMENT_TYPES:
        columns["payment_method_code"] = data.get("paymentMethod")
        columns["financial_account_id"] = _int_or_none(data.get("financialAccountId"))
        columns["value_date"] = _date(data.get("valueDate"))
    if document_type in ALLOCATABLE_TYPES:
        columns["due_date"] = _date(data.get("dueDate"))
    return columns


async def _document_currency_inputs(
    session: AsyncSession,
    data: dict[str, Any],
    *,
    document_currency: str,
    base_currency: str,
    on_date: date | None,
    stored_rate: Decimal | None = None,
) -> tuple[str, Decimal, str, int]:
    """``(currency, rate, base currency, precision)`` for the document being saved.

    The rate is the document's own snapshot of the conversion, so it is validated
    and stored with the document rather than looked up again later — a posting
    reads the document, never the rate store:

    * a document already in the base currency always stores rate 1, whatever a
      client sends: the rate is not part of that document;
    * otherwise a rate the client sent wins, so an operator can book a contract
      rate the store does not carry;
    * when the client sent none, an update keeps the stored rate; failing that,
      the latest approved rate for the pair is applied;
    * when nothing resolves the save is refused, because defaulting to 1 would
      mis-state every converted amount on the document.
    """
    currency = await assert_currency_code(session, document_currency)
    base = await assert_currency_code(session, base_currency, field="baseCurrency")
    precision = await currency_precision(session, currency)
    if fx.same_currency(currency, base):
        return currency, Decimal("1"), base, precision
    rate = data.get("exchangeRate")
    if rate in (None, ""):
        rate = stored_rate
    if rate in (None, ""):
        rate = await resolve_document_rate(session, currency, base, on_date)
        if rate is None:
            raise ValidationFailed(
                f"No approved exchange rate is configured for {currency} to {base}.",
                {fx.RATE_FIELD: "Enter the exchange rate, or add one in Master Data -> Currency Rates."},
            )
    return currency, fx.document_rate(currency, base, rate), base, precision


async def _line_account_id(session: AsyncSession, line: dict[str, Any]) -> int | None:
    """The account a line posts to, or None when the posting rules should decide.

    An account named by the caller - by code or by id - is validated as a postable
    leaf account before it is stored, because posting prefers a line's own account
    over the rule. A blank account stays blank: ``post_document`` resolves it from
    the rule in force at posting time.
    """
    reference = line.get("accountCode") or line.get("accountId")
    if reference in (None, ""):
        return None
    account = await _resolve_account_ref(session, reference)
    if account is None:
        raise ValidationFailed(
            f"Unknown account '{reference}'.",
            field_errors={"lines": "Choose an account from the chart of accounts."},
        )
    return _validate_posting_account(account, "line").id


async def save_document(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    default_currency = await get_default_currency(session)
    document_type = str(data.get("documentType") or data.get("document_type") or "CUSTOMER_INVOICE").upper()
    document_id = data.get("id")
    document: FinancialDocument | None = None
    if document_id and str(document_id).isdigit():
        document = await session.get(FinancialDocument, int(document_id))
    lines = data.get("lines") or []
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")
    # Currency, rate, base currency and precision are resolved once, from the
    # incoming value when there is one and from the stored document otherwise, so
    # create and update cannot disagree about the conversion.
    currency_code, exchange_rate, base_currency, precision = await _document_currency_inputs(
        session,
        data,
        document_currency=str(
            data.get("currency")
            or (document.currency_code if document is not None else default_currency)
            or default_currency
        ),
        base_currency=default_currency,
        on_date=_date(data.get("documentDate") or data.get("date"))
        or (document.document_date if document is not None else None)
        or date.today(),
        stored_rate=document.exchange_rate if document is not None else None,
    )
    if document is None:
        if document_type not in KNOWN_DOCUMENT_TYPES:
            raise ValidationFailed(
                f"Unknown document type '{document_type}'.",
                field_errors={"documentType": "Choose one of the configured financial document types."},
            )
        number = data.get("documentNo") or data.get("debitNoteNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, document_type)
        columns = _document_columns(data, document_type, default_currency)
        columns["document_date"] = columns.get("document_date") or date.today()
        document = FinancialDocument(
            document_no=str(number),
            document_type=document_type,
            status="DRAFT",
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            base_currency_code=base_currency,
            created_by_user_id=context.user_id,
            data={},
            **columns,
        )
        session.add(document)
        await session.flush()
    else:
        if document.status not in {"DRAFT"}:
            raise InvalidState("Only draft documents can be edited; posted documents require a reversal.")
        if (data.get("documentType") or data.get("document_type")) and document_type != document.document_type:
            # The number was allocated from the original type's sequence, so the two
            # would disagree for ever; a mis-typed draft is deleted and recreated. A
            # caller that sends no type at all keeps the stored one.
            raise ValidationFailed(
                "A financial document keeps the type it was created with.",
                field_errors={"documentType": f"This document is a {document.document_type}."},
            )
        for column, value in _document_columns(data, document.document_type, default_currency).items():
            if value is not None:
                setattr(document, column, value)
        if data.get("currency") is not None or data.get("exchangeRate") is not None:
            document.currency_code = currency_code
            document.exchange_rate = exchange_rate
        document.base_currency_code = base_currency
        document.status = "DRAFT"

    await session.execute(delete(FinancialDocumentLine).where(FinancialDocumentLine.financial_document_id == document.id))
    from app.modules.master_data.service import resolve_reference_id

    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        quantity = _decimal(line.get("quantity"), Decimal("1"))
        unit_price = _decimal(line.get("unitPrice"), Decimal("0"))
        discount = _decimal(line.get("discount"), Decimal("0"))
        tax_rate = _decimal(line.get("taxRate"), Decimal("0"))
        base = quantity * unit_price
        tax_amount = (base - discount) * tax_rate / Decimal("100") if tax_rate else Decimal("0")
        amount = _decimal(line.get("amount"), base - discount + tax_amount)
        subtotal += base
        discount_total += discount
        tax_total += tax_amount
        session.add(
            FinancialDocumentLine(
                financial_document_id=document.id,
                line_no=index + 1,
                description=str(line.get("description") or "Line"),
                fee_type_id=await resolve_reference_id(
                    session,
                    "fee_type",
                    line.get("feeTypeId") or line.get("fee_type_id"),
                    line.get("feeType") or line.get("fee_type"),
                ),
                quantity=quantity,
                unit_price=unit_price,
                discount_amount=discount,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                line_amount=amount,
                service_order_id=_int_or_none(line.get("serviceOrderId")),
                service_order_container_id=_int_or_none(line.get("serviceOrderContainerId")),
                account_id=await _line_account_id(session, line),
            )
        )
    document.subtotal_amount = subtotal
    document.discount_amount = discount_total
    document.tax_amount = tax_total
    document.total_amount = subtotal - discount_total + tax_total
    # The converted amounts, rounded with the currency's own precision. Deriving
    # them here (and again at posting) is what keeps the document, the journal it
    # writes and the printed invoice showing the same base-currency figures.
    document.base_currency_code = base_currency
    document.base_subtotal_amount = fx.convert_to_base(subtotal, exchange_rate, precision)
    document.base_discount_amount = fx.convert_to_base(discount_total, exchange_rate, precision)
    document.base_tax_amount = fx.convert_to_base(tax_total, exchange_rate, precision)
    document.base_total_amount = fx.convert_to_base(
        subtotal - discount_total + tax_total, exchange_rate, precision
    )
    document.data = jsonable({key: value for key, value in data.items() if key not in {"id", "lines", "createdAt", "updatedAt"}})
    await session.commit()
    saved_lines = await _document_lines(session, document.id)
    names = (await _document_names(session, [document])).get(document.id, {})
    return document_payload(
        document,
        document.data or {},
        saved_lines,
        names,
        await _line_account_codes(session, document.document_type, saved_lines),
    )


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- Posting engine ----------------------------------------------------------
async def _account_by_code(session: AsyncSession, code: str) -> ChartOfAccount | None:
    return (
        await session.execute(
            select(ChartOfAccount).where(ChartOfAccount.account_code == code)
        )
    ).scalars().first()


async def _resolve_account_ref(session: AsyncSession, value: Any) -> ChartOfAccount | None:
    """Accept an account code (canonical) or a numeric id (legacy clients)."""
    if value in (None, ""):
        return None
    account = await _account_by_code(session, str(value))
    if account is None and str(value).isdigit():
        account = await session.get(ChartOfAccount, int(value))
    return account


def rule_resolver(session: AsyncSession) -> PostingRuleResolver:
    """One resolver per request; it caches the accounts it touches."""
    return PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS)


def posting_service(session: AsyncSession) -> AccountingPostingService:
    return AccountingPostingService(rule_resolver(session))


def _validate_posting_account(account: ChartOfAccount | None, label: str) -> ChartOfAccount:
    return validate_postable(account, label)


async def post_document(session: AsyncSession, context: RequestContext, document_id: int) -> dict:
    """Post a financial document as one atomic, balanced journal entry.

    The accounting itself lives in :class:`AccountingPostingService`; this
    function owns the transaction, the state machine and the database guards.
    A failure anywhere below leaves the document in DRAFT with no journal.
    """
    document = (
        await session.execute(select(FinancialDocument).where(FinancialDocument.id == document_id).with_for_update())
    ).scalars().first()
    if document is None:
        raise NotFound("Financial document not found.")
    if document.status == "POSTED":
        return document_payload(document, document.data or {}, await _document_lines(session, document.id))
    if document.status != "DRAFT":
        raise InvalidState(f"Cannot post a document in status {document.status}.")

    # Reject a second posting of the same document even if the document row were
    # somehow reset to DRAFT: the unique posting link is the real guarantee.
    existing_posting = (
        await session.execute(
            select(FinancialDocumentPosting).where(FinancialDocumentPosting.financial_document_id == document.id)
        )
    ).scalars().first()
    if existing_posting is not None:
        raise Conflict("DUPLICATE_POSTING", "This document has already been posted.")

    posting_date = document.posting_date or document.document_date or date.today()
    document.posting_date = posting_date
    period = await resolve_period(session, posting_date)
    if period.status == "CLOSED":
        raise Conflict("PERIOD_CLOSED", "The accounting period is closed.")

    total = document.total_amount or Decimal("0")
    document_lines = await _document_lines(session, document.id)
    draft = await posting_service(session).build(
        document_type=document.document_type,
        total=total,
        description=document.description or document.document_no,
        lines=[
            DocumentLineInput(
                description=source_line.description or document.description or document.document_no,
                amount=source_line.line_amount or Decimal("0"),
                tax=source_line.tax_amount or Decimal("0"),
                fee_type_id=source_line.fee_type_id,
                account_id=source_line.account_id,
            )
            for source_line in document_lines
        ],
    )
    if len(draft.lines) < 2:
        raise ValidationFailed(
            "A journal needs at least two lines.",
            field_errors={"lines": "Add the document lines before posting."},
        )

    entry_no = await allocate_number(session, "JOURNAL")
    entry = JournalEntry(
        entry_no=entry_no,
        entry_type="AUTOMATIC",
        entry_date=posting_date,
        posting_date=posting_date,
        accounting_period_id=period.id,
        # Created as DRAFT, promoted to POSTED once its lines are attached. The
        # database guards lines of posted journals, and the audit say-so is that
        # a journal must exist as a draft before it is posted.
        status="DRAFT",
        description=f"Posting of {document.document_no}",
        source_document_id=document.id,
        # The rule that resolved the accounts. A real foreign key so "which
        # documents posted through this rule" is a join, not a JSON scan.
        posting_rule_id=draft.rule_id,
        created_by_user_id=context.user_id,
        posted_by_user_id=context.user_id,
        posted_at=datetime.now(UTC),
        # Which rule and which accounting shape produced this entry. Snapshotting
        # it here is what makes a posting explainable after the rule changes.
        data=draft.resolution,
    )
    session.add(entry)
    await session.flush()

    exchange_rate = document.exchange_rate or Decimal("1")
    # The stored converted amounts must agree with the journal this posting writes.
    # `save_document` already derives them from the same rate; recomputing here
    # also repairs a document written before these columns existed.
    precision = await currency_precision(session, document.currency_code)
    document.base_currency_code = document.base_currency_code or await get_default_currency(session)
    document.base_subtotal_amount = fx.convert_to_base(document.subtotal_amount or Decimal("0"), exchange_rate, precision)
    document.base_discount_amount = fx.convert_to_base(document.discount_amount or Decimal("0"), exchange_rate, precision)
    document.base_tax_amount = fx.convert_to_base(document.tax_amount or Decimal("0"), exchange_rate, precision)
    document.base_total_amount = fx.convert_to_base(document.total_amount or Decimal("0"), exchange_rate, precision)
    for line_no, draft_line in enumerate(draft.lines, start=1):
        session.add(
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_no=line_no,
                account_id=draft_line.account.id,
                party_id=document.party_id,
                service_order_id=document.service_order_id,
                financial_document_id=document.id,
                description=draft_line.description,
                debit_amount=draft_line.amount if draft_line.debit else Decimal("0"),
                credit_amount=Decimal("0") if draft_line.debit else draft_line.amount,
                currency_code=document.currency_code,
                exchange_rate=exchange_rate,
                base_debit_amount=draft_line.amount * exchange_rate if draft_line.debit else Decimal("0"),
                base_credit_amount=Decimal("0") if draft_line.debit else draft_line.amount * exchange_rate,
            )
        )

    # The lines must land while the header is still DRAFT. ``fn_guard_journal_line``
    # is an immediate trigger and rejects any line written to a POSTED entry, so
    # flipping the status in the same flush would fail: SQLAlchemy emits the
    # header UPDATE before the line INSERTs, and the trigger would see POSTED.
    await session.flush()

    # The draft is balanced by construction; re-checking here means a future
    # strategy cannot slip an unbalanced entry past the service boundary.
    draft.assert_balanced()
    entry.debit_total = draft.debit_total
    entry.credit_total = draft.credit_total
    entry.status = "POSTED"
    await session.flush()
    session.add(FinancialDocumentPosting(financial_document_id=document.id, journal_entry_id=entry.id))
    document.status = "POSTED"
    document.posted_by_user_id = context.user_id
    document.posted_at = datetime.now(UTC)
    await session.commit()
    await cache.bump("reports")
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


async def reverse_document(session: AsyncSession, context: RequestContext, document_id: int, reason: str) -> dict:
    document = (
        await session.execute(
            select(FinancialDocument).where(FinancialDocument.id == document_id).with_for_update()
        )
    ).scalars().first()
    if document is None:
        raise NotFound("Financial document not found.")
    if document.status == "REVERSED":
        raise Conflict("DOCUMENT_ALREADY_REVERSED", "This document is already reversed.")
    if document.status != "POSTED":
        raise InvalidState("Only posted documents can be reversed.")
    posting = (
        await session.execute(select(FinancialDocumentPosting).where(FinancialDocumentPosting.financial_document_id == document.id))
    ).scalars().first()
    if posting is None:
        raise NotFound("Original posting not found.")
    original_entry = await session.get(JournalEntry, posting.journal_entry_id)
    posting_date = date.today()
    period = await resolve_period(session, posting_date)
    if period.status == "CLOSED":
        raise Conflict("PERIOD_CLOSED", "The accounting period is closed.")
    entry_no = await allocate_number(session, "JOURNAL")
    reversal = JournalEntry(
        entry_no=entry_no,
        entry_type="REVERSAL",
        entry_date=posting_date,
        posting_date=posting_date,
        accounting_period_id=period.id,
        # DRAFT until its lines exist, for the same reason as post_document().
        status="DRAFT",
        description=f"Reversal of {original_entry.entry_no if original_entry else document.document_no}: {reason}",
        source_document_id=document.id,
        # A reversal mirrors an existing entry, so it carries that entry's rule:
        # the usage list must show both the posting and its reversal, or an
        # auditor would see a debit with the credit missing.
        posting_rule_id=original_entry.posting_rule_id if original_entry else None,
        reversal_of_journal_entry_id=original_entry.id if original_entry else None,
        created_by_user_id=context.user_id,
        posted_by_user_id=context.user_id,
        posted_at=datetime.now(UTC),
    )
    session.add(reversal)
    await session.flush()
    original_lines = (
        await session.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == original_entry.id))
    ).scalars().all()
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for index, line in enumerate(original_lines, start=1):
        debit_total += line.credit_amount
        credit_total += line.debit_amount
        session.add(
            JournalEntryLine(
                journal_entry_id=reversal.id,
                line_no=index,
                account_id=line.account_id,
                party_id=line.party_id,
                service_order_id=line.service_order_id,
                financial_document_id=document.id,
                description=f"Reversal: {line.description or ''}",
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                currency_code=line.currency_code,
                exchange_rate=line.exchange_rate,
                base_debit_amount=line.base_credit_amount,
                base_credit_amount=line.base_debit_amount,
            )
        )
    # Same ordering rule as post_document(): the mirrored lines must land while
    # the reversal header is still DRAFT, or fn_guard_journal_line rejects them.
    await session.flush()
    reversal.debit_total = debit_total
    reversal.credit_total = credit_total
    reversal.status = "POSTED"
    await session.flush()
    # Undo payment allocations so the subledger (paid_amount) matches the ledger.
    allocations = (
        await session.execute(
            select(FinancialDocumentAllocation).where(
                or_(
                    FinancialDocumentAllocation.payment_document_id == document.id,
                    FinancialDocumentAllocation.target_document_id == document.id,
                )
            )
        )
    ).scalars().all()
    for allocation in allocations:
        other_id = (
            allocation.target_document_id
            if allocation.payment_document_id == document.id
            else allocation.payment_document_id
        )
        other = await session.get(FinancialDocument, other_id)
        if other is not None:
            other.paid_amount = max(
                Decimal("0"), (other.paid_amount or Decimal("0")) - (allocation.allocated_amount or Decimal("0"))
            )
        await session.delete(allocation)
    document.paid_amount = Decimal("0")
    document.status = "REVERSED"
    await session.commit()
    await cache.bump("reports")
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


def _allocation_fx(
    amount: Decimal,
    payment_rate: Decimal | None,
    target_rate: Decimal | None,
    precision: int,
) -> tuple[Decimal, Decimal, Decimal]:
    """Base value of one allocated amount on each side, and their difference.

    A payment and the invoice it settles may have been booked at different rates,
    so the same allocated amount is worth a different base amount on each side.
    The difference is the exchange gain or loss the settlement realises: it is
    reported on the allocation, and posted separately when an ``EXCHANGE_DIFFERENCE``
    posting rule is configured. Nothing here re-values a posted document.
    """
    payment_base = fx.convert_to_base(amount, payment_rate or Decimal("1"), precision)
    target_base = fx.convert_to_base(amount, target_rate or Decimal("1"), precision)
    return payment_base, target_base, fx.quantize_money(payment_base - target_base, precision)


async def allocate_payment(
    session: AsyncSession,
    context: RequestContext,
    payment_id: int,
    data: dict[str, Any],
    idempotency_key: str | None = None,
) -> dict:
    if idempotency_key:
        existing = (
            await session.execute(
                select(FinancialDocumentAllocation).where(
                    FinancialDocumentAllocation.idempotency_key == idempotency_key
                )
            )
        ).scalars().first()
        if existing is not None:
            payment_doc = await session.get(FinancialDocument, existing.payment_document_id)
            target_doc = await session.get(FinancialDocument, existing.target_document_id)
            replay_precision = await currency_precision(
                session, existing.allocated_currency_code or (payment_doc.currency_code if payment_doc else None)
            )
            replay_payment_base, replay_target_base, replay_difference = _allocation_fx(
                existing.allocated_amount,
                existing.exchange_rate,
                target_doc.exchange_rate if target_doc else existing.exchange_rate,
                replay_precision,
            )
            return {
                "paymentDocumentId": str(existing.payment_document_id),
                "targetDocumentId": str(existing.target_document_id),
                "allocatedAmount": float(existing.allocated_amount),
                "paymentBaseAmount": float(replay_payment_base),
                "targetBaseAmount": float(replay_target_base),
                "exchangeDifference": float(replay_difference),
                "paymentBalance": float((payment_doc.total_amount or Decimal("0")) - (payment_doc.paid_amount or Decimal("0"))) if payment_doc else 0.0,
                "targetOutstanding": float((target_doc.total_amount or Decimal("0")) - (target_doc.paid_amount or Decimal("0"))) if target_doc else 0.0,
                "idempotentReplay": True,
            }
    payment = (
        await session.execute(select(FinancialDocument).where(FinancialDocument.id == payment_id).with_for_update())
    ).scalars().first()
    target_id = _int_or_none(data.get("target_document_id") or data.get("targetDocumentId"))
    amount = _decimal(data.get("amount") or data.get("allocated_amount"))
    if payment is None:
        raise NotFound("Payment document not found.")
    if target_id is None:
        raise ValidationFailed("Target document is required.")
    target = (
        await session.execute(select(FinancialDocument).where(FinancialDocument.id == target_id).with_for_update())
    ).scalars().first()
    if target is None:
        raise NotFound("Target document not found.")
    if payment.document_type not in PAYMENT_TYPES:
        raise ValidationFailed("Only payment or receipt documents can be allocated.")
    if target.document_type not in INVOICE_TYPES:
        raise ValidationFailed("Allocations must target an invoice or supplier bill.")
    if payment.status != "POSTED" or target.status != "POSTED":
        raise InvalidState("Both payment and target documents must be posted.")
    if payment.currency_code != target.currency_code:
        raise Conflict("CURRENCY_MISMATCH", "Payment and target currency must match.")
    if amount <= 0:
        raise ValidationFailed("Allocated amount must be greater than zero.")

    allocated_so_far = await session.scalar(
        select(func.coalesce(func.sum(FinancialDocumentAllocation.allocated_amount), 0)).where(
            FinancialDocumentAllocation.payment_document_id == payment.id
        )
    )
    available = (payment.total_amount or Decimal("0")) - Decimal(str(allocated_so_far or 0))
    if amount > available:
        raise Conflict("ALLOCATION_EXCEEDS_BALANCE", "Allocation exceeds the available payment balance.")
    outstanding = (target.total_amount or Decimal("0")) - (target.paid_amount or Decimal("0"))
    if amount > outstanding:
        raise Conflict("ALLOCATION_EXCEEDS_BALANCE", "Allocation exceeds the target outstanding balance.")

    session.add(
        FinancialDocumentAllocation(
            payment_document_id=payment.id,
            target_document_id=target.id,
            allocated_amount=amount,
            allocated_currency_code=payment.currency_code,
            exchange_rate=payment.exchange_rate,
            created_by_user_id=context.user_id,
            idempotency_key=idempotency_key,
        )
    )
    # Both sides of the settlement, valued in the base currency.
    allocation_precision = await currency_precision(session, payment.currency_code)
    payment_base_amount, target_base_amount, exchange_difference = _allocation_fx(
        amount, payment.exchange_rate, target.exchange_rate, allocation_precision
    )
    payment.paid_amount = (payment.paid_amount or Decimal("0")) + amount
    target.paid_amount = (target.paid_amount or Decimal("0")) + amount
    await session.commit()
    await cache.bump("reports")
    return {
        "paymentDocumentId": str(payment.id),
        "targetDocumentId": str(target.id),
        "allocatedAmount": float(amount),
        "paymentBaseAmount": float(payment_base_amount),
        "targetBaseAmount": float(target_base_amount),
        "exchangeDifference": float(exchange_difference),
        "paymentBalance": float((payment.total_amount or Decimal("0")) - (payment.paid_amount or Decimal("0"))),
        "targetOutstanding": float((target.total_amount or Decimal("0")) - (target.paid_amount or Decimal("0"))),
    }


async def create_invoice_from_charge(
    session: AsyncSession,
    context: RequestContext,
    charge: ServiceOrderCharge,
    *,
    commit: bool = True,
) -> dict:
    if charge.status != "ISSUED":
        raise InvalidState("Only an issued service charge can create a finance invoice.")
    existing = (
        await session.execute(
            select(FinancialDocumentSource).where(
                FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE", FinancialDocumentSource.source_id == charge.id
            )
        )
    ).scalars().first()
    if existing is not None:
        document = await session.get(FinancialDocument, existing.financial_document_id)
        if document is not None:
            return document_payload(document, document.data or {}, await _document_lines(session, document.id))
    order = await session.get(ServiceOrder, charge.service_order_id)
    number = await allocate_number(session, "CUSTOMER_INVOICE")
    # The charge keeps its currency and is never rewritten. The invoice resolves
    # its own approved rate for that currency at its own date: a rate that moves
    # after the charge exists changes the invoice, never the historical source.
    invoice_currency, invoice_rate, invoice_base, invoice_precision = await _document_currency_inputs(
        session,
        {},
        document_currency=str(charge.currency_code or await get_default_currency(session)),
        base_currency=await get_default_currency(session),
        on_date=date.today(),
    )
    document = FinancialDocument(
        document_no=number,
        document_type="CUSTOMER_INVOICE",
        document_date=date.today(),
        status="DRAFT",
        party_id=order.customer_party_id if order else None,
        service_order_id=charge.service_order_id,
        currency_code=invoice_currency,
        exchange_rate=invoice_rate,
        base_currency_code=invoice_base,
        description=f"Generated from service charge {charge.charge_no}",
        subtotal_amount=charge.subtotal_amount,
        discount_amount=charge.discount_amount,
        tax_amount=charge.tax_amount,
        total_amount=charge.total_amount,
        base_subtotal_amount=fx.convert_to_base(charge.subtotal_amount or Decimal("0"), invoice_rate, invoice_precision),
        base_discount_amount=fx.convert_to_base(charge.discount_amount or Decimal("0"), invoice_rate, invoice_precision),
        base_tax_amount=fx.convert_to_base(charge.tax_amount or Decimal("0"), invoice_rate, invoice_precision),
        base_total_amount=fx.convert_to_base(charge.total_amount or Decimal("0"), invoice_rate, invoice_precision),
        created_by_user_id=context.user_id,
        data={"sourceChargeNo": charge.charge_no},
    )
    session.add(document)
    await session.flush()
    charge_lines = (
        await session.execute(
            select(ServiceOrderChargeLine)
            .where(ServiceOrderChargeLine.service_order_charge_id == charge.id)
            .order_by(ServiceOrderChargeLine.line_no)
        )
    ).scalars().all()
    for line in charge_lines:
        session.add(
            FinancialDocumentLine(
                financial_document_id=document.id,
                line_no=line.line_no,
                description=line.description,
                fee_type_id=line.fee_type_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_amount=line.discount_amount,
                tax_rate=line.tax_rate,
                tax_amount=line.tax_amount,
                line_amount=line.line_amount,
                service_order_id=charge.service_order_id,
                service_order_container_id=line.service_order_container_id,
            )
        )
    session.add(
        FinancialDocumentSource(
            financial_document_id=document.id,
            source_type="SERVICE_ORDER_CHARGE",
            source_id=charge.id,
        )
    )
    if commit:
        await session.commit()
        await cache.bump("reports")
    else:
        await session.flush()
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


async def _service_order_invoice_documents(
    session: AsyncSession, order_id: int
) -> list[FinancialDocument]:
    """Every customer invoice generated for a service order, oldest first.

    Two link shapes exist and both must be followed. ``create_invoice_from_service_order``
    records one ``SERVICE_ORDER`` source for the order; ``create_invoice_from_charge``
    records only a ``SERVICE_ORDER_CHARGE`` source for the charge it was issued
    from. Looking for the order-level source alone returned ``None`` for every
    invoice created by issuing charges, so the endpoint reported "no invoice" for a
    document that existed and the create path raised a misleading
    "already invoiced" error.
    """
    order_level = (
        await session.execute(
            select(FinancialDocument)
            .join(
                FinancialDocumentSource,
                FinancialDocumentSource.financial_document_id == FinancialDocument.id,
            )
            .where(
                FinancialDocumentSource.source_type == "SERVICE_ORDER",
                FinancialDocumentSource.source_id == order_id,
                FinancialDocument.status != "REVERSED",
            )
            .order_by(FinancialDocument.id)
        )
    ).scalars().all()
    if order_level:
        return list(order_level)

    # source_id of a SERVICE_ORDER_CHARGE row is the charge id, so the join scopes
    # the lookup to this order's charges.
    charge_level = (
        await session.execute(
            select(FinancialDocument)
            .join(
                FinancialDocumentSource,
                FinancialDocumentSource.financial_document_id == FinancialDocument.id,
            )
            .join(ServiceOrderCharge, ServiceOrderCharge.id == FinancialDocumentSource.source_id)
            .where(
                FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE",
                ServiceOrderCharge.service_order_id == order_id,
                FinancialDocument.status != "REVERSED",
            )
            .order_by(FinancialDocument.id)
        )
    ).scalars().all()
    return list(charge_level)


async def get_service_order_invoice(session: AsyncSession, context: RequestContext, order_id: int) -> dict | None:
    """Return the customer invoice generated for a service order, if any.

    Returns the oldest when an order carries one invoice per issued charge, which is
    what the charge-issue workflow produces. The order-level invoice is preferred
    when it exists.
    """
    documents = await _service_order_invoice_documents(session, order_id)
    if not documents:
        return None
    document = documents[0]
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


async def create_invoice_from_service_order(session: AsyncSession, context: RequestContext, order: ServiceOrder) -> dict:
    """Create one invoice for a Service Order from all of its not-yet-invoiced charges.

    Idempotent per order: when the order already has a generated customer invoice
    (from either link shape — see ``_service_order_invoice_documents``) that
    document is returned instead of creating a second one.
    """
    default_currency = await get_default_currency(session)
    existing = await get_service_order_invoice(session, context, order.id)
    if existing is not None:
        return existing
    charges = (
        await session.execute(
            select(ServiceOrderCharge)
            .where(ServiceOrderCharge.service_order_id == order.id)
            .order_by(ServiceOrderCharge.id)
        )
    ).scalars().all()
    if not charges:
        raise ValidationFailed("No service charges to invoice.")
    charge_ids = [charge.id for charge in charges]
    invoiced_ids = set(
        (
            await session.execute(
                select(FinancialDocumentSource.source_id).where(
                    FinancialDocumentSource.source_type == "SERVICE_ORDER_CHARGE",
                    FinancialDocumentSource.source_id.in_(charge_ids),
                )
            )
        ).scalars().all()
    )
    pending = [charge for charge in charges if charge.id not in invoiced_ids]
    if not pending:
        raise ValidationFailed("All service charges for this order are already invoiced.")
    zero = Decimal("0")
    subtotal = sum((charge.subtotal_amount or zero for charge in pending), zero)
    discount = sum((charge.discount_amount or zero for charge in pending), zero)
    tax = sum((charge.tax_amount or zero for charge in pending), zero)
    total = sum((charge.total_amount or zero for charge in pending), zero)
    number = await allocate_number(session, "CUSTOMER_INVOICE")
    document = FinancialDocument(
        document_no=number,
        document_type="CUSTOMER_INVOICE",
        document_date=date.today(),
        status="DRAFT",
        party_id=order.customer_party_id,
        service_order_id=order.id,
        currency_code=order.currency_code or default_currency,
        description=f"Service order {order.service_order_no}",
        subtotal_amount=subtotal,
        discount_amount=discount,
        tax_amount=tax,
        total_amount=total,
        created_by_user_id=context.user_id,
        data={"sourceChargeNos": [charge.charge_no for charge in pending]},
    )
    session.add(document)
    await session.flush()
    line_no = 1
    for charge in pending:
        charge_lines = (
            await session.execute(
                select(ServiceOrderChargeLine)
                .where(ServiceOrderChargeLine.service_order_charge_id == charge.id)
                .order_by(ServiceOrderChargeLine.line_no)
            )
        ).scalars().all()
        for line in charge_lines:
            session.add(
                FinancialDocumentLine(
                    financial_document_id=document.id,
                    line_no=line_no,
                    description=line.description,
                    fee_type_id=line.fee_type_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_amount=line.discount_amount,
                    tax_rate=line.tax_rate,
                    tax_amount=line.tax_amount,
                    line_amount=line.line_amount,
                    service_order_id=order.id,
                    service_order_container_id=line.service_order_container_id,
                )
            )
            line_no += 1
        session.add(
            FinancialDocumentSource(
                financial_document_id=document.id,
                source_type="SERVICE_ORDER_CHARGE",
                source_id=charge.id,
            )
        )
    session.add(
        FinancialDocumentSource(
            financial_document_id=document.id,
            source_type="SERVICE_ORDER",
            source_id=order.id,
        )
    )
    await session.commit()
    await cache.bump("reports")
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


# --- Journals ----------------------------------------------------------------
async def _journal_lines(session: AsyncSession, journal_id: int) -> list[JournalEntryLine]:
    return list(
        (
            await session.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == journal_id).order_by(JournalEntryLine.line_no))
        ).scalars().all()
    )


async def journal_payload(session: AsyncSession, entry: JournalEntry) -> dict[str, Any]:
    lines = await _journal_lines(session, entry.id)
    source_no = None
    if entry.source_document_id:
        source = await session.get(FinancialDocument, entry.source_document_id)
        source_no = source.document_no if source else None
    return {
        "id": str(entry.id),
        "entryNo": entry.entry_no,
        "entryType": entry.entry_type,
        "entryDate": entry.entry_date.isoformat() if entry.entry_date else None,
        "postingDate": entry.posting_date.isoformat() if entry.posting_date else None,
        "periodId": str(entry.accounting_period_id) if entry.accounting_period_id else None,
        "sourceDocumentId": str(entry.source_document_id) if entry.source_document_id else None,
        "sourceDocumentNo": source_no,
        "status": entry.status,
        "description": entry.description,
        "debitTotal": float(entry.debit_total or 0),
        "creditTotal": float(entry.credit_total or 0),
        "balanceDifference": float((entry.debit_total or 0) - (entry.credit_total or 0)),
        "lines": [
            {
                "id": str(line.id),
                "account_id": line.account_id,
                "account_code": (
                    (await session.get(ChartOfAccount, line.account_id)).account_code
                    if line.account_id and (await session.get(ChartOfAccount, line.account_id))
                    else None
                ),
                "description": line.description,
                "party": str(line.party_id) if line.party_id else None,
                "serviceOrder": str(line.service_order_id) if line.service_order_id else None,
                "debit_amount": float(line.debit_amount or 0),
                "credit_amount": float(line.credit_amount or 0),
                "currency": line.currency_code,
            }
            for line in lines
        ],
    }


async def list_journals(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(JournalEntry)
    if page.status:
        stmt = stmt.where(JournalEntry.status == str(page.status).upper())
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(JournalEntry, page, JournalEntry.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    items = [await journal_payload(session, row) for row in rows]
    return paged(items, page, total)


async def get_journal(session: AsyncSession, context: RequestContext, journal_id: int) -> dict:
    entry = await session.get(JournalEntry, journal_id)
    if entry is None:
        raise NotFound("Journal entry not found.")
    return await journal_payload(session, entry)


async def save_journal(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    default_currency = await get_default_currency(session)
    journal_id = data.get("id")
    entry: JournalEntry | None = None
    if journal_id and str(journal_id).isdigit():
        entry = await session.get(JournalEntry, int(journal_id))
    entry_date = _date(data.get("entryDate")) or date.today()
    posting_date = _date(data.get("postingDate")) or entry_date
    period = await resolve_period(session, posting_date)
    lines = data.get("lines") or []
    if entry is None:
        number = data.get("entryNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, "JOURNAL")
        entry = JournalEntry(
            entry_no=str(number),
            entry_type=str(data.get("entryType") or "MANUAL").upper(),
            entry_date=entry_date,
            posting_date=posting_date,
            accounting_period_id=period.id,
            status="DRAFT",
            description=data.get("description"),
            created_by_user_id=context.user_id,
        )
        session.add(entry)
        await session.flush()
    else:
        if entry.status == "POSTED":
            raise InvalidState("Posted journals cannot be edited; reverse instead.")
        entry.entry_date = entry_date
        entry.posting_date = posting_date
        entry.accounting_period_id = period.id
        entry.description = data.get("description") or entry.description
    await session.execute(delete(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    # Validated once per distinct code, so a twenty-line journal in one currency
    # costs one lookup rather than twenty.
    validated_currencies: dict[str, str] = {}
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        account = None
        account_id = _int_or_none(line.get("account_id") or line.get("accountId"))
        if account_id is not None:
            account = await session.get(ChartOfAccount, account_id)
        if account is None:
            code = line.get("account_code") or line.get("accountCode")
            account = await _account_by_code(session, str(code)) if code else None
        if account is None:
            raise ValidationFailed(
                "Every journal line must reference a valid account.",
                {"lines": f"Line {index + 1} has an unknown account."},
            )
        _validate_posting_account(account, f"line {index + 1}")
        debit_amount = _decimal(line.get("debit_amount") or line.get("debitAmount"))
        credit_amount = _decimal(line.get("credit_amount") or line.get("creditAmount"))
        exchange_rate = _decimal(line.get("exchangeRate"), Decimal("1"))
        if debit_amount < 0 or credit_amount < 0:
            raise ValidationFailed(
                "Journal amounts cannot be negative.",
                {"lines": f"Line {index + 1} contains a negative amount."},
            )
        if (debit_amount > 0) == (credit_amount > 0):
            raise ValidationFailed(
                "Each journal line must contain either a debit or a credit.",
                {"lines": f"Line {index + 1} must have exactly one positive side."},
            )
        if exchange_rate <= 0:
            raise ValidationFailed(
                "Journal exchange rate must be greater than zero.",
                {"lines": f"Line {index + 1} has an invalid exchange rate."},
            )
        debit_total += debit_amount
        credit_total += credit_amount
        requested_currency = str(line.get("currency") or default_currency)
        if requested_currency not in validated_currencies:
            validated_currencies[requested_currency] = await assert_currency_code(session, requested_currency)
        line_currency = validated_currencies[requested_currency]
        session.add(
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_no=index + 1,
                account_id=account.id,
                party_id=_int_or_none(line.get("party")),
                service_order_id=_int_or_none(line.get("serviceOrder")),
                description=line.get("description"),
                debit_amount=debit_amount,
                credit_amount=credit_amount,
                currency_code=line_currency,
                exchange_rate=exchange_rate,
                base_debit_amount=debit_amount * exchange_rate,
                base_credit_amount=credit_amount * exchange_rate,
            )
        )
    entry.debit_total = debit_total
    entry.credit_total = credit_total
    entry.data = jsonable({key: value for key, value in data.items() if key not in {"id", "lines", "createdAt", "updatedAt"}})
    await session.commit()
    return await journal_payload(session, entry)


async def post_journal(session: AsyncSession, context: RequestContext, journal_id: int) -> dict:
    entry = (
        await session.execute(select(JournalEntry).where(JournalEntry.id == journal_id).with_for_update())
    ).scalars().first()
    if entry is None:
        raise NotFound("Journal entry not found.")
    if entry.status == "POSTED":
        return await journal_payload(session, entry)
    if entry.status != "DRAFT":
        raise InvalidState(f"Cannot post a journal in status {entry.status}.")
    lines = await _journal_lines(session, entry.id)
    if len(lines) < 2:
        raise ValidationFailed("A journal must have at least two lines before posting.")
    for index, line in enumerate(lines, start=1):
        if line.debit_amount < 0 or line.credit_amount < 0 or ((line.debit_amount > 0) == (line.credit_amount > 0)):
            raise ValidationFailed(
                "Every journal line must contain exactly one positive debit or credit.",
                {"lines": f"Line {index} is invalid."},
            )
    debit_total = sum((line.debit_amount or Decimal("0") for line in lines), Decimal("0"))
    credit_total = sum((line.credit_amount or Decimal("0") for line in lines), Decimal("0"))
    if debit_total != credit_total or debit_total == 0:
        raise Conflict("JOURNAL_UNBALANCED", "Total debit must equal total credit and be non-zero.")
    # ...and in the base currency, which a multi-currency entry can violate while
    # its own-currency sides cancel. Each line carries the base amount it was
    # converted to, so this sums what was stored rather than re-deriving it.
    base_debit_total = sum((line.base_debit_amount or Decimal("0") for line in lines), Decimal("0"))
    base_credit_total = sum((line.base_credit_amount or Decimal("0") for line in lines), Decimal("0"))
    if base_debit_total != base_credit_total:
        raise Conflict(
            "JOURNAL_UNBALANCED",
            "Total base-currency debit must equal total base-currency credit.",
        )
    period = await session.get(AccountingPeriod, entry.accounting_period_id) if entry.accounting_period_id else None
    if period is not None and period.status == "CLOSED":
        raise Conflict("PERIOD_CLOSED", "The accounting period is closed.")
    entry.status = "POSTED"
    entry.posted_at = datetime.now(UTC)
    entry.posted_by_user_id = context.user_id
    entry.debit_total = debit_total
    entry.credit_total = credit_total
    await session.commit()
    await cache.bump("reports")
    return await journal_payload(session, entry)


async def list_posting_rules(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(PostingRule)
    total = await count_query(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(*list_sort_orders(PostingRule, page, PostingRule.id))
            .limit(page.page_size)
            .offset(page.offset)
        )
    ).scalars().all()
    items = [await posting_rule_payload(session, rule) for rule in rows]
    return paged(items, page, total)


async def _posting_rule_data(session: AsyncSession, data: dict[str, Any], current: PostingRule | None = None) -> dict[str, Any]:
    """Validate one posting-rule payload and return the column values to write.

    Accounts are checked here rather than at posting time: a rule that points at
    a header or inactive account is a configuration mistake, and refusing it
    while the administrator is on the screen is worth far more than failing the
    first posting that hits it.
    """
    errors: dict[str, str] = {}
    document_type = str(data.get("documentType") or (current.document_type if current else "")).strip().upper()
    if not document_type:
        errors["documentType"] = "Select the document type this rule applies to."
    elif document_type not in KNOWN_DOCUMENT_TYPES:
        errors["documentType"] = "Unknown document type."

    status = str(data.get("status") or (current.status if current else "ACTIVE")).strip().upper()
    if status not in {"ACTIVE", "INACTIVE"}:
        errors["status"] = "Status must be ACTIVE or INACTIVE."

    fee_type_id = _int_or_none(data.get("feeTypeId", (current.fee_type_id if current else None)))

    debit, debit_error = await _rule_account(session, data, current, "debitAccount", "debit_account_id", "Debit")
    credit, credit_error = await _rule_account(session, data, current, "creditAccount", "credit_account_id", "Credit")
    tax, tax_error = await _rule_account(
        session, data, current, "taxAccount", "tax_account_id", "Tax", required=False
    )
    # Collect rather than raise on the first problem: an administrator filling a
    # new rule in should see every account that needs attention in one pass.
    for field, message in (("debitAccount", debit_error), ("creditAccount", credit_error), ("taxAccount", tax_error)):
        if message:
            errors[field] = message

    # A blank priority is an omitted optional field, not a malformed number: the
    # form sends "" when the administrator leaves it empty.
    priority = data.get("priority")
    if priority in (None, ""):
        priority_value = current.priority if current else 0
    else:
        try:
            priority_value = int(priority)
        except (TypeError, ValueError):
            errors["priority"] = "Priority must be a whole number."
            priority_value = 0
    if not errors.get("priority") and priority_value < 0:
        errors["priority"] = "Priority cannot be negative."

    if errors:
        raise ValidationFailed("Please correct the posting rule.", field_errors=errors)
    assert debit is not None and credit is not None  # guaranteed by the errors above

    values: dict[str, Any] = {
        "document_type": document_type,
        "fee_type_id": fee_type_id,
        "debit_account_id": debit.id,
        "credit_account_id": credit.id,
        "tax_account_id": tax.id if tax else None,
        "status": status,
        "priority": priority_value,
        "description": (str(data["description"]).strip() if data.get("description") is not None
                        else (current.description if current else None)) or None,
    }
    if debit.id == credit.id:
        raise ValidationFailed(
            "Please correct the posting rule.",
            field_errors={"creditAccount": "The credit account must differ from the debit account."},
        )
    await _assert_unique_priority(session, values, exclude_id=current.id if current else None)
    return values


async def _rule_account(
    session: AsyncSession,
    data: dict[str, Any],
    current: PostingRule | None,
    field: str,
    column: str,
    label: str,
    *,
    required: bool = True,
) -> tuple[ChartOfAccount | None, str | None]:
    """Resolve one account reference, keeping an existing value when omitted.

    Returns ``(account, error)`` rather than raising, so the caller can report
    every unusable account at once.
    """
    if field not in data and current is not None:
        account_id = getattr(current, column)
        return (await session.get(ChartOfAccount, account_id) if account_id else None), None
    value = data.get(field)
    if value in (None, ""):
        return None, f"Select the {label.lower()} account." if required else None
    account = await _resolve_account_ref(session, value)
    if account is None:
        return None, "That account is not in the chart of accounts."
    try:
        return validate_postable(account, label.lower(), field), None
    except ValidationFailed as failure:
        messages = list((failure.field_errors or {}).values())
        return None, messages[0] if messages else failure.message


async def _assert_unique_priority(
    session: AsyncSession,
    values: dict[str, Any],
    *,
    exclude_id: int | None = None,
) -> None:
    """One active rule per (document type, fee type, priority).

    Several active rules may target one scope - that is what ``priority`` is for -
    but two of them may not share a priority, because the resolver would then have
    no defensible winner. The partial unique index added in revision
    ``f8a9b0c1d2e3`` enforces exactly this in the database; this check exists to
    turn the violation into a 409 with a field-level message the UI can render
    instead of a driver error.
    """
    if values["status"] != POSTING_RULE_ACTIVE:
        return
    fee_filter = (
        PostingRule.fee_type_id == values["fee_type_id"]
        if values["fee_type_id"] is not None
        else PostingRule.fee_type_id.is_(None)
    )
    stmt = select(PostingRule).where(
        PostingRule.document_type == values["document_type"],
        fee_filter,
        PostingRule.priority == values["priority"],
        PostingRule.status == POSTING_RULE_ACTIVE,
    )
    if exclude_id is not None:
        stmt = stmt.where(PostingRule.id != exclude_id)
    duplicate = (await session.execute(stmt)).scalars().first()
    if duplicate is not None:
        raise _duplicate_priority(values)


async def _flush_rule(session: AsyncSession, values: dict[str, Any]) -> None:
    """Flush a rule write, reporting a lost priority race as a 409.

    ``_assert_unique_priority`` is a read-then-write, so two concurrent requests
    can both pass it. The partial unique index is the authority; this turns the
    driver's IntegrityError into the same field-level conflict the service check
    raises, so a race is a legible refusal rather than a 500.
    """
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if "uq_posting_rules_active_priority" not in str(exc.orig):
            raise
        raise _duplicate_priority(values) from exc


def _duplicate_priority(values: dict[str, Any]) -> Conflict:
    field = "feeTypeId" if values["fee_type_id"] is not None else "documentType"
    return Conflict(
        "DUPLICATE_POSTING_RULE",
        "An active posting rule already uses this document, fee type and priority.",
        field_errors={
            field: "Deactivate the existing rule, or give this one a different priority.",
            "priority": f"Priority {values['priority']} is already taken for this scope.",
        },
    )


async def create_posting_rule(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    values = await _posting_rule_data(session, data)
    rule = PostingRule(**values)
    session.add(rule)
    await _flush_rule(session, values)
    return await posting_rule_payload(session, rule)


# --- Single-record reads and deletes (generic module CRUD contract) ----------
async def get_account(session: AsyncSession, context: RequestContext, account_id: int) -> dict:
    account = await session.get(ChartOfAccount, account_id)
    if account is None:
        raise NotFound("Account not found.")
    parent = await session.get(ChartOfAccount, account.parent_account_id) if account.parent_account_id else None
    return account_payload(account, parent.account_code if parent else None)


async def delete_accounts(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    """Delete ledger accounts that are neither active nor referenced.

    A chart-of-accounts row is referenced by journal lines, financial-account
    mappings, posting rules and document lines. Removing one would leave posted
    history without its account, so the guards refuse it instead.
    """
    for account_id in ids:
        account = await session.get(ChartOfAccount, account_id)
        if account is None:
            continue
        await deletion.require_inactive(account.status, label="chart of accounts record")
        await deletion.ensure_deletable(
            session,
            account,
            label=f"Account {account.account_code}",
            detail="Deactivate it instead, or reverse and reassign the postings that use it.",
        )
        await session.delete(account)
    await session.commit()


async def get_financial_account(session: AsyncSession, context: RequestContext, account_id: int) -> dict:
    account = await session.get(FinancialAccount, account_id)
    if account is None:
        raise NotFound("Financial account not found.")
    return await financial_account_payload(session, account)


async def update_financial_account(session: AsyncSession, context: RequestContext, account_id: int, data: dict[str, Any]) -> dict:
    account = await session.get(FinancialAccount, account_id)
    if account is None:
        raise NotFound("Financial account not found.")
    if data.get("ledgerCode") is not None:
        ledger = await _account_by_code(session, str(data["ledgerCode"]))
        if ledger is None:
            raise ValidationFailed("Ledger account not found.", {"ledgerCode": "Unknown account"})
        account.account_id = ledger.id
    for key, column in (
        ("accountName", "account_name"),
        ("bankName", "bank_name"),
        ("accountNumberMasked", "account_number_masked"),
    ):
        if data.get(key) is not None:
            setattr(account, column, data[key])
    if data.get("accountType") is not None:
        account.account_type = str(data["accountType"]).upper()
    if data.get("currency") is not None:
        account.currency_code = str(data["currency"])
    if data.get("status") is not None:
        account.status = str(data["status"]).upper()
    await session.commit()
    return await financial_account_payload(session, account)


async def delete_financial_accounts(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    """Delete cash/bank accounts that are neither active nor referenced.

    A financial account is referenced by payments and receipts, so deleting one
    would orphan settled cash movements.
    """
    for account_id in ids:
        account = await session.get(FinancialAccount, account_id)
        if account is None:
            continue
        await deletion.require_inactive(account.status, label="financial account")
        await deletion.ensure_deletable(
            session,
            account,
            label=f"Financial account {account.account_name}",
            detail="Deactivate it instead so historical payments keep resolving.",
        )
        await session.delete(account)
    await session.commit()


async def get_period(session: AsyncSession, context: RequestContext, period_id: int) -> dict:
    period = await session.get(AccountingPeriod, period_id)
    if period is None:
        raise NotFound("Accounting period not found.")
    return period_payload(period)


async def get_sequence(session: AsyncSession, context: RequestContext, sequence_id: int) -> dict:
    sequence = await session.get(DocumentSequence, sequence_id)
    if sequence is None:
        raise NotFound("Document sequence not found.")
    return sequence_payload(sequence)


async def posting_rule_payload(session: AsyncSession, rule: PostingRule) -> dict:
    """Full rule representation used by the list, the detail read and writes."""
    debit = await session.get(ChartOfAccount, rule.debit_account_id)
    credit = await session.get(ChartOfAccount, rule.credit_account_id)
    tax = await session.get(ChartOfAccount, rule.tax_account_id) if rule.tax_account_id else None
    fee_type = await session.get(FeeType, rule.fee_type_id) if rule.fee_type_id else None
    return {
        "id": str(rule.id),
        "documentType": rule.document_type,
        "documentTypeLabel": DOCUMENT_TYPE_LABELS.get(rule.document_type, rule.document_type),
        "feeTypeId": str(rule.fee_type_id) if rule.fee_type_id else None,
        "feeType": fee_type.name if fee_type else None,
        "debitAccount": debit.account_code if debit else None,
        "creditAccount": credit.account_code if credit else None,
        "taxAccount": tax.account_code if tax else None,
        "priority": rule.priority,
        "description": rule.description,
        "status": rule.status,
        "createdAt": rule.created_at,
        "updatedAt": rule.updated_at,
    }


async def get_posting_rule(session: AsyncSession, context: RequestContext, rule_id: int) -> dict:
    rule = await session.get(PostingRule, rule_id)
    if rule is None:
        raise NotFound("Posting rule not found.")
    return await posting_rule_payload(session, rule)


async def update_posting_rule(session: AsyncSession, context: RequestContext, rule_id: int, data: dict[str, Any]) -> dict:
    """Change a rule's accounts, scope, priority or status.

    Only the rule changes: posted journals already carry their own account ids and
    amounts, so editing the mapping cannot retroactively rewrite history. New
    postings pick up the new accounts; the reversal path stays available for
    anything already posted.
    """
    rule = await session.get(PostingRule, rule_id)
    if rule is None:
        raise NotFound("Posting rule not found.")
    values = await _posting_rule_data(session, data, current=rule)
    for key, value in values.items():
        setattr(rule, key, value)
    await _flush_rule(session, values)
    return await posting_rule_payload(session, rule)


async def delete_posting_rules(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    """Delete posting rules that are neither active nor referenced.

    Deleting the rule a document type resolves through would make the next posting
    fall back to the code default, silently changing which accounts are used.
    Deactivate the rule instead.
    """
    for rule_id in ids:
        rule = await session.get(PostingRule, rule_id)
        if rule is None:
            continue
        await deletion.require_inactive(rule.status, label="posting rule")
        await deletion.ensure_deletable(
            session,
            rule,
            label=f"Posting rule {rule.document_type}",
            detail="Deactivate it instead so historical postings keep their mapping.",
        )
        await session.delete(rule)
    await session.commit()


async def delete_journals(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    for journal_id in ids:
        entry = await session.get(JournalEntry, journal_id)
        if entry is None:
            continue
        if entry.status == "POSTED":
            raise InvalidState("Posted journals cannot be deleted; reverse instead.")
        await session.execute(delete(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))
        await session.delete(entry)
    await session.commit()

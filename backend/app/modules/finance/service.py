from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from app.core.pagination import PageParams, count_query, paged
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
from app.modules.operations.models import ServiceOrder, ServiceOrderCharge, ServiceOrderChargeLine

DEFAULT_ACCOUNTS: dict[str, tuple[str, str]] = {
    "CUSTOMER_INVOICE": ("1100", "4010"),
    "SUPPLIER_BILL": ("5010", "2010"),
    "CUSTOMER_RECEIPT": ("1020", "1100"),
    "SUPPLIER_PAYMENT": ("2010", "1020"),
    "OTHER_INCOME": ("1020", "4020"),
    "OTHER_EXPENSE": ("5030", "1020"),
    "TRANSFER": ("1020", "1010"),
    "ADJUSTMENT": ("5030", "1020"),
}
PAYMENT_TYPES = {"CUSTOMER_RECEIPT", "SUPPLIER_PAYMENT"}
INVOICE_TYPES = {"CUSTOMER_INVOICE", "SUPPLIER_BILL"}


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
    stmt = select(ChartOfAccount).where(ChartOfAccount.organization_id == context.organization_id)
    if page.q:
        pattern = f"%{page.q}%"
        stmt = stmt.where(ChartOfAccount.account_code.ilike(pattern) | ChartOfAccount.account_name.ilike(pattern))
    if page.status:
        stmt = stmt.where(ChartOfAccount.status == str(page.status).upper())
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(ChartOfAccount.account_code).limit(page.page_size).offset(page.offset))).scalars().all()
    codes = {row.id: row.account_code for row in rows}
    items = [account_payload(row, codes.get(row.parent_account_id)) for row in rows]
    return paged(items, page, total)


async def create_account(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    account = ChartOfAccount(
        organization_id=context.organization_id,
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
    if account is None or account.organization_id != context.organization_id:
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
    stmt = select(FinancialAccount).where(FinancialAccount.organization_id == context.organization_id)
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(FinancialAccount.id).limit(page.page_size).offset(page.offset))).scalars().all()
    items = [await financial_account_payload(session, row) for row in rows]
    return paged(items, page, total)


async def create_financial_account(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    ledger_code = data.get("ledgerCode")
    ledger = (
        await session.execute(
            select(ChartOfAccount).where(
                ChartOfAccount.organization_id == context.organization_id, ChartOfAccount.account_code == ledger_code
            )
        )
    ).scalars().first()
    if ledger is None:
        raise ValidationFailed("Ledger account not found.", {"ledgerCode": "Unknown account"})
    account = FinancialAccount(
        organization_id=context.organization_id,
        account_id=ledger.id,
        account_name=str(data.get("accountName") or ledger.account_name),
        account_type=str(data.get("accountType") or "Bank").upper(),
        currency_code=str(data.get("currency") or "USD"),
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


async def list_periods(session: AsyncSession, context: RequestContext) -> list[dict]:
    rows = (
        await session.execute(
            select(AccountingPeriod)
            .where(AccountingPeriod.organization_id == context.organization_id)
            .order_by(AccountingPeriod.period_year.desc(), AccountingPeriod.period_month.desc())
        )
    ).scalars().all()
    return [period_payload(row) for row in rows]


async def resolve_period(session: AsyncSession, organization_id: int, posting_date: date) -> AccountingPeriod:
    period = (
        await session.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.organization_id == organization_id,
                AccountingPeriod.start_date <= posting_date,
                AccountingPeriod.end_date >= posting_date,
            )
        )
    ).scalars().first()
    if period is None:
        period = AccountingPeriod(
            organization_id=organization_id,
            period_year=posting_date.year,
            period_month=posting_date.month,
            start_date=posting_date.replace(day=1),
            end_date=posting_date,
            status="OPEN",
        )
        session.add(period)
        await session.flush()
    return period


async def update_period(session: AsyncSession, context: RequestContext, period_id: int, data: dict[str, Any]) -> dict:
    period = await session.get(AccountingPeriod, period_id)
    if period is None or period.organization_id != context.organization_id:
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
    if period is None or period.organization_id != context.organization_id:
        raise NotFound("Accounting period not found.")
    period.status = "CLOSED"
    period.closed_at = datetime.now(UTC)
    period.closed_by_user_id = context.user_id
    await session.commit()
    return period_payload(period)


def sequence_payload(sequence: DocumentSequence, organization_name: str | None = None) -> dict[str, Any]:
    preview = f"{sequence.prefix}{sequence.period_year}-{str(sequence.last_value + 1).zfill(sequence.padding_length)}"
    return {
        "id": str(sequence.id),
        "documentType": sequence.document_type,
        "year": sequence.period_year,
        "prefix": sequence.prefix,
        "lastValue": sequence.last_value,
        "paddingLength": sequence.padding_length,
        "nextNumberPreview": preview,
        "organizationName": organization_name,
        "status": sequence.status.capitalize() if sequence.status.isupper() else sequence.status,
    }


async def list_sequences(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(DocumentSequence).where(DocumentSequence.organization_id == context.organization_id)
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(DocumentSequence.id).limit(page.page_size).offset(page.offset))).scalars().all()
    return paged([sequence_payload(row, context.organization_name) for row in rows], page, total)


async def upsert_sequence(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    year = int(data.get("year") or datetime.now(UTC).year)
    document_type = str(data.get("documentType") or "").upper()
    sequence = (
        await session.execute(
            select(DocumentSequence).where(
                DocumentSequence.organization_id == context.organization_id,
                DocumentSequence.document_type == document_type,
                DocumentSequence.period_year == year,
            )
        )
    ).scalars().first()
    if sequence is None:
        sequence = DocumentSequence(
            organization_id=context.organization_id,
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
    return sequence_payload(sequence, context.organization_name)


# --- Financial documents -----------------------------------------------------
def document_payload(document: FinancialDocument, data: dict[str, Any], lines: list[FinancialDocumentLine] | None = None) -> dict[str, Any]:
    payload = dict(data or {})
    payload.update(
        {
            "id": str(document.id),
            "documentNo": document.document_no,
            "debitNoteNo": document.document_no,
            "documentType": document.document_type,
            "documentDate": document.document_date.isoformat() if document.document_date else None,
            "postingDate": document.posting_date.isoformat() if document.posting_date else None,
            "dueDate": document.due_date.isoformat() if document.due_date else None,
            "status": document.status.capitalize() if document.status.isupper() else document.status,
            "rawStatus": document.status,
            "currency": document.currency_code,
            "exchangeRate": float(document.exchange_rate or 1),
            "subtotal": float(document.subtotal_amount or 0),
            "discount": float(document.discount_amount or 0),
            "tax": float(document.tax_amount or 0),
            "total": float(document.total_amount or 0),
            "amount": float(document.total_amount or 0),
            "paidAmount": float(document.paid_amount or 0),
            "balance": float((document.total_amount or 0) - (document.paid_amount or 0)),
            "partyId": document.party_id,
            "serviceOrderId": str(document.service_order_id) if document.service_order_id else None,
            "orgId": document.organization_id,
            "branchId": document.branch_id,
            "referenceNumber": document.reference_number,
            "createdAt": document.created_at.isoformat() if document.created_at else None,
        }
    )
    if lines is not None:
        payload["lines"] = [_line_payload(line) for line in lines]
    return payload


def _line_payload(line: FinancialDocumentLine) -> dict[str, Any]:
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
        "serviceOrderId": str(line.service_order_id) if line.service_order_id else None,
    }


async def _document_lines(session: AsyncSession, document_id: int) -> list[FinancialDocumentLine]:
    return list(
        (
            await session.execute(
                select(FinancialDocumentLine)
                .where(FinancialDocumentLine.financial_document_id == document_id)
                .order_by(FinancialDocumentLine.line_no)
            )
        ).scalars().all()
    )


async def list_documents(session: AsyncSession, context: RequestContext, page: PageParams, document_type: str | None = None) -> dict:
    stmt = select(FinancialDocument).where(FinancialDocument.organization_id == context.organization_id)
    if not context.can_select_all_branches and context.branch_id is not None:
        stmt = stmt.where(FinancialDocument.branch_id == context.branch_id)
    if document_type:
        stmt = stmt.where(FinancialDocument.document_type == document_type)
    if page.status:
        stmt = stmt.where(FinancialDocument.status == str(page.status).upper())
    if page.q:
        pattern = f"%{page.q}%"
        stmt = stmt.where(
            FinancialDocument.document_no.ilike(pattern) | FinancialDocument.description.ilike(pattern)
        )
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(FinancialDocument.id.desc()).limit(page.page_size).offset(page.offset))).scalars().all()
    return paged([document_payload(row, row.data or {}, await _document_lines(session, row.id)) for row in rows], page, total)


async def get_document(session: AsyncSession, context: RequestContext, document_id: int) -> dict:
    document = await session.get(FinancialDocument, document_id)
    if document is None or document.organization_id != context.organization_id:
        raise NotFound("Financial document not found.")
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


async def save_document(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    document_type = str(data.get("documentType") or data.get("document_type") or "CUSTOMER_INVOICE").upper()
    document_id = data.get("id")
    document: FinancialDocument | None = None
    if document_id and str(document_id).isdigit():
        document = await session.get(FinancialDocument, int(document_id))
        if document is not None and document.organization_id != context.organization_id:
            document = None
    lines = data.get("lines") or []
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")
    if document is None:
        number = data.get("documentNo") or data.get("debitNoteNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, context.organization_id, document_type)
        document = FinancialDocument(
            organization_id=context.organization_id,
            branch_id=int(data.get("branchId") or context.branch_id or 0) or context.branch_id,
            document_no=str(number),
            document_type=document_type,
            document_date=_date(data.get("documentDate")) or date.today(),
            status="DRAFT",
            party_id=_int_or_none(data.get("partyId")),
            service_order_id=_int_or_none(data.get("serviceOrderId")),
            currency_code=str(data.get("currency") or "USD"),
            exchange_rate=_decimal(data.get("exchangeRate"), Decimal("1")),
            description=data.get("description"),
            reference_number=data.get("referenceNumber"),
            due_date=_date(data.get("dueDate")),
            financial_account_id=_int_or_none(data.get("financialAccountId")),
            created_by_user_id=context.user_id,
            data={},
        )
        session.add(document)
        await session.flush()
    else:
        if document.status not in {"DRAFT"}:
            raise InvalidState("Only draft documents can be edited; posted documents require a reversal.")
        document.status = "DRAFT"
        document.document_date = _date(data.get("documentDate")) or document.document_date
        for key, column in (("partyId", "party_id"), ("serviceOrderId", "service_order_id"), ("description", "description"), ("referenceNumber", "reference_number"), ("dueDate", "due_date")):
            if data.get(key) is not None:
                setattr(document, column, _int_or_none(data[key]) if key.endswith("Id") else (_date(data[key]) if key == "dueDate" else data[key]))

    await session.execute(delete(FinancialDocumentLine).where(FinancialDocumentLine.financial_document_id == document.id))
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
                fee_type_id=_int_or_none(line.get("feeTypeId")),
                quantity=quantity,
                unit_price=unit_price,
                discount_amount=discount,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                line_amount=amount,
                service_order_id=_int_or_none(line.get("serviceOrderId")),
                service_order_container_id=_int_or_none(line.get("serviceOrderContainerId")),
                account_id=_int_or_none(line.get("accountId")),
            )
        )
    document.subtotal_amount = subtotal
    document.discount_amount = discount_total
    document.tax_amount = tax_total
    document.total_amount = subtotal - discount_total + tax_total
    document.data = jsonable({key: value for key, value in data.items() if key not in {"id", "lines", "createdAt", "updatedAt"}})
    await session.commit()
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- Posting engine ----------------------------------------------------------
async def _account_by_code(session: AsyncSession, organization_id: int, code: str) -> ChartOfAccount | None:
    return (
        await session.execute(
            select(ChartOfAccount).where(
                ChartOfAccount.organization_id == organization_id, ChartOfAccount.account_code == code
            )
        )
    ).scalars().first()


async def _resolve_rule(session: AsyncSession, organization_id: int, document_type: str) -> tuple[ChartOfAccount | None, ChartOfAccount | None, ChartOfAccount | None]:
    rule = (
        await session.execute(
            select(PostingRule).where(
                PostingRule.organization_id == organization_id,
                PostingRule.document_type == document_type,
                PostingRule.fee_type_id.is_(None),
                PostingRule.status == "ACTIVE",
            )
        )
    ).scalars().first()
    debit = await session.get(ChartOfAccount, rule.debit_account_id) if rule else None
    credit = await session.get(ChartOfAccount, rule.credit_account_id) if rule else None
    tax = await session.get(ChartOfAccount, rule.tax_account_id) if rule and rule.tax_account_id else None
    if debit is None or credit is None:
        codes = DEFAULT_ACCOUNTS.get(document_type, ("1100", "4010"))
        debit = debit or await _account_by_code(session, organization_id, codes[0])
        credit = credit or await _account_by_code(session, organization_id, codes[1])
    return debit, credit, tax


async def post_document(session: AsyncSession, context: RequestContext, document_id: int) -> dict:
    document = (
        await session.execute(select(FinancialDocument).where(FinancialDocument.id == document_id).with_for_update())
    ).scalars().first()
    if document is None or document.organization_id != context.organization_id:
        raise NotFound("Financial document not found.")
    if document.status == "POSTED":
        return document_payload(document, document.data or {}, await _document_lines(session, document.id))
    if document.status != "DRAFT":
        raise InvalidState(f"Cannot post a document in status {document.status}.")

    posting_date = document.posting_date or document.document_date or date.today()
    document.posting_date = posting_date
    period = await resolve_period(session, document.organization_id, posting_date)
    if period.status == "CLOSED":
        raise Conflict("PERIOD_CLOSED", "The accounting period is closed.")

    debit_account, credit_account, tax_account = await _resolve_rule(session, document.organization_id, document.document_type)
    if debit_account is None or credit_account is None:
        raise ValidationFailed("No posting rule or default account could be resolved.")
    if not debit_account.is_postable or not credit_account.is_postable:
        raise ValidationFailed("Posting accounts must be postable.")

    total = document.total_amount or Decimal("0")
    if total <= 0:
        raise ValidationFailed("Document total must be greater than zero before posting.")

    entry_no = await allocate_number(session, document.organization_id, "JOURNAL")
    entry = JournalEntry(
        organization_id=document.organization_id,
        branch_id=document.branch_id,
        entry_no=entry_no,
        entry_type="AUTOMATIC",
        entry_date=posting_date,
        posting_date=posting_date,
        accounting_period_id=period.id,
        status="POSTED",
        description=f"Posting of {document.document_no}",
        source_document_id=document.id,
        created_by_user_id=context.user_id,
        posted_by_user_id=context.user_id,
        posted_at=datetime.now(UTC),
    )
    session.add(entry)
    await session.flush()

    lines: list[JournalEntryLine] = []
    tax_amount = document.tax_amount or Decimal("0")
    net_amount = total - tax_amount
    lines.append(
        JournalEntryLine(
            journal_entry_id=entry.id,
            line_no=1,
            account_id=debit_account.id,
            party_id=document.party_id,
            service_order_id=document.service_order_id,
            financial_document_id=document.id,
            branch_id=document.branch_id,
            description=document.description or document.document_no,
            debit_amount=total,
            credit_amount=Decimal("0"),
            currency_code=document.currency_code,
            exchange_rate=document.exchange_rate,
            base_debit_amount=total * (document.exchange_rate or Decimal("1")),
            base_credit_amount=Decimal("0"),
        )
    )
    credit_lines = []
    if tax_amount > 0 and tax_account is not None:
        credit_lines.append((credit_account, net_amount))
        credit_lines.append((tax_account, tax_amount))
    else:
        credit_lines.append((credit_account, total))
    for index, (account, amount) in enumerate(credit_lines, start=2):
        lines.append(
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_no=index,
                account_id=account.id,
                party_id=document.party_id,
                service_order_id=document.service_order_id,
                financial_document_id=document.id,
                branch_id=document.branch_id,
                description=document.description or document.document_no,
                debit_amount=Decimal("0"),
                credit_amount=amount,
                currency_code=document.currency_code,
                exchange_rate=document.exchange_rate,
                base_debit_amount=Decimal("0"),
                base_credit_amount=amount * (document.exchange_rate or Decimal("1")),
            )
        )
    for line in lines:
        session.add(line)
    total_debit = sum((line.debit_amount for line in lines), Decimal("0"))
    total_credit = sum((line.credit_amount for line in lines), Decimal("0"))
    if total_debit != total_credit:
        raise Conflict("JOURNAL_UNBALANCED", "The generated journal is not balanced.")
    entry.debit_total = total_debit
    entry.credit_total = total_credit
    session.add(FinancialDocumentPosting(financial_document_id=document.id, journal_entry_id=entry.id))
    document.status = "POSTED"
    document.posted_by_user_id = context.user_id
    document.posted_at = datetime.now(UTC)
    await session.commit()
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


async def reverse_document(session: AsyncSession, context: RequestContext, document_id: int, reason: str) -> dict:
    document = await session.get(FinancialDocument, document_id)
    if document is None or document.organization_id != context.organization_id:
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
    period = await resolve_period(session, document.organization_id, posting_date)
    if period.status == "CLOSED":
        raise Conflict("PERIOD_CLOSED", "The accounting period is closed.")
    entry_no = await allocate_number(session, document.organization_id, "JOURNAL")
    reversal = JournalEntry(
        organization_id=document.organization_id,
        branch_id=document.branch_id,
        entry_no=entry_no,
        entry_type="REVERSAL",
        entry_date=posting_date,
        posting_date=posting_date,
        accounting_period_id=period.id,
        status="POSTED",
        description=f"Reversal of {original_entry.entry_no if original_entry else document.document_no}: {reason}",
        source_document_id=document.id,
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
                branch_id=line.branch_id,
                description=f"Reversal: {line.description or ''}",
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                currency_code=line.currency_code,
                exchange_rate=line.exchange_rate,
                base_debit_amount=line.base_credit_amount,
                base_credit_amount=line.base_debit_amount,
            )
        )
    reversal.debit_total = debit_total
    reversal.credit_total = credit_total
    document.status = "REVERSED"
    await session.commit()
    return document_payload(document, document.data or {}, await _document_lines(session, document.id))


async def allocate_payment(session: AsyncSession, context: RequestContext, payment_id: int, data: dict[str, Any]) -> dict:
    payment = (
        await session.execute(select(FinancialDocument).where(FinancialDocument.id == payment_id).with_for_update())
    ).scalars().first()
    target_id = _int_or_none(data.get("target_document_id") or data.get("targetDocumentId"))
    amount = _decimal(data.get("amount") or data.get("allocated_amount"))
    if payment is None or payment.organization_id != context.organization_id:
        raise NotFound("Payment document not found.")
    if target_id is None:
        raise ValidationFailed("Target document is required.")
    target = (
        await session.execute(select(FinancialDocument).where(FinancialDocument.id == target_id).with_for_update())
    ).scalars().first()
    if target is None or target.organization_id != context.organization_id:
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
        )
    )
    payment.paid_amount = (payment.paid_amount or Decimal("0")) + amount
    target.paid_amount = (target.paid_amount or Decimal("0")) + amount
    await session.commit()
    return {
        "paymentDocumentId": str(payment.id),
        "targetDocumentId": str(target.id),
        "allocatedAmount": float(amount),
        "paymentBalance": float((payment.total_amount or Decimal("0")) - (payment.paid_amount or Decimal("0"))),
        "targetOutstanding": float((target.total_amount or Decimal("0")) - (target.paid_amount or Decimal("0"))),
    }


async def create_invoice_from_charge(session: AsyncSession, context: RequestContext, charge: ServiceOrderCharge) -> dict:
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
    number = await allocate_number(session, context.organization_id, "CUSTOMER_INVOICE")
    document = FinancialDocument(
        organization_id=context.organization_id,
        branch_id=charge.branch_id,
        document_no=number,
        document_type="CUSTOMER_INVOICE",
        document_date=date.today(),
        status="DRAFT",
        party_id=order.customer_party_id if order else None,
        service_order_id=charge.service_order_id,
        currency_code=charge.currency_code,
        description=f"Generated from service charge {charge.charge_no}",
        subtotal_amount=charge.subtotal_amount,
        discount_amount=charge.discount_amount,
        tax_amount=charge.tax_amount,
        total_amount=charge.total_amount,
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
    await session.commit()
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
        "branchName": None,
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
    stmt = select(JournalEntry).where(JournalEntry.organization_id == context.organization_id)
    if page.status:
        stmt = stmt.where(JournalEntry.status == str(page.status).upper())
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(JournalEntry.id.desc()).limit(page.page_size).offset(page.offset))).scalars().all()
    items = [await journal_payload(session, row) for row in rows]
    return paged(items, page, total)


async def get_journal(session: AsyncSession, context: RequestContext, journal_id: int) -> dict:
    entry = await session.get(JournalEntry, journal_id)
    if entry is None or entry.organization_id != context.organization_id:
        raise NotFound("Journal entry not found.")
    return await journal_payload(session, entry)


async def save_journal(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    journal_id = data.get("id")
    entry: JournalEntry | None = None
    if journal_id and str(journal_id).isdigit():
        entry = await session.get(JournalEntry, int(journal_id))
        if entry is not None and entry.organization_id != context.organization_id:
            entry = None
    entry_date = _date(data.get("entryDate")) or date.today()
    posting_date = _date(data.get("postingDate")) or entry_date
    period = await resolve_period(session, context.organization_id, posting_date)
    lines = data.get("lines") or []
    if entry is None:
        number = data.get("entryNo")
        if not number or not str(number).strip():
            number = await allocate_number(session, context.organization_id, "JOURNAL")
        entry = JournalEntry(
            organization_id=context.organization_id,
            branch_id=int(data.get("branchId") or context.branch_id or 0) or context.branch_id,
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
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        account_id = _int_or_none(line.get("account_id") or line.get("accountId"))
        if account_id is None:
            code = line.get("account_code") or line.get("accountCode")
            account = await _account_by_code(session, context.organization_id, str(code)) if code else None
            account_id = account.id if account else None
        debit_amount = _decimal(line.get("debit_amount") or line.get("debitAmount"))
        credit_amount = _decimal(line.get("credit_amount") or line.get("creditAmount"))
        debit_total += debit_amount
        credit_total += credit_amount
        session.add(
            JournalEntryLine(
                journal_entry_id=entry.id,
                line_no=index + 1,
                account_id=int(account_id or 1),
                party_id=_int_or_none(line.get("party")),
                service_order_id=_int_or_none(line.get("serviceOrder")),
                branch_id=entry.branch_id,
                description=line.get("description"),
                debit_amount=debit_amount,
                credit_amount=credit_amount,
                currency_code=str(line.get("currency") or "USD"),
                exchange_rate=_decimal(line.get("exchangeRate"), Decimal("1")),
                base_debit_amount=debit_amount,
                base_credit_amount=credit_amount,
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
    if entry is None or entry.organization_id != context.organization_id:
        raise NotFound("Journal entry not found.")
    if entry.status == "POSTED":
        return await journal_payload(session, entry)
    if entry.status != "DRAFT":
        raise InvalidState(f"Cannot post a journal in status {entry.status}.")
    lines = await _journal_lines(session, entry.id)
    debit_total = sum((line.debit_amount or Decimal("0") for line in lines), Decimal("0"))
    credit_total = sum((line.credit_amount or Decimal("0") for line in lines), Decimal("0"))
    if debit_total != credit_total or debit_total == 0:
        raise Conflict("JOURNAL_UNBALANCED", "Total debit must equal total credit and be non-zero.")
    period = await session.get(AccountingPeriod, entry.accounting_period_id) if entry.accounting_period_id else None
    if period is not None and period.status == "CLOSED":
        raise Conflict("PERIOD_CLOSED", "The accounting period is closed.")
    entry.status = "POSTED"
    entry.posted_at = datetime.now(UTC)
    entry.posted_by_user_id = context.user_id
    entry.debit_total = debit_total
    entry.credit_total = credit_total
    await session.commit()
    return await journal_payload(session, entry)


async def list_posting_rules(session: AsyncSession, context: RequestContext, page: PageParams) -> dict:
    stmt = select(PostingRule).where(PostingRule.organization_id == context.organization_id)
    total = await count_query(session, stmt)
    rows = (await session.execute(stmt.order_by(PostingRule.id).limit(page.page_size).offset(page.offset))).scalars().all()
    items = []
    for rule in rows:
        debit = await session.get(ChartOfAccount, rule.debit_account_id)
        credit = await session.get(ChartOfAccount, rule.credit_account_id)
        tax = await session.get(ChartOfAccount, rule.tax_account_id) if rule.tax_account_id else None
        items.append(
            {
                "id": str(rule.id),
                "documentType": rule.document_type,
                "feeType": str(rule.fee_type_id) if rule.fee_type_id else None,
                "debitAccount": debit.account_code if debit else None,
                "creditAccount": credit.account_code if credit else None,
                "taxAccount": tax.account_code if tax else None,
                "status": rule.status,
            }
        )
    return paged(items, page, total)


async def create_posting_rule(session: AsyncSession, context: RequestContext, data: dict[str, Any]) -> dict:
    debit = await _account_by_code(session, context.organization_id, str(data.get("debitAccount")))
    credit = await _account_by_code(session, context.organization_id, str(data.get("creditAccount")))
    if debit is None or credit is None:
        raise ValidationFailed("Debit and credit accounts must exist.")
    rule = PostingRule(
        organization_id=context.organization_id,
        document_type=str(data.get("documentType") or "CUSTOMER_INVOICE").upper(),
        debit_account_id=debit.id,
        credit_account_id=credit.id,
        tax_account_id=_int_or_none(data.get("taxAccount")),
        status=str(data.get("status") or "ACTIVE").upper(),
    )
    session.add(rule)
    await session.commit()
    return {"id": str(rule.id), "documentType": rule.document_type, "debitAccount": debit.account_code, "creditAccount": credit.account_code}


# --- Single-record reads and deletes (generic module CRUD contract) ----------
async def get_account(session: AsyncSession, context: RequestContext, account_id: int) -> dict:
    account = await session.get(ChartOfAccount, account_id)
    if account is None or account.organization_id != context.organization_id:
        raise NotFound("Account not found.")
    parent = await session.get(ChartOfAccount, account.parent_account_id) if account.parent_account_id else None
    return account_payload(account, parent.account_code if parent else None)


async def delete_accounts(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    for account_id in ids:
        account = await session.get(ChartOfAccount, account_id)
        if account is not None and account.organization_id == context.organization_id:
            await session.delete(account)
    await session.commit()


async def get_financial_account(session: AsyncSession, context: RequestContext, account_id: int) -> dict:
    account = await session.get(FinancialAccount, account_id)
    if account is None or account.organization_id != context.organization_id:
        raise NotFound("Financial account not found.")
    return await financial_account_payload(session, account)


async def update_financial_account(session: AsyncSession, context: RequestContext, account_id: int, data: dict[str, Any]) -> dict:
    account = await session.get(FinancialAccount, account_id)
    if account is None or account.organization_id != context.organization_id:
        raise NotFound("Financial account not found.")
    if data.get("ledgerCode") is not None:
        ledger = await _account_by_code(session, context.organization_id, str(data["ledgerCode"]))
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
    for account_id in ids:
        account = await session.get(FinancialAccount, account_id)
        if account is not None and account.organization_id == context.organization_id:
            await session.delete(account)
    await session.commit()


async def get_period(session: AsyncSession, context: RequestContext, period_id: int) -> dict:
    period = await session.get(AccountingPeriod, period_id)
    if period is None or period.organization_id != context.organization_id:
        raise NotFound("Accounting period not found.")
    return period_payload(period)


async def get_sequence(session: AsyncSession, context: RequestContext, sequence_id: int) -> dict:
    sequence = await session.get(DocumentSequence, sequence_id)
    if sequence is None or sequence.organization_id != context.organization_id:
        raise NotFound("Document sequence not found.")
    return sequence_payload(sequence, context.organization_name)


async def posting_rule_payload(session: AsyncSession, rule: PostingRule) -> dict:
    debit = await session.get(ChartOfAccount, rule.debit_account_id)
    credit = await session.get(ChartOfAccount, rule.credit_account_id)
    tax = await session.get(ChartOfAccount, rule.tax_account_id) if rule.tax_account_id else None
    return {
        "id": str(rule.id),
        "documentType": rule.document_type,
        "feeType": str(rule.fee_type_id) if rule.fee_type_id else None,
        "debitAccount": debit.account_code if debit else None,
        "creditAccount": credit.account_code if credit else None,
        "taxAccount": tax.account_code if tax else None,
        "status": rule.status,
    }


async def get_posting_rule(session: AsyncSession, context: RequestContext, rule_id: int) -> dict:
    rule = await session.get(PostingRule, rule_id)
    if rule is None or rule.organization_id != context.organization_id:
        raise NotFound("Posting rule not found.")
    return await posting_rule_payload(session, rule)


async def update_posting_rule(session: AsyncSession, context: RequestContext, rule_id: int, data: dict[str, Any]) -> dict:
    rule = await session.get(PostingRule, rule_id)
    if rule is None or rule.organization_id != context.organization_id:
        raise NotFound("Posting rule not found.")
    if data.get("documentType") is not None:
        rule.document_type = str(data["documentType"]).upper()
    if data.get("status") is not None:
        rule.status = str(data["status"]).upper()
    if data.get("debitAccount") is not None:
        debit = await _account_by_code(session, context.organization_id, str(data["debitAccount"]))
        if debit is None:
            raise ValidationFailed("Debit account must exist.")
        rule.debit_account_id = debit.id
    if data.get("creditAccount") is not None:
        credit = await _account_by_code(session, context.organization_id, str(data["creditAccount"]))
        if credit is None:
            raise ValidationFailed("Credit account must exist.")
        rule.credit_account_id = credit.id
    if "taxAccount" in data:
        rule.tax_account_id = _int_or_none(data.get("taxAccount"))
    await session.commit()
    return await posting_rule_payload(session, rule)


async def delete_posting_rules(session: AsyncSession, context: RequestContext, ids: list[int]) -> None:
    for rule_id in ids:
        rule = await session.get(PostingRule, rule_id)
        if rule is not None and rule.organization_id == context.organization_id:
            await session.delete(rule)
    await session.commit()

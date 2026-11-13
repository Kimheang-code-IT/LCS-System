"""Posted financial projections with explicit cutoff, currency and reconciliation.

The existing ledger projection owns posting semantics. This module only reads
those facts; it never posts balancing adjustments or invents cash-flow mappings.
"""
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailed
from app.modules.finance.models import FinancialDocument, FinancialDocumentAllocation, JournalEntry
from app.modules.master_data.models import BusinessParty
from app.modules.operations.models import ServiceOrder
from app.modules.reports.repository import ReportRepository
from app.modules.settings.service import get_default_currency

ZERO = Decimal("0")


def decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def json_numbers(value):
    """The report contract exposes amounts as JSON numbers.

    All arithmetic above this boundary stays ``Decimal``; converting only the
    finished projection avoids float drift inside sums and reconciliations.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_numbers(item) for item in value]
    return value


async def financial_statement(session: AsyncSession, key: str, filters: dict) -> dict:
    start, end = filters.get("fromDate"), filters.get("toDate") or date.today()
    if start and start > end:
        raise ValidationFailed("The report date range is invalid.", {"toDate": "Cannot precede the from date."})
    base = await get_default_currency(session)
    repository = ReportRepository(session)
    stmt = repository._posted_ledger_statement().where(JournalEntry.posting_date <= end)
    currencies = filters.get("currencies") or []
    parties = filters.get("parties") or []
    all_rows = [dict(row) for row in (await session.execute(stmt.order_by(
        JournalEntry.posting_date, JournalEntry.id
    ))).mappings()]
    rows = [row for row in all_rows if (not currencies or row["currency_code"] in currencies)
        and (not parties or str(row["party_name"] or "") in parties)]
    period_rows = [row for row in rows if not start or row["posting_date"] >= start]
    result = {"items": [], "groups": [], "totals": {}, "meta": {
        "generatedAt": datetime.now(UTC).isoformat(), "baseCurrency": base,
        "basis": "POSTED journals; amounts in base currency", "warnings": [],
        "currencies": sorted({row["currency_code"] for row in all_rows}),
        "parties": sorted({str(row["party_name"]) for row in all_rows if row["party_name"]}),
        "fromDate": start.isoformat() if start else None, "toDate": end.isoformat(),
    }}
    if key in {"accounts-receivable", "accounts-payable"}:
        return await _subledger(session, key, filters, rows, result, end)
    if key == "cash-flow":
        cash_rows = [row for row in rows if row["financial_account_id"]]
        opening = sum((decimal(row["base_debit_amount"])-decimal(row["base_credit_amount"])
            for row in cash_rows if start and row["posting_date"] < start), ZERO)
        closing = sum((decimal(row["base_debit_amount"])-decimal(row["base_credit_amount"]) for row in cash_rows), ZERO)
        # Exclude both legs only for wholly cash-to-cash journals. Mixed journals
        # retain their real gross external movements and net cash effect.
        journal_rows = defaultdict(list)
        for row in rows:
            journal_rows[row["journal_id"]].append(row)
        transfers = {jid for jid, lines in journal_rows.items()
            if all(line["financial_account_id"] for line in lines)
            and sum((decimal(line["base_debit_amount"])-decimal(line["base_credit_amount"]) for line in lines), ZERO) == ZERO}
        inflow = outflow = ZERO
        running = opening
        for row in cash_rows:
            if (start and row["posting_date"] < start) or row["journal_id"] in transfers:
                continue
            debit, credit = decimal(row["base_debit_amount"]), decimal(row["base_credit_amount"])
            inflow += debit
            outflow += credit
            running += debit-credit
            result["items"].append(_ledger_row(row, base) | {"cashIn": debit, "cashOut": credit, "runningBalance": running})
        result["totals"] = {"openingCash": opening, "inflow": inflow, "outflow": outflow,
            "net": inflow-outflow, "closingCash": closing, "difference": opening+inflow-outflow-closing}
        result["meta"]["warnings"] = ["Operating, investing and financing classifications are not configured. Cash movements are shown without invented classifications."]
        result["meta"]["classificationSupported"] = False
        return result
    scoped = rows if key == "balance-sheet" else period_rows
    amounts = defaultdict(lambda: ZERO)
    account_rows = {}
    for row in scoped:
        account_rows[row["account_id"]] = row
        net = decimal(row["base_debit_amount"])-decimal(row["base_credit_amount"])
        amounts[row["account_id"]] += -net if row["account_type"].upper() in {"REVENUE", "LIABILITY", "EQUITY"} else net
    kinds = ["ASSET", "LIABILITY", "EQUITY"] if key == "balance-sheet" else ["REVENUE", "EXPENSE"]
    totals = {kind: sum((amount for account_id, amount in amounts.items()
        if account_rows[account_id]["account_type"].upper() == kind), ZERO)
        for kind in {"ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"}}
    earnings = totals["REVENUE"]-totals["EXPENSE"]
    for kind in kinds:
        items = [{"name": f"{row['account_code']} · {row['account_name']}", "amount": amounts[account_id]}
            for account_id, row in account_rows.items() if row["account_type"].upper() == kind]
        if kind == "EQUITY":
            items.append({"name": "Unclosed earnings through cutoff", "amount": earnings})
        result["groups"].append({"type": kind.capitalize(), "rows": items,
            "total": totals[kind]+(earnings if kind == "EQUITY" else ZERO)})
    if key == "balance-sheet":
        difference = totals["ASSET"]-totals["LIABILITY"]-totals["EQUITY"]-earnings
        result["totals"] = {"assets": totals["ASSET"], "liabilities": totals["LIABILITY"],
            "equity": totals["EQUITY"], "unclosedEarnings": earnings, "difference": difference}
    else:
        result["totals"] = {"revenue": totals["REVENUE"], "expense": totals["EXPENSE"], "net": earnings}
        if key == "revenue-expense":
            result["items"] = [_ledger_row(row, base) | {
                "revenue": decimal(row["base_credit_amount"])-decimal(row["base_debit_amount"]) if row["account_type"].upper() == "REVENUE" else ZERO,
                "expense": decimal(row["base_debit_amount"])-decimal(row["base_credit_amount"]) if row["account_type"].upper() == "EXPENSE" else ZERO,
                "type": "Revenue" if row["account_type"].upper() == "REVENUE" else "Expense",
                "amount": (decimal(row["base_credit_amount"])-decimal(row["base_debit_amount"]))
                    if row["account_type"].upper() == "REVENUE" else (decimal(row["base_debit_amount"])-decimal(row["base_credit_amount"])),
            } for row in scoped if row["account_type"].upper() in {"REVENUE", "EXPENSE"}]
    return result


def _aging_bucket(days_overdue: int, outstanding: Decimal) -> str:
    """Aging category for an open balance; settled rows have no bucket."""
    if outstanding <= 0:
        return ""
    if days_overdue <= 0:
        return "Current"
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def _ledger_row(row: dict, base: str) -> dict:
    return {"id": str(row["id"]), "postingDate": row["posting_date"],
        "journalId": str(row["journal_id"]), "journalNo": row["entry_no"],
        "sourceDocumentId": str(row["source_document_id"] or ""), "sourceDocument": row["source_document_no"],
        "accountCode": row["account_code"], "accountName": row["account_name"],
        "account": f"{row['account_code']} · {row['account_name']}", "accountType": row["account_type"].capitalize(),
        "description": row["description"], "party": row["party_name"] or "", "jobNo": row["service_order_no"] or "",
        "currency": base, "amountCurrency": base, "documentCurrency": row["currency_code"],
        "debit": decimal(row["base_debit_amount"]), "credit": decimal(row["base_credit_amount"])}


async def _subledger(session, key, filters, ledger, result, cutoff):
    customer = key == "accounts-receivable"
    invoice_type = "CUSTOMER_INVOICE" if customer else "SUPPLIER_BILL"
    credit_type = "CREDIT_NOTE" if customer else "SUPPLIER_CREDIT_NOTE"
    payment_type = "CUSTOMER_RECEIPT" if customer else "SUPPLIER_PAYMENT"
    reversed_ids = set((await session.scalars(select(JournalEntry.source_document_id).where(
        JournalEntry.entry_type == "REVERSAL", JournalEntry.status == "POSTED", JournalEntry.posting_date <= cutoff
    ))).all())
    stmt = select(FinancialDocument, BusinessParty.display_name, ServiceOrder.service_order_no).outerjoin(
        BusinessParty, BusinessParty.id == FinancialDocument.party_id
    ).outerjoin(ServiceOrder, ServiceOrder.id == FinancialDocument.service_order_id).where(
        FinancialDocument.document_type.in_([invoice_type, credit_type, payment_type]),
        FinancialDocument.status.in_(["POSTED", "REVERSED"]),
        func.coalesce(FinancialDocument.posting_date, FinancialDocument.document_date) <= cutoff,
    )
    allocations = (await session.scalars(select(FinancialDocumentAllocation).where(
        func.date(FinancialDocumentAllocation.allocated_at) <= cutoff,
        or_(FinancialDocumentAllocation.reversed_at.is_(None), func.date(FinancialDocumentAllocation.reversed_at) > cutoff),
    ))).all()
    paid = defaultdict(lambda: ZERO)
    used = defaultdict(lambda: ZERO)
    for allocation in allocations:
        paid[allocation.target_document_id] += allocation.target_amount
        used[allocation.payment_document_id] += allocation.allocated_amount
    by_currency = defaultdict(lambda: ZERO)
    base_outstanding = ZERO
    for doc, party, job in (await session.execute(stmt)).all():
        if doc.id in reversed_ids or (filters.get("currencies") and doc.currency_code not in filters["currencies"]) or (filters.get("parties") and str(party or "") not in filters["parties"]):
            continue
        is_invoice = doc.document_type == invoice_type
        allocated = paid[doc.id] if is_invoice else used[doc.id] if doc.document_type == payment_type else ZERO
        balance = (doc.total_amount-allocated) * (1 if is_invoice else -1)
        by_currency[doc.currency_code] += balance
        base_balance = balance*(doc.exchange_rate or Decimal("1"))
        base_outstanding += base_balance
        days = (cutoff-doc.due_date).days if doc.due_date else 0
        result["items"].append({"id": str(doc.id), "documentNo": doc.document_no, "invoiceNo": doc.document_no,
            "billNo": doc.document_no, "documentType": doc.document_type, "partyId": str(doc.party_id or ""),
            "customer": party or "", "supplier": party or "", "jobNo": job or "",
            "postingDate": doc.posting_date, "invoiceDate": doc.document_date, "billDate": doc.document_date,
            "dueDate": doc.due_date, "currency": doc.currency_code, "total": doc.total_amount,
            "paid": allocated, "balance": balance, "outstanding": balance, "baseOutstanding": base_balance,
            "aging": f"{days}d" if days > 0 and balance > 0 else "",
            "agingDays": max(days, 0) if balance > 0 else 0,
            "agingBucket": _aging_bucket(days, balance),
            "status": "PAID" if balance == 0 else "OPEN"})
    # Resolve actual control accounts from posted source sides, not a hardcoded
    # chart code. Manual postings on these accounts remain visible differences.
    source_types = dict((await session.execute(select(FinancialDocument.id, FinancialDocument.document_type))).all())
    controls = set()
    for row in ledger:
        kind = source_types.get(row["source_document_id"])
        if row["entry_type"] == "REVERSAL":
            continue
        control_debit = (customer and kind == invoice_type) or (not customer and kind in {credit_type, payment_type})
        control_credit = (customer and kind in {credit_type, payment_type}) or (not customer and kind == invoice_type)
        if (control_debit and decimal(row["base_debit_amount"]) > 0) or (control_credit and decimal(row["base_credit_amount"]) > 0):
            controls.add(row["account_id"])
    control = sum(((decimal(row["base_debit_amount"])-decimal(row["base_credit_amount"]))*(1 if customer else -1)
        for row in ledger if row["account_id"] in controls), ZERO)
    difference = base_outstanding-control
    result["totals"] = {"baseOutstanding": base_outstanding, "controlBalance": control,
        "difference": difference, "perCurrency": dict(by_currency)}
    if difference:
        result["meta"]["warnings"].append("Subledger/control discrepancy: inspect manual control postings, historical data and unposted exchange differences; no balancing adjustment was applied.")
    result["meta"]["basis"] = "Posted documents and retained allocations effective at cutoff; original currencies shown separately"
    return result

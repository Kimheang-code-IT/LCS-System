from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.config import settings
from app.core.context import RequestContext
from app.modules.finance.models import ChartOfAccount, FinancialDocument, JournalEntry, JournalEntryLine
from app.modules.master_data.models import BusinessParty
from app.modules.operations.models import ServiceOrder
from app.modules.quotations.models import Quotation
from app.modules.reports.repository import ReportRepository


def _f(value: Any) -> float:
    return float(value or 0)


def _cache_scope(context: RequestContext) -> str:
    """Authorization scope fingerprint.

    Reports expose no per-row scoping today (every caller holding
    ``report.read`` sees identical aggregates), so the scope marker keeps the
    keys explicit without fragmenting the cache per role.
    """
    return "admin" if context.is_platform_admin else "standard"


async def receivables(session: AsyncSession, context: RequestContext) -> list[dict]:
    cache_parts = ("receivables", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    from datetime import date as _date
    today = _date.today().isoformat()
    stmt = (
        select(FinancialDocument, BusinessParty.display_name, ServiceOrder.service_order_no)
        .outerjoin(BusinessParty, BusinessParty.id == FinancialDocument.party_id)
        .outerjoin(ServiceOrder, ServiceOrder.id == FinancialDocument.service_order_id)
        .where(
            FinancialDocument.document_type == "CUSTOMER_INVOICE",
            FinancialDocument.status == "POSTED",
        )
    )
    rows = (await session.execute(stmt)).all()
    items = []
    for row, party_name, service_order_no in rows:
        outstanding = (row.total_amount or Decimal("0")) - (row.paid_amount or Decimal("0"))
        due = row.due_date.isoformat() if row.due_date else None
        doc_date = row.document_date.isoformat() if row.document_date else None
        aging_days = None
        if due and doc_date:
            try:
                aging_days = (_date.fromisoformat(today) - _date.fromisoformat(due)).days
            except ValueError:
                aging_days = None
        items.append(
            {
                "id": str(row.id),
                "documentNo": row.document_no,
                "invoiceNo": row.document_no,
                "partyId": row.party_id,
                "customer": party_name or "",
                "jobNo": service_order_no or "",
                "documentDate": doc_date,
                "invoiceDate": doc_date,
                "dueDate": due,
                "currency": row.currency_code,
                "total": _f(row.total_amount),
                "paid": _f(row.paid_amount),
                "balance": _f(outstanding),
                "outstanding": _f(outstanding),
                "aging": f"{aging_days}d" if aging_days is not None and aging_days > 0 else "",
                "status": "PAID" if outstanding <= 0 else ("PARTIAL" if row.paid_amount else "OPEN"),
            }
        )
    await cache.set_json(
        "reports", *cache_parts, value=items, ttl_seconds=settings.cache_ttl_report_seconds
    )
    return items


async def payables(session: AsyncSession, context: RequestContext) -> list[dict]:
    cache_parts = ("payables", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    from datetime import date as _date
    today = _date.today().isoformat()
    stmt = (
        select(FinancialDocument, BusinessParty.display_name, ServiceOrder.service_order_no)
        .outerjoin(BusinessParty, BusinessParty.id == FinancialDocument.party_id)
        .outerjoin(ServiceOrder, ServiceOrder.id == FinancialDocument.service_order_id)
        .where(
            FinancialDocument.document_type == "SUPPLIER_BILL",
            FinancialDocument.status == "POSTED",
        )
    )
    rows = (await session.execute(stmt)).all()
    items = []
    for row, party_name, service_order_no in rows:
        outstanding = (row.total_amount or Decimal("0")) - (row.paid_amount or Decimal("0"))
        due = row.due_date.isoformat() if row.due_date else None
        doc_date = row.document_date.isoformat() if row.document_date else None
        aging_days = None
        if due and doc_date:
            try:
                aging_days = (_date.fromisoformat(today) - _date.fromisoformat(due)).days
            except ValueError:
                aging_days = None
        items.append(
            {
                "id": str(row.id),
                "documentNo": row.document_no,
                "invoiceNo": row.document_no,
                "partyId": row.party_id,
                "supplier": party_name or "",
                "jobNo": service_order_no or "",
                "documentDate": doc_date,
                "billDate": doc_date,
                "dueDate": due,
                "currency": row.currency_code,
                "total": _f(row.total_amount),
                "paid": _f(row.paid_amount),
                "balance": _f(outstanding),
                "outstanding": _f(outstanding),
                "aging": f"{aging_days}d" if aging_days is not None and aging_days > 0 else "",
                "status": "PAID" if outstanding <= 0 else ("PARTIAL" if row.paid_amount else "OPEN"),
            }
        )
    await cache.set_json(
        "reports", *cache_parts, value=items, ttl_seconds=settings.cache_ttl_report_seconds
    )
    return items


async def _account_type_totals(session: AsyncSession, context: RequestContext, account_type: str) -> list[dict]:
    stmt = (
        select(
            ChartOfAccount.account_code,
            ChartOfAccount.account_name,
            func.coalesce(func.sum(JournalEntryLine.base_debit_amount), 0),
            func.coalesce(func.sum(JournalEntryLine.base_credit_amount), 0),
        )
        .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            ChartOfAccount.account_type == account_type,
            JournalEntry.status == "POSTED",
        )
    )
    rows = (await session.execute(
        stmt.group_by(ChartOfAccount.account_code, ChartOfAccount.account_name)
        .order_by(ChartOfAccount.account_code)
    )).all()
    result = []
    for code, name, debit, credit in rows:
        if account_type in {"REVENUE", "LIABILITY", "EQUITY"}:
            amount = Decimal(str(credit)) - Decimal(str(debit))
        else:
            amount = Decimal(str(debit)) - Decimal(str(credit))
        result.append({"accountCode": code, "accountName": name, "amount": _f(amount), "debit": _f(debit), "credit": _f(credit)})
    return result


async def income(session: AsyncSession, context: RequestContext) -> list[dict]:
    cache_parts = ("income", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    result = await _account_type_totals(session, context, "REVENUE")
    await cache.set_json("reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds)
    return result


async def expenses(session: AsyncSession, context: RequestContext) -> list[dict]:
    cache_parts = ("expenses", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    result = await _account_type_totals(session, context, "EXPENSE")
    await cache.set_json("reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds)
    return result


async def profitability(session: AsyncSession, context: RequestContext) -> list[dict]:
    cache_parts = ("profitability", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    rows = await ReportRepository(session).service_order_finance_rows()
    items = []
    for row in rows:
        revenue = Decimal(str(row["posted_revenue"] or 0))
        cost = Decimal(str(row["posted_cost"] or 0))
        issued_charges = Decimal(str(row["issued_charges"] or 0))
        draft_revenue = Decimal(str(row["draft_revenue"] or 0))
        profit = revenue - cost
        uninvoiced = max(Decimal("0"), issued_charges - revenue - draft_revenue)
        items.append(
            {
                "id": str(row["id"]),
                "jobNo": row["service_order_no"],
                "serviceOrderNo": row["service_order_no"],
                "customer": row["customer_name"] or "",
                "status": row["status"],
                "currency": row["currency_code"],
                "date": row["created_at"].date().isoformat() if row["created_at"] else None,
                "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
                "quoted": _f(row["quoted"]),
                "serviceCharges": _f(issued_charges),
                "draftServiceCharges": _f(row["draft_charges"]),
                "chargeCount": int(row["charge_count"] or 0),
                "draftRevenue": _f(draft_revenue),
                "uninvoicedCharges": _f(uninvoiced),
                "revenue": _f(revenue),
                "postedRevenue": _f(revenue),
                "cost": _f(cost),
                "postedCost": _f(cost),
                "totalCost": _f(cost),
                "profit": _f(profit),
                "grossProfit": _f(profit),
                "margin": _f(profit / revenue * 100) if revenue else 0.0,
            }
        )
    await cache.set_json(
        "reports", *cache_parts, value=items, ttl_seconds=settings.cache_ttl_report_seconds
    )
    return items


async def ledger_lines(session: AsyncSession, context: RequestContext) -> list[dict]:
    cache_parts = ("ledger-lines", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    rows = await ReportRepository(session).posted_ledger_rows()
    balances: dict[str, Decimal] = {}
    items: list[dict] = []
    for row in rows:
        debit = Decimal(str(row["base_debit_amount"] or 0))
        credit = Decimal(str(row["base_credit_amount"] or 0))
        account_code = str(row["account_code"])
        balances[account_code] = balances.get(account_code, Decimal("0")) + debit - credit
        items.append(
            {
                "id": str(row["id"]),
                "postingDate": row["posting_date"].isoformat() if row["posting_date"] else None,
                "journalNo": row["entry_no"],
                "sourceDocument": row["source_document_no"],
                "accountCode": account_code,
                "account": f"{account_code} · {row['account_name']}",
                "accountName": row["account_name"],
                "accountType": str(row["account_type"]).capitalize(),
                "description": row["description"] or row["journal_description"],
                "partyId": row["party_id"],
                "party": row["party_name"] or "",
                "serviceOrderId": row["service_order_id"],
                "jobNo": row["service_order_no"] or "",
                "currency": row["currency_code"],
                "debit": _f(debit),
                "credit": _f(credit),
                "runningBalance": _f(balances[account_code]),
                "isCashAccount": row["financial_account_id"] is not None,
            }
        )
    await cache.set_json("reports", *cache_parts, value=items, ttl_seconds=settings.cache_ttl_report_seconds)
    return items


async def quotation_performance(session: AsyncSession, context: RequestContext) -> dict:
    total = await session.scalar(select(func.count()).select_from(Quotation))
    rows = (
        await session.execute(
            select(Quotation.status, func.count()).group_by(Quotation.status)
        )
    ).all()
    return {"total": int(total or 0), "byStatus": {status: int(count) for status, count in rows}}


async def service_order_report(session: AsyncSession, context: RequestContext) -> dict:
    total = await session.scalar(select(func.count()).select_from(ServiceOrder))
    rows = (
        await session.execute(
            select(ServiceOrder.status, func.count()).group_by(ServiceOrder.status)
        )
    ).all()
    return {"total": int(total or 0), "byStatus": {status: int(count) for status, count in rows}}


async def financial_summary(session: AsyncSession, context: RequestContext) -> dict:
    cache_parts = ("financial-summary", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    assets = await _account_type_totals(session, context, "ASSET")
    liabilities = await _account_type_totals(session, context, "LIABILITY")
    revenue = await _account_type_totals(session, context, "REVENUE")
    expense = await _account_type_totals(session, context, "EXPENSE")
    sum_of = lambda rows: sum((row["amount"] for row in rows), 0.0)  # noqa: E731
    total_revenue = sum_of(revenue)
    total_expense = sum_of(expense)
    result = {
        "assets": {"total": sum_of(assets), "accounts": assets},
        "liabilities": {"total": sum_of(liabilities), "accounts": liabilities},
        "revenue": {"total": total_revenue, "accounts": revenue},
        "expenses": {"total": total_expense, "accounts": expense},
        "profit": round(total_revenue - total_expense, 4),
    }
    await cache.set_json(
        "reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds
    )
    return result


_AGING_BUCKETS = ["not_due", "d1_30", "d31_60", "d61_90", "d90_plus"]


def _aging_bucket(due_date: Any, today: Any) -> str:
    if not due_date or not today:
        return "not_due"
    try:
        from datetime import date as _date
        if isinstance(due_date, str):
            due = _date.fromisoformat(due_date)
        else:
            due = due_date
        if isinstance(today, str):
            tday = _date.fromisoformat(today)
        else:
            tday = today
        days = (tday - due).days
        if days <= 0:
            return "not_due"
        if days <= 30:
            return "d1_30"
        if days <= 60:
            return "d31_60"
        if days <= 90:
            return "d61_90"
        return "d90_plus"
    except Exception:
        return "not_due"


def _empty_aging() -> list[dict]:
    return [{"key": key, "amount": 0.0} for key in _AGING_BUCKETS]


def _bucketize(aging: list[dict], due_date: Any, today: Any, outstanding: float) -> None:
    bucket = _aging_bucket(due_date, today)
    for item in aging:
        if item["key"] == bucket:
            item["amount"] = round(item["amount"] + max(outstanding, 0), 4)


async def _service_order_status_counts(
    session: AsyncSession, context: RequestContext, granularity: str | None = None
) -> dict:
    stmt = select(ServiceOrder.status, func.count())
    if granularity is not None:
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        start: datetime | None = None
        if granularity == "day":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif granularity == "month":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        if start is not None:
            stmt = stmt.where(ServiceOrder.created_at >= start)
    rows = (await session.execute(stmt.group_by(ServiceOrder.status))).all()
    counts = {status: int(count) for status, count in rows}
    return {
        "openOrders": counts.get("OPEN", 0),
        "inProgressOrders": counts.get("IN_PROGRESS", 0),
        "onHoldOrders": counts.get("ON_HOLD", 0),
        "awaitingClosure": counts.get("COMPLETED", 0),
        "byStatus": [
            {"status": status, "count": counts.get(status, 0)}
            for status in ["OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETED"]
        ],
    }


async def _journal_revenue_expense(
    session: AsyncSession, context: RequestContext, granularity: str = "month"
) -> tuple[float, float, list[dict]]:
    from datetime import date as _date
    today = _date.today()
    current_month = today.isoformat()[:7]
    current_year = today.isoformat()[:4]

    stmt = (
        select(
            JournalEntryLine,
            ChartOfAccount.account_type,
            JournalEntry.posting_date,
        )
        .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            ChartOfAccount.account_type.in_(["REVENUE", "EXPENSE"]),
            JournalEntry.status == "POSTED",
        )
    )
    rows = (await session.execute(stmt)).all()
    by_bucket: dict[str, dict[str, float]] = {}
    total_revenue = 0.0
    total_expense = 0.0
    for line, account_type, posting_date in rows:
        if not posting_date:
            continue
        iso = posting_date.isoformat() if hasattr(posting_date, "isoformat") else str(posting_date)
        if granularity == "day":
            # Daily view covers the current month only.
            key: str | None = iso[:10] if iso[:7] == current_month else None
        elif granularity == "year":
            key = iso[:4]
        else:
            # Monthly view covers the current year only.
            key = iso[:7] if iso[:4] == current_year else None
        debit = _f(line.base_debit_amount)
        credit = _f(line.base_credit_amount)
        if account_type == "REVENUE":
            amount = round(credit - debit, 4)
            total_revenue = round(total_revenue + amount, 4)
        else:
            amount = round(debit - credit, 4)
            total_expense = round(total_expense + amount, 4)
        if key is None:
            continue
        bucket = by_bucket.setdefault(key, {"revenue": 0.0, "expense": 0.0})
        if account_type == "REVENUE":
            bucket["revenue"] = round(bucket["revenue"] + amount, 4)
        else:
            bucket["expense"] = round(bucket["expense"] + amount, 4)
    points = [
        {"period": key, "revenue": bucket["revenue"], "expense": bucket["expense"]}
        for key, bucket in sorted(by_bucket.items())
    ]
    return total_revenue, total_expense, points


async def _customers(session: AsyncSession, context: RequestContext) -> list[str]:
    stmt = (
        select(BusinessParty.display_name)
        .join(ServiceOrder, ServiceOrder.customer_party_id == BusinessParty.id)
        .where(
            BusinessParty.display_name.is_not(None),
        )
    )
    rows = (await session.execute(stmt.distinct())).scalars().all()
    return sorted([str(r) for r in rows if r])


async def dashboard(session: AsyncSession, context: RequestContext, granularity: str = "month") -> dict:
    cache_parts = ("dashboard", _cache_scope(context), granularity)
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached
    from datetime import date as _date
    today = _date.today().isoformat()

    status_counts = await _service_order_status_counts(session, context)
    chart_status_counts = await _service_order_status_counts(session, context, granularity)
    receivable_rows = await receivables(session, context)
    payable_rows = await payables(session, context)
    total_revenue, total_expense, revenue_expense_points = await _journal_revenue_expense(
        session, context, granularity
    )
    customer_list = await _customers(session, context)

    receivables_total = round(sum(row["balance"] for row in receivable_rows), 4)
    payables_total = round(sum(row["balance"] for row in payable_rows), 4)

    receivables_aging = _empty_aging()
    overdue_receivable_count = 0
    for row in receivable_rows:
        if row.get("balance", 0) <= 0:
            continue
        due = row.get("dueDate") or row.get("documentDate")
        _bucketize(receivables_aging, due, today, row["balance"])
        if _aging_bucket(due, today) != "not_due":
            overdue_receivable_count += 1

    payables_aging = _empty_aging()
    for row in payable_rows:
        if row.get("balance", 0) <= 0:
            continue
        due = row.get("dueDate") or row.get("documentDate")
        _bucketize(payables_aging, due, today, row["balance"])

    result = {
        "generatedAt": _date.today().isoformat(),
        "summary": {
            "openOrders": status_counts["openOrders"],
            "inProgressOrders": status_counts["inProgressOrders"],
            "onHoldOrders": status_counts["onHoldOrders"],
            "awaitingClosure": status_counts["awaitingClosure"],
            "receivables": receivables_total,
            "overdueReceivableCount": overdue_receivable_count,
            "payables": payables_total,
            "cashBankBalance": 0.0,
            "revenue": total_revenue,
            "expense": total_expense,
        },
        "charts": {
            "revenueExpense": revenue_expense_points,
            "ordersByStatus": chart_status_counts["byStatus"],
            "receivablesAging": receivables_aging,
            "payablesAging": payables_aging,
        },
        "options": {
            "customers": customer_list,
        },
    }
    await cache.set_json(
        "reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_dashboard_seconds
    )
    return result

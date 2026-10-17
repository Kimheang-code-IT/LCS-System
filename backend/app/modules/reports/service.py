from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.config import settings
from app.core.context import RequestContext
from app.modules.finance.models import (
    ChartOfAccount,
    FinancialAccount,
    FinancialDocument,
    JournalEntry,
    JournalEntryLine,
)
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


async def trial_balance(session: AsyncSession, context: RequestContext) -> dict:
    """Posted debit/credit totals per account plus the balance control.

    Reads only POSTED journals, and sums the base-currency columns so a
    multi-currency ledger is not added up in mixed denominations. A reversed
    document is represented by its own reversal journal, so summing POSTED entries
    cannot double-count it.

    ``balanced`` is the control: the sum of every debit must equal the sum of every
    credit, and the net across all accounts must be zero. A false value means the
    ledger is broken and must not be reported as a financial statement.
    """
    cache_parts = ("trial-balance", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached

    rows = await ReportRepository(session).posted_trial_balance_rows()
    items: list[dict] = []
    totals = {"debit": Decimal("0"), "credit": Decimal("0")}
    for row in rows:
        debit = Decimal(str(row["total_debit"] or 0))
        credit = Decimal(str(row["total_credit"] or 0))
        totals["debit"] += debit
        totals["credit"] += credit
        items.append(
            {
                "accountId": str(row["account_id"]),
                "accountCode": row["account_code"],
                "accountName": row["account_name"],
                "accountType": row["account_type"],
                "debit": float(debit),
                "credit": float(credit),
                # Debit-normal presentation: a credit balance shows as negative.
                "balance": float(debit - credit),
            }
        )

    total_debit = round(float(totals["debit"]), 4)
    total_credit = round(float(totals["credit"]), 4)
    result = {
        "items": items,
        "totals": {
            "debit": total_debit,
            "credit": total_credit,
            "difference": round(total_debit - total_credit, 4),
        },
        # Both must hold: the two sides must agree, and the whole ledger must net
        # to zero. A non-zero net with equal sides would mean a sign error.
        "balanced": total_debit == total_credit and round(total_debit - total_credit, 4) == 0,
    }
    await cache.set_json("reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds)
    return result


async def profit_loss(session: AsyncSession, context: RequestContext) -> dict:
    """Revenue, expense and net result from POSTED journals.

    Each account's amount is signed by its normal balance (credit-normal for
    revenue), so a credit balance reads as positive revenue rather than a negative
    debit. ``net`` is the control: revenue minus expense.

    No period filter is applied here; the caller scopes by period through the
    dashboard's granularity or a date filter. Documenting that explicitly is
    deliberate — a statement that silently covers "all time" is worse than one that
    says so.
    """
    cache_parts = ("profit-loss", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached

    revenue_rows = await _account_type_totals(session, context, "REVENUE")
    expense_rows = await _account_type_totals(session, context, "EXPENSE")
    revenue = round(sum(row["amount"] for row in revenue_rows), 4)
    expense = round(sum(row["amount"] for row in expense_rows), 4)
    result = {
        "revenue": revenue,
        "expense": expense,
        "net": round(revenue - expense, 4),
        "revenueAccounts": revenue_rows,
        "expenseAccounts": expense_rows,
        "basis": "POSTED journals, base currency",
    }
    await cache.set_json("reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds)
    return result


async def balance_sheet(session: AsyncSession, context: RequestContext) -> dict:
    """Assets, liabilities and equity from POSTED journals, with the accounting control.

    The control is ``assets == liabilities + equity + net result``. Retained
    earnings are included explicitly as the current-period net result because this
    installation does not post a year-end closing entry; folding it in silently
    would hide the reason the two sides differ. ``balanced`` is true only when the
    identity holds to the cent.
    """
    cache_parts = ("balance-sheet", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached

    asset_rows = await _account_type_totals(session, context, "ASSET")
    liability_rows = await _account_type_totals(session, context, "LIABILITY")
    equity_rows = await _account_type_totals(session, context, "EQUITY")
    revenue_rows = await _account_type_totals(session, context, "REVENUE")
    expense_rows = await _account_type_totals(session, context, "EXPENSE")

    assets = round(sum(row["amount"] for row in asset_rows), 4)
    liabilities = round(sum(row["amount"] for row in liability_rows), 4)
    equity = round(sum(row["amount"] for row in equity_rows), 4)
    net_result = round(
        sum(row["amount"] for row in revenue_rows) - sum(row["amount"] for row in expense_rows), 4
    )
    right_side = round(liabilities + equity + net_result, 4)

    result = {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "retainedEarnings": net_result,
        "liabilitiesAndEquity": right_side,
        "difference": round(assets - right_side, 4),
        "balanced": abs(round(assets - right_side, 4)) < 0.0001,
        "assetAccounts": asset_rows,
        "liabilityAccounts": liability_rows,
        "equityAccounts": equity_rows,
        "basis": "POSTED journals, base currency",
    }
    await cache.set_json("reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds)
    return result


async def cash_flow(session: AsyncSession, context: RequestContext) -> dict:
    """Cash movements through the accounts the administrator mapped as cash/bank.

    Uses the same definition as the dashboard's cash balance, so the closing figure
    here and that card can never disagree. Inflows and outflows are reported
    separately, and the net movement plus the opening balance equals the closing
    balance by construction — that identity is the reconciliation.
    """
    cache_parts = ("cash-flow", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached

    flows = await ReportRepository(session).cash_flow_rows()
    items: list[dict] = []
    inflow = Decimal("0")
    outflow = Decimal("0")
    for row in flows:
        debit = Decimal(str(row["debit"] or 0))
        credit = Decimal(str(row["credit"] or 0))
        inflow += debit
        outflow += credit
        items.append(
            {
                "accountId": str(row["account_id"]),
                "accountCode": row["account_code"],
                "accountName": row["account_name"],
                "inflow": float(debit),
                "outflow": float(credit),
                "net": float(debit - credit),
            }
        )

    net = inflow - outflow
    result = {
        "inflow": float(inflow),
        "outflow": float(outflow),
        "net": float(net),
        "closingBalance": float(net),
        "accounts": items,
        "basis": "POSTED journals on accounts mapped in financial_accounts, base currency",
    }
    await cache.set_json("reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds)
    return result


async def container_register(session: AsyncSession, context: RequestContext) -> dict:
    """Container register: every container with its order, type and status counts.

    Operational report required alongside the order register. Containers are
    lifetime-tracked rather than archived, so nothing is filtered out here; the
    status breakdown tells an operator where the boxes are.
    """
    cache_parts = ("container-register", _cache_scope(context))
    cached = await cache.get_json("reports", *cache_parts)
    if cached is not None:
        return cached

    rows = await ReportRepository(session).container_register_rows()
    items = [
        {
            "id": str(row["id"]),
            "containerNumber": row["container_number"],
            "containerType": row["container_type"],
            "sealSerial": row["seal_serial"],
            "status": (row["status"] or "").upper(),
            "serviceOrderId": str(row["service_order_id"]) if row["service_order_id"] else None,
            "serviceOrderNo": row["service_order_no"],
            "customer": row["customer_name"],
            "grossWeightKg": _f(row["gross_weight_kg"]) if row["gross_weight_kg"] is not None else None,
            "pickupDate": row["pickup_date"].isoformat() if row["pickup_date"] else None,
            "returnDate": row["return_date"].isoformat() if row["return_date"] else None,
        }
        for row in rows
    ]

    by_status: dict[str, int] = {}
    for item in items:
        key = item["status"] or "UNKNOWN"
        by_status[key] = by_status.get(key, 0) + 1

    result = {
        "items": items,
        "total": len(items),
        "byStatus": [{"status": status, "count": count} for status, count in sorted(by_status.items())],
    }
    await cache.set_json("reports", *cache_parts, value=result, ttl_seconds=settings.cache_ttl_report_seconds)
    return result


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

# Statuses a service order can actually hold. Mirrors ORDER_STATUS in
# operations/service.py; kept here so reports never count a status the
# application cannot produce.
SERVICE_ORDER_LIFECYCLE = ("ACTIVE", "INACTIVE", "FINISHED")


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

    # The order lifecycle is a three-state one: ACTIVE / INACTIVE / FINISHED
    # (see ORDER_STATUS in operations/service.py). The dashboard payload keeps its
    # four legacy key names because the frontend contract depends on them, so the
    # keys are mapped onto the states that actually exist rather than counted by
    # name. Counting by name made every card report 0 on every installation.
    return {
        "openOrders": counts.get("ACTIVE", 0),
        "inProgressOrders": counts.get("ACTIVE", 0),
        "onHoldOrders": counts.get("INACTIVE", 0),
        "awaitingClosure": counts.get("FINISHED", 0),
        # Charts are data-driven, so they report the real lifecycle. The frontend
        # KPI cards deep-link with the pre-simplification filter values and need
        # the same mapping applied; tracked in docs/18_implementation_checklist.md.
        "byStatus": [
            {"status": status, "count": counts.get(status, 0)}
            for status in SERVICE_ORDER_LIFECYCLE
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


async def _cash_bank_balance(session: AsyncSession) -> float:
    """Net posted balance of the ledger accounts configured as cash or bank.

    Derived from the administrator's own mapping in ``financial_accounts`` rather
    than from hardcoded account codes, so a renamed or re-coded chart of accounts
    keeps working. Assets are debit-normal, so the balance is debit minus credit.
    Only POSTED journals count, which makes this consistent with every other
    balance in the dashboard. Amounts use the base-currency columns so a
    multi-currency cash account is not summed in mixed denominations.
    """
    stmt = (
        select(JournalEntryLine.base_debit_amount, JournalEntryLine.base_credit_amount)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .join(FinancialAccount, FinancialAccount.account_id == JournalEntryLine.account_id)
        .where(JournalEntry.status == "POSTED")
    )
    rows = (await session.execute(stmt)).all()
    balance = 0.0
    for debit, credit in rows:
        balance = round(balance + _f(debit) - _f(credit), 4)
    return balance


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
    cash_bank_balance = await _cash_bank_balance(session)

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
            "cashBankBalance": cash_bank_balance,
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

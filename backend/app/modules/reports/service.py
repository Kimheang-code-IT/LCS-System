from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.pagination import PageParams, parse_date
from app.modules.finance.models import ChartOfAccount, FinancialDocument, JournalEntry, JournalEntryLine
from app.modules.operations.models import ServiceOrder
from app.modules.quotations.models import Quotation


def _f(value: Any) -> float:
    return float(value or 0)


async def _scope_filters(context: RequestContext, model: Any, stmt: Any, page: PageParams) -> Any:
    if hasattr(model, "organization_id"):
        stmt = stmt.where(model.organization_id == context.organization_id)
    if hasattr(model, "branch_id") and not context.can_select_all_branches and context.branch_id is not None:
        stmt = stmt.where(model.branch_id == context.branch_id)
    if page.from_date and hasattr(model, "document_date"):
        parsed = parse_date(page.from_date)
        if parsed:
            stmt = stmt.where(model.document_date >= parsed)
    if page.to_date and hasattr(model, "document_date"):
        parsed = parse_date(page.to_date)
        if parsed:
            stmt = stmt.where(model.document_date <= parsed)
    return stmt


async def receivables(session: AsyncSession, context: RequestContext) -> list[dict]:
    rows = (
        await session.execute(
            select(FinancialDocument).where(
                FinancialDocument.organization_id == context.organization_id,
                FinancialDocument.document_type == "CUSTOMER_INVOICE",
                FinancialDocument.status == "POSTED",
            )
        )
    ).scalars().all()
    items = []
    for row in rows:
        outstanding = (row.total_amount or Decimal("0")) - (row.paid_amount or Decimal("0"))
        items.append(
            {
                "id": str(row.id),
                "documentNo": row.document_no,
                "partyId": row.party_id,
                "documentDate": row.document_date.isoformat() if row.document_date else None,
                "dueDate": row.due_date.isoformat() if row.due_date else None,
                "currency": row.currency_code,
                "total": _f(row.total_amount),
                "paid": _f(row.paid_amount),
                "balance": _f(outstanding),
                "status": "PAID" if outstanding <= 0 else ("PARTIAL" if row.paid_amount else "OPEN"),
            }
        )
    return items


async def payables(session: AsyncSession, context: RequestContext) -> list[dict]:
    rows = (
        await session.execute(
            select(FinancialDocument).where(
                FinancialDocument.organization_id == context.organization_id,
                FinancialDocument.document_type == "SUPPLIER_BILL",
                FinancialDocument.status == "POSTED",
            )
        )
    ).scalars().all()
    items = []
    for row in rows:
        outstanding = (row.total_amount or Decimal("0")) - (row.paid_amount or Decimal("0"))
        items.append(
            {
                "id": str(row.id),
                "documentNo": row.document_no,
                "partyId": row.party_id,
                "documentDate": row.document_date.isoformat() if row.document_date else None,
                "dueDate": row.due_date.isoformat() if row.due_date else None,
                "currency": row.currency_code,
                "total": _f(row.total_amount),
                "paid": _f(row.paid_amount),
                "balance": _f(outstanding),
                "status": "PAID" if outstanding <= 0 else ("PARTIAL" if row.paid_amount else "OPEN"),
            }
        )
    return items


async def _account_type_totals(session: AsyncSession, context: RequestContext, account_type: str) -> list[dict]:
    rows = (
        await session.execute(
            select(
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                func.coalesce(func.sum(JournalEntryLine.base_debit_amount), 0),
                func.coalesce(func.sum(JournalEntryLine.base_credit_amount), 0),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                ChartOfAccount.organization_id == context.organization_id,
                ChartOfAccount.account_type == account_type,
                JournalEntry.status == "POSTED",
            )
            .group_by(ChartOfAccount.account_code, ChartOfAccount.account_name)
            .order_by(ChartOfAccount.account_code)
        )
    ).all()
    result = []
    for code, name, debit, credit in rows:
        if account_type in {"REVENUE", "LIABILITY", "EQUITY"}:
            amount = Decimal(str(credit)) - Decimal(str(debit))
        else:
            amount = Decimal(str(debit)) - Decimal(str(credit))
        result.append({"accountCode": code, "accountName": name, "amount": _f(amount), "debit": _f(debit), "credit": _f(credit)})
    return result


async def income(session: AsyncSession, context: RequestContext) -> list[dict]:
    return await _account_type_totals(session, context, "REVENUE")


async def expenses(session: AsyncSession, context: RequestContext) -> list[dict]:
    return await _account_type_totals(session, context, "EXPENSE")


async def profitability(session: AsyncSession, context: RequestContext) -> list[dict]:
    orders = (
        await session.execute(
            select(ServiceOrder).where(ServiceOrder.organization_id == context.organization_id)
        )
    ).scalars().all()
    items = []
    for order in orders:
        revenue = await session.scalar(
            select(func.coalesce(func.sum(FinancialDocument.total_amount), 0)).where(
                FinancialDocument.service_order_id == order.id,
                FinancialDocument.document_type == "CUSTOMER_INVOICE",
                FinancialDocument.status == "POSTED",
            )
        )
        cost = await session.scalar(
            select(func.coalesce(func.sum(FinancialDocument.total_amount), 0)).where(
                FinancialDocument.service_order_id == order.id,
                FinancialDocument.document_type == "SUPPLIER_BILL",
                FinancialDocument.status == "POSTED",
            )
        )
        profit = Decimal(str(revenue or 0)) - Decimal(str(cost or 0))
        items.append(
            {
                "id": str(order.id),
                "jobNo": order.service_order_no,
                "serviceOrderNo": order.service_order_no,
                "status": order.status,
                "currency": order.currency_code,
                "revenue": _f(revenue),
                "cost": _f(cost),
                "totalCost": _f(cost),
                "profit": _f(profit),
                "margin": _f(profit / Decimal(str(revenue)) * 100) if revenue else 0.0,
            }
        )
    return items


async def quotation_performance(session: AsyncSession, context: RequestContext) -> dict:
    total = await session.scalar(
        select(func.count()).select_from(Quotation).where(Quotation.organization_id == context.organization_id)
    )
    rows = (
        await session.execute(
            select(Quotation.status, func.count()).where(Quotation.organization_id == context.organization_id).group_by(Quotation.status)
        )
    ).all()
    return {"total": int(total or 0), "byStatus": {status: int(count) for status, count in rows}}


async def service_order_report(session: AsyncSession, context: RequestContext) -> dict:
    total = await session.scalar(
        select(func.count()).select_from(ServiceOrder).where(ServiceOrder.organization_id == context.organization_id)
    )
    rows = (
        await session.execute(
            select(ServiceOrder.status, func.count())
            .where(ServiceOrder.organization_id == context.organization_id)
            .group_by(ServiceOrder.status)
        )
    ).all()
    return {"total": int(total or 0), "byStatus": {status: int(count) for status, count in rows}}


async def financial_summary(session: AsyncSession, context: RequestContext) -> dict:
    assets = await _account_type_totals(session, context, "ASSET")
    liabilities = await _account_type_totals(session, context, "LIABILITY")
    revenue = await _account_type_totals(session, context, "REVENUE")
    expense = await _account_type_totals(session, context, "EXPENSE")
    sum_of = lambda rows: sum((row["amount"] for row in rows), 0.0)  # noqa: E731
    total_revenue = sum_of(revenue)
    total_expense = sum_of(expense)
    return {
        "assets": {"total": sum_of(assets), "accounts": assets},
        "liabilities": {"total": sum_of(liabilities), "accounts": liabilities},
        "revenue": {"total": total_revenue, "accounts": revenue},
        "expenses": {"total": total_expense, "accounts": expense},
        "profit": round(total_revenue - total_expense, 4),
    }


async def dashboard(session: AsyncSession, context: RequestContext) -> dict:
    open_orders = await session.scalar(
        select(func.count()).select_from(ServiceOrder).where(
            ServiceOrder.organization_id == context.organization_id,
            ServiceOrder.status.in_(["OPEN", "IN_PROGRESS", "ON_HOLD"]),
        )
    )
    quotations = await session.scalar(
        select(func.count()).select_from(Quotation).where(Quotation.organization_id == context.organization_id)
    )
    receivable_rows = await receivables(session, context)
    payable_rows = await payables(session, context)
    return {
        "openServiceOrders": int(open_orders or 0),
        "quotations": int(quotations or 0),
        "receivableTotal": round(sum(row["balance"] for row in receivable_rows), 4),
        "payableTotal": round(sum(row["balance"] for row in payable_rows), 4),
        "receivables": receivable_rows,
        "payables": payable_rows,
    }

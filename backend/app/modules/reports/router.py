from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.core.rate_limit import enforce_rate_limit
from app.modules.reports import service

router = APIRouter()

# Report queries aggregate large tables: cap per-user request rate so a single
# session cannot hammer them. Limits are generous for normal dashboards.
_REPORT_ACCESS = require_permission("report.read")
REPORT_RATE_LIMIT = 120
REPORT_RATE_WINDOW_SECONDS = 60


async def report_access(
    context: RequestContext = Depends(_REPORT_ACCESS),
) -> RequestContext:
    await enforce_rate_limit(
        f"reports:user:{context.user_id}",
        limit=REPORT_RATE_LIMIT,
        window_seconds=REPORT_RATE_WINDOW_SECONDS,
    )
    return context


@router.get("/reports/dashboard")
async def dashboard(
    granularity: Literal["day", "month", "year"] = "month",
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.dashboard(session, context, granularity)}


@router.get("/reports/service-orders")
async def service_orders_report(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.service_order_report(session, context)}


@router.get("/reports/quotation-performance")
async def quotation_performance(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.quotation_performance(session, context)}


@router.get("/reports/profit-loss")
async def profit_loss_report(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Revenue, expense and net result from POSTED journals."""
    return {"data": await service.profit_loss(session, context)}


@router.get("/reports/balance-sheet")
async def balance_sheet_report(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Assets, liabilities and equity, with the accounting identity as a control."""
    return {"data": await service.balance_sheet(session, context)}


@router.get("/reports/cash-flow")
async def cash_flow_report(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Cash and bank movements, using the same account mapping as the dashboard."""
    return {"data": await service.cash_flow(session, context)}


@router.get("/reports/container-register")
async def container_register_report(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Container register with a status breakdown."""
    return {"data": await service.container_register(session, context)}


@router.get("/reports/trial-balance")
async def trial_balance(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Posted debit/credit totals per account, with a balance check.

    Server-side rather than derived in the browser: the trial balance is the
    control that proves the ledger balances, and a control computed from a
    paginated client-side row set is not a control.
    """
    return {"data": await service.trial_balance(session, context)}


@router.get("/reports/receivables")
async def receivables(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.receivables(session, context)}


@router.get("/reports/payables")
async def payables(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.payables(session, context)}


@router.get("/reports/income")
async def income(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.income(session, context)}


@router.get("/reports/expenses")
async def expenses(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.expenses(session, context)}


@router.get("/reports/profitability")
@router.get("/reports/service-order-profitability")
async def profitability(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.profitability(session, context)}


@router.get("/reports/ledger-lines")
async def ledger_lines(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.ledger_lines(session, context)}


@router.get("/reports/financial-summary")
async def financial_summary(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.financial_summary(session, context)}


# Aliases used by the metadata-driven module list for derived collections.
@router.get("/receivables")
async def receivables_alias(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.receivables(session, context)}


@router.get("/payables")
async def payables_alias(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.payables(session, context)}


@router.get("/profitability")
async def profitability_alias(
    context: RequestContext = Depends(report_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.profitability(session, context)}

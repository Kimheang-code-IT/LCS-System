from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_any_permission
from app.core.rate_limit import enforce_rate_limit
from app.modules.reports import engine, service
from app.modules.reports.schemas import (
    GeneralLedgerExportFilters,
    GeneralLedgerFilters,
    GeneralLedgerReport,
    TrialBalanceExportFilters,
    TrialBalanceFilters,
    TrialBalanceReport,
)

router = APIRouter()

# Report queries aggregate large tables: cap per-user request rate so a single
# session cannot hammer them. Limits are generous for normal dashboards.
REPORT_RATE_LIMIT = 120
REPORT_RATE_WINDOW_SECONDS = 60


def report_access(*page_codes: str):
    """Require one report page code, with ``report.read`` for legacy roles."""
    guard = require_any_permission(*page_codes, "report.read")

    async def dependency(
        context: RequestContext = Depends(guard),
    ) -> RequestContext:
        await enforce_rate_limit(
            f"reports:user:{context.user_id}",
            limit=REPORT_RATE_LIMIT,
            window_seconds=REPORT_RATE_WINDOW_SECONDS,
        )
        return context

    return dependency


@router.get("/reports/dashboard")
async def dashboard(
    granularity: Literal["day", "month", "year"] = "month",
    context: RequestContext = Depends(report_access("dashboard.summary")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.dashboard(session, context, granularity)}


@router.get("/reports/service-orders")
async def service_orders_report(
    context: RequestContext = Depends(report_access("reports.service_order_register.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.service_order_report(session, context)}


@router.get("/reports/quotation-performance")
async def quotation_performance(
    context: RequestContext = Depends(report_access("sales.quotations.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.quotation_performance(session, context)}


@router.get("/reports/profit-loss")
async def profit_loss_report(
    context: RequestContext = Depends(report_access("reports.profit_loss.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Revenue, expense and net result from POSTED journals."""
    return {"data": await service.profit_loss(session, context)}


@router.get("/reports/balance-sheet")
async def balance_sheet_report(
    context: RequestContext = Depends(report_access("reports.balance_sheet.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Assets, liabilities and equity, with the accounting identity as a control."""
    return {"data": await service.balance_sheet(session, context)}


@router.get("/reports/cash-flow")
async def cash_flow_report(
    context: RequestContext = Depends(report_access("reports.cash_flow.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Cash and bank movements, using the same account mapping as the dashboard."""
    return {"data": await service.cash_flow(session, context)}


@router.get("/reports/container-register")
async def container_register_report(
    context: RequestContext = Depends(report_access("reports.service_order_containers.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Container register with a status breakdown."""
    return {"data": await service.container_register(session, context)}


@router.get("/reports/trial-balance")
async def trial_balance(
    context: RequestContext = Depends(report_access("reports.trial_balance.view")),
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
    context: RequestContext = Depends(report_access("reports.accounts_receivable.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.receivables(session, context)}


@router.get("/reports/payables")
async def payables(
    context: RequestContext = Depends(report_access("reports.accounts_payable.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.payables(session, context)}


@router.get("/reports/income")
async def income(
    context: RequestContext = Depends(report_access("reports.revenue_expense.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.income(session, context)}


@router.get("/reports/expenses")
async def expenses(
    context: RequestContext = Depends(report_access("reports.revenue_expense.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.expenses(session, context)}


@router.get("/reports/profitability")
@router.get("/reports/service-order-profitability")
async def profitability(
    context: RequestContext = Depends(report_access("reports.service_order_profitability.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.profitability(session, context)}


@router.get("/reports/ledger-lines")
async def ledger_lines(
    context: RequestContext = Depends(report_access("reports.general_ledger.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.ledger_lines(session, context)}


# --- On-demand report generation ---------------------------------------------
# A report page posts its filters and receives one page plus the metadata that
# produced it. Nothing is fetched until the user asks for a report.
@router.post("/reports/trial-balance/generate")
async def generate_trial_balance(
    payload: TrialBalanceFilters | None = Body(default=None),
    context: RequestContext = Depends(report_access(engine.permission_for("trial-balance"))),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Debit/credit movement per account for a period, from POSTED journals.

    Opening balances carry the movement before ``fromDate`` so a mid-history
    period still opens at a real position. The response reports a difference
    instead of hiding one.
    """
    report = await engine.generate(session, context, "trial-balance", payload or TrialBalanceFilters())
    return {"data": TrialBalanceReport.model_validate(report).model_dump()}


@router.post("/reports/general-ledger/generate")
async def generate_general_ledger(
    payload: GeneralLedgerFilters | None = Body(default=None),
    context: RequestContext = Depends(report_access(engine.permission_for("general-ledger"))),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Posted ledger lines in deterministic order, one server-paginated page at a time.

    Each row carries the running balance for its account, continued from that
    account's opening balance before ``fromDate``.
    """
    report = await engine.generate(session, context, "general-ledger", payload or GeneralLedgerFilters())
    return {"data": GeneralLedgerReport.model_validate(report).model_dump()}


# --- Full-result exports ------------------------------------------------------
# Same filters, permission and calculation as Generate; the response streams every
# matching row instead of one page, so an export is never limited to what the
# table happened to show.
def _csv_response(key: str, stream) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{engine.export_filename(key)}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/reports/trial-balance/export")
async def export_trial_balance(
    payload: TrialBalanceExportFilters | None = Body(default=None),
    context: RequestContext = Depends(report_access(engine.permission_for("trial-balance"))),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Every account in the filtered trial balance as CSV, with its totals row."""
    request = payload or TrialBalanceExportFilters()
    return _csv_response(
        "trial-balance",
        engine.export_csv(session, context, "trial-balance", request),
    )


@router.post("/reports/general-ledger/export")
async def export_general_ledger(
    payload: GeneralLedgerExportFilters | None = Body(default=None),
    context: RequestContext = Depends(report_access(engine.permission_for("general-ledger"))),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Every matching ledger line as CSV, streamed, with its totals row."""
    request = payload or GeneralLedgerExportFilters()
    return _csv_response(
        "general-ledger",
        engine.export_csv(session, context, "general-ledger", request),
    )


@router.get("/reports/financial-summary")
async def financial_summary(
    context: RequestContext = Depends(report_access("reports.trial_balance.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.financial_summary(session, context)}


# Aliases used by the metadata-driven module list for derived collections.
@router.get("/receivables")
async def receivables_alias(
    context: RequestContext = Depends(report_access("reports.accounts_receivable.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.receivables(session, context)}


@router.get("/payables")
async def payables_alias(
    context: RequestContext = Depends(report_access("reports.accounts_payable.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.payables(session, context)}


@router.get("/profitability")
async def profitability_alias(
    context: RequestContext = Depends(report_access("reports.service_order_profitability.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.profitability(session, context)}

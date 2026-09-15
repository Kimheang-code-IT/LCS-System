from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import require_permission
from app.modules.reports import service

router = APIRouter()


@router.get("/reports/dashboard")
async def dashboard(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.dashboard(session, context)}


@router.get("/reports/service-orders")
async def service_orders_report(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.service_order_report(session, context)}


@router.get("/reports/quotation-performance")
async def quotation_performance(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.quotation_performance(session, context)}


@router.get("/reports/receivables")
async def receivables(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.receivables(session, context)}


@router.get("/reports/payables")
async def payables(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.payables(session, context)}


@router.get("/reports/income")
async def income(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.income(session, context)}


@router.get("/reports/expenses")
async def expenses(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.expenses(session, context)}


@router.get("/reports/profitability")
@router.get("/reports/service-order-profitability")
async def profitability(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.profitability(session, context)}


@router.get("/reports/financial-summary")
async def financial_summary(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.financial_summary(session, context)}


# Aliases used by the metadata-driven module list for derived collections.
@router.get("/receivables")
async def receivables_alias(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.receivables(session, context)}


@router.get("/payables")
async def payables_alias(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.payables(session, context)}


@router.get("/profitability")
async def profitability_alias(
    context: RequestContext = Depends(require_permission("report.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.profitability(session, context)}

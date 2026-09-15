from __future__ import annotations

from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.finance.router import router as finance_router
from app.modules.master_data.router import router as master_data_router
from app.modules.operations.router import router as operations_router
from app.modules.quotations.router import router as quotations_router
from app.modules.reports.router import router as reports_router

api_router = APIRouter()
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(quotations_router, tags=["quotations"])
api_router.include_router(operations_router, tags=["operations"])
api_router.include_router(finance_router, tags=["finance"])
api_router.include_router(reports_router, tags=["reports"])
api_router.include_router(master_data_router, tags=["master-data"])
api_router.include_router(audit_router, tags=["audit"])


@api_router.get("/health")
async def health() -> dict:
    return {"data": {"status": "ok"}}

from __future__ import annotations

from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.backup.router import router as backup_router
from app.modules.finance.router import router as finance_router
from app.modules.master_data.router import router as master_data_router
from app.modules.operations.router import router as operations_router
from app.modules.quotations.router import router as quotations_router
from app.modules.reports.router import router as reports_router
from app.modules.settings.router import router as settings_router
from app.modules.setup.router import router as setup_router

api_router = APIRouter()
api_router.include_router(setup_router, tags=["setup"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(quotations_router, tags=["quotations"])
api_router.include_router(operations_router, tags=["operations"])
api_router.include_router(finance_router, tags=["finance"])
api_router.include_router(reports_router, tags=["reports"])
api_router.include_router(master_data_router, tags=["master-data"])
api_router.include_router(settings_router, tags=["settings"])
api_router.include_router(backup_router, tags=["backup"])
api_router.include_router(audit_router, tags=["audit"])


@api_router.get("/health")
async def health() -> dict:
    return {"data": {"status": "ok"}}

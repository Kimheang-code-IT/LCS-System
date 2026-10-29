"""Import/Export endpoints. Authorization mirrors each module's own module
guards (Master Data: ``master.reference.view`` to read/export, ``master.reference.manage``
to import), and the import session is bound to the uploading user only.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context
from app.core.exceptions import AccessDenied, ValidationFailed
from app.modules.excel_io import service, templates
from app.modules.excel_io.registry import MAX_FILE_BYTES

router = APIRouter(prefix="/excel")

#: Per-user, per-action sliding windows. Scaled for the approved 2 vCPU / 4 GB
#: deployment: workbook parsing (validate) is the expensive path and gets the
#: tightest window; reads stay cheap. Keys are pruned when the map grows.
_RATE_WINDOW_SECONDS = 60
_RATE_LIMITS: dict[str, int] = {
    "modules": 120,
    "template": 20,
    "validate": 10,
    "commit": 10,
    "export": 20,
    "history": 60,
}
_RATE_BUCKETS: dict[tuple[int, str], deque[float]] = defaultdict(deque)
_RATE_BUCKETS_LOCK = threading.Lock()


def _rate_limit(context: RequestContext, action: str) -> None:
    now = time.monotonic()
    limit = _RATE_LIMITS.get(action, 30)
    key = (context.user_id, action)
    with _RATE_BUCKETS_LOCK:
        bucket = _RATE_BUCKETS[key]
        while bucket and bucket[0] < now - _RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            raise AccessDenied("Too many import/export requests; try again shortly.")
        bucket.append(now)
        if len(_RATE_BUCKETS) > 1000:
            for bucket_key, entries in list(_RATE_BUCKETS.items()):
                if not entries or entries[-1] < now - _RATE_WINDOW_SECONDS:
                    _RATE_BUCKETS.pop(bucket_key, None)


def _require(context: RequestContext, permission: str) -> None:
    if not context.has_permission(permission):
        raise AccessDenied(f"Missing permission: {permission}")


@router.get("/modules")
async def list_modules(
    request: Request,
    context: RequestContext = Depends(get_current_context),
) -> dict:
    _rate_limit(context, "modules")
    # Offer only the modules this caller may use: the catalog carries the module
    # names, match keys and permission codes, so an unscoped list would describe
    # import surfaces the caller cannot reach.
    catalog = [
        module
        for module in service.module_catalog()
        if context.has_permission(str(module["viewPermission"]))
        or context.has_permission(str(module["managePermission"]))
    ]
    return {"data": catalog}


@router.get("/{module}/template")
async def download_template(
    module: str,
    request: Request,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> Any:
    _rate_limit(context, "template")
    excel_module = service.get_module(module)
    _require(context, excel_module.view_permission)
    content = await templates.build_template(session, excel_module)
    return _spreadsheet(content, f"{module}-import-template.xlsx")


@router.post("/{module}/validate")
async def validate_upload(
    request: Request,
    module: str,
    file: UploadFile = File(...),
    mode: str = Form("CREATE_ONLY"),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _rate_limit(context, "validate")
    excel_module = service.get_module(module)
    _require(context, excel_module.manage_permission)
    if file.filename and not file.filename.lower().endswith(".xlsx"):
        raise ValidationFailed("Only .xlsx workbooks are accepted.", {"file": "Unsupported extension"})
    # Reject a declared oversized body before buffering it: reading first would
    # spool the whole upload to disk before the size check could refuse it.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_FILE_BYTES + 64 * 1024:
        raise ValidationFailed("The file is too large.", {"file": "File too large"})
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise ValidationFailed("The file is too large.", {"file": "File too large"})
    if not content:
        raise ValidationFailed("The uploaded file is empty.", {"file": "Empty file"})
    return {"data": await service.start_import(session, context, excel_module, file.filename or "upload.xlsx", content, mode)}


@router.get("/imports/{token}")
async def import_preview(
    token: str,
    request: Request,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _rate_limit(context, "modules")
    return {"data": await service.get_preview_rows(session, token, context)}


@router.post("/imports/{token}/commit")
async def commit_import(
    token: str,
    request: Request,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _rate_limit(context, "commit")
    state = await service.get_session_state(session, token, context)
    excel_module = service.get_module(state.module)
    _require(context, excel_module.manage_permission)
    return {"data": await service.confirm_import(session, context, token)}


@router.post("/imports/{token}/cancel")
async def cancel_import(
    token: str,
    request: Request,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _rate_limit(context, "commit")
    await service.cancel_import(session, token, context)
    return {"data": {"status": "CANCELLED"}}


@router.get("/imports/{token}/error-report")
async def download_error_report(
    token: str,
    request: Request,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> Any:
    _rate_limit(context, "validate")
    state = await service.get_preview_rows(session, token, context)
    excel_module = service.get_module(state["module"])
    _require(context, excel_module.manage_permission)
    content = service.build_error_report(excel_module, state["rows"])
    return _spreadsheet(content, f"{excel_module.key}-import-errors.xlsx")


@router.post("/{module}/export")
async def export(
    request: Request,
    module: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> Any:
    _rate_limit(context, "export")
    excel_module = service.get_module(module)
    _require(context, excel_module.view_permission)
    ids = [int(value) for value in (payload.get("ids") or [])]
    filters = payload.get("filters")
    fmt = str(payload.get("format") or "xlsx").strip().lower()
    content = await service.export_rows(session, excel_module, ids or None, filters if isinstance(filters, dict) else None, fmt)
    if fmt == "csv":
        return _spreadsheet(content, f"{module}-export.csv", "text/csv; charset=utf-8")
    return _spreadsheet(content, f"{module}-export.xlsx")


@router.get("/{module}/export-count")
async def export_count(
    request: Request,
    module: str,
    date_from: str | None = None,
    date_to: str | None = None,
    created_by: str | None = None,
    updated_by: str | None = None,
    status: str | None = None,
    search: str | None = None,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _rate_limit(context, "export")
    excel_module = service.get_module(module)
    _require(context, excel_module.view_permission)
    filters = {
        key: value
        for key, value in {
            "date_from": date_from, "date_to": date_to, "created_by": created_by,
            "updated_by": updated_by, "status": status, "search": search,
        }.items()
        if value not in (None, "")
    }
    count = await service.export_count(session, excel_module, filters)
    return {"data": {"count": count}}


@router.get("/history")
async def import_history(
    request: Request,
    module: str | None = None,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _rate_limit(context, "history")
    if module:
        excel_module = service.get_module(module)
        _require(context, excel_module.view_permission)
    else:
        # Unscoped history spans every module, so it needs the same read right
        # as any single module rather than being visible to every caller.
        _require(context, "master.reference.view")
    return {"data": {"items": await service.history(session, module)}}


def _spreadsheet(content: bytes, filename: str, media_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") -> Any:
    from fastapi import Response

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

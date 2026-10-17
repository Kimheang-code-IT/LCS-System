from __future__ import annotations

import os

from fastapi import APIRouter, Body, Depends, File, Form, Header, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context, require_permission
from app.core.pagination import PageParams, page_params
from app.modules.master_data import config_versions
from app.modules.operations import component_tabs as component_tabs_service
from app.modules.operations import service

router = APIRouter()


@router.get("/service-orders")
async def list_service_orders(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_service_orders(session, context, page)}


@router.post("/service-orders", status_code=status.HTTP_201_CREATED)
async def create_service_order(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_service_order(session, context, payload)}


@router.delete("/service-orders")
async def delete_service_orders(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    removed = await service.delete_service_orders(session, ids)
    return {"data": {"removed": removed}}


@router.get("/service-orders/{identifier}/containers")
async def list_containers(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_containers(session, context, identifier)}


@router.post("/service-orders/{identifier}/containers", status_code=status.HTTP_201_CREATED)
async def add_container(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    container = await service.add_container(session, context, identifier, payload)
    await session.commit()
    return {"data": container}


@router.get("/service-orders/{identifier}/movements")
async def list_movements(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_movements(session, context, identifier)}


@router.post("/service-orders/{identifier}/movements", status_code=status.HTTP_201_CREATED)
async def save_movement(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_movement(session, context, identifier, payload)}


@router.delete("/service-orders/{identifier}/movements")
async def delete_movements(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    removed = await service.delete_movements(session, context, identifier, ids)
    return {"data": {"removed": removed}}


@router.get("/service-orders/{identifier}/milestones")
async def list_milestones(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_milestones(session, context, identifier)}


@router.post("/service-orders/{identifier}/milestones", status_code=status.HTTP_201_CREATED)
async def save_milestone(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_milestone(session, context, identifier, payload)}


@router.delete("/service-orders/{identifier}/milestones")
async def delete_milestones(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    removed = await service.delete_milestones(session, context, identifier, ids)
    return {"data": {"removed": removed}}


@router.get("/service-orders/{identifier}/configuration-version")
async def get_service_order_configuration_version(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """The published configuration snapshot this order was captured under."""
    order = await service.resolve_order(session, context, identifier)
    return {"data": await config_versions.version_for_order(session, order)}


@router.get("/service-orders/{identifier}/component-tabs")
async def list_component_tabs(
    identifier: str,
    direction_id: int | None = None,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order = await service.resolve_order(session, context, identifier)
    return {"data": await component_tabs_service.bootstrap(session, context, order.id, direction_id)}


@router.get("/service-orders/{identifier}/component-tabs/groups/{group_id}/rows")
async def list_component_group_rows(
    identifier: str,
    group_id: int,
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order = await service.resolve_order(session, context, identifier)
    return {"data": await component_tabs_service.list_rows(session, context, order.id, group_id, page)}


@router.post("/service-orders/{identifier}/component-tabs/groups/{group_id}/rows/bulk")
async def bulk_save_component_group_rows(
    identifier: str,
    group_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order = await service.resolve_order(session, context, identifier)
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if rows is None and isinstance(payload, dict):
        rows = payload.get("items") or []
    result = await component_tabs_service.bulk_save(session, context, order.id, group_id, rows or [])
    await session.commit()
    return {"data": result}


@router.get("/service-orders/{identifier}/charges")
async def list_order_charges(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_charge.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_order_charges(session, context, identifier)}


@router.post("/service-orders/{identifier}/charges", status_code=status.HTTP_201_CREATED)
async def create_order_charge(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_charge.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_charge(session, context, payload, order_identifier=identifier)}


@router.get("/service-orders/{identifier}/invoice")
async def get_service_order_invoice(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_charge.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.finance import service as finance_service

    order = await service.resolve_order(session, context, identifier)
    return {"data": await finance_service.get_service_order_invoice(session, context, order.id)}


@router.post("/service-orders/{identifier}/invoice", status_code=status.HTTP_201_CREATED)
async def create_service_order_invoice(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_charge.convert_to_invoice")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.finance import service as finance_service

    order = await service.resolve_order(session, context, identifier)
    return {"data": await finance_service.create_invoice_from_service_order(session, context, order)}


@router.get("/service-orders/{identifier}")
async def get_service_order(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_service_order(session, context, identifier)}


@router.put("/service-orders/{identifier}")
@router.post("/service-orders/{identifier}")
async def update_service_order(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = {**payload, "id": identifier}
    return {"data": await service.save_service_order(session, context, payload)}


@router.post("/service-orders/{identifier}/finish")
async def finish_service_order(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    before = await service.order_status(session, identifier)
    record = await service.finish_service_order(session, context, identifier)
    await service.record_order_status_change(
        session, context, record, before, "SERVICE_ORDER_FINISHED", "finish",
    )
    return {"data": record}


@router.get("/service-charges")
async def list_service_charges(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("service_charge.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_charges(session, context, page)}


@router.post("/service-charges", status_code=status.HTTP_201_CREATED)
async def create_service_charge(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_charge.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_charge(session, context, payload)}


@router.get("/service-charges/{charge_id}")
async def get_service_charge(
    charge_id: str,
    context: RequestContext = Depends(require_permission("service_charge.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_charge(session, context, int(charge_id))}


@router.put("/service-charges/{charge_id}")
async def update_service_charge(
    charge_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_charge.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_charge(session, context, {**payload, "id": charge_id})}


@router.delete("/service-charges")
async def delete_service_charges(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_charge.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    removed = await service.delete_charges(session, ids)
    return {"data": {"removed": removed}}


@router.post("/service-charges/{charge_id}/issue")
async def issue_service_charge(
    charge_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("service_charge.issue")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    before = await service.charge_status(session, int(charge_id))
    charge = await service.issue_charge(session, context, int(charge_id))
    await service.record_charge_status_change(session, context, int(charge_id), before, charge)
    await session.commit()
    return {"data": charge}


@router.post("/service-charges/{charge_id}/create-finance-invoice", status_code=status.HTTP_201_CREATED)
async def create_finance_invoice(
    charge_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("service_charge.convert_to_invoice")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    document = await service.charge_to_invoice(session, context, int(charge_id))
    await session.commit()
    return {"data": document}


@router.post("/attachments/presign")
async def presign_attachment(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("attachment.upload")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {
        "data": await service.presign(
            session,
            str(payload.get("file_name") or payload.get("fileName") or "file"),
            str(payload.get("mime_type") or payload.get("mimeType") or ""),
        )
    }


@router.get("/attachments")
async def list_attachments(
    module: str | None = None,
    record_no: str | None = None,
    context: RequestContext = Depends(require_permission("attachment.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_attachments(session, context, module or "", record_no or "")}


@router.delete("/attachments")
async def delete_attachments(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("attachment.delete")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Soft-delete attachments so they stop being listed, served, or linked."""
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    return {"data": {"removed": await service.delete_attachments(session, context, ids)}}


@router.get("/attachments/file/{storage_key:path}")
async def download_attachment(
    storage_key: str,
    context: RequestContext = Depends(require_permission("attachment.read")),
) -> Response:
    content, content_type = await service.read_attachment(storage_key)
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{os.path.basename(storage_key).replace(chr(34), "")}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/attachments/upload", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    storage_key: str | None = Form(default=None),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    context.require("attachment.upload")
    content = await file.read(settings.upload_max_size_mb * 1024 * 1024 + 1)
    return {"data": await service.store_upload(session, context, file.filename or "file", file.content_type or "", content, storage_key)}

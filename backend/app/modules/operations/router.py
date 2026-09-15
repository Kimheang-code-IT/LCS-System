from __future__ import annotations

import os

from fastapi import APIRouter, Body, Depends, File, Form, Header, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context, require_permission
from app.core.pagination import PageParams, page_params
from app.modules.audit.service import write_audit
from app.modules.operations import service
from app.modules.operations import service_order_tabs as dynamic_tabs

router = APIRouter()


async def _resolve_order_id(session: AsyncSession, context: RequestContext, identifier: str) -> int:
    order = await service.resolve_order(session, context, identifier)
    return order.id


@router.get("/service-orders/{identifier}/dynamic-tabs")
async def list_dynamic_tabs(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order_id = await _resolve_order_id(session, context, identifier)
    return {"data": await dynamic_tabs.bootstrap(session, context, order_id)}


@router.get("/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows")
async def list_dynamic_rows(
    identifier: str,
    tab_id: int,
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order_id = await _resolve_order_id(session, context, identifier)
    return {"data": await dynamic_tabs.list_rows(session, context, order_id, tab_id, page)}


@router.post("/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows", status_code=status.HTTP_201_CREATED)
async def create_dynamic_row(
    identifier: str,
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order_id = await _resolve_order_id(session, context, identifier)
    row = await dynamic_tabs.create_row(session, context, order_id, tab_id, payload)
    await write_audit(
        session, context, event_type="DYNAMIC_ROW_CREATED", entity_type="service_order_tab_row", entity_id=int(row["id"]), action="create"
    )
    await session.commit()
    return {"data": row}


@router.post("/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows/bulk")
async def bulk_save_dynamic_rows(
    identifier: str,
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order_id = await _resolve_order_id(session, context, identifier)
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if rows is None and isinstance(payload, dict):
        rows = payload.get("items") or []
    result = await dynamic_tabs.bulk_save(session, context, order_id, tab_id, rows or [])
    await write_audit(
        session,
        context,
        event_type="DYNAMIC_TAB_SAVED",
        entity_type="service_order",
        entity_id=order_id,
        action="bulk_save",
        after={"tabId": str(tab_id), "rowCount": len(result["items"])},
    )
    await session.commit()
    return {"data": result}


@router.patch("/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows/{row_id}")
async def update_dynamic_row(
    identifier: str,
    tab_id: int,
    row_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order_id = await _resolve_order_id(session, context, identifier)
    return {"data": await dynamic_tabs.update_row(session, context, order_id, tab_id, row_id, payload)}


@router.delete("/service-orders/{identifier}/dynamic-tabs/{tab_id}/rows/{row_id}")
async def delete_dynamic_row(
    identifier: str,
    tab_id: int,
    row_id: int,
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order_id = await _resolve_order_id(session, context, identifier)
    result = await dynamic_tabs.delete_row(session, context, order_id, tab_id, row_id)
    await write_audit(
        session,
        context,
        event_type="DYNAMIC_ROW_DELETED",
        entity_type="service_order_tab_row",
        entity_id=row_id,
        action="delete",
    )
    await session.commit()
    return {"data": result}


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
    for order_id in ids:
        order = await session.get(service.ServiceOrder, order_id)
        if order is not None and order.organization_id == context.organization_id:
            await session.delete(order)
    await session.commit()
    return {"data": {"removed": len(ids)}}


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
    await write_audit(
        session,
        context,
        event_type="CONTAINER_ADDED",
        entity_type="container",
        entity_id=int(container["id"]),
        action="create",
        after={"containerNumber": container.get("containerNumber")},
    )
    await session.commit()
    return {"data": container}


@router.get("/service-orders/{identifier}/components")
async def list_components(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_components(session, context, identifier)}


@router.post("/service-orders/{identifier}/components", status_code=status.HTTP_201_CREATED)
async def add_component(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.ensure_component(session, context, identifier, payload)}


@router.get("/service-orders/{identifier}/charges")
async def list_order_charges(
    identifier: str,
    context: RequestContext = Depends(require_permission("service_charge.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    order = await service.resolve_order(session, context, identifier)
    from sqlalchemy import select

    from app.modules.operations.models import ServiceOrderCharge

    rows = (
        await session.execute(select(ServiceOrderCharge).where(ServiceOrderCharge.service_order_id == order.id))
    ).scalars().all()
    return {"data": [service.charge_record(row, row.data or {}) for row in rows]}


@router.post("/service-orders/{identifier}/charges", status_code=status.HTTP_201_CREATED)
async def create_order_charge(
    identifier: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_charge.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.save_charge(session, context, payload, order_identifier=identifier)}


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


@router.post("/service-order-components/{component_id}/values")
async def save_component_values(
    component_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.replace_component_values(session, context, component_id, payload.get("values") or [])}


@router.put("/service-order-components/{component_id}/values")
async def put_component_values(
    component_id: str,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.replace_component_values(session, context, component_id, payload.get("values") or [])}


@router.post("/service-order-components/{component_id}/complete")
async def complete_component(
    component_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    component = await service.complete_component(session, context, component_id)
    await write_audit(
        session,
        context,
        event_type="COMPONENT_COMPLETED",
        entity_type="service_order_component",
        entity_id=int(component_id),
        action="complete",
    )
    await session.commit()
    return {"data": component}


@router.get("/service-order-components/{component_id}")
async def get_component(
    component_id: str,
    context: RequestContext = Depends(require_permission("service_order.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.modules.operations.models import ServiceOrderComponent

    component = await session.get(ServiceOrderComponent, int(component_id))
    if component is None:
        from app.core.exceptions import NotFound

        raise NotFound("Component not found.")
    return {"data": await service._component_payload(session, component)}


@router.delete("/service-order-components/{component_id}")
async def delete_component(
    component_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("service_order.update")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.remove_component(session, context, component_id)}


@router.get("/service-charges")
async def list_service_charges(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("service_charge.create")),
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
    context: RequestContext = Depends(require_permission("service_charge.create")),
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
    from app.modules.operations.models import ServiceOrderCharge

    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    for charge_id in ids:
        charge = await session.get(ServiceOrderCharge, charge_id)
        if charge is not None and charge.organization_id == context.organization_id and charge.status == "DRAFT":
            await session.delete(charge)
    await session.commit()
    return {"data": {"removed": len(ids)}}


@router.post("/service-charges/{charge_id}/issue")
async def issue_service_charge(
    charge_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(require_permission("service_charge.issue")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    charge = await service.issue_charge(session, context, int(charge_id))
    await write_audit(
        session,
        context,
        event_type="SERVICE_CHARGE_ISSUED",
        entity_type="service_order_charge",
        entity_id=int(charge_id),
        action="issue",
    )
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
    await write_audit(
        session,
        context,
        event_type="SERVICE_CHARGE_CONVERTED",
        entity_type="service_order_charge",
        entity_id=int(charge_id),
        action="convert_to_invoice",
        after={"documentId": document.get("id")},
    )
    await session.commit()
    return {"data": document}


@router.post("/attachments/presign")
async def presign_attachment(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("attachment.upload")),
) -> dict:
    return {
        "data": service.presign(
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


@router.post("/attachments", status_code=status.HTTP_201_CREATED)
async def create_attachment(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("attachment.upload")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {
        "data": service.presign(
            str(payload.get("file_name") or payload.get("fileName") or "file"),
            str(payload.get("mime_type") or payload.get("mimeType") or ""),
        )
    }


@router.get("/attachments/file/{storage_key:path}")
async def download_attachment(
    storage_key: str,
    context: RequestContext = Depends(require_permission("attachment.read")),
) -> Response:
    content, content_type = await service.read_attachment(storage_key)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{os.path.basename(storage_key)}"'},
    )


@router.post("/attachments/upload", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    storage_key: str | None = Form(default=None),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    context.require("attachment.upload")
    content = await file.read()
    return {"data": await service.store_upload(session, context, file.filename or "file", file.content_type or "", content, storage_key)}

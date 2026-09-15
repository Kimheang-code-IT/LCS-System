from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context
from app.core.pagination import PageParams, page_params
from app.modules.master_data import service
from app.modules.master_data import service_order_tabs as tab_config_service


def _read_guard(context: RequestContext) -> RequestContext:
    if not (context.has_permission("master.reference.view") or context.has_permission("configuration.manage")):
        from app.core.exceptions import AccessDenied

        raise AccessDenied("Missing permission: master.reference.view")
    return context


def _write_guard(context: RequestContext) -> RequestContext:
    from app.core.exceptions import AccessDenied

    if not (
        context.has_permission("master.reference.manage")
        or context.has_permission("configuration.manage")
        or context.is_platform_admin
    ):
        raise AccessDenied("Missing permission: master.reference.manage")
    return context


def _config_read_guard(context: RequestContext) -> RequestContext:
    from app.core.exceptions import AccessDenied

    if not (
        context.has_permission("service_order_config.view")
        or context.has_permission("service_order.read")
        or context.has_permission("configuration.manage")
        or context.is_platform_admin
    ):
        raise AccessDenied("Missing permission: service_order_config.view")
    return context


def _config_manage_guard(context: RequestContext, action: str) -> RequestContext:
    from app.core.exceptions import AccessDenied

    code = f"service_order_config.{action}"
    if not (
        context.has_permission(code)
        or context.has_permission("configuration.manage")
        or context.is_platform_admin
    ):
        raise AccessDenied(f"Missing permission: {code}")
    return context


router = APIRouter()


def _register(collection: str) -> None:
    async def list_items(
        page: PageParams = Depends(page_params),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _read_guard(context)
        return {"data": await service.list_reference(session, context, collection, page)}

    async def create_item(
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        return {"data": await service.create_reference(session, collection, payload)}

    async def get_item(
        item_id: str,
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _read_guard(context)
        return {"data": await service.get_reference(session, collection, _as_int(item_id))}

    async def update_item(
        item_id: str,
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        return {"data": await service.update_reference(session, collection, _as_int(item_id), payload)}

    async def delete_item(
        item_id: str,
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        await service.delete_reference(session, collection, [_as_int(item_id)])
        return {"data": {"removed": True}}

    async def bulk_delete(
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        raw_ids = payload.get("ids") or []
        await service.delete_reference(session, collection, [_as_int(value) for value in raw_ids])
        return {"data": {"removed": len(raw_ids)}}

    router.add_api_route(f"/{collection}", list_items, methods=["GET"], name=f"list_{collection}")
    router.add_api_route(f"/{collection}", create_item, methods=["POST"], status_code=status.HTTP_201_CREATED, name=f"create_{collection}")
    router.add_api_route(f"/{collection}", bulk_delete, methods=["DELETE"], name=f"delete_{collection}")
    router.add_api_route(f"/{collection}/bulk-delete", bulk_delete, methods=["POST"], name=f"bulk_delete_{collection}")
    router.add_api_route(f"/{collection}/{{item_id}}", get_item, methods=["GET"], name=f"get_{collection}")
    router.add_api_route(f"/{collection}/{{item_id}}", update_item, methods=["PUT"], name=f"update_{collection}")
    router.add_api_route(f"/{collection}/{{item_id}}", delete_item, methods=["DELETE"], name=f"delete_{collection}")


def _as_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        from app.core.exceptions import NotFound

        raise NotFound() from None


def _register_generic(collection: str) -> None:
    async def list_items(
        page: PageParams = Depends(page_params),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _read_guard(context)
        return {"data": await service.list_generic(session, context, collection, page)}

    async def create_item(
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        return {"data": await service.create_generic(session, context, collection, payload)}

    async def get_item(
        item_id: str,
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _read_guard(context)
        return {"data": await service.get_generic(session, context, collection, _as_int(item_id))}

    async def update_item(
        item_id: str,
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        return {"data": await service.update_generic(session, context, collection, _as_int(item_id), payload)}

    async def delete_item(
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        raw_ids = payload.get("ids") or []
        await service.delete_generic(session, context, collection, [_as_int(value) for value in raw_ids])
        return {"data": {"removed": len(raw_ids)}}

    router.add_api_route(f"/{collection}", list_items, methods=["GET"], name=f"list_{collection}")
    router.add_api_route(f"/{collection}", create_item, methods=["POST"], status_code=status.HTTP_201_CREATED, name=f"create_{collection}")
    router.add_api_route(f"/{collection}", delete_item, methods=["DELETE"], name=f"delete_{collection}")
    router.add_api_route(f"/{collection}/{{item_id}}", get_item, methods=["GET"], name=f"get_{collection}")
    router.add_api_route(f"/{collection}/{{item_id}}", update_item, methods=["PUT"], name=f"update_{collection}")


@router.get("/service-order-tabs")
async def list_service_order_tabs(
    page: PageParams = Depends(page_params),
    include_archived: bool = False,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await tab_config_service.list_tabs(session, context, page, include_archived)}


@router.post("/service-order-tabs", status_code=status.HTTP_201_CREATED)
async def create_service_order_tab(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {"data": await tab_config_service.create_tab(session, context, payload)}


@router.get("/service-order-tabs/{tab_id}/columns")
async def list_service_order_columns(
    tab_id: int,
    include_archived: bool = False,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await tab_config_service.list_columns(session, context, tab_id, include_archived)}


@router.post("/service-order-tabs/{tab_id}/columns", status_code=status.HTTP_201_CREATED)
async def create_service_order_column(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {"data": await tab_config_service.create_column(session, context, tab_id, payload)}


@router.post("/service-order-tabs/{tab_id}/columns/reorder")
async def reorder_service_order_columns(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    ordered = [int(value) for value in payload.get("orderedIds") or payload.get("ids") or [] if str(value).isdigit()]
    return {"data": await tab_config_service.reorder_columns(session, context, tab_id, ordered)}


@router.patch("/service-order-tabs/{tab_id}")
async def update_service_order_tab(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await tab_config_service.update_tab(session, context, tab_id, payload)}


@router.delete("/service-order-tabs/{tab_id}")
async def delete_service_order_tab(
    tab_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await tab_config_service.delete_tab(session, context, tab_id)}


@router.patch("/service-order-columns/{column_id}")
async def update_service_order_column(
    column_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await tab_config_service.update_column(session, context, column_id, payload)}


@router.delete("/service-order-columns/{column_id}")
async def delete_service_order_column(
    column_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await tab_config_service.delete_column(session, context, column_id)}


@router.get("/service-order-tabs/meta/column-types")
async def service_order_column_types(
    context: RequestContext = Depends(get_current_context),
) -> dict:
    _config_read_guard(context)
    return {
        "data": {
            "columnTypes": list(tab_config_service.COLUMN_TYPES),
            "referenceTypes": list(tab_config_service.REFERENCE_TYPES),
        }
    }


@router.get("/ui-schemas/{page:path}")
async def get_ui_schema(
    page: str,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from sqlalchemy import select

    from app.modules.master_data.models import ModuleRecord

    row = (
        await session.execute(
            select(ModuleRecord).where(
                ModuleRecord.organization_id == context.organization_id,
                ModuleRecord.collection == "__ui_schema__",
                ModuleRecord.record_no == page,
            )
        )
    ).scalars().first()
    return {"data": (row.data if row else None)}


for _collection in service.SPECS:
    _register(_collection)

for _collection in sorted(service.GENERIC_COLLECTIONS):
    _register_generic(_collection)

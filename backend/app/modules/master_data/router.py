from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context
from app.core.pagination import PageParams, page_params
from app.modules.master_data import component_config as component_config_service
from app.modules.master_data import service


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
        await service.delete_reference(session, context, collection, [_as_int(item_id)])
        return {"data": {"removed": True}}

    async def bulk_delete(
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _write_guard(context)
        raw_ids = payload.get("ids") or []
        await service.delete_reference(session, context, collection, [_as_int(value) for value in raw_ids])
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
                ModuleRecord.collection == "__ui_schema__",
                ModuleRecord.record_no == page,
            )
        )
    ).scalars().first()
    return {"data": (row.data if row else None)}


@router.get("/component-tabs/meta/types")
async def component_config_types(
    context: RequestContext = Depends(get_current_context),
) -> dict:
    _config_read_guard(context)
    return {
        "data": {
            "dataTypes": list(component_config_service.DATA_TYPES),
            "referenceTypes": list(component_config_service.REFERENCE_TYPES),
            "renderModes": list(component_config_service.RENDER_MODES),
        }
    }


# --- Component attributes ----------------------------------------------------
@router.get("/component-attributes")
async def list_component_attributes(
    page: PageParams = Depends(page_params),
    include_archived: bool = False,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await component_config_service.list_attributes(session, context, page, include_archived)}


@router.post("/component-attributes", status_code=status.HTTP_201_CREATED)
async def create_component_attribute(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {"data": await component_config_service.create_attribute(session, context, payload)}


@router.patch("/component-attributes/{attribute_id}")
async def update_component_attribute(
    attribute_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await component_config_service.update_attribute(session, context, attribute_id, payload)}


@router.delete("/component-attributes/{attribute_id}")
async def delete_component_attribute(
    attribute_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await component_config_service.delete_attribute(session, context, attribute_id)}


# --- Component groups --------------------------------------------------------
@router.get("/component-groups")
async def list_component_groups(
    page: PageParams = Depends(page_params),
    include_archived: bool = False,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await component_config_service.list_groups(session, context, page, include_archived)}


@router.post("/component-groups", status_code=status.HTTP_201_CREATED)
async def create_component_group(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {"data": await component_config_service.create_group(session, context, payload)}


@router.get("/component-groups/{group_id}/attributes")
async def list_component_group_attributes(
    group_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await component_config_service.list_group_attributes(session, context, group_id)}


@router.post("/component-groups/{group_id}/attributes", status_code=status.HTTP_201_CREATED)
async def add_component_group_attribute(
    group_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await component_config_service.add_group_attribute(session, context, group_id, payload)}


@router.post("/component-groups/{group_id}/attributes/reorder")
async def reorder_component_group_attributes(
    group_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    ordered = [int(value) for value in payload.get("orderedIds") or payload.get("ids") or [] if str(value).isdigit()]
    return {"data": await component_config_service.reorder_group_attributes(session, context, group_id, ordered)}


@router.patch("/component-groups/{group_id}")
async def update_component_group(
    group_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await component_config_service.update_group(session, context, group_id, payload)}


@router.delete("/component-groups/{group_id}")
async def delete_component_group(
    group_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await component_config_service.delete_group(session, context, group_id)}


@router.patch("/component-group-attributes/{membership_id}")
async def update_component_group_attribute(
    membership_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await component_config_service.update_group_attribute(session, context, membership_id, payload)}


@router.delete("/component-group-attributes/{membership_id}")
async def remove_component_group_attribute(
    membership_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await component_config_service.remove_group_attribute(session, context, membership_id)}


# --- Component tabs ----------------------------------------------------------
@router.get("/component-tabs")
async def list_component_tabs(
    page: PageParams = Depends(page_params),
    include_archived: bool = False,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await component_config_service.list_tabs(session, context, page, include_archived)}


@router.post("/component-tabs", status_code=status.HTTP_201_CREATED)
async def create_component_tab(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {"data": await component_config_service.create_tab(session, context, payload)}


@router.get("/component-tabs/{tab_id}")
async def get_component_tab(
    tab_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await component_config_service._tab_detail(session, context, tab_id)}


@router.patch("/component-tabs/{tab_id}")
async def update_component_tab(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await component_config_service.update_tab(session, context, tab_id, payload)}


@router.delete("/component-tabs/{tab_id}")
async def delete_component_tab(
    tab_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await component_config_service.delete_tab(session, context, tab_id)}


@router.get("/component-tabs/{tab_id}/groups")
async def list_component_tab_groups(
    tab_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await component_config_service.list_tab_groups(session, context, tab_id)}


@router.post("/component-tabs/{tab_id}/groups", status_code=status.HTTP_201_CREATED)
async def add_component_tab_group(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await component_config_service.add_tab_group(session, context, tab_id, payload)}


@router.post("/component-tabs/{tab_id}/groups/reorder")
async def reorder_component_tab_groups(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    ordered = [int(value) for value in payload.get("orderedIds") or payload.get("ids") or [] if str(value).isdigit()]
    return {"data": await component_config_service.reorder_tab_groups(session, context, tab_id, ordered)}


@router.delete("/component-tab-groups/{tab_group_id}")
async def remove_component_tab_group(
    tab_group_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await component_config_service.remove_tab_group(session, context, tab_group_id)}


@router.post("/component-tabs/{tab_id}/trade-directions")
async def set_component_tab_directions(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    direction_ids = [int(value) for value in payload.get("tradeDirectionIds") or [] if str(value).isdigit()]
    return {"data": await component_config_service.set_tab_directions(session, context, tab_id, direction_ids)}


for _collection in service.SPECS:
    _register(_collection)

for _collection in sorted(service.GENERIC_COLLECTIONS):
    _register_generic(_collection)

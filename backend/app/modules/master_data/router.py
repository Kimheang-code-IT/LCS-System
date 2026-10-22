from __future__ import annotations

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context
from app.core.pagination import PageParams, page_params
from app.core.validation import validate_id_list
from app.modules.master_data import component_config as component_config_service
from app.modules.master_data import config_versions, service
from app.modules.master_data.schemas import (
    ComponentAttributeCreate,
    ComponentAttributeUpdate,
    ComponentGroupAttributeCreate,
    ComponentGroupAttributeUpdate,
    ComponentGroupCreate,
    ComponentGroupUpdate,
    ComponentTabCreate,
    ComponentTabGroupCreate,
    ComponentTabGroupLayout,
    ComponentTabUpdate,
    ConfigurationPublishRequest,
    ConfigurationRollbackRequest,
    ConfigurationVersionUpdate,
)


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


#: Reference collections that have their own matrix page. Collections without an
#: entry keep the coarse ``master.reference`` guard.
_COLLECTION_PAGE_PREFIX: dict[str, str] = {
    "businessParties": "master.business_parties",
    "placeRoles": "master.place_roles",
    "partyRoles": "master.party_roles",
    "tradeDirections": "master.trade_directions",
    "containerTypes": "master.container_types",
    "transportTypes": "master.transport_types",
    "transportAssets": "master.transport_assets",
    "feeTypes": "master.fee_types",
    "currencies": "master.currencies",
    "currencyRates": "master.currencies",
}


def _collection_guard(context: RequestContext, collection: str, action: str) -> RequestContext:
    prefix = _COLLECTION_PAGE_PREFIX.get(collection)
    if not prefix:
        return _read_guard(context) if action == "view" else _write_guard(context)
    if context.is_platform_admin or context.has_permission(f"{prefix}.{action}"):
        return context
    legacy = "master.reference.view" if action == "view" else "master.reference.manage"
    if context.has_permission(legacy):
        return context
    from app.core.exceptions import AccessDenied

    raise AccessDenied(f"Missing permission: {prefix}.{action}")


def _config_read_guard(context: RequestContext) -> RequestContext:
    from app.core.exceptions import AccessDenied

    if not (
        context.has_permission("configuration.read")
        or context.has_permission("service_order_config.view")
        or context.has_permission("configuration.manage")
        or context.is_platform_admin
    ):
        raise AccessDenied("Missing permission: configuration.read")
    return context


def _config_action_guard(context: RequestContext, code: str, *legacy: str) -> RequestContext:
    from app.core.exceptions import AccessDenied

    if context.is_platform_admin or context.has_permission(code) or any(context.has_permission(item) for item in legacy):
        return context
    raise AccessDenied(f"Missing permission: {code}")


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


def _config_publish_guard(context: RequestContext) -> RequestContext:
    """Publishing is stricter than editing: it changes the live form for everyone."""
    from app.core.exceptions import AccessDenied

    if not (
        context.has_permission("service_order_config.publish")
        or context.has_permission("configuration.manage")
        or context.is_platform_admin
    ):
        raise AccessDenied("Missing permission: service_order_config.publish")
    return context


router = APIRouter()


def _register(collection: str) -> None:
    async def list_items(
        page: PageParams = Depends(page_params),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _collection_guard(context, collection, "view")
        return {"data": await service.list_reference(session, context, collection, page)}

    async def create_item(
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _collection_guard(context, collection, "create")
        return {"data": await service.create_reference(session, collection, payload)}

    async def get_item(
        item_id: str,
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _collection_guard(context, collection, "view")
        return {"data": await service.get_reference(session, collection, _as_int(item_id))}

    async def update_item(
        item_id: str,
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _collection_guard(context, collection, "update")
        return {"data": await service.update_reference(session, collection, _as_int(item_id), payload)}

    async def delete_item(
        item_id: str,
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _collection_guard(context, collection, "delete")
        await service.delete_reference(session, context, collection, [_as_int(item_id)])
        return {"data": {"removed": True}}

    async def bulk_delete(
        payload: dict = Body(default={}),
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        _collection_guard(context, collection, "delete")
        ids = validate_id_list(payload)
        await service.delete_reference(session, context, collection, ids)
        return {"data": {"removed": len(ids)}}

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
        ids = validate_id_list(payload)
        await service.delete_generic(session, context, collection, ids)
        return {"data": {"removed": len(ids)}}

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
    _read_guard(context)
    return {"data": await service.get_ui_schema(session, page)}


@router.get("/configuration-versions")
async def list_configuration_versions(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await config_versions.list_versions(session, context, page)}


@router.get("/configuration-versions/active")
async def active_configuration_version(
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await config_versions.active_version(session, context)}


@router.get("/configuration-versions/activation-history")
async def configuration_activation_history(
    page: PageParams = Depends(page_params),
    version_id: int | None = None,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await config_versions.activation_history(session, context, page, version_id)}


@router.get("/configuration-versions/preview")
async def preview_configuration_version(
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await config_versions.preview(session, context)}


@router.post("/configuration-versions", status_code=status.HTTP_201_CREATED)
async def publish_configuration_version(
    payload: ConfigurationPublishRequest,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_action_guard(context, "configuration.publish", "service_order_config.publish", "configuration.manage")
    return {
        "data": await config_versions.publish(
            session, context, payload.changeNote
        )
    }


@router.get("/configuration-versions/{version_id}")
async def get_configuration_version(
    version_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await config_versions.get_version(session, context, version_id)}


@router.patch("/configuration-versions/{version_id}")
async def update_configuration_version(
    version_id: int,
    payload: ConfigurationVersionUpdate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {"data": await config_versions.update_draft(session, context, version_id, payload.changeNote)}


@router.delete("/configuration-versions/{version_id}")
async def delete_configuration_version(
    version_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await config_versions.delete_draft(session, context, version_id)}


@router.get("/configuration-versions/{version_id}/preview")
async def preview_configuration_version_snapshot(
    version_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await config_versions.preview_version(session, context, version_id)}


@router.get("/configuration-versions/{version_id}/activate-history")
async def configuration_version_activation_history(
    version_id: int,
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_read_guard(context)
    return {"data": await config_versions.activation_history(session, context, page, version_id)}


@router.get("/configuration-versions/{version_id}/compare/{other_version_id}")
async def compare_configuration_versions(
    version_id: int,
    other_version_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_action_guard(context, "configuration.compare", "configuration.read", "configuration.manage")
    return {"data": await config_versions.compare(session, context, version_id, other_version_id)}


@router.post("/configuration-versions/{version_id}/activate")
async def activate_configuration_version(
    version_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_action_guard(context, "configuration.activate", "configuration.manage")
    return {"data": await config_versions.activate(session, context, version_id)}


@router.post("/configuration-versions/{version_id}/rollback", status_code=status.HTTP_201_CREATED)
async def rollback_configuration_version(
    version_id: int,
    payload: ConfigurationRollbackRequest,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_action_guard(context, "configuration.rollback", "configuration.manage")
    return {"data": await config_versions.rollback(session, context, version_id, payload.reason)}


@router.post("/configuration-versions/{version_id}/retire")
async def retire_configuration_version(
    version_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_action_guard(context, "configuration.publish", "service_order_config.publish", "configuration.manage")
    return {"data": await config_versions.retire(session, context, version_id)}


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
            "displayModes": list(component_config_service.LAYOUT_DISPLAY_MODES),
            "dataCardinalities": list(component_config_service.DATA_CARDINALITIES),
            "formColumnCounts": list(component_config_service.FORM_COLUMN_COUNTS),
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
    payload: ComponentAttributeCreate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {
        "data": await component_config_service.create_attribute(
            session, context, payload.model_dump(exclude_unset=True)
        )
    }


@router.patch("/component-attributes/{attribute_id}")
async def update_component_attribute(
    attribute_id: int,
    payload: ComponentAttributeUpdate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {
        "data": await component_config_service.update_attribute(
            session, context, attribute_id, payload.model_dump(exclude_unset=True)
        )
    }


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
    payload: ComponentGroupCreate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {
        "data": await component_config_service.create_group(
            session, context, payload.model_dump(exclude_unset=True)
        )
    }


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
    payload: ComponentGroupAttributeCreate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {
        "data": await component_config_service.add_group_attribute(
            session, context, group_id, payload.model_dump(exclude_unset=True)
        )
    }


@router.post("/component-groups/{group_id}/attributes/reorder")
async def reorder_component_group_attributes(
    group_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    ordered = validate_id_list({"ids": payload.get("orderedIds") or payload.get("ids") or []})
    return {"data": await component_config_service.reorder_group_attributes(session, context, group_id, ordered)}


@router.patch("/component-groups/{group_id}")
async def update_component_group(
    group_id: int,
    payload: ComponentGroupUpdate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {
        "data": await component_config_service.update_group(
            session, context, group_id, payload.model_dump(exclude_unset=True)
        )
    }


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
    payload: ComponentGroupAttributeUpdate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {
        "data": await component_config_service.update_group_attribute(
            session, context, membership_id, payload.model_dump(exclude_unset=True)
        )
    }


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
    payload: ComponentTabCreate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "create")
    return {
        "data": await component_config_service.create_tab(
            session, context, payload.model_dump(exclude_unset=True)
        )
    }


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
    payload: ComponentTabUpdate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {
        "data": await component_config_service.update_tab(
            session, context, tab_id, payload.model_dump(exclude_unset=True)
        )
    }


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
    payload: ComponentTabGroupCreate,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    return {
        "data": await component_config_service.add_tab_group(
            session, context, tab_id, payload.model_dump(exclude_unset=True)
        )
    }


@router.patch("/component-tab-groups/{tab_group_id}")
async def update_component_tab_group(
    tab_group_id: int,
    payload: ComponentTabGroupLayout,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update one group's layout within its tab."""
    _config_manage_guard(context, "update")
    return {
        "data": await component_config_service.update_tab_group(
            session, context, tab_group_id, payload.model_dump(exclude_unset=True)
        )
    }


@router.post("/component-tabs/{tab_id}/groups/reorder")
async def reorder_component_tab_groups(
    tab_id: int,
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "update")
    ordered = validate_id_list({"ids": payload.get("orderedIds") or payload.get("ids") or []})
    return {"data": await component_config_service.reorder_tab_groups(session, context, tab_id, ordered)}


@router.delete("/component-tab-groups/{tab_group_id}")
async def remove_component_tab_group(
    tab_group_id: int,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _config_manage_guard(context, "delete")
    return {"data": await component_config_service.remove_tab_group(session, context, tab_group_id)}


for _collection in service.SPECS:
    _register(_collection)

for _collection in sorted(service.GENERIC_COLLECTIONS):
    _register_generic(_collection)

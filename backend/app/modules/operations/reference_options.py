"""Resolve reference-type option maps shared by Service Order dynamic forms."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.modules.auth.models import User
from app.modules.master_data.models import (
    BusinessParty,
    FeeType,
    Place,
    TransportAsset,
    TransportType,
)
from app.modules.operations.models import ServiceOrderContainer

REFERENCE_TYPES = (
    "business_party",
    "place",
    "transport_asset",
    "transport_type",
    "container",
    "fee_type",
    "user",
)


async def _reference_options(
    session: AsyncSession, context: RequestContext, reference_type: str, order_id: int
) -> dict[int, str]:
    if reference_type == "business_party":
        rows = (
            await session.execute(
                select(BusinessParty.id, BusinessParty.legal_name).where(BusinessParty.status == "ACTIVE")
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "place":
        rows = (await session.execute(select(Place.id, Place.name).where(Place.status == "ACTIVE"))).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "transport_asset":
        rows = (
            await session.execute(
                select(TransportAsset.id, TransportAsset.identity).where(TransportAsset.status == "ACTIVE")
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "transport_type":
        rows = (await session.execute(select(TransportType.id, TransportType.name))).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "fee_type":
        rows = (await session.execute(select(FeeType.id, FeeType.name))).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "container":
        rows = (
            await session.execute(
                select(ServiceOrderContainer.id, ServiceOrderContainer.container_number).where(
                    ServiceOrderContainer.service_order_id == order_id
                )
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}
    if reference_type == "user":
        rows = (await session.execute(select(User.id, User.display_name).where(User.status == "ACTIVE"))).all()
        return {int(row[0]): str(row[1]) for row in rows}
    return {}


async def reference_options(
    session: AsyncSession, context: RequestContext, order_id: int, reference_types: list[str] | None = None
) -> dict[str, dict[str, str]]:
    types = reference_types or list(REFERENCE_TYPES)
    result: dict[str, dict[str, str]] = {}
    for reference_type in types:
        options = await _reference_options(session, context, reference_type, order_id)
        result[reference_type] = {str(key): label for key, label in options.items()}
    return result

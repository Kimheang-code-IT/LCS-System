from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, count_query, list_sort_orders
from app.modules.operations.models import (
    ServiceOrder,
    ServiceOrderCharge,
    ServiceOrderContainer,
    ServiceOrderContainerRequirement,
)


class OperationsRepository:
    """Persistence and aggregate loading for operational records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_order(self, identifier: str | int) -> ServiceOrder | None:
        text = str(identifier)
        if text.isdigit():
            order = await self.session.get(ServiceOrder, int(text))
            if order is not None:
                return order
        result = await self.session.execute(
            select(ServiceOrder).where(ServiceOrder.service_order_no == text)
        )
        return result.scalars().first()

    async def order_page(self, page: PageParams, *, status: str | None) -> tuple[list[ServiceOrder], int]:
        stmt = select(ServiceOrder)
        if status:
            stmt = stmt.where(ServiceOrder.status == status)
        if page.q:
            pattern = f"%{page.q}%"
            stmt = stmt.where(
                ServiceOrder.service_order_no.ilike(pattern)
                | ServiceOrder.data["customer"].as_string().ilike(pattern)
            )
        total = await count_query(self.session, stmt)
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(ServiceOrder, page, ServiceOrder.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    async def order_containers(
        self, order_id: int
    ) -> tuple[list[ServiceOrderContainer], list[ServiceOrderContainerRequirement]]:
        containers = list(
            (
                await self.session.execute(
                    select(ServiceOrderContainer).where(ServiceOrderContainer.service_order_id == order_id)
                )
            ).scalars().all()
        )
        requirements = list(
            (
                await self.session.execute(
                    select(ServiceOrderContainerRequirement).where(
                        ServiceOrderContainerRequirement.service_order_id == order_id
                    )
                )
            ).scalars().all()
        )
        return containers, requirements

    async def orders_by_ids(self, ids: list[int]) -> list[ServiceOrder]:
        if not ids:
            return []
        result = await self.session.execute(select(ServiceOrder).where(ServiceOrder.id.in_(set(ids))))
        return list(result.scalars().all())

    async def charges_by_ids(self, ids: list[int]) -> list[ServiceOrderCharge]:
        if not ids:
            return []
        result = await self.session.execute(
            select(ServiceOrderCharge).where(ServiceOrderCharge.id.in_(set(ids)))
        )
        return list(result.scalars().all())

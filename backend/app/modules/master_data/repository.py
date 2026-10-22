from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, count_query, list_sort_orders
from app.modules.master_data.models import ModuleRecord


class MasterDataRepository:
    """Query component for typed references and generic configuration rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reference_page(
        self,
        model: type,
        *,
        search_columns: tuple[str, ...],
        status_field: str,
        page: PageParams,
        order_by: tuple[str, ...] = (),
    ) -> tuple[list[Any], int]:
        stmt = select(model).where(model.deleted_at.is_(None))
        if page.q:
            pattern = f"%{page.q}%"
            conditions = [getattr(model, column).ilike(pattern) for column in search_columns]
            if conditions:
                stmt = stmt.where(or_(*conditions))
        if page.status:
            stmt = stmt.where(getattr(model, status_field) == page.status)
        total = await count_query(self.session, stmt)
        default_order = [getattr(model, column) for column in order_by] or [model.id.desc()]
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(model, page, *default_order))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    async def reference(self, model: type, record_id: int) -> Any | None:
        row = await self.session.get(model, record_id)
        return row if row is not None and row.deleted_at is None else None

    async def references(self, model: type, ids: list[int]) -> list[Any]:
        if not ids:
            return []
        result = await self.session.execute(select(model).where(model.id.in_(set(ids))))
        return list(result.scalars().all())

    async def generic_page(self, collection: str, page: PageParams) -> tuple[list[ModuleRecord], int]:
        stmt = select(ModuleRecord).where(
            ModuleRecord.collection == collection,
            ModuleRecord.deleted_at.is_(None),
        )
        if page.q:
            stmt = stmt.where(ModuleRecord.data["name"].as_string().ilike(f"%{page.q}%"))
        if page.status:
            stmt = stmt.where(ModuleRecord.status == page.status)
        total = await count_query(self.session, stmt)
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(ModuleRecord, page, ModuleRecord.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    async def generic(self, collection: str, record_id: int) -> ModuleRecord | None:
        row = await self.session.get(ModuleRecord, record_id)
        if row is None or row.collection != collection or row.deleted_at is not None:
            return None
        return row

    async def generic_by_record_no(self, collection: str, record_no: str) -> ModuleRecord | None:
        result = await self.session.execute(
            select(ModuleRecord).where(
                ModuleRecord.collection == collection,
                ModuleRecord.record_no == record_no,
                ModuleRecord.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    def add(self, row: Any) -> None:
        self.session.add(row)

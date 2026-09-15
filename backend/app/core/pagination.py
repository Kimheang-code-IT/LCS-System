from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, TypeVar

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


@dataclass
class PageParams:
    page: int = 1
    page_size: int = 50
    q: str | None = None
    status: str | None = None
    sort_by: str | None = None
    sort_order: str = "desc"
    from_date: str | None = None
    to_date: str | None = None
    branch_id: int | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_order: str = Query("desc"),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    branch_id: int | None = Query(None),
    sortKey: str | None = Query(None),
    sortDir: str | None = Query(None),
    dateFrom: str | None = Query(None),
    dateTo: str | None = Query(None),
) -> PageParams:
    effective_sort = sort_by or sortKey
    effective_dir = sort_order if sort_by else (sortDir or sort_order)
    return PageParams(
        page=page,
        page_size=page_size,
        q=q,
        status=status,
        sort_by=effective_sort,
        sort_order="asc" if str(effective_dir).lower() == "asc" else "desc",
        from_date=from_date or dateFrom,
        to_date=to_date or dateTo,
        branch_id=branch_id,
    )


def page_meta(page: PageParams, total: int) -> dict[str, int]:
    return {"page": page.page, "page_size": page.page_size, "total": total}


def paged(items: list[Any], page: PageParams, total: int) -> dict[str, Any]:
    return {"items": items, "meta": page_meta(page, total)}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


async def count_query(session: AsyncSession, stmt: Select) -> int:
    return int(await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, list_sort_orders
from app.modules.backup.models import BackupRun


class BackupRunRepository:
    """Read model for backup history; backup orchestration remains in the service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest(self) -> BackupRun | None:
        result = await self.session.execute(select(BackupRun).order_by(BackupRun.id.desc()).limit(1))
        return result.scalars().first()

    async def page(self, page: PageParams) -> tuple[list[BackupRun], int]:
        total = int(await self.session.scalar(select(func.count()).select_from(BackupRun)) or 0)
        result = await self.session.execute(
            select(BackupRun)
            .order_by(*list_sort_orders(BackupRun, page, BackupRun.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

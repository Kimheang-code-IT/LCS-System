from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, count_query, list_sort_orders
from app.modules.master_data.models import BusinessParty
from app.modules.quotations.models import (
    Quotation,
    QuotationConversion,
    QuotationRevision,
)


class QuotationRepository:
    """Persistence for quotation aggregates and revision history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def page(self, page: PageParams, *, status: str | None) -> tuple[list[Quotation], int]:
        stmt = select(Quotation)
        if status:
            stmt = stmt.where(Quotation.status == status)
        if page.q:
            pattern = f"%{page.q}%"
            stmt = stmt.where(
                Quotation.quotation_no.ilike(pattern) | Quotation.data["customer"].as_string().ilike(pattern)
            )
        total = await count_query(self.session, stmt)
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(Quotation, page, Quotation.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    async def latest_revisions(self, quotation_ids: list[int]) -> dict[int, QuotationRevision]:
        if not quotation_ids:
            return {}
        result = await self.session.execute(
            select(QuotationRevision)
            .where(QuotationRevision.quotation_id.in_(quotation_ids))
            .order_by(QuotationRevision.quotation_id, QuotationRevision.revision_no.desc())
        )
        latest: dict[int, QuotationRevision] = {}
        for revision in result.scalars().all():
            latest.setdefault(revision.quotation_id, revision)
        return latest

    async def latest_revision(self, quotation_id: int) -> QuotationRevision | None:
        return (await self.latest_revisions([quotation_id])).get(quotation_id)

    async def conversion_map(self, quotation_ids: list[int]) -> dict[int, tuple[str, str]]:
        if not quotation_ids:
            return {}
        from app.modules.operations.models import ServiceOrder

        result = await self.session.execute(
            select(QuotationRevision.quotation_id, QuotationConversion.service_order_id, ServiceOrder.service_order_no)
            .join(QuotationConversion, QuotationConversion.quotation_revision_id == QuotationRevision.id)
            .join(ServiceOrder, ServiceOrder.id == QuotationConversion.service_order_id)
            .where(QuotationRevision.quotation_id.in_(quotation_ids))
        )
        return {quotation_id: (str(order_id), order_no) for quotation_id, order_id, order_no in result.all()}

    async def party_names(self, party_ids: list[int]) -> dict[int, str]:
        if not party_ids:
            return {}
        result = await self.session.execute(
            select(BusinessParty.id, BusinessParty.legal_name).where(BusinessParty.id.in_(party_ids))
        )
        return dict(result.all())

    async def revisions(self, quotation_id: int) -> list[QuotationRevision]:
        result = await self.session.execute(
            select(QuotationRevision)
            .where(QuotationRevision.quotation_id == quotation_id)
            .order_by(QuotationRevision.revision_no.desc())
        )
        return list(result.scalars().all())

    async def conversion_for_quotation(self, quotation_id: int) -> QuotationConversion | None:
        result = await self.session.execute(
            select(QuotationConversion)
            .join(QuotationRevision, QuotationRevision.id == QuotationConversion.quotation_revision_id)
            .where(QuotationRevision.quotation_id == quotation_id)
        )
        return result.scalars().first()

    async def competing_revisions(self, quotation_id: int, revision_id: int) -> list[QuotationRevision]:
        result = await self.session.execute(
            select(QuotationRevision).where(
                QuotationRevision.quotation_id == quotation_id,
                QuotationRevision.id != revision_id,
                QuotationRevision.status.in_(("SENT", "ACCEPTED")),
            )
        )
        return list(result.scalars().all())

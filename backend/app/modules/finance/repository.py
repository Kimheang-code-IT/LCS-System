from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, count_query, list_sort_orders
from app.modules.finance.models import (
    ChartOfAccount,
    FinancialAccount,
    FinancialDocument,
    FinancialDocumentLine,
    JournalEntry,
    JournalEntryLine,
)


class FinanceRepository:
    """Read/write query component for ledgers and financial documents.

    Posted-document invariants stay in the service layer. This component only
    constructs persistence queries and never commits independently.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def account_page(self, page: PageParams) -> tuple[list[ChartOfAccount], int]:
        stmt = select(ChartOfAccount)
        if page.q:
            pattern = f"%{page.q}%"
            stmt = stmt.where(
                ChartOfAccount.account_code.ilike(pattern) | ChartOfAccount.account_name.ilike(pattern)
            )
        if page.status:
            stmt = stmt.where(ChartOfAccount.status == str(page.status).upper())
        total = await count_query(self.session, stmt)
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(ChartOfAccount, page, ChartOfAccount.account_code))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    async def financial_account_page(self, page: PageParams) -> tuple[list[FinancialAccount], int]:
        stmt = select(FinancialAccount)
        total = await count_query(self.session, stmt)
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(FinancialAccount, page, FinancialAccount.id))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    async def financial_account_details(
        self, accounts: list[FinancialAccount]
    ) -> tuple[dict[int, ChartOfAccount], dict[int, object]]:
        account_ids = {account.account_id for account in accounts if account.account_id}
        if not account_ids:
            return {}, {}
        ledgers = {
            ledger.id: ledger
            for ledger in (
                await self.session.execute(select(ChartOfAccount).where(ChartOfAccount.id.in_(account_ids)))
            ).scalars().all()
        }
        balance_result = await self.session.execute(
            select(
                JournalEntryLine.account_id,
                func.coalesce(
                    func.sum(JournalEntryLine.base_debit_amount - JournalEntryLine.base_credit_amount), 0
                ),
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(JournalEntryLine.account_id.in_(account_ids), JournalEntry.status == "POSTED")
            .group_by(JournalEntryLine.account_id)
        )
        return ledgers, dict(balance_result.all())

    async def document_page(
        self,
        page: PageParams,
        *,
        document_type: str | None = None,
        party_id: int | None = None,
    ) -> tuple[list[FinancialDocument], int]:
        stmt = select(FinancialDocument)
        if document_type:
            stmt = stmt.where(FinancialDocument.document_type == document_type)
        if party_id is not None:
            stmt = stmt.where(FinancialDocument.party_id == party_id)
        if page.status:
            stmt = stmt.where(FinancialDocument.status == str(page.status).upper())
        if page.q:
            pattern = f"%{page.q}%"
            stmt = stmt.where(
                FinancialDocument.document_no.ilike(pattern) | FinancialDocument.description.ilike(pattern)
            )
        total = await count_query(self.session, stmt)
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(FinancialDocument, page, FinancialDocument.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    async def document_lines(self, document_ids: list[int]) -> dict[int, list[FinancialDocumentLine]]:
        if not document_ids:
            return {}
        result = await self.session.execute(
            select(FinancialDocumentLine)
            .where(FinancialDocumentLine.financial_document_id.in_(document_ids))
            .order_by(FinancialDocumentLine.financial_document_id, FinancialDocumentLine.line_no)
        )
        grouped: defaultdict[int, list[FinancialDocumentLine]] = defaultdict(list)
        for line in result.scalars().all():
            grouped[line.financial_document_id].append(line)
        return dict(grouped)

    async def document_with_lines(
        self, document_id: int
    ) -> tuple[FinancialDocument | None, list[FinancialDocumentLine]]:
        document = await self.session.get(FinancialDocument, document_id)
        if document is None:
            return None, []
        lines = await self.document_lines([document_id])
        return document, lines.get(document_id, [])

    async def documents_by_ids(self, ids: list[int]) -> list[FinancialDocument]:
        if not ids:
            return []
        result = await self.session.execute(
            select(FinancialDocument).where(FinancialDocument.id.in_(set(ids)))
        )
        return list(result.scalars().all())

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import Select, and_, case, func, select
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

#: Document types that carry outstanding money once posted; receipts move cash
#: against already-posted documents and do not owe anything themselves.
OUTSTANDING_DOCUMENT_TYPES = (
    "CUSTOMER_INVOICE",
    "SUPPLIER_BILL",
    "CREDIT_NOTE",
    "SUPPLIER_CREDIT_NOTE",
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
                    func.sum(case(
                        (FinancialAccount.currency_code == await self._base_currency(), JournalEntryLine.base_debit_amount - JournalEntryLine.base_credit_amount),
                        (JournalEntryLine.currency_code == FinancialAccount.currency_code, JournalEntryLine.debit_amount - JournalEntryLine.credit_amount),
                        else_=0,
                    )), 0
                ),
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .join(FinancialAccount, FinancialAccount.account_id == JournalEntryLine.account_id)
            .where(JournalEntryLine.account_id.in_(account_ids), JournalEntry.status == "POSTED")
            .group_by(JournalEntryLine.account_id)
        )
        return ledgers, dict(balance_result.all())

    async def _base_currency(self) -> str:
        from app.modules.settings.service import get_default_currency
        return await get_default_currency(self.session)

    async def document_page(
        self,
        page: PageParams,
        *,
        document_type: str | None = None,
        party_id: int | None = None,
        service_order_id: int | None = None,
    ) -> tuple[list[FinancialDocument], int]:
        stmt = self._document_statement(
            page, document_type=document_type, party_id=party_id, service_order_id=service_order_id,
        )
        total = await count_query(self.session, stmt)
        result = await self.session.execute(
            stmt.order_by(*list_sort_orders(FinancialDocument, page, FinancialDocument.id.desc()))
            .limit(page.page_size)
            .offset(page.offset)
        )
        return list(result.scalars().all()), total

    def _document_statement(
        self,
        page: PageParams,
        *,
        document_type: str | None = None,
        party_id: int | None = None,
        service_order_id: int | None = None,
    ) -> Select:
        """The financial documents a caller may see under the list's filters."""
        stmt = select(FinancialDocument)
        if document_type:
            stmt = stmt.where(FinancialDocument.document_type == document_type)
        if party_id is not None:
            stmt = stmt.where(FinancialDocument.party_id == party_id)
        if service_order_id is not None:
            stmt = stmt.where(FinancialDocument.service_order_id == service_order_id)
        if page.status:
            stmt = stmt.where(FinancialDocument.status == str(page.status).upper())
        if page.q:
            pattern = f"%{page.q}%"
            stmt = stmt.where(
                FinancialDocument.document_no.ilike(pattern) | FinancialDocument.description.ilike(pattern)
            )
        # Date filters: the page params accept `from_date`/`to_date` (also
        # `dateFrom`/`dateTo` aliases) so mobile and web lists can scope a range.
        from app.core.pagination import parse_date

        if parse_date(page.from_date) is not None:
            stmt = stmt.where(FinancialDocument.document_date >= parse_date(page.from_date))
        if parse_date(page.to_date) is not None:
            stmt = stmt.where(FinancialDocument.document_date <= parse_date(page.to_date))
        return stmt

    async def document_totals(
        self,
        page: PageParams,
        *,
        document_type: str | None = None,
        party_id: int | None = None,
        service_order_id: int | None = None,
    ) -> dict[str, dict[str, float]]:
        """Per-currency grand total and outstanding for the filtered list.

        Same WHERE clause as ``document_page``, so the footer totals agree with
        the whole filtered list even when only the first page is loaded.
        Outstanding counts money the business still owes or is owed: a posted
        receivable/payable document (drafts have none yet, reversed ones are
        undone, receipts move no outstanding), as ``total - paid``.
        """
        statement = self._document_statement(
            page, document_type=document_type, party_id=party_id, service_order_id=service_order_id,
        ).order_by(None).subquery()
        outstanding = case(
            (
                and_(
                    statement.c.status == "POSTED",
                    statement.c.document_type.in_(OUTSTANDING_DOCUMENT_TYPES),
                ),
                statement.c.total_amount - statement.c.paid_amount,
            ),
            else_=0,
        )
        stmt = (
            select(
                statement.c.currency_code,
                func.sum(statement.c.total_amount),
                func.sum(outstanding),
            )
            .select_from(statement)
            .group_by(statement.c.currency_code)
        )
        result = await self.session.execute(stmt)
        return {
            currency: {"grand": float(grand or 0), "outstanding": float(unpaid or 0)}
            for currency, grand, unpaid in result.all()
        }

    async def document_base_totals(
        self,
        page: PageParams,
        base_currency: str,
        *,
        document_type: str | None = None,
        party_id: int | None = None,
        service_order_id: int | None = None,
    ) -> dict[str, float | str]:
        """One base-currency total for the filtered list.

        Uses each document's **stored** conversion (``base_total_amount`` written
        when it was saved/posted, and its stored ``exchange_rate`` for the still
        outstanding part) — never today's rate. This is what the list footer
        shows so mixed-currency rows reconcile with the ledger instead of being
        added as bare numbers.
        """
        statement = self._document_statement(
            page, document_type=document_type, party_id=party_id, service_order_id=service_order_id,
        ).order_by(None).subquery()
        outstanding = case(
            (
                and_(
                    statement.c.status == "POSTED",
                    statement.c.document_type.in_(OUTSTANDING_DOCUMENT_TYPES),
                ),
                (statement.c.total_amount - statement.c.paid_amount) * statement.c.exchange_rate,
            ),
            else_=0,
        )
        result = (
            await self.session.execute(
                select(func.sum(statement.c.base_total_amount), func.sum(outstanding)).select_from(statement)
            )
        ).one()
        grand, unpaid = result
        return {
            "currency": str(base_currency or "").strip().upper(),
            "grand": float(grand or 0),
            "outstanding": float(unpaid or 0),
        }

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

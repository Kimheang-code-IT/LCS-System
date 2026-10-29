from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

from sqlalchemy import case, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.modules.finance.models import (
    ChartOfAccount,
    FinancialAccount,
    FinancialDocument,
    JournalEntry,
    JournalEntryLine,
)
from app.modules.master_data.models import BusinessParty, ContainerType
from app.modules.operations.models import ServiceOrder, ServiceOrderCharge, ServiceOrderContainer
from app.modules.quotations.models import QuotationRevision


class ReportRepository:
    """Set-based read models used by operational and financial reports."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def service_order_finance_rows(self) -> list[dict]:
        charge_totals = (
            select(
                ServiceOrderCharge.service_order_id.label("service_order_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (ServiceOrderCharge.status == "ISSUED", ServiceOrderCharge.total_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("issued_charges"),
                func.coalesce(
                    func.sum(
                        case(
                            (ServiceOrderCharge.status == "DRAFT", ServiceOrderCharge.total_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("draft_charges"),
                func.count(ServiceOrderCharge.id).label("charge_count"),
            )
            .group_by(ServiceOrderCharge.service_order_id)
            .subquery()
        )
        finance_totals = (
            select(
                FinancialDocument.service_order_id.label("service_order_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (FinancialDocument.document_type == "CUSTOMER_INVOICE")
                                & (FinancialDocument.status == "POSTED"),
                                FinancialDocument.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("posted_revenue"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (FinancialDocument.document_type == "SUPPLIER_BILL")
                                & (FinancialDocument.status == "POSTED"),
                                FinancialDocument.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("posted_cost"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (FinancialDocument.document_type == "CUSTOMER_INVOICE")
                                & (FinancialDocument.status == "DRAFT"),
                                FinancialDocument.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("draft_revenue"),
            )
            .where(FinancialDocument.service_order_id.is_not(None))
            .group_by(FinancialDocument.service_order_id)
            .subquery()
        )
        stmt = (
            select(
                ServiceOrder.id,
                ServiceOrder.service_order_no,
                ServiceOrder.status,
                ServiceOrder.currency_code,
                ServiceOrder.created_at,
                BusinessParty.display_name.label("customer_name"),
                func.coalesce(QuotationRevision.total_amount, 0).label("quoted"),
                func.coalesce(charge_totals.c.issued_charges, 0).label("issued_charges"),
                func.coalesce(charge_totals.c.draft_charges, 0).label("draft_charges"),
                func.coalesce(charge_totals.c.charge_count, 0).label("charge_count"),
                func.coalesce(finance_totals.c.posted_revenue, 0).label("posted_revenue"),
                func.coalesce(finance_totals.c.posted_cost, 0).label("posted_cost"),
                func.coalesce(finance_totals.c.draft_revenue, 0).label("draft_revenue"),
            )
            .outerjoin(BusinessParty, BusinessParty.id == ServiceOrder.customer_party_id)
            .outerjoin(QuotationRevision, QuotationRevision.id == ServiceOrder.quotation_revision_id)
            .outerjoin(charge_totals, charge_totals.c.service_order_id == ServiceOrder.id)
            .outerjoin(finance_totals, finance_totals.c.service_order_id == ServiceOrder.id)
            .order_by(ServiceOrder.id.desc())
        )
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def container_register_rows(self) -> list[dict]:
        """Every container with the order, customer and type it belongs to."""
        stmt = (
            select(
                ServiceOrderContainer.id,
                ServiceOrderContainer.container_number,
                ServiceOrderContainer.seal_serial,
                ServiceOrderContainer.status,
                ServiceOrderContainer.gross_weight_kg,
                ServiceOrderContainer.pickup_date,
                ServiceOrderContainer.return_date,
                ServiceOrderContainer.service_order_id,
                ServiceOrder.service_order_no,
                BusinessParty.display_name.label("customer_name"),
                ContainerType.name.label("container_type"),
            )
            .join(ServiceOrder, ServiceOrder.id == ServiceOrderContainer.service_order_id)
            .outerjoin(BusinessParty, BusinessParty.id == ServiceOrder.customer_party_id)
            .outerjoin(ContainerType, ContainerType.id == ServiceOrderContainer.container_type_id)
            .order_by(ServiceOrder.service_order_no, ServiceOrderContainer.id)
        )
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def cash_flow_rows(self) -> list[dict]:
        """Posted debit/credit movements on the ledger accounts mapped as cash/bank."""
        stmt = (
            select(
                ChartOfAccount.id.label("account_id"),
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                func.coalesce(func.sum(JournalEntryLine.base_debit_amount), 0).label("debit"),
                func.coalesce(func.sum(JournalEntryLine.base_credit_amount), 0).label("credit"),
            )
            .select_from(FinancialAccount)
            .join(ChartOfAccount, ChartOfAccount.id == FinancialAccount.account_id)
            .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(JournalEntry.status == "POSTED")
            .group_by(ChartOfAccount.id, ChartOfAccount.account_code, ChartOfAccount.account_name)
            .order_by(ChartOfAccount.account_code)
        )
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def posted_trial_balance_rows(self) -> list[dict]:
        """Posted debit/credit totals per account.

        Grouped in the database rather than aggregated in Python, and restricted to
        POSTED journals via an inner join so a draft never contributes. Uses the
        base-currency columns so the two sides stay comparable across currencies.
        """
        stmt = (
            select(
                ChartOfAccount.id.label("account_id"),
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.base_debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntryLine.base_credit_amount), 0).label("total_credit"),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(JournalEntry.status == "POSTED")
            .group_by(
                ChartOfAccount.id,
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
            )
            .order_by(ChartOfAccount.account_code)
        )
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    def _posted_ledger_statement(self) -> Select:
        """The posted ledger projection every ledger report reads.

        One definition of "posted line", so the general ledger, the cash-flow
        report and the statements cannot drift onto different filters. Drafts
        are excluded by the status predicate; a reversal is its own POSTED
        journal and therefore appears as a real, opposite movement.
        """
        return (
            select(
                JournalEntryLine.id,
                JournalEntry.id.label("journal_id"),
                JournalEntry.posting_date,
                JournalEntry.entry_no,
                JournalEntry.entry_type,
                JournalEntry.description.label("journal_description"),
                FinancialDocument.id.label("source_document_id"),
                FinancialDocument.document_no.label("source_document_no"),
                ChartOfAccount.id.label("account_id"),
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
                JournalEntryLine.description,
                JournalEntryLine.party_id,
                BusinessParty.display_name.label("party_name"),
                JournalEntryLine.service_order_id,
                ServiceOrder.service_order_no,
                JournalEntryLine.currency_code,
                JournalEntryLine.base_debit_amount,
                JournalEntryLine.base_credit_amount,
                FinancialAccount.id.label("financial_account_id"),
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .join(ChartOfAccount, ChartOfAccount.id == JournalEntryLine.account_id)
            .outerjoin(FinancialDocument, FinancialDocument.id == JournalEntry.source_document_id)
            .outerjoin(BusinessParty, BusinessParty.id == JournalEntryLine.party_id)
            .outerjoin(ServiceOrder, ServiceOrder.id == JournalEntryLine.service_order_id)
            .outerjoin(FinancialAccount, FinancialAccount.account_id == ChartOfAccount.id)
            .where(JournalEntry.status == "POSTED")
        )

    async def posted_ledger_rows(self) -> list[dict]:
        stmt = self._posted_ledger_statement().order_by(
            JournalEntry.posting_date, JournalEntry.id, JournalEntryLine.line_no
        )
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    async def trial_balance_balances(
        self,
        *,
        from_date: date | None,
        to_date: date | None,
        account_from: str | None = None,
        account_to: str | None = None,
    ) -> list[dict]:
        """Posted movement per account, split into opening and period totals.

        One grouped query, not one query per account: the opening balance is the
        movement before ``from_date`` and the period movement is the rest, both
        summed from ``base_*`` columns so a multi-currency ledger is never added
        up in mixed denominations.
        """
        result = await self.session.execute(
            self._trial_balance_statement(
                from_date=from_date, to_date=to_date, account_from=account_from, account_to=account_to
            )
        )
        return [dict(row) for row in result.mappings().all()]

    def _trial_balance_statement(
        self,
        *,
        from_date: date | None,
        to_date: date | None,
        account_from: str | None = None,
        account_to: str | None = None,
    ) -> Select:
        opening = JournalEntry.posting_date < from_date if from_date else false()
        conditions = [JournalEntry.status == "POSTED"]
        if to_date:
            conditions.append(JournalEntry.posting_date <= to_date)
        if account_from:
            conditions.append(ChartOfAccount.account_code >= account_from)
        if account_to:
            conditions.append(ChartOfAccount.account_code <= account_to)
        return (
            select(
                ChartOfAccount.id.label("account_id"),
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
                func.coalesce(
                    func.sum(JournalEntryLine.base_debit_amount).filter(opening), 0
                ).label("opening_debit"),
                func.coalesce(
                    func.sum(JournalEntryLine.base_credit_amount).filter(opening), 0
                ).label("opening_credit"),
                func.coalesce(
                    func.sum(JournalEntryLine.base_debit_amount).filter(~opening), 0
                ).label("period_debit"),
                func.coalesce(
                    func.sum(JournalEntryLine.base_credit_amount).filter(~opening), 0
                ).label("period_credit"),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(*conditions)
            .group_by(
                ChartOfAccount.id,
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
            )
            .order_by(ChartOfAccount.account_code)
        )

    @staticmethod
    def _ledger_conditions(
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        before: date | None = None,
        account_code: str | None = None,
        party: str | None = None,
        voucher_type: str | None = None,
        voucher_no: str | None = None,
        currency: str | None = None,
    ) -> list:
        """Predicates shared by the ledger page, its totals and its opening balance.

        ``before`` replaces the period range with an exclusive upper bound, which
        is what an opening balance needs.
        """
        conditions: list = [JournalEntry.status == "POSTED"]
        if before:
            conditions.append(JournalEntry.posting_date < before)
        else:
            if from_date:
                conditions.append(JournalEntry.posting_date >= from_date)
            if to_date:
                conditions.append(JournalEntry.posting_date <= to_date)
        if account_code:
            conditions.append(ChartOfAccount.account_code == account_code)
        if party:
            # A correlated id filter rather than a join, so the same predicate
            # works in the page, totals and opening-balance statements.
            conditions.append(
                JournalEntryLine.party_id.in_(
                    select(BusinessParty.id).where(BusinessParty.display_name.ilike(f"%{party}%"))
                )
            )
        if voucher_type:
            conditions.append(func.upper(JournalEntry.entry_type) == voucher_type.upper())
        if voucher_no:
            conditions.append(JournalEntry.entry_no.ilike(f"%{voucher_no}%"))
        if currency:
            conditions.append(func.upper(JournalEntryLine.currency_code) == currency.upper())
        return conditions

    async def ledger_opening_balances(self, *, from_date: date | None, **filters) -> dict[int, Decimal]:
        """Signed movement per account strictly before the report period."""
        if not from_date:
            return {}
        result = await self.session.execute(
            self._opening_balances_statement(from_date=from_date, **filters)
        )
        return {int(row["account_id"]): Decimal(str(row["net"] or 0)) for row in result.mappings()}

    def _opening_balances_statement(self, *, from_date: date | None, **filters) -> Select:
        conditions = self._ledger_conditions(before=from_date, **filters)
        return (
            select(
                JournalEntryLine.account_id.label("account_id"),
                func.coalesce(
                    func.sum(JournalEntryLine.base_debit_amount - JournalEntryLine.base_credit_amount), 0
                ).label("net"),
            )
            .select_from(JournalEntryLine)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .join(ChartOfAccount, ChartOfAccount.id == JournalEntryLine.account_id)
            .where(*conditions)
            .group_by(JournalEntryLine.account_id)
        )

    async def general_ledger_totals(self, **filters) -> tuple[int, Decimal, Decimal]:
        """Row count and signed sums over the whole filtered set (not the page)."""
        conditions = self._ledger_conditions(**filters)
        stmt = (
            select(
                func.count(JournalEntryLine.id).label("total"),
                func.coalesce(func.sum(JournalEntryLine.base_debit_amount), 0).label("debit"),
                func.coalesce(func.sum(JournalEntryLine.base_credit_amount), 0).label("credit"),
            )
            .select_from(JournalEntryLine)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .join(ChartOfAccount, ChartOfAccount.id == JournalEntryLine.account_id)
            .where(*conditions)
        )
        row = (await self.session.execute(stmt)).mappings().one()
        return (
            int(row["total"] or 0),
            Decimal(str(row["debit"] or 0)),
            Decimal(str(row["credit"] or 0)),
        )

    async def general_ledger_page(self, *, offset: int, limit: int, **filters) -> list[dict]:
        """One page of posted ledger lines with a running balance per account.

        The window function is evaluated over the whole filtered set and only
        then sliced, so a later page continues from the earlier balance instead
        of restarting at the page boundary. Ordering is the posting date and
        then the immutable (journal, line) identity, which keeps pagination
        stable when several lines share a date.
        """
        stmt = self._general_ledger_statement(**filters).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

    def _general_ledger_statement(self, **filters) -> Select:
        conditions = self._ledger_conditions(**filters)
        running = (
            func.sum(JournalEntryLine.base_debit_amount - JournalEntryLine.base_credit_amount)
            .over(
                partition_by=JournalEntryLine.account_id,
                order_by=(
                    JournalEntry.posting_date,
                    JournalEntry.id,
                    JournalEntryLine.line_no,
                ),
            )
            .label("running_balance")
        )
        return (
            self._posted_ledger_statement()
            .add_columns(running)
            .where(*conditions)
            .order_by(JournalEntry.posting_date, JournalEntry.id, JournalEntryLine.line_no)
        )

    async def general_ledger_stream(self, **filters) -> AsyncIterator[dict]:
        """Every matching line, streamed: an export never loads the ledger at once.

        Same statement as the page, without LIMIT, executed as a server-side
        cursor where the driver supports one (PostgreSQL); the rows are consumed
        in batches so memory stays bounded by the batch, not by the result size.
        """
        result = await self.session.stream(
            self._general_ledger_statement(**filters).execution_options(yield_per=500)
        )
        async for row in result.mappings():
            yield dict(row)

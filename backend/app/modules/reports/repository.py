from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def posted_ledger_rows(self) -> list[dict]:
        stmt = (
            select(
                JournalEntryLine.id,
                JournalEntry.posting_date,
                JournalEntry.entry_no,
                JournalEntry.description.label("journal_description"),
                FinancialDocument.document_no.label("source_document_no"),
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
            .order_by(JournalEntry.posting_date, JournalEntry.id, JournalEntryLine.line_no)
        )
        result = await self.session.execute(stmt)
        return [dict(row) for row in result.mappings().all()]

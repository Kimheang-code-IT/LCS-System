from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin, TimestampMixin, utcnow
from app.core.types import JSONType


class ChartOfAccount(PKMixin, TimestampMixin, Base):
    __tablename__ = "chart_of_accounts"
    __table_args__ = (UniqueConstraint("account_code", name="uq_coa_code"),)

    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chart_of_accounts.id"))
    normal_balance: Mapped[str] = mapped_column(String(10), nullable=False, default="DEBIT")
    is_postable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class FinancialAccount(PKMixin, TimestampMixin, Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (UniqueConstraint("account_id", name="uq_financial_accounts_account"),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chart_of_accounts.id"), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, default="BANK")
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    bank_name: Mapped[str | None] = mapped_column(String(255))
    account_number_masked: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class AccountingPeriod(PKMixin, TimestampMixin, Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (UniqueConstraint("period_year", "period_month", name="uq_periods_year_month"),)

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN", index=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentSequence(PKMixin, TimestampMixin, Base):
    __tablename__ = "document_sequences"
    __table_args__ = (UniqueConstraint("document_type", "period_year", name="uq_sequences_type_year"),)

    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    padding_length: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class FinancialDocument(PKMixin, TimestampMixin, Base):
    __tablename__ = "financial_documents"
    __table_args__ = (UniqueConstraint("document_no", name="uq_financial_documents_no"),)

    document_no: Mapped[str] = mapped_column(String(50), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    party_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("business_parties.id"))
    service_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service_orders.id"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text)
    reference_number: Mapped[str | None] = mapped_column(String(128))
    due_date: Mapped[date | None] = mapped_column(Date)
    payment_method_code: Mapped[str | None] = mapped_column(String(64))
    financial_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("financial_accounts.id"))
    value_date: Mapped[date | None] = mapped_column(Date)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    posted_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_document_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("financial_documents.id"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class FinancialDocumentLine(PKMixin, Base):
    __tablename__ = "financial_document_lines"
    __table_args__ = (UniqueConstraint("financial_document_id", "line_no", name="uq_financial_document_lines_no"),)

    financial_document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("financial_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fee_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fee_types.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=1)
    unit_code: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    service_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service_orders.id"))
    service_order_container_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service_order_containers.id"))
    account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chart_of_accounts.id"))


class FinancialDocumentSource(PKMixin, Base):
    __tablename__ = "financial_document_sources"
    __table_args__ = (UniqueConstraint("financial_document_id", "source_type", "source_id", "relationship_type", name="uq_fin_doc_sources"),)

    financial_document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("financial_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False, default="GENERATED_FROM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())


class FinancialDocumentAllocation(PKMixin, Base):
    __tablename__ = "financial_document_allocations"

    payment_document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("financial_documents.id"), nullable=False, index=True)
    target_document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("financial_documents.id"), nullable=False, index=True)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    allocated_currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=1)
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)


class PostingRule(PKMixin, TimestampMixin, Base):
    __tablename__ = "posting_rules"

    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fee_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fee_types.id"))
    debit_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chart_of_accounts.id"), nullable=False)
    credit_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chart_of_accounts.id"), nullable=False)
    tax_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chart_of_accounts.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class JournalEntry(PKMixin, TimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("entry_no", name="uq_journal_entries_no"),)

    entry_no: Mapped[str] = mapped_column(String(50), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(64), nullable=False, default="MANUAL")
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False)
    accounting_period_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("accounting_periods.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    description: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("financial_documents.id"))
    reversal_of_journal_entry_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("journal_entries.id"))
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    posted_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    debit_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    credit_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)


class JournalEntryLine(PKMixin, Base):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (UniqueConstraint("journal_entry_id", "line_no", name="uq_journal_entry_lines_no"),)

    journal_entry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chart_of_accounts.id"), nullable=False, index=True)
    party_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("business_parties.id"))
    service_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("service_orders.id"))
    financial_document_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("financial_documents.id"))
    description: Mapped[str | None] = mapped_column(Text)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False, default=1)
    base_debit_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)
    base_credit_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=0)


class FinancialDocumentPosting(PKMixin, Base):
    __tablename__ = "financial_document_postings"
    __table_args__ = (UniqueConstraint("financial_document_id", "journal_entry_id", name="uq_fin_doc_postings"),)

    financial_document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("financial_documents.id"), nullable=False)
    journal_entry_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("journal_entries.id"), nullable=False)
    posting_role: Mapped[str] = mapped_column(String(32), nullable=False, default="ORIGINAL_POSTING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())

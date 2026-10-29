"""Request and response contracts for the on-demand report engine.

Filters are validated here; accounting rules stay in ``ledger_reports.py``.
Every generated report returns the same ``meta`` envelope so the SPA can show
what was run, when, and over which period instead of silently presenting an
old result as current.

Money is summed and stored as ``Decimal``/``NUMERIC``; the response models
declare ``float`` because every other LCS endpoint already serialises money as
a JSON number and the SPA formats it at the edge.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REPORT_PAGE_SIZE_MAX = 200


class ReportFilters(BaseModel):
    """Filters every generated report accepts."""

    model_config = ConfigDict(extra="forbid")

    fromDate: date | None = None
    toDate: date | None = None
    fiscalYear: int | None = Field(default=None, ge=2000, le=2999)
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=50, ge=1, le=REPORT_PAGE_SIZE_MAX)


class TrialBalanceFilters(ReportFilters):
    accountFrom: str | None = Field(default=None, max_length=32)
    accountTo: str | None = Field(default=None, max_length=32)


class GeneralLedgerFilters(ReportFilters):
    accountCode: str | None = Field(default=None, max_length=32)
    party: str | None = Field(default=None, max_length=255)
    voucherType: str | None = Field(default=None, max_length=64)
    voucherNo: str | None = Field(default=None, max_length=50)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class TrialBalanceExportFilters(TrialBalanceFilters):
    """Trial-balance filters plus an optional column selection for the CSV."""

    fields: list[str] | None = Field(default=None, max_length=32)


class GeneralLedgerExportFilters(GeneralLedgerFilters):
    """General-ledger filters plus an optional column selection for the CSV."""

    fields: list[str] | None = Field(default=None, max_length=32)


class ReportMeta(BaseModel):
    reportKey: str
    title: str
    titleKey: str
    generatedAt: datetime
    page: int
    pageSize: int
    total: int
    filters: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class TrialBalanceRow(BaseModel):
    accountId: str
    accountCode: str
    accountName: str
    accountType: str
    openingDebit: float
    openingCredit: float
    periodDebit: float
    periodCredit: float
    closingDebit: float
    closingCredit: float


class TrialBalanceTotals(BaseModel):
    openingDebit: float
    openingCredit: float
    periodDebit: float
    periodCredit: float
    closingDebit: float
    closingCredit: float


class TrialBalanceReport(BaseModel):
    meta: ReportMeta
    items: list[TrialBalanceRow]
    totals: TrialBalanceTotals
    balanced: bool
    imbalance: float


class GeneralLedgerRow(BaseModel):
    id: str
    postingDate: date | None
    journalNo: str
    journalId: str
    voucherType: str
    voucherNo: str
    sourceDocument: str | None
    sourceDocumentId: str | None
    accountId: str
    accountCode: str
    accountName: str
    account: str
    description: str | None
    partyId: int | None
    party: str
    currency: str
    debit: float
    credit: float
    runningBalance: float


class GeneralLedgerTotals(BaseModel):
    debit: float
    credit: float
    closingBalance: float


class GeneralLedgerReport(BaseModel):
    meta: ReportMeta
    openingBalance: float
    items: list[GeneralLedgerRow]
    totals: GeneralLedgerTotals

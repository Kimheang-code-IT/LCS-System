import type { FreightRecord } from '~/types/record'
import { outstandingOf } from '~/utils/freight/finance'
import { codeTitle } from '~/utils/freight/format'
import { JOB_FINANCE_LINE_KIND, jobFinanceLineKind, type JobFinanceLineKind } from '~/utils/table/line-table-rules'

/** One row of the unified Finance grid. `_kind` is the discriminator, never a column. */
export type JobFinanceLine = Record<string, unknown>

/** i18n keys for the Type column; the component resolves them with `t`. */
export const JOB_FINANCE_LINE_LABEL_KEYS: Record<JobFinanceLineKind, string> = {
  [JOB_FINANCE_LINE_KIND.charge]: 'freight.ui.financeLineCharge',
  [JOB_FINANCE_LINE_KIND.expense]: 'freight.ui.financeLineExpense',
  [JOB_FINANCE_LINE_KIND.document]: 'freight.ui.financeLineInvoice',
}

/**
 * Expense rows are the only writable part of the grid, so their persisted shape
 * is pinned here rather than spread from the display row. `supplier` is the
 * pre-consolidation name for `party` and is still read for existing jobs.
 */
export function normalizeJobFinanceExpense(row: JobFinanceLine): JobFinanceLine {
  const quantity = Number(row.quantity || 0)
  const unitPrice = Number(row.unitPrice || 0)
  return {
    id: String(row.id || '').trim(),
    _kind: JOB_FINANCE_LINE_KIND.expense,
    date: String(row.date || ''),
    reference: String(row.reference || ''),
    description: String(row.description || ''),
    party: String(row.party || row.supplier || ''),
    quantity,
    unitPrice,
    amount: Number((quantity * unitPrice).toFixed(2)),
    remark: String(row.remark || ''),
  }
}

/** Locked projection of the service order's priced lines. */
export function jobFinanceChargeLines(job: FreightRecord, customer: string): JobFinanceLine[] {
  const lines = Array.isArray(job.pricingLines) ? job.pricingLines as JobFinanceLine[] : []
  const fallback = Array.isArray(job.containerPayments) ? job.containerPayments as JobFinanceLine[] : []
  return (lines.length ? lines : fallback).map((row, index) => ({
    _kind: JOB_FINANCE_LINE_KIND.charge,
    id: `charge-${index}`,
    reference: String(row.chargeNo || ''),
    date: String(row.date || ''),
    description: String(row.description || row.feeType || ''),
    party: customer,
    quantity: Number(row.quantity || 0),
    unitPrice: Number(row.unitPrice || 0),
    amount: Number(row.lineTotal ?? row.total ?? (Number(row.quantity || 0) * Number(row.unitPrice || 0))),
    outstanding: '',
    status: codeTitle(row.status),
    remark: String(row.remark || ''),
  }))
}

/** Locked projection of the service order's financial documents. */
export function jobFinanceDocumentLines(documents: FreightRecord[]): JobFinanceLine[] {
  return documents.map(row => ({
    _kind: JOB_FINANCE_LINE_KIND.document,
    _documentId: String(row.id || ''),
    reference: String(row.debitNoteNo || row.paymentNo || ''),
    date: String(row.date || ''),
    description: codeTitle(row.documentType),
    party: String(row.partyName || row.customer || ''),
    // A document is one posted total, not a priced quantity — those cells stay empty.
    quantity: '',
    unitPrice: '',
    amount: Number(row.total ?? row.amount ?? 0),
    outstanding: outstandingOf(row),
    status: codeTitle(row.status),
    remark: String(row.remark || ''),
  }))
}

/**
 * The single Finance grid: charges, then expenses, then documents. `typeLabel`
 * resolves the localized Type cell so no translated string is ever persisted.
 */
export function jobFinanceLines({
  charges,
  expenses,
  documents,
  typeLabel,
}: {
  charges: JobFinanceLine[]
  expenses: JobFinanceLine[]
  documents: FreightRecord[]
  typeLabel: (kind: JobFinanceLineKind | '') => string
}): JobFinanceLine[] {
  return [...charges, ...expenses, ...jobFinanceDocumentLines(documents)]
    .map(row => ({ ...row, type: typeLabel(jobFinanceLineKind(row)) }))
}

/** Charge and document rows are projections of other collections and stay locked. */
export function isJobFinanceRowEditable(row: JobFinanceLine, editable: boolean) {
  return editable && jobFinanceLineKind(row) === JOB_FINANCE_LINE_KIND.expense
}

/**
 * Write path: keep only the expense rows, normalized. Locked rows are dropped so
 * an edit can never leak a projected charge or document into `job.expenses`.
 */
export function jobFinanceExpenseRows(lines: JobFinanceLine[]): JobFinanceLine[] {
  return lines
    .filter(row => jobFinanceLineKind(row) === JOB_FINANCE_LINE_KIND.expense)
    .map(normalizeJobFinanceExpense)
}

export function jobFinanceLineTotals(lines: JobFinanceLine[]) {
  const total = (kind: JobFinanceLineKind) => Math.round(lines
    .filter(row => jobFinanceLineKind(row) === kind)
    .reduce((sum, row) => sum + Number(row.amount || 0), 0) * 100) / 100
  return {
    [JOB_FINANCE_LINE_KIND.charge]: total(JOB_FINANCE_LINE_KIND.charge),
    [JOB_FINANCE_LINE_KIND.expense]: total(JOB_FINANCE_LINE_KIND.expense),
    [JOB_FINANCE_LINE_KIND.document]: total(JOB_FINANCE_LINE_KIND.document),
  }
}

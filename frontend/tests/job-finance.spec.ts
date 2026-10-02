import { describe, expect, it } from 'vitest'
import {
  isJobFinanceRowEditable,
  jobFinanceChargeLines,
  jobFinanceDocumentLines,
  jobFinanceExpenseRows,
  jobFinanceLineTotals,
  jobFinanceLines,
  normalizeJobFinanceExpense,
} from '../app/utils/freight/job-finance'
import { JOB_FINANCE_LINE_KIND } from '../app/utils/table/line-table-rules'

const typeLabel = (kind: string) => (kind ? kind.toLowerCase() : '')

describe('job finance grid', () => {
  const job = {
    id: 'job-1',
    pricingLines: [
      { description: 'Sea freight', quantity: 2, unitPrice: 500, lineTotal: 1000 },
      { description: 'THC', quantity: 1, unitPrice: 120, total: 120 },
    ],
  } as Record<string, unknown>

  const documents = [
    { id: 'doc-1', documentType: 'CUSTOMER_INVOICE', debitNoteNo: 'INV-001', date: '2026-02-01', total: 1000, allocatedAmount: 400, status: 'POSTED', currency: 'USD' },
    { id: 'doc-2', documentType: 'DEBIT_NOTE', debitNoteNo: 'DN-002', date: '2026-02-05', total: 50, allocatedAmount: 50, status: 'POSTED' },
  ]

  const expenses = [normalizeJobFinanceExpense({ id: 'exp-1', description: 'Port fee', party: 'Sok', quantity: 2, unitPrice: 30 })]
  const grid = jobFinanceLines({ charges: jobFinanceChargeLines(job, 'Acme'), expenses, documents, typeLabel })

  it('merges charges, expenses and documents into one row list in that order', () => {
    expect(grid.map(row => row._kind)).toEqual([
      JOB_FINANCE_LINE_KIND.charge,
      JOB_FINANCE_LINE_KIND.charge,
      JOB_FINANCE_LINE_KIND.expense,
      JOB_FINANCE_LINE_KIND.document,
      JOB_FINANCE_LINE_KIND.document,
    ])
  })

  it('projects charges onto the shared column set and falls back to container payments', () => {
    expect(grid[0]).toMatchObject({
      reference: '',
      description: 'Sea freight',
      party: 'Acme',
      quantity: 2,
      unitPrice: 500,
      amount: 1000,
      outstanding: '',
    })

    const withoutPricing = jobFinanceChargeLines({ containerPayments: [{ feeType: 'Trucking', quantity: 1, unitPrice: 80 }] }, '')
    expect(withoutPricing[0]).toMatchObject({ description: 'Trucking', amount: 80 })
  })

  it('projects documents with their outstanding balance and type label', () => {
    expect(jobFinanceDocumentLines(documents)[0]).toMatchObject({
      reference: 'INV-001',
      description: 'Customer Invoice',
      quantity: '',
      unitPrice: '',
      amount: 1000,
      outstanding: 600,
      status: 'Posted',
    })
  })

  it('only allows expense rows to be edited', () => {
    expect(isJobFinanceRowEditable(grid[2]!, true)).toBe(true)
    expect(isJobFinanceRowEditable(grid[0]!, true)).toBe(false)
    expect(isJobFinanceRowEditable(grid[3]!, true)).toBe(false)
    // A read-only service order locks the expense rows too.
    expect(isJobFinanceRowEditable(grid[2]!, false)).toBe(false)
  })

  it('persists expense rows only, so a projected charge can never be written back', () => {
    const expensesAfterEdit = jobFinanceExpenseRows(grid.map(row => row._kind === JOB_FINANCE_LINE_KIND.expense
      ? { ...row, description: 'Port fee (rev)', quantity: 3 }
      : row))

    expect(expensesAfterEdit).toHaveLength(1)
    expect(expensesAfterEdit[0]).toMatchObject({
      id: 'exp-1',
      _kind: JOB_FINANCE_LINE_KIND.expense,
      description: 'Port fee (rev)',
      quantity: 3,
      unitPrice: 30,
      amount: 90,
    })
    expect(expensesAfterEdit[0]).not.toHaveProperty('_documentId')
    expect(expensesAfterEdit[0]).not.toHaveProperty('type')
  })

  it('reads the pre-consolidation supplier key and always recomputes the amount', () => {
    expect(normalizeJobFinanceExpense({ supplier: 'Sok', quantity: '4', unitPrice: '12.5' })).toMatchObject({
      party: 'Sok',
      quantity: 4,
      unitPrice: 12.5,
      amount: 50,
    })
  })

  it('totals each kind separately', () => {
    expect(jobFinanceLineTotals(grid)).toEqual({ CHARGE: 1120, EXPENSE: 60, DOCUMENT: 1050 })
  })
})

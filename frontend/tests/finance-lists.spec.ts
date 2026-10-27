import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { FREIGHT_REPORTS } from '../app/config/freight-reports'
import { getFreightModule } from '../app/config/freight-modules'

const keys = (path: string) => getFreightModule(path)!.columns.map(column => column.key)
const report = (slug: string) => FREIGHT_REPORTS.find(item => item.slug === slug)!
const reportKeys = (slug: string) => report(slug).columns.map(column => column.key)

describe('finance list columns', () => {
  it('financial documents start with Document No. then SO No.', () => {
    expect(keys('/finance/documents')).toEqual([
      'documentNo',
      'jobNo',
      'documentType',
      'customer',
      'date',
      'total',
      'outstanding',
      'status',
      'createdBy',
      'createdAt',
    ])
    expect(getFreightModule('/finance/documents')?.titleField).toBe('documentNo')
  })

  it('keeps the chart of accounts hierarchy columns', () => {
    expect(keys('/finance/chart-of-accounts')).toEqual([
      'accountCode',
      'accountName',
      'accountType',
      'parentCode',
      'normalBalance',
      'postable',
      'status',
    ])
  })

  it('financial accounts move type next to the name and drop an unreliable balance', () => {
    expect(keys('/finance/financial-accounts')).toEqual([
      'accountName',
      'accountType',
      'ledgerCode',
      'currency',
      'bankName',
      'accountNumberMasked',
      'status',
    ])
  })

  it('journals show source, SO No., debit/credit and creator', () => {
    expect(keys('/finance/journals')).toEqual([
      'entryNo',
      'postingDate',
      'sourceDocumentNo',
      'jobNo',
      'description',
      'debitTotal',
      'creditTotal',
      'status',
      'createdBy',
    ])
  })

  it('accounting periods and posting rules keep their required columns', () => {
    expect(keys('/finance/accounting-periods')).toEqual([
      'name',
      'startDate',
      'endDate',
      'status',
      'postingCount',
      'closedBy',
      'closedAt',
    ])
    expect(keys('/finance/posting-rules')).toEqual([
      'documentTypeLabel',
      'feeType',
      'debitAccount',
      'creditAccount',
      'taxAccount',
      'priority',
      'status',
    ])
  })
})

describe('financial report columns', () => {
  it('revenue & expense and cash flow put SO No. / Business Party in place', () => {
    expect(reportKeys('revenue-expense')).toEqual([
      'postingDate',
      'jobNo',
      'party',
      'account',
      'description',
      'revenue',
      'expense',
    ])
    expect(reportKeys('cash-flow')).toEqual([
      'postingDate',
      'account',
      'sourceDocument',
      'party',
      'description',
      'cashIn',
      'cashOut',
      'runningBalance',
    ])
  })

  it('receivables and payables keep invoice/bill numbers and totals', () => {
    expect(reportKeys('accounts-receivable')).toEqual([
      'invoiceNo',
      'jobNo',
      'customer',
      'invoiceDate',
      'dueDate',
      'total',
      'paid',
      'outstanding',
      'status',
    ])
    expect(reportKeys('accounts-payable')).toEqual([
      'invoiceNo',
      'jobNo',
      'supplier',
      'billDate',
      'dueDate',
      'total',
      'paid',
      'outstanding',
      'status',
    ])
  })

  it('ledger and trial balance keep every debit/credit column', () => {
    expect(reportKeys('general-ledger')).toEqual([
      'postingDate',
      'journalNo',
      'sourceDocument',
      'account',
      'description',
      'debit',
      'credit',
      'runningBalance',
    ])
    expect(reportKeys('trial-balance')).toEqual([
      'accountCode',
      'accountName',
      'openingDebit',
      'openingCredit',
      'periodDebit',
      'periodCredit',
      'closingDebit',
      'closingCredit',
    ])
  })

  it('links report references by API id', () => {
    const source = readFileSync(fileURLToPath(new URL('../app/components/freight/ReportsView.vue', import.meta.url)), 'utf8')
    expect(source).toContain("prefix:'/finance/documents/'")
    expect(source).toContain("prefix:'/finance/journals/'")
    expect(source).toContain("prefix:'/finance/chart-of-accounts/'")
    expect(source).toContain("id:row.original.journalId")
  })
})

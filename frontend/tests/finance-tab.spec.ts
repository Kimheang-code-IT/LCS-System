import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { JOB_FINANCE_LINES_TABLE } from '../app/config/job-workspace-forms'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const source = readFileSync(`${APP}/components/freight/JobFinance.vue`, 'utf8')

describe('service order finance tab', () => {
  it('shows only Type, Date, Description, Business Party, Amount and Status', () => {
    expect(JOB_FINANCE_LINES_TABLE.columns.map(column => column.key)).toEqual([
      'type',
      'date',
      'description',
      'party',
      'amount',
      'status',
    ])
    expect(JOB_FINANCE_LINES_TABLE.columns.find(column => column.key === 'party')?.labelKey)
      .toBe('freight.ui.cols.customer')
    expect(JOB_FINANCE_LINES_TABLE.hideAddRow).toBe(true)
  })

  it('lists only financial documents linked to the current order', () => {
    expect(source).toContain('props.documents')
    expect(source).toContain('isLinkedToJob')
    expect(source).not.toContain('jobFinanceChargeLines')
    expect(source).not.toContain('job.expenses')
    expect(source).not.toContain('createClientId')
  })

  it('uses dynamic Document Types from Master Data, not hardcoded options', () => {
    expect(source).toContain("store.list('documentTypes')")
    expect(source).toContain("available.includes('service_order_finance')")
    expect(source).toContain('FINANCE_ENTRY_BEHAVIORS')
    expect(source).toContain('documentTypeId')
    expect(source).toContain('lcs.finance.createDocument')
    expect(source).toContain('lcs.finance.allocate')
    expect(source).toContain('freight.ui.noFinanceEntries')
    for (const forbidden of ['MANUAL_TYPES', 'financeEntryTypes.customerCharge']) {
      expect(source).not.toContain(forbidden)
    }
  })
})

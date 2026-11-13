import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { JOB_FINANCE_LINES_TABLE } from '../app/config/job-workspace-forms'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const source = readFileSync(`${APP}/components/freight/JobFinance.vue`, 'utf8')

describe('service order finance tab', () => {
  it('edits entries inline with Date, Type, Description and Amount', () => {
    // Party and currency are not columns: income entries default to the order
    // customer and the order currency, and both are completed through the
    // Additional Details dialog when the document needs something else.
    expect(JOB_FINANCE_LINES_TABLE.columns.map(column => column.key)).toEqual([
      'date',
      'type',
      'description',
      'amount',
    ])
    expect(JOB_FINANCE_LINES_TABLE.columns.find(column => column.key === 'type')?.type).toBe('select')
    expect(JOB_FINANCE_LINES_TABLE.hideAddRow).toBe(true)
    expect(JOB_FINANCE_LINES_TABLE.hideTitle).toBe(true)
  })

  it('lists only financial documents linked to the current order', () => {
    expect(source).toContain('service_order_id: orderId')
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

  it('defaults new entries to today in the configured timezone and resolves the income party', () => {
    expect(source).toContain('todayIso()')
    expect(source).not.toContain('new Date().toISOString().slice(0, 10)')
    expect(source).toContain('customerPartyId')
    expect(source).toContain('INCOME_BEHAVIORS.has(behavior)')
    expect(source).toContain(':items="addEntryItems"')
    expect(source).not.toContain('openCreate')
    expect(source).toContain("date: 'date'")
  })
})

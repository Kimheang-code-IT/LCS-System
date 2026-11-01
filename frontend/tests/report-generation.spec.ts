import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  EMPTY_REPORT_FILTERS,
  hasReportFilters,
  isGeneratedReport,
  reportExportBody,
  reportGenerateBody,
} from '../app/utils/freight/report-request'
import { csvCell } from '../app/utils/export/csv'

const SOURCE = readFileSync(
  fileURLToPath(new URL('../app/components/freight/ReportsView.vue', import.meta.url)),
  'utf8',
)
const QUERIES = readFileSync(
  fileURLToPath(new URL('../app/utils/freight/report-queries.ts', import.meta.url)),
  'utf8',
)

const filters = (overrides: Partial<typeof EMPTY_REPORT_FILTERS> = {}) => ({
  ...EMPTY_REPORT_FILTERS,
  ...overrides,
})

describe('report generation request', () => {
  it('auto-loads a report when its page opens', () => {
    // The slug watcher (immediate) resets, applies remembered filters and runs
    // the same guarded generate path.
    expect(SOURCE).toContain('void generateReport()')
    expect(SOURCE.match(/watch\(slug, \(next\) => \{[\s\S]*?void generateReport\(\)/)).toBeTruthy()
  })

  it('never lets a superseded run overwrite a newer result or queue duplicate requests', () => {
    expect(SOURCE).toContain('const token = ++runToken.value')
    // The run token is declared before the immediate slug watcher: that
    // callback runs during setup, and the loader reads the token.
    expect(SOURCE.indexOf('const runToken = ref(0)')).toBeLessThan(SOURCE.indexOf('watch(slug'))
    expect(SOURCE).toContain('if (token !== runToken.value) return')
    expect(SOURCE).toContain('finally {\n    if (token === runToken.value) generating.value = false')
  })

  it('only builds a body for reports with a generate endpoint', () => {
    expect(isGeneratedReport('trial-balance')).toBe(true)
    expect(isGeneratedReport('general-ledger')).toBe(true)
    expect(isGeneratedReport('service-orders')).toBe(false)
    expect(reportGenerateBody('service-orders', filters(), 1, 20)).toBeNull()
  })

  it('offers Rebuild as a forced recalculation that never writes financial data', () => {
    expect(SOURCE).toContain("t('freight.reportCatalog.rebuild')")
    expect(SOURCE).toContain('@click="refreshReport"')
    // Operational reports refresh their store cache; the rebuild path itself
    // only reads: generate/export requests, never a POST to a financial record.
    expect(SOURCE).toContain('if (!useBackend.value) store.reload()')
    expect(SOURCE).not.toContain('rebuildReport')
  })

  it('loads the four operations reports automatically with no Generate or Rebuild step', () => {
    expect(SOURCE).toContain("OPS_REPORT_SLUGS = ['service-orders', 'service-order-status', 'containers', 'profitability']")
    // The manual actions are hidden on the auto-loading pages (they remain on
    // the financial ledger reports that still need them).
    expect(SOURCE).toContain('<template v-if="!autoLoad">')
    // The empty state on an auto-loading page never offers Generate.
    expect(SOURCE).toMatch(/if \(autoLoad\.value\) \{[\s\S]*?generateError\.value[\s\S]*?\]/)
  })

  it('applies operations-report filters live instead of flagging results stale', () => {
    expect(SOURCE).toMatch(
      /watch\(\[q, party, status, currency, dateFrom, dateTo, extraFilters, slug, sort\], \(\) => \{[\s\S]*?if \(autoLoad\.value\) return/,
    )
  })

  it('waits for the report collections so the loading state covers an operational load', () => {
    expect(SOURCE).toContain('store.ensure(collection)')
  })

  it('offers a retry beside the error alert after a failed automatic load', () => {
    expect(SOURCE).toContain(`t('session.retry')`)
  })

  it('does not poll in the background', () => {
    expect(SOURCE).not.toContain('setInterval')
  })

  it('keeps reading the profitability rows from the read-only endpoint', () => {
    expect(SOURCE).toContain('reports.profitability()')
  })

  it('sends the trial balance period, account range and fiscal year', () => {
    const body = reportGenerateBody(
      'trial-balance',
      filters({
        dateFrom: '2026-01-01',
        dateTo: '2026-01-31',
        accountFrom: '1000',
        accountTo: '4999',
        fiscalYear: '2026',
      }),
      2,
      50,
    )
    expect(body).toEqual({
      page: 2,
      pageSize: 50,
      fromDate: '2026-01-01',
      toDate: '2026-01-31',
      fiscalYear: 2026,
      accountFrom: '1000',
      accountTo: '4999',
    })
  })

  it('sends the general ledger account, party, voucher and currency filters', () => {
    const body = reportGenerateBody(
      'general-ledger',
      filters({
        dateFrom: '2026-01-01',
        accountCode: ' 1100 ',
        party: 'Acme',
        voucherType: 'manual',
        voucherNo: 'JV-1',
        currency: 'usd',
      }),
      1,
      20,
    )
    expect(body).toEqual({
      page: 1,
      pageSize: 20,
      fromDate: '2026-01-01',
      accountCode: '1100',
      party: 'Acme',
      voucherType: 'manual',
      voucherNo: 'JV-1',
      currency: 'USD',
    })
  })

  it('omits blank filters so the backend applies its own defaults', () => {
    expect(reportGenerateBody('general-ledger', filters({ accountCode: '  ' }), 1, 20)).toEqual({
      page: 1,
      pageSize: 20,
    })
    expect(hasReportFilters(filters())).toBe(false)
    expect(hasReportFilters(filters({ dateFrom: '2026-01-01' }))).toBe(true)
  })

  it('keeps the trial balance arithmetic on the server only', () => {
    expect(QUERIES).not.toContain('buildTrialBalanceReportRows')
  })

  it('asks the backend for the full filtered result when exporting', () => {
    expect(reportExportBody('trial-balance', filters({ dateFrom: '2026-01-01' }), ['accountCode'])).toEqual({
      fromDate: '2026-01-01',
      fields: ['accountCode'],
    })
    // No page/pageSize: an export is not limited to the visible page.
    expect(reportExportBody('general-ledger', filters({ accountCode: '1100' }))).toEqual({
      accountCode: '1100',
    })
    expect(reportExportBody('service-orders', filters())).toBeNull()
    expect(SOURCE).toContain('reports.exportTrialBalance(body)')
    expect(SOURCE).toContain('reports.exportGeneralLedger(body)')
    expect(SOURCE).toContain('downloadBlob(blob')
  })

  it('neutralises a spreadsheet formula in an exported cell', () => {
    expect(csvCell('=SUM(A1)')).toBe(`"'=SUM(A1)"`)
    expect(csvCell('+1')).toBe(`"'+1"`)
    expect(csvCell('@import')).toBe(`"'@import"`)
    expect(csvCell('Acme "Shipping"')).toBe(`"Acme ""Shipping"""`)
    // A negative amount is data, not a formula.
    expect(csvCell('-125.5')).toBe(`"-125.5"`)
  })
})

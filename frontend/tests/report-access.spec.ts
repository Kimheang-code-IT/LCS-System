import { describe, expect, it } from 'vitest'
import { defaultReportPathForUser, reportAreaPermission } from '../app/utils/freight/report-access'

describe('report access', () => {
  it('maps report areas to page permissions', () => {
    expect(reportAreaPermission('finance')).toBe('finance.reports.view')
    expect(reportAreaPermission('operations')).toBe('operations.reports.view')
  })

  it('defaults finance users to finance reports', () => {
    const path = defaultReportPathForUser(permission => permission === 'finance.reports.view')
    expect(path).toBe('/reports/finance/revenue-expense')
  })

  it('defaults operations users to operations reports', () => {
    const path = defaultReportPathForUser(permission => permission === 'operations.reports.view')
    expect(path).toBe('/reports/operations/service-orders')
  })
})

import { describe, expect, it } from 'vitest'
import { FREIGHT_REPORTS } from '../app/config/freight-reports'
import { defaultReportPathForUser, reportAreaPermission, reportRoutePermission } from '../app/utils/freight/report-access'

function report(slug: string) {
  const found = FREIGHT_REPORTS.find(item => item.slug === slug)
  if (!found) throw new Error(`Unknown report ${slug}`)
  return found
}

describe('report access', () => {
  it('maps each report to its own matrix page permission', () => {
    expect(reportRoutePermission(report('trial-balance'))).toBe('reports.trial_balance.view')
    expect(reportRoutePermission(report('service-orders'))).toBe('reports.service_order_register.view')
  })

  it('keeps the legacy report-area codes valid', () => {
    expect(reportAreaPermission('finance')).toBe('finance.reports.view')
    expect(reportAreaPermission('operations')).toBe('operations.reports.view')
  })

  it('defaults finance users to the first finance report they may open', () => {
    const path = defaultReportPathForUser(permission => permission === 'reports.revenue_expense.view')
    expect(path).toBe('/reports/finance/revenue-expense')
  })

  it('defaults operations users to the first operations report they may open', () => {
    const path = defaultReportPathForUser(permission => permission === 'reports.service_order_register.view')
    expect(path).toBe('/reports/operations/service-orders')
  })
})

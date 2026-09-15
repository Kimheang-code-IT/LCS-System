import { FREIGHT_REPORTS, freightReportPath, type FreightReportDefinition } from '~/config/freight-reports'

/** Page permission required to open reports in a catalog group. */
export function reportAreaPermission(area: string) {
  return area === 'finance' ? 'finance.accounting.view' : 'operations.service_orders.view'
}

export function reportRoutePermission(report: FreightReportDefinition) {
  return reportAreaPermission(report.group)
}

export function defaultReportPathForUser(canAccessPage: (permission: string) => boolean) {
  const operations = FREIGHT_REPORTS.find(report => report.group === 'operations')
  const finance = FREIGHT_REPORTS.find(report => report.group === 'finance')
  if (operations && canAccessPage(reportAreaPermission('operations'))) {
    return freightReportPath(operations)
  }
  if (finance && canAccessPage(reportAreaPermission('finance'))) {
    return freightReportPath(finance)
  }
  return '/'
}

import { FREIGHT_REPORTS, freightReportPath, type FreightReportDefinition } from '~/config/freight-reports'

const REPORT_PERMISSION_PREFIXES: Readonly<Record<string, string>> = {
  'service-orders': 'reports.service_order_register',
  'service-order-status': 'reports.service_order_status',
  'containers': 'reports.service_order_containers',
  'profitability': 'reports.service_order_profitability',
  'revenue-expense': 'reports.revenue_expense',
  'accounts-receivable': 'reports.accounts_receivable',
  'accounts-payable': 'reports.accounts_payable',
  'general-ledger': 'reports.general_ledger',
  'trial-balance': 'reports.trial_balance',
  'profit-loss': 'reports.profit_loss',
  'balance-sheet': 'reports.balance_sheet',
  'cash-flow': 'reports.cash_flow',
}

/** Page permission of one report; each report is its own matrix row. */
export function reportRoutePermission(report: FreightReportDefinition) {
  const prefix = REPORT_PERMISSION_PREFIXES[report.slug]
  return prefix ? `${prefix}.view` : 'report.read'
}

/** Legacy area permission, kept for sessions created before per-report rows. */
export function reportAreaPermission(area: string) {
  return area === 'finance' ? 'finance.reports.view' : 'operations.reports.view'
}

export function defaultReportPathForUser(canAccessPage: (permission: string) => boolean) {
  const report = FREIGHT_REPORTS.find(item => canAccessPage(reportRoutePermission(item)))
  return report ? freightReportPath(report) : '/'
}

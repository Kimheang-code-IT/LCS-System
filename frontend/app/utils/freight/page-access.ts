import { normalizeRoutePath } from '~/utils/auth/session'

/**
 * Canonical page permission for every routed screen. The route guard checks
 * these codes (and the legacy fallbacks below) so a role created in the Roles &
 * Permissions matrix can open exactly the pages it was granted.
 */
export const PAGE_ROUTE_PERMISSIONS: Readonly<Record<string, string>> = {
  '/': 'dashboard.view',
  '/quotations': 'sales.quotations.view',
  '/quotations/new': 'sales.quotations.create',
  '/service-orders': 'operations.service_orders.view',
  '/service-orders/new': 'operations.service_orders.create',
  '/service-charges': 'finance.service_charges.view',
  '/service-charges/new': 'finance.service_charges.create',
  '/finance/documents': 'finance.financial_documents.view',
  '/finance/documents/new': 'finance.financial_documents.create',
  '/finance/chart-of-accounts': 'finance.chart_of_accounts.view',
  '/finance/chart-of-accounts/new': 'finance.chart_of_accounts.create',
  '/finance/financial-accounts': 'finance.financial_accounts.view',
  '/finance/financial-accounts/new': 'finance.financial_accounts.create',
  '/finance/journals': 'finance.journal_entries.view',
  '/finance/accounting-periods': 'finance.accounting_periods.view',
  '/finance/posting-rules': 'finance.posting_rules.view',
  '/finance/posting-rules/new': 'finance.posting_rules.create',
  '/master-data/business-parties': 'master.business_parties.view',
  '/master-data/business-parties/new': 'master.business_parties.create',
  '/master-data/place-roles': 'master.place_roles.view',
  '/master-data/place-roles/new': 'master.place_roles.create',
  '/master-data/trade-directions': 'master.trade_directions.view',
  '/master-data/trade-directions/new': 'master.trade_directions.create',
  '/master-data/container-types': 'master.container_types.view',
  '/master-data/container-types/new': 'master.container_types.create',
  '/master-data/transport-types': 'master.transport_types.view',
  '/master-data/transport-types/new': 'master.transport_types.create',
  '/master-data/transport-assets': 'master.transport_assets.view',
  '/master-data/transport-assets/new': 'master.transport_assets.create',
  '/master-data/fee-types': 'master.fee_types.view',
  '/master-data/fee-types/new': 'master.fee_types.create',
  '/master-data/currencies': 'master.currencies.view',
  '/master-data/currencies/new': 'master.currencies.create',
  '/master-data/document-types': 'master.reference.view',
  '/master-data/document-types/new': 'master.reference.view',
  '/configuration/component-attributes': 'configuration.view',
  '/configuration/component-groups': 'configuration.view',
  '/configuration/component-tabs': 'configuration.view',
  '/configuration/versions': 'configuration.view',
  '/configuration/versions/new': 'configuration.create',
  '/administration/users': 'admin.users.view',
  '/administration/users/new': 'admin.users.create',
  '/administration/roles': 'admin.roles.view',
  '/administration/roles/new': 'admin.roles.create',
  '/administration/document-sequences': 'admin.document_sequences.view',
  '/administration/document-sequences/new': 'admin.document_sequences.create',
  '/administration/system-settings': 'settings.app_config.view',
  '/administration/archive': 'admin.archive.view',
  '/administration/audit-logs': 'admin.audit_logs.view',
}

const REPORT_PAGE_PREFIXES: Readonly<Record<string, string>> = {
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

const SORTED_ROUTES = Object.entries(PAGE_ROUTE_PERMISSIONS)
  .sort(([left], [right]) => right.length - left.length)

function reportPermissionForPath(segments: string[]): string {
  // `/reports/<group>/<slug>` (current) and `/reports/<slug>` (pre-redirect).
  const slug = segments[segments.length - 1] || ''
  const prefix = REPORT_PAGE_PREFIXES[slug]
  return prefix ? `${prefix}.view` : ''
}

/** Resolve the canonical page permission for a route path. */
export function requiredPagePermissionForPath(path: string): string {
  const normalized = normalizeRoutePath(path)

  if (normalized.startsWith('/reports/')) {
    return reportPermissionForPath(normalized.slice('/reports/'.length).split('/'))
  }

  const match = SORTED_ROUTES.find(([route]) => normalized === route || normalized.startsWith(`${route}/`))
  return match ? match[1] : ''
}

/**
 * Legacy permission codes that used to guard the same screen. A session created
 * before the matrix existed may only carry these, so the guard accepts either.
 */
function legacyPermissionsFor(pagePermission: string): readonly string[] {
  if (pagePermission === 'dashboard.view') return ['report.read']
  if (pagePermission === 'dashboard.export' || pagePermission === 'dashboard.summary') return ['report.export']
  if (pagePermission.startsWith('reports.')) {
    return [pagePermission.endsWith('.export') ? 'report.export' : 'report.read']
  }
  if (pagePermission.startsWith('sales.quotations.')) return ['sales.quotations.edit']
  if (pagePermission.startsWith('operations.service_orders.')) return ['operations.service_orders.edit']
  if (pagePermission.startsWith('finance.service_charges.')) return ['finance.service_charges.edit']
  if (pagePermission.startsWith('finance.financial_documents.')) return ['finance.financial_documents.edit']
  if (
    pagePermission.startsWith('finance.chart_of_accounts.')
    || pagePermission.startsWith('finance.financial_accounts.')
    || pagePermission.startsWith('finance.journal_entries.')
    || pagePermission.startsWith('finance.accounting_periods.')
  ) {
    return pagePermission.endsWith('.view') ? ['finance.accounting.view'] : ['finance.accounting.edit']
  }
  if (pagePermission.startsWith('finance.posting_rules.')) {
    return [pagePermission.endsWith('.view') ? 'finance.posting_rules.view' : 'finance.posting_rules.edit']
  }
  if (pagePermission.startsWith('master.')) {
    return [pagePermission.endsWith('.view') ? 'master.reference.view' : 'master.reference.manage']
  }
  if (pagePermission.startsWith('configuration.')) return ['configuration.manage']
  if (pagePermission.startsWith('admin.users.')) return ['admin.user_manage']
  if (pagePermission.startsWith('admin.roles.')) return ['admin.role_manage']
  if (pagePermission.startsWith('admin.document_sequences.')) return ['configuration.manage']
  if (pagePermission === 'admin.archive.view') return ['archive.view']
  if (pagePermission === 'admin.archive.export') return ['report.export']
  if (pagePermission === 'admin.archive.restore') return ['archive.restore']
  if (pagePermission.startsWith('admin.audit_logs.')) return ['audit_log.read']
  if (pagePermission.startsWith('settings.')) return ['settings.manage']
  return []
}

/** Canonical permission first, then the legacy code that used to guard the page. */
export function pagePermissionCandidatesForPath(path: string): string[] {
  const canonical = requiredPagePermissionForPath(path)
  if (!canonical) return []
  return [...new Set([canonical, ...legacyPermissionsFor(canonical)])]
}

/** Page action code for a `<prefix>.view` page permission, e.g. `master.place_roles.update`. */
export function pageActionPermission(
  pagePermission: string | undefined,
  action: 'create' | 'update' | 'delete' | 'export' | 'submit' | 'restore',
): string {
  if (!pagePermission?.endsWith('.view')) return ''
  return `${pagePermission.slice(0, -'.view'.length)}.${action}`
}

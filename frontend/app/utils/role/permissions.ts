import type { AppRolePermissionRow } from '~/types/entities'

/**
 * The Roles & Permissions matrix.
 *
 * A matrix row is one *page*; a checkbox is one action on it. The codes the
 * matrix stores are page codes (`sales.quotations.view`). Turning a page code
 * into the API capabilities that page needs is the backend's job — it does that
 * once when the role is saved and Casbin then evaluates the result. Nothing here
 * implies one permission from another, so the UI can never disagree with the
 * server about what a checkbox grants.
 *
 * `ROLE_DOCUMENT_TYPES` is the fallback page list (labels, order, groups). When
 * the server catalog is available (`/api/v1/permissions/catalog`) it replaces it,
 * so a page added on the backend appears here without a frontend release.
 */

/** Display order for matrix action checkboxes. */
export const ROLE_PERMISSION_ACTIONS = [
  'view',
  'create',
  'update',
  'delete',
  'submit',
  'export',
  'summary',
  'quotation',
  're_quotation',
  'restore',
] as const

export type RolePermissionAction = (typeof ROLE_PERMISSION_ACTIONS)[number]

export interface RoleDocumentTypeDefinition {
  value: string
  labelKey: string
  permissionPrefix: string
  actions: readonly string[]
  group: string
  groupLabelKey?: string
}

const CRUD_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'update', 'delete', 'export']
const READ_ACTIONS: readonly RolePermissionAction[] = ['view', 'export']
const DOCUMENT_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'update', 'delete', 'submit', 'export']
const QUOTATION_ACTIONS: readonly RolePermissionAction[] = [
  'view',
  'create',
  'update',
  'delete',
  'submit',
  're_quotation',
  'quotation',
  'export',
]
const SETTINGS_ACTIONS: readonly RolePermissionAction[] = ['view', 'update']
const BACKUP_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'update']

const group = (key: string) => ({ group: key, groupLabelKey: `lcs.rolePermissions.groups.${key}` })

/** Every page in the application, in navigation order. */
export const ROLE_DOCUMENT_TYPES: readonly RoleDocumentTypeDefinition[] = [
  { ...group('dashboard'), value: 'dashboard', labelKey: 'freight.pages.dashboard', permissionPrefix: 'dashboard', actions: ['view', 'export', 'summary'] },

  { ...group('sales'), value: 'sales_quotations', labelKey: 'freight.pages.quotations', permissionPrefix: 'sales.quotations', actions: QUOTATION_ACTIONS },

  { ...group('operations'), value: 'operations_service_orders', labelKey: 'freight.pages.serviceOrders', permissionPrefix: 'operations.service_orders', actions: DOCUMENT_ACTIONS },
  { ...group('operations'), value: 'reports_service_order_register', labelKey: 'freight.reportCatalog.reports.service-orders.title', permissionPrefix: 'reports.service_order_register', actions: READ_ACTIONS },
  { ...group('operations'), value: 'reports_service_order_status', labelKey: 'freight.reportCatalog.reports.service-order-status.title', permissionPrefix: 'reports.service_order_status', actions: READ_ACTIONS },
  { ...group('operations'), value: 'reports_service_order_containers', labelKey: 'freight.reportCatalog.reports.containers.title', permissionPrefix: 'reports.service_order_containers', actions: READ_ACTIONS },
  { ...group('operations'), value: 'reports_service_order_profitability', labelKey: 'freight.reportCatalog.reports.profitability.title', permissionPrefix: 'reports.service_order_profitability', actions: READ_ACTIONS },

  { ...group('finance'), value: 'finance_service_charges', labelKey: 'freight.pages.serviceCharges', permissionPrefix: 'finance.service_charges', actions: DOCUMENT_ACTIONS },
  { ...group('finance'), value: 'finance_financial_documents', labelKey: 'freight.pages.financialDocuments', permissionPrefix: 'finance.financial_documents', actions: DOCUMENT_ACTIONS },
  { ...group('finance'), value: 'finance_chart_of_accounts', labelKey: 'freight.pages.chartOfAccounts', permissionPrefix: 'finance.chart_of_accounts', actions: CRUD_ACTIONS },
  { ...group('finance'), value: 'finance_financial_accounts', labelKey: 'freight.pages.financialAccounts', permissionPrefix: 'finance.financial_accounts', actions: CRUD_ACTIONS },
  { ...group('finance'), value: 'finance_journal_entries', labelKey: 'freight.pages.journals', permissionPrefix: 'finance.journal_entries', actions: CRUD_ACTIONS },
  { ...group('finance'), value: 'finance_accounting_periods', labelKey: 'freight.pages.accountingPeriods', permissionPrefix: 'finance.accounting_periods', actions: ['view', 'update', 'export'] },
  { ...group('finance'), value: 'finance_posting_rules', labelKey: 'freight.pages.postingRules', permissionPrefix: 'finance.posting_rules', actions: CRUD_ACTIONS },

  { ...group('reports'), value: 'reports_revenue_expense', labelKey: 'freight.reportCatalog.reports.revenue-expense.title', permissionPrefix: 'reports.revenue_expense', actions: READ_ACTIONS },
  { ...group('reports'), value: 'reports_accounts_receivable', labelKey: 'freight.reportCatalog.reports.accounts-receivable.title', permissionPrefix: 'reports.accounts_receivable', actions: READ_ACTIONS },
  { ...group('reports'), value: 'reports_accounts_payable', labelKey: 'freight.reportCatalog.reports.accounts-payable.title', permissionPrefix: 'reports.accounts_payable', actions: READ_ACTIONS },
  { ...group('reports'), value: 'reports_general_ledger', labelKey: 'freight.reportCatalog.reports.general-ledger.title', permissionPrefix: 'reports.general_ledger', actions: READ_ACTIONS },
  { ...group('reports'), value: 'reports_trial_balance', labelKey: 'freight.reportCatalog.reports.trial-balance.title', permissionPrefix: 'reports.trial_balance', actions: READ_ACTIONS },
  { ...group('reports'), value: 'reports_profit_loss', labelKey: 'freight.reportCatalog.reports.profit-loss.title', permissionPrefix: 'reports.profit_loss', actions: READ_ACTIONS },
  { ...group('reports'), value: 'reports_balance_sheet', labelKey: 'freight.reportCatalog.reports.balance-sheet.title', permissionPrefix: 'reports.balance_sheet', actions: READ_ACTIONS },
  { ...group('reports'), value: 'reports_cash_flow', labelKey: 'freight.reportCatalog.reports.cash-flow.title', permissionPrefix: 'reports.cash_flow', actions: READ_ACTIONS },

  { ...group('master'), value: 'master_business_parties', labelKey: 'freight.pages.businessParties', permissionPrefix: 'master.business_parties', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_party_roles', labelKey: 'freight.pages.partyRoles', permissionPrefix: 'master.party_roles', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_place_roles', labelKey: 'freight.pages.placeRoles', permissionPrefix: 'master.place_roles', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_trade_directions', labelKey: 'freight.pages.tradeDirections', permissionPrefix: 'master.trade_directions', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_container_types', labelKey: 'freight.pages.containerTypes', permissionPrefix: 'master.container_types', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_transport_types', labelKey: 'freight.pages.transportTypes', permissionPrefix: 'master.transport_types', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_transport_assets', labelKey: 'freight.pages.transportAssets', permissionPrefix: 'master.transport_assets', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_fee_types', labelKey: 'freight.pages.feeTypes', permissionPrefix: 'master.fee_types', actions: CRUD_ACTIONS },
  { ...group('master'), value: 'master_currencies', labelKey: 'freight.pages.currencies', permissionPrefix: 'master.currencies', actions: CRUD_ACTIONS },

  { ...group('configuration'), value: 'configuration', labelKey: 'freight.nav.configuration', permissionPrefix: 'configuration', actions: CRUD_ACTIONS },

  { ...group('admin'), value: 'admin_document_sequences', labelKey: 'freight.pages.documentSequences', permissionPrefix: 'admin.document_sequences', actions: CRUD_ACTIONS },
  { ...group('admin'), value: 'admin_users', labelKey: 'freight.pages.users', permissionPrefix: 'admin.users', actions: CRUD_ACTIONS },
  { ...group('admin'), value: 'admin_roles', labelKey: 'freight.pages.roles', permissionPrefix: 'admin.roles', actions: CRUD_ACTIONS },
  { ...group('admin'), value: 'admin_audit_logs', labelKey: 'freight.pages.auditLogs', permissionPrefix: 'admin.audit_logs', actions: READ_ACTIONS },
  { ...group('admin'), value: 'admin_archive', labelKey: 'freight.pages.archive', permissionPrefix: 'admin.archive', actions: ['view', 'export', 'restore'] },

  { ...group('settings'), value: 'settings_app_config', labelKey: 'freight.pages.settings', permissionPrefix: 'settings.app_config', actions: SETTINGS_ACTIONS },
  { ...group('settings'), value: 'settings_backup', labelKey: 'freight.pages.backup', permissionPrefix: 'settings.backup', actions: BACKUP_ACTIONS },
] as const

const ACTION_ORDER = new Map<string, number>(ROLE_PERMISSION_ACTIONS.map((action, index) => [action, index]))

export function pagesOf(catalog: readonly RoleDocumentTypeDefinition[] | null | undefined): readonly RoleDocumentTypeDefinition[] {
  return catalog && catalog.length ? catalog : ROLE_DOCUMENT_TYPES
}

export function groupsOf(pages: readonly RoleDocumentTypeDefinition[]): string[] {
  return [...new Set(pages.map(page => page.group))]
}

function sortActions(actions: Iterable<string>): string[] {
  return [...new Set(actions)].sort((left, right) => {
    const leftIndex = ACTION_ORDER.get(left) ?? Number.MAX_SAFE_INTEGER
    const rightIndex = ACTION_ORDER.get(right) ?? Number.MAX_SAFE_INTEGER
    return leftIndex - rightIndex || left.localeCompare(right)
  })
}

/** Ordered, de-duplicated actions; any non-view action keeps `view` selected. */
export function normalizePermissionActions(actions: readonly string[] | null | undefined): string[] {
  const values = new Set((actions || []).filter(Boolean))
  if ([...values].some(action => action !== 'view')) values.add('view')
  return sortActions(values)
}

function normaliseRows(
  rows: readonly AppRolePermissionRow[] | null | undefined,
  pages: readonly RoleDocumentTypeDefinition[],
): AppRolePermissionRow[] {
  const byType = new Map((rows || []).map(row => [row.documentType, row]))
  return pages.map((page) => {
    const existing = byType.get(page.value)
    const actions = normalizePermissionActions(existing?.actions)
      .filter(action => page.actions.includes(action))
    return {
      id: existing?.id || `perm_${page.value}`,
      documentType: page.value,
      onlyIfCreator: Boolean(existing?.onlyIfCreator),
      level: Math.min(9, Math.max(0, Number(existing?.level || 0))),
      actions,
    }
  })
}

/** Merge API rows with the page catalog and discard unknown pages/actions. */
export function normalizePermissionRows(
  rows: readonly AppRolePermissionRow[] | null | undefined,
  includeEmpty = true,
  catalog?: readonly RoleDocumentTypeDefinition[] | null,
): AppRolePermissionRow[] {
  const normalized = normaliseRows(rows, pagesOf(catalog))
  return includeEmpty ? normalized : normalized.filter(row => row.actions.length > 0)
}

/**
 * Build matrix rows from the flat page codes a role stores. `*` (the protected
 * super administrator grant) ticks every box.
 */
export function permissionRowsFromFlatKeys(
  codes: readonly string[] | null | undefined,
  catalog?: readonly RoleDocumentTypeDefinition[] | null,
): AppRolePermissionRow[] {
  const pages = pagesOf(catalog)
  const definitions = new Map(pages.map(page => [page.permissionPrefix, page]))
  const granted = new Map<string, Set<string>>()
  for (const code of codes || []) {
    if (code === '*') {
      for (const page of pages) granted.set(page.value, new Set(page.actions))
      continue
    }
    const dot = code.lastIndexOf('.')
    if (dot <= 0) continue
    const page = definitions.get(code.slice(0, dot))
    const action = code.slice(dot + 1)
    if (!page || !page.actions.includes(action)) continue
    const actions = granted.get(page.value) || new Set<string>()
    actions.add(action)
    granted.set(page.value, actions)
  }
  return normaliseRows(
    [...granted].map(([documentType, actions]) => ({
      id: `perm_${documentType}`,
      documentType,
      onlyIfCreator: false,
      level: 0,
      actions: [...actions],
    })),
    pages,
  )
}

/** Enforce action dependencies consistently for checkbox and API payload flows. */
export function setPermissionAction(
  row: AppRolePermissionRow,
  action: string,
  enabled: boolean,
): AppRolePermissionRow {
  const actions = new Set(normalizePermissionActions(row.actions))
  if (enabled) {
    actions.add(action)
    actions.add('view')
  }
  else if (action === 'view') {
    actions.clear()
  }
  else {
    actions.delete(action)
  }
  return { ...row, actions: sortActions(actions) }
}

/** Page permission codes sent to the API for a set of matrix rows. */
export function permissionRowsToFlatKeys(
  rows: AppRolePermissionRow[],
  catalog?: readonly RoleDocumentTypeDefinition[] | null,
): string[] {
  const pages = pagesOf(catalog)
  const definitions = new Map(pages.map(page => [page.value, page]))
  const keys = new Set<string>()
  for (const row of normaliseRows(rows, pages)) {
    const prefix = definitions.get(row.documentType)?.permissionPrefix
    if (!prefix) continue
    for (const action of row.actions) keys.add(`${prefix}.${action}`)
  }
  return [...keys].sort()
}

/** Every code the matrix can render as a checkbox (`prefix.action`). */
export function pagePermissionCodes(
  catalog?: readonly RoleDocumentTypeDefinition[] | null,
): Set<string> {
  const codes = new Set<string>()
  for (const page of pagesOf(catalog)) {
    for (const action of page.actions) codes.add(`${page.permissionPrefix}.${action}`)
  }
  return codes
}

/**
 * Codes a role holds that the matrix cannot show — a capability granted through
 * the API without its page (for example `backup.read`). They are carried through a
 * save unchanged instead of being dropped by the page-only payload.
 */
export function extraPermissionCodes(
  codes: readonly string[] | null | undefined,
  catalog?: readonly RoleDocumentTypeDefinition[] | null,
): string[] {
  const pages = pagePermissionCodes(catalog)
  return [...new Set((codes || [])
    .map(code => String(code).trim())
    .filter(code => code && code !== '*' && !pages.has(code)))]
    .sort()
}

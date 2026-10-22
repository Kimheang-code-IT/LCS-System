import type { AppRolePermissionRow } from '~/types/entities'

/** Actions exposed per page in the role permission matrix. */
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
  actions: readonly RolePermissionAction[]
  group: string
  groupLabelKey: string
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
const ADMIN_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'update', 'delete', 'export']
const SETTINGS_ACTIONS: readonly RolePermissionAction[] = ['view', 'update']
const BACKUP_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'update']

const group = (key: string) => ({ group: key, groupLabelKey: `lcs.rolePermissions.groups.${key}` })

/**
 * Every page in the application, in navigation order.
 *
 * `permissionPrefix` is combined with an action to form the permission code
 * stored on the role (for example `sales.quotations.view`). The backend maps
 * these page permissions onto the source/API permissions they imply.
 */
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

  { ...group('configuration'), value: 'configuration', labelKey: 'freight.nav.configuration', permissionPrefix: 'configuration', actions: ADMIN_ACTIONS },

  { ...group('admin'), value: 'admin_document_sequences', labelKey: 'freight.pages.documentSequences', permissionPrefix: 'admin.document_sequences', actions: ADMIN_ACTIONS },
  { ...group('admin'), value: 'admin_users', labelKey: 'freight.pages.users', permissionPrefix: 'admin.users', actions: ADMIN_ACTIONS },
  { ...group('admin'), value: 'admin_roles', labelKey: 'freight.pages.roles', permissionPrefix: 'admin.roles', actions: ADMIN_ACTIONS },
  { ...group('admin'), value: 'admin_audit_logs', labelKey: 'freight.pages.auditLogs', permissionPrefix: 'admin.audit_logs', actions: READ_ACTIONS },
  { ...group('admin'), value: 'admin_archive', labelKey: 'freight.pages.archive', permissionPrefix: 'admin.archive', actions: ['view', 'export', 'restore'] },

  { ...group('settings'), value: 'settings_app_config', labelKey: 'freight.pages.settings', permissionPrefix: 'settings.app_config', actions: SETTINGS_ACTIONS },
  { ...group('settings'), value: 'settings_backup', labelKey: 'freight.pages.backup', permissionPrefix: 'settings.backup', actions: BACKUP_ACTIONS },
] as const

export const ROLE_PERMISSION_GROUPS: readonly string[] =
  [...new Set(ROLE_DOCUMENT_TYPES.map(definition => definition.group))]

/**
 * Navigation permission codes still used by module configuration. They are
 * accepted as a fallback by the route guard and hydrated onto the row they
 * belong to, so a role saved before the matrix existed still renders.
 */
export const PAGE_PERMISSION_ALIASES: Record<string, readonly string[]> = {
  reports_accounts_receivable: ['finance.accounts_receivable.view'],
  reports_accounts_payable: ['finance.accounts_payable.view'],
  reports_service_order_profitability: ['finance.job_profitability.view'],
  admin_archive: ['archive.view'],
}

const ALIAS_ROWS: Map<string, string> = new Map(
  ROLE_DOCUMENT_TYPES.flatMap(definition =>
    (PAGE_PERMISSION_ALIASES[definition.value] || []).map(alias => [alias, definition.value] as const),
  ),
)

const ACTION_SET = new Set<string>(ROLE_PERMISSION_ACTIONS)
const LEGACY_ACTION_MAP: Record<string, RolePermissionAction | undefined> = {
  select: 'view',
  read: 'view',
  write: 'update',
  edit: 'update',
  email: 'update',
  report: 'view',
  import: 'create',
  mask: 'view',
  manage: 'update',
  download: 'export',
}

function addAction(target: Map<string, Set<RolePermissionAction>>, value: string, action: RolePermissionAction) {
  const set = target.get(value) || new Set<RolePermissionAction>()
  set.add(action)
  target.set(value, set)
}

function allReportViews(): Array<{ value: string, action: RolePermissionAction }> {
  return ROLE_DOCUMENT_TYPES
    .filter(definition => definition.permissionPrefix.startsWith('reports.'))
    .map(definition => ({ value: definition.value, action: 'view' }))
}

function allReportExports(): Array<{ value: string, action: RolePermissionAction }> {
  return ROLE_DOCUMENT_TYPES
    .filter(definition => definition.permissionPrefix.startsWith('reports.'))
    .map(definition => ({ value: definition.value, action: 'export' }))
}

function allMasterActions(actions: readonly RolePermissionAction[]) {
  return ROLE_DOCUMENT_TYPES
    .filter(definition => definition.permissionPrefix.startsWith('master.'))
    .flatMap(definition => actions.map(action => ({ value: definition.value, action })))
}

/**
 * Legacy source/API permission codes mapped onto matrix pages. Used to hydrate
 * the matrix for roles that were granted permissions before the page catalog
 * existed. New roles store the page codes directly.
 */
export const SOURCE_PERMISSION_PAGE_ACTIONS: Record<string, ReadonlyArray<{ value: string, action: RolePermissionAction }>> = {
  'dashboard.summary': [{ value: 'dashboard', action: 'summary' }],
  'dashboard.view': [{ value: 'dashboard', action: 'view' }],

  'quotation.read': [{ value: 'sales_quotations', action: 'view' }],
  'quotation.create': [{ value: 'sales_quotations', action: 'create' }],
  'quotation.update': [{ value: 'sales_quotations', action: 'update' }],
  'quotation.update_draft': [{ value: 'sales_quotations', action: 'update' }],
  'quotation.delete': [{ value: 'sales_quotations', action: 'delete' }],
  'quotation.submit': [{ value: 'sales_quotations', action: 'submit' }],
  'quotation.send': [
    { value: 'sales_quotations', action: 'submit' },
    { value: 'sales_quotations', action: 'quotation' },
  ],
  'quotation.revise': [{ value: 'sales_quotations', action: 're_quotation' }],
  'quotation.accept': [{ value: 'sales_quotations', action: 'update' }],
  'quotation.convert': [{ value: 'sales_quotations', action: 'update' }, { value: 'operations_service_orders', action: 'view' }],
  'sales.quotations.edit': [
    { value: 'sales_quotations', action: 'update' },
    { value: 'sales_quotations', action: 'delete' },
    { value: 'sales_quotations', action: 'submit' },
    { value: 'sales_quotations', action: 're_quotation' },
    { value: 'sales_quotations', action: 'quotation' },
  ],

  'service_order.read': [{ value: 'operations_service_orders', action: 'view' }],
  'service_order.create': [{ value: 'operations_service_orders', action: 'create' }],
  'service_order.update': [{ value: 'operations_service_orders', action: 'update' }],
  'service_order.delete': [{ value: 'operations_service_orders', action: 'delete' }],
  'service_order.submit': [{ value: 'operations_service_orders', action: 'submit' }],
  'service_order.complete': [{ value: 'operations_service_orders', action: 'submit' }],
  'service_order_config.view': [{ value: 'operations_service_orders', action: 'view' }],
  'service_order_config.create': [{ value: 'operations_service_orders', action: 'create' }],
  'service_order_config.update': [{ value: 'operations_service_orders', action: 'update' }],
  'service_order_config.delete': [{ value: 'operations_service_orders', action: 'delete' }],
  'operations.service_orders.edit': [
    { value: 'operations_service_orders', action: 'update' },
    { value: 'operations_service_orders', action: 'submit' },
    { value: 'operations_service_orders', action: 'delete' },
  ],

  'service_charge.read': [{ value: 'finance_service_charges', action: 'view' }],
  'service_charge.create': [{ value: 'finance_service_charges', action: 'create' }],
  'service_charge.update': [{ value: 'finance_service_charges', action: 'update' }],
  'service_charge.delete': [{ value: 'finance_service_charges', action: 'delete' }],
  'service_charge.submit': [{ value: 'finance_service_charges', action: 'submit' }],
  'service_charge.issue': [{ value: 'finance_service_charges', action: 'submit' }],
  'service_charge.convert_to_invoice': [{ value: 'finance_service_charges', action: 'update' }],
  'finance.service_charges.edit': [
    { value: 'finance_service_charges', action: 'update' },
    { value: 'finance_service_charges', action: 'submit' },
  ],

  'financial_document.read': [{ value: 'finance_financial_documents', action: 'view' }],
  'financial_document.create': [{ value: 'finance_financial_documents', action: 'create' }],
  'financial_document.update': [{ value: 'finance_financial_documents', action: 'update' }],
  'financial_document.update_draft': [{ value: 'finance_financial_documents', action: 'update' }],
  'financial_document.delete': [{ value: 'finance_financial_documents', action: 'delete' }],
  'financial_document.submit': [{ value: 'finance_financial_documents', action: 'submit' }],
  'financial_document.post': [{ value: 'finance_financial_documents', action: 'submit' }],
  'financial_document.reverse': [{ value: 'finance_financial_documents', action: 'update' }],
  'financial_document.allocate': [{ value: 'finance_financial_documents', action: 'update' }],
  'finance.financial_documents.edit': [
    { value: 'finance_financial_documents', action: 'update' },
    { value: 'finance_financial_documents', action: 'submit' },
    { value: 'finance_financial_documents', action: 'delete' },
  ],

  'chart_of_accounts.read': [{ value: 'finance_chart_of_accounts', action: 'view' }],
  'chart_of_accounts.create': [{ value: 'finance_chart_of_accounts', action: 'create' }],
  'chart_of_accounts.update': [{ value: 'finance_chart_of_accounts', action: 'update' }],
  'chart_of_accounts.delete': [{ value: 'finance_chart_of_accounts', action: 'delete' }],
  'chart_of_accounts.manage': [CRUD_ACTIONS.map(action => ({ value: 'finance_chart_of_accounts', action }))].flat(),
  'financial_account.read': [{ value: 'finance_financial_accounts', action: 'view' }],
  'financial_account.create': [{ value: 'finance_financial_accounts', action: 'create' }],
  'financial_account.update': [{ value: 'finance_financial_accounts', action: 'update' }],
  'financial_account.delete': [{ value: 'finance_financial_accounts', action: 'delete' }],
  'journal_entry.read': [
    { value: 'finance_journal_entries', action: 'view' },
    { value: 'finance_chart_of_accounts', action: 'view' },
    { value: 'finance_financial_accounts', action: 'view' },
  ],
  'journal_entry.create': [{ value: 'finance_journal_entries', action: 'create' }],
  'journal_entry.update': [{ value: 'finance_journal_entries', action: 'update' }],
  'journal_entry.delete': [{ value: 'finance_journal_entries', action: 'delete' }],
  'journal_entry.post': [{ value: 'finance_journal_entries', action: 'update' }],
  'accounting_period.read': [{ value: 'finance_accounting_periods', action: 'view' }],
  'accounting_period.update': [{ value: 'finance_accounting_periods', action: 'update' }],
  'accounting_period.close': [{ value: 'finance_accounting_periods', action: 'update' }],
  'posting_rule.read': [{ value: 'finance_posting_rules', action: 'view' }],
  'posting_rule.create': [{ value: 'finance_posting_rules', action: 'create' }],
  'posting_rule.update': [{ value: 'finance_posting_rules', action: 'update' }],
  'posting_rule.delete': [{ value: 'finance_posting_rules', action: 'delete' }],
  'posting_rule.manage': [
    { value: 'finance_posting_rules', action: 'view' },
    { value: 'finance_posting_rules', action: 'create' },
    { value: 'finance_posting_rules', action: 'update' },
    { value: 'finance_posting_rules', action: 'delete' },
  ],

  'report.read': [...allReportViews(), { value: 'dashboard', action: 'view' }],
  'report.export': [
    ...allReportExports(),
    { value: 'dashboard', action: 'export' },
    { value: 'sales_quotations', action: 'export' },
    { value: 'operations_service_orders', action: 'export' },
    { value: 'finance_service_charges', action: 'export' },
    { value: 'finance_financial_documents', action: 'export' },
  ],
  'reports.view': allReportViews(),
  'finance.accounts_receivable.view': [{ value: 'reports_accounts_receivable', action: 'view' }],
  'finance.accounts_payable.view': [{ value: 'reports_accounts_payable', action: 'view' }],
  'finance.job_profitability.view': [{ value: 'reports_service_order_profitability', action: 'view' }],

  'master.reference.view': allMasterActions(['view']),
  'master.reference.manage': allMasterActions(['create', 'update', 'delete']),

  'configuration.read': [{ value: 'configuration', action: 'view' }],
  'configuration.manage': [
    { value: 'configuration', action: 'view' },
    { value: 'configuration', action: 'create' },
    { value: 'configuration', action: 'update' },
    { value: 'configuration', action: 'delete' },
    { value: 'admin_document_sequences', action: 'view' },
    { value: 'admin_document_sequences', action: 'create' },
    { value: 'admin_document_sequences', action: 'update' },
    { value: 'admin_document_sequences', action: 'delete' },
    { value: 'settings_app_config', action: 'view' },
    { value: 'settings_app_config', action: 'update' },
  ],
  'configuration.configure': [{ value: 'configuration', action: 'update' }],

  'user.read': [{ value: 'admin_users', action: 'view' }],
  'user.manage': ADMIN_ACTIONS.map(action => ({ value: 'admin_users', action })),
  'role.read': [{ value: 'admin_roles', action: 'view' }],
  'role.manage': ADMIN_ACTIONS.map(action => ({ value: 'admin_roles', action })),
  'audit_log.read': [{ value: 'admin_audit_logs', action: 'view' }],
  'archive.view': [{ value: 'admin_archive', action: 'view' }],
  'archive.restore': [{ value: 'admin_archive', action: 'restore' }],
  'archive.hard_delete': [{ value: 'admin_archive', action: 'delete' }],

  'settings.manage': [
    { value: 'settings_app_config', action: 'view' },
    { value: 'settings_app_config', action: 'update' },
    { value: 'settings_backup', action: 'view' },
    { value: 'settings_backup', action: 'create' },
    { value: 'settings_backup', action: 'update' },
  ],
  'backup.read': [{ value: 'settings_backup', action: 'view' }],
  'backup.manage': [{ value: 'settings_backup', action: 'create' }, { value: 'settings_backup', action: 'update' }],

  'finance.accounting.view': [
    { value: 'finance_chart_of_accounts', action: 'view' },
    { value: 'finance_financial_accounts', action: 'view' },
    { value: 'finance_journal_entries', action: 'view' },
    { value: 'finance_accounting_periods', action: 'view' },
  ],
  'finance.accounting.create': [
    { value: 'finance_chart_of_accounts', action: 'create' },
    { value: 'finance_financial_accounts', action: 'create' },
    { value: 'finance_journal_entries', action: 'create' },
  ],
  'finance.accounting.edit': [
    { value: 'finance_chart_of_accounts', action: 'update' },
    { value: 'finance_chart_of_accounts', action: 'create' },
    { value: 'finance_chart_of_accounts', action: 'delete' },
    { value: 'finance_financial_accounts', action: 'update' },
    { value: 'finance_financial_accounts', action: 'create' },
    { value: 'finance_financial_accounts', action: 'delete' },
    { value: 'finance_journal_entries', action: 'update' },
    { value: 'finance_accounting_periods', action: 'update' },
  ],
  'finance.accounting.delete': [
    { value: 'finance_chart_of_accounts', action: 'delete' },
    { value: 'finance_financial_accounts', action: 'delete' },
    { value: 'finance_journal_entries', action: 'delete' },
  ],
  'finance.view': [
    { value: 'finance_chart_of_accounts', action: 'view' },
    { value: 'finance_financial_accounts', action: 'view' },
    { value: 'finance_journal_entries', action: 'view' },
    { value: 'finance_accounting_periods', action: 'view' },
  ],
}

export function normalizePermissionActions(actions: readonly string[] | null | undefined): RolePermissionAction[] {
  const normalized = new Set<RolePermissionAction>()
  for (const raw of actions || []) {
    const action = ACTION_SET.has(raw)
      ? raw as RolePermissionAction
      : LEGACY_ACTION_MAP[raw]
    if (action) normalized.add(action)
  }
  if ([...normalized].some(action => action !== 'view')) normalized.add('view')
  return ROLE_PERMISSION_ACTIONS.filter(action => normalized.has(action))
}

/** Merge API rows with the current matrix catalog and discard unknown rows/actions. */
export function normalizePermissionRows(
  rows: readonly AppRolePermissionRow[] | null | undefined,
  includeEmpty = true,
): AppRolePermissionRow[] {
  const byType = new Map((rows || []).map(row => [row.documentType, row]))
  const normalized = ROLE_DOCUMENT_TYPES.map((definition) => {
    const existing = byType.get(definition.value)
    const actions = normalizePermissionActions(existing?.actions)
      .filter(action => definition.actions.includes(action))
    return {
      id: existing?.id || `perm_${definition.value}`,
      documentType: definition.value,
      onlyIfCreator: Boolean(existing?.onlyIfCreator),
      level: Math.min(9, Math.max(0, Number(existing?.level || 0))),
      actions,
    }
  })
  return includeEmpty ? normalized : normalized.filter(row => row.actions.length > 0)
}

/**
 * Build matrix rows from flat permission codes. Accepts both page codes emitted
 * by this matrix (`sales.quotations.view`) and legacy source codes
 * (`quotation.read`) so previously saved roles render correctly.
 */
export function permissionRowsFromFlatKeys(
  codes: readonly string[] | null | undefined,
): AppRolePermissionRow[] {
  const definitions = new Map(ROLE_DOCUMENT_TYPES.map(item => [item.permissionPrefix, item.value]))
  const granted = new Map<string, Set<RolePermissionAction>>()

  for (const code of codes || []) {
    const mapped = SOURCE_PERMISSION_PAGE_ACTIONS[code]
    if (mapped) {
      for (const item of mapped) addAction(granted, item.value, item.action)
      continue
    }

    const dot = code.lastIndexOf('.')
    if (dot > 0) {
      const prefix = code.slice(0, dot)
      const rawAction = code.slice(dot + 1)
      const value = definitions.get(prefix)
      const action = ACTION_SET.has(rawAction)
        ? rawAction as RolePermissionAction
        : LEGACY_ACTION_MAP[rawAction]
      if (value && action) {
        addAction(granted, value, action)
        continue
      }
    }

    const aliasValue = ALIAS_ROWS.get(code)
    if (aliasValue) addAction(granted, aliasValue, 'view')
  }

  return ROLE_DOCUMENT_TYPES.map((definition) => {
    const actions = normalizePermissionActions([...(granted.get(definition.value) || [])])
      .filter(action => definition.actions.includes(action))
    return {
      id: `perm_${definition.value}`,
      documentType: definition.value,
      onlyIfCreator: false,
      level: 0,
      actions,
    }
  })
}

/** Enforce action dependencies consistently for checkbox and API payload flows. */
export function setPermissionAction(
  row: AppRolePermissionRow,
  action: string,
  enabled: boolean,
): AppRolePermissionRow {
  const normalizedAction = ACTION_SET.has(action)
    ? action as RolePermissionAction
    : LEGACY_ACTION_MAP[action]
  if (!normalizedAction) return row
  const actions = new Set(normalizePermissionActions(row.actions))
  if (enabled) {
    actions.add(normalizedAction)
    actions.add('view')
  }
  else if (normalizedAction === 'view') {
    actions.clear()
  }
  else {
    actions.delete(normalizedAction)
  }
  const ordered = ROLE_PERMISSION_ACTIONS.filter(item => actions.has(item))
  return { ...row, actions: ordered }
}

/** Expanded page permission codes sent to the API for a set of matrix rows. */
export function permissionRowsToFlatKeys(rows: AppRolePermissionRow[]): string[] {
  const definitions = new Map(ROLE_DOCUMENT_TYPES.map(item => [item.value, item]))
  const keys = new Set<string>()
  for (const row of normalizePermissionRows(rows, false)) {
    const prefix = definitions.get(row.documentType)?.permissionPrefix
    if (!prefix) continue
    for (const action of row.actions) keys.add(`${prefix}.${action}`)
    // Navigation aliases travel with the row so the page is visible in the menu.
    if (row.actions.includes('view')) {
      for (const alias of PAGE_PERMISSION_ALIASES[row.documentType] || []) keys.add(alias)
    }
  }
  return [...keys].sort()
}

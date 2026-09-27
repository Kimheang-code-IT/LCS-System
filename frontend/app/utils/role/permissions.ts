import type { AppRolePermissionRow } from '~/types/docetra/entities'

/** Actions exposed per page in the role permission matrix. */
export const ROLE_PERMISSION_ACTIONS = ['view', 'create', 'edit', 'delete', 'export'] as const

export type RolePermissionAction = (typeof ROLE_PERMISSION_ACTIONS)[number]

export interface RoleDocumentTypeDefinition {
  value: string
  labelKey: string
  permissionPrefix: string
  actions: readonly RolePermissionAction[]
}

const CRUD_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'edit', 'delete', 'export']
const READ_ACTIONS: readonly RolePermissionAction[] = ['view', 'export']
const ADMIN_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'edit', 'delete']
const SETTINGS_ACTIONS: readonly RolePermissionAction[] = ['view', 'edit']

/**
 * Every page in the application, in navigation order.
 *
 * `permissionPrefix` is combined with an action to form the permission code
 * stored on the role (for example `sales.quotations.view`). The backend maps
 * these page permissions onto the source/API permissions they imply.
 */
export const ROLE_DOCUMENT_TYPES: readonly RoleDocumentTypeDefinition[] = [
  { value: 'dashboard', labelKey: 'freight.pages.dashboard', permissionPrefix: 'dashboard', actions: ['view'] },
  { value: 'sales_quotations', labelKey: 'freight.pages.quotations', permissionPrefix: 'sales.quotations', actions: CRUD_ACTIONS },
  { value: 'operations_service_orders', labelKey: 'freight.pages.serviceOrders', permissionPrefix: 'operations.service_orders', actions: CRUD_ACTIONS },
  { value: 'finance_service_charges', labelKey: 'freight.pages.serviceCharges', permissionPrefix: 'finance.service_charges', actions: CRUD_ACTIONS },
  { value: 'finance_financial_documents', labelKey: 'freight.pages.financialDocuments', permissionPrefix: 'finance.financial_documents', actions: CRUD_ACTIONS },
  { value: 'finance_accounting', labelKey: 'freight.pages.accounting', permissionPrefix: 'finance.accounting', actions: CRUD_ACTIONS },
  { value: 'operations_reports', labelKey: 'freight.pages.operationsReports', permissionPrefix: 'operations.reports', actions: READ_ACTIONS },
  { value: 'finance_reports', labelKey: 'freight.pages.financeReports', permissionPrefix: 'finance.reports', actions: READ_ACTIONS },
  { value: 'master_reference', labelKey: 'freight.nav.master', permissionPrefix: 'master.reference', actions: CRUD_ACTIONS },
  { value: 'configuration', labelKey: 'freight.nav.configuration', permissionPrefix: 'configuration', actions: ADMIN_ACTIONS },
  { value: 'admin_users', labelKey: 'freight.pages.users', permissionPrefix: 'admin.users', actions: ADMIN_ACTIONS },
  { value: 'admin_roles', labelKey: 'freight.pages.roles', permissionPrefix: 'admin.roles', actions: ADMIN_ACTIONS },
  { value: 'admin_document_sequences', labelKey: 'freight.pages.documentSequences', permissionPrefix: 'admin.document_sequences', actions: ADMIN_ACTIONS },
  { value: 'admin_audit_logs', labelKey: 'freight.pages.auditLogs', permissionPrefix: 'admin.audit_logs', actions: READ_ACTIONS },
  { value: 'settings_app_config', labelKey: 'freight.pages.settings', permissionPrefix: 'settings.app_config', actions: SETTINGS_ACTIONS },
  { value: 'settings_backup', labelKey: 'freight.pages.backup', permissionPrefix: 'settings.backup', actions: SETTINGS_ACTIONS },
] as const

/**
 * Legacy source/API permission codes mapped onto matrix pages. Used to hydrate
 * the matrix for roles that were granted permissions before the page catalog
 * existed. New roles store the page codes directly.
 */
const SOURCE_PERMISSION_PAGE_ACTIONS: Record<string, ReadonlyArray<{ value: string, action: RolePermissionAction }>> = {
  'quotation.read': [{ value: 'sales_quotations', action: 'view' }],
  'quotation.create': [{ value: 'sales_quotations', action: 'create' }],
  'quotation.update_draft': [{ value: 'sales_quotations', action: 'edit' }],
  'quotation.send': [{ value: 'sales_quotations', action: 'edit' }],
  'quotation.accept': [{ value: 'sales_quotations', action: 'edit' }],
  'quotation.convert': [{ value: 'sales_quotations', action: 'edit' }, { value: 'operations_service_orders', action: 'view' }],
  'service_order.read': [{ value: 'operations_service_orders', action: 'view' }],
  'service_order.create': [{ value: 'operations_service_orders', action: 'create' }],
  'service_order.update': [{ value: 'operations_service_orders', action: 'edit' }],
  'service_order.complete': [{ value: 'operations_service_orders', action: 'edit' }],
  'service_charge.create': [{ value: 'finance_service_charges', action: 'view' }, { value: 'finance_service_charges', action: 'create' }],
  'service_charge.issue': [{ value: 'finance_service_charges', action: 'edit' }],
  'service_charge.convert_to_invoice': [{ value: 'finance_service_charges', action: 'edit' }],
  'financial_document.read': [{ value: 'finance_financial_documents', action: 'view' }],
  'financial_document.create': [{ value: 'finance_financial_documents', action: 'create' }],
  'financial_document.update_draft': [{ value: 'finance_financial_documents', action: 'edit' }],
  'financial_document.post': [{ value: 'finance_financial_documents', action: 'edit' }],
  'financial_document.reverse': [{ value: 'finance_financial_documents', action: 'edit' }],
  'financial_document.allocate': [{ value: 'finance_financial_documents', action: 'edit' }],
  'journal_entry.read': [{ value: 'finance_accounting', action: 'view' }],
  'journal_entry.create': [{ value: 'finance_accounting', action: 'create' }],
  'journal_entry.post': [{ value: 'finance_accounting', action: 'edit' }],
  'accounting_period.read': [{ value: 'finance_accounting', action: 'view' }],
  'accounting_period.close': [{ value: 'finance_accounting', action: 'edit' }],
  'chart_of_accounts.manage': [{ value: 'finance_accounting', action: 'edit' }],
  'audit_log.read': [{ value: 'admin_audit_logs', action: 'view' }],
  'report.read': [{ value: 'operations_reports', action: 'view' }, { value: 'finance_reports', action: 'view' }],
  'report.export': [{ value: 'operations_reports', action: 'export' }, { value: 'finance_reports', action: 'export' }],
  'master.reference.view': [{ value: 'master_reference', action: 'view' }],
  'master.reference.manage': [
    { value: 'master_reference', action: 'create' },
    { value: 'master_reference', action: 'edit' },
    { value: 'master_reference', action: 'delete' },
  ],
  'configuration.manage': [
    { value: 'configuration', action: 'view' },
    { value: 'configuration', action: 'create' },
    { value: 'configuration', action: 'edit' },
    { value: 'configuration', action: 'delete' },
    { value: 'admin_document_sequences', action: 'view' },
    { value: 'admin_document_sequences', action: 'create' },
    { value: 'admin_document_sequences', action: 'edit' },
    { value: 'admin_document_sequences', action: 'delete' },
    { value: 'settings_app_config', action: 'view' },
    { value: 'settings_app_config', action: 'edit' },
  ],
  'configuration.configure': [{ value: 'configuration', action: 'edit' }],
  'user.read': [{ value: 'admin_users', action: 'view' }],
  'user.manage': [
    { value: 'admin_users', action: 'view' },
    { value: 'admin_users', action: 'create' },
    { value: 'admin_users', action: 'edit' },
    { value: 'admin_users', action: 'delete' },
  ],
  'role.read': [{ value: 'admin_roles', action: 'view' }],
  'role.manage': [
    { value: 'admin_roles', action: 'view' },
    { value: 'admin_roles', action: 'create' },
    { value: 'admin_roles', action: 'edit' },
    { value: 'admin_roles', action: 'delete' },
  ],
  'settings.manage': [
    { value: 'settings_app_config', action: 'view' },
    { value: 'settings_app_config', action: 'edit' },
    { value: 'settings_backup', action: 'view' },
    { value: 'settings_backup', action: 'edit' },
  ],
  'backup.read': [{ value: 'settings_backup', action: 'view' }],
  'backup.manage': [{ value: 'settings_backup', action: 'edit' }],
  'finance.view': [{ value: 'finance_accounting', action: 'view' }],
}

const ACTION_SET = new Set<string>(ROLE_PERMISSION_ACTIONS)
const LEGACY_ACTION_MAP: Record<string, RolePermissionAction | undefined> = {
  select: 'view',
  read: 'view',
  write: 'edit',
  email: 'edit',
  report: 'view',
  import: 'create',
  mask: 'view',
  manage: 'edit',
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
  const add = (value: string, action: RolePermissionAction) => {
    const set = granted.get(value) || new Set<RolePermissionAction>()
    set.add(action)
    granted.set(value, set)
  }

  for (const code of codes || []) {
    const dot = code.lastIndexOf('.')
    if (dot > 0) {
      const prefix = code.slice(0, dot)
      const action = code.slice(dot + 1)
      const value = definitions.get(prefix)
      if (value && ACTION_SET.has(action)) {
        add(value, action as RolePermissionAction)
        continue
      }
    }
    for (const mapping of SOURCE_PERMISSION_PAGE_ACTIONS[code] || []) {
      add(mapping.value, mapping.action)
    }
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
  }
  return [...keys].sort()
}

import type { PermissionScope, SourcePermission } from '~/types/lcs/domain'
import { SOURCE_PERMISSIONS } from '~/types/lcs/domain'
import type { AuthUser } from '~/types/auth-user'

/** Map UI page keys to source permission codes. Frontend hiding is not authorization. */
export const PAGE_TO_SOURCE: Record<string, SourcePermission | SourcePermission[]> = {
  'dashboard.view': 'report.read',
  'sales.quotations.view': 'quotation.read',
  'sales.quotations.create': 'quotation.create',
  'sales.quotations.edit': 'quotation.update_draft',
  'operations.service_orders.view': 'service_order.read',
  'finance.service_charges.view': 'service_charge.create',
  'finance.financial_documents.view': 'financial_document.read',
  'reports.view': 'report.read',
  'admin.users.view': 'user.read',
  'admin.roles.view': 'role.read',
  'admin.audit_logs.view': 'audit_log.read',
  'master.reference.view': ['organization.read', 'branch.read'],
  'configuration.manage': 'service_order.update',
  'admin.organization.view': ['organization.read', 'branch.read'],
  'finance.accounting.view': ['journal_entry.read', 'accounting_period.read'],
}

export function allSourcePermissions(): SourcePermission[] {
  return [...SOURCE_PERMISSIONS]
}

export function userSourcePermissions(user: AuthUser | null | undefined): SourcePermission[] {
  if (!user) return []
  if (user.pageAccess?.includes('ALL_PAGES') || user.permissions?.includes('ALL_PAGES')) {
    return allSourcePermissions()
  }
  if (user.sourcePermissions?.length) {
    return user.sourcePermissions.filter((code): code is SourcePermission =>
      (SOURCE_PERMISSIONS as readonly string[]).includes(code),
    )
  }
  return []
}

export function hasSourcePermission(user: AuthUser | null | undefined, code: SourcePermission) {
  return userSourcePermissions(user).includes(code)
}

export function userPermissionScope(user: AuthUser | null | undefined): PermissionScope {
  if (!user) return 'NONE'
  return user.permissionScope || 'BRANCH'
}

export function canSelectAllBranches(user: AuthUser | null | undefined) {
  return userPermissionScope(user) === 'ORGANIZATION'
}

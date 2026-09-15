import type { PermissionScope, SourcePermission } from '~/types/lcs/domain'

export interface AuthUser {
  id?: number
  name: string
  email: string
  role?: string
  avatar?: string
  /** Flat UI page keys. Frontend hiding is not authorization. */
  permissions?: string[]
  /** Route/page ids the user may access. Empty/undefined = no frontend restriction. */
  pageAccess?: string[]
  organizationId?: number
  organizationCode?: string
  organizationName?: string
  branchId?: number
  branchName?: string
  assignedBranchIds?: number[]
  permissionScope?: PermissionScope
  sourcePermissions?: SourcePermission[]
}

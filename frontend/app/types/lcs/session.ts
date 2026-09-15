import type { PermissionScope, SourcePermission } from '~/types/lcs/domain'

export interface LcsSession {
  userId: number
  userName: string
  organizationId: number
  branchId: number | 'all'
  assignedBranchIds: number[]
  permissionScope: PermissionScope
  sourcePermissions: SourcePermission[]
}

export const ALL_BRANCHES = 'all' as const
export type BranchSelection = number | typeof ALL_BRANCHES

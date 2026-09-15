import type { AuthUser } from '~/types/auth-user'
import type { LcsSession } from '~/types/lcs/session'
import { allSourcePermissions, userPermissionScope, userSourcePermissions } from '~/utils/lcs/permissions'

export function sessionFromUser(
  user: AuthUser | null | undefined,
  organizationId?: number,
  branchId?: number | 'all',
): LcsSession {
  const assigned = user?.assignedBranchIds?.length
    ? [...user.assignedBranchIds]
    : (user?.branchId ? [user.branchId] : [])
  const source = userSourcePermissions(user)
  return {
    userId: user?.id || 0,
    userName: user?.name || 'System',
    organizationId: organizationId || user?.organizationId || 0,
    branchId: branchId ?? user?.branchId ?? 'all',
    assignedBranchIds: assigned,
    permissionScope: userPermissionScope(user),
    sourcePermissions: source.length ? source : (user?.pageAccess?.includes('ALL_PAGES') ? allSourcePermissions() : []),
  }
}

import type { AuthUser } from '~/types/auth-user'

export const AUTH_STORAGE_KEY = 'lcs-auth-user'

/** Cookie-safe user: identity + scope only. Permissions stay in localStorage. */
export function compactAuthUser(user: AuthUser): AuthUser {
  const isAllAccess = user.role === 'SuperAdmin' || user.pageAccess?.includes('ALL_PAGES')
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
    avatar: user.avatar,
    pageAccess: isAllAccess ? ['ALL_PAGES'] : undefined,
    organizationId: user.organizationId,
    organizationCode: user.organizationCode,
    organizationName: user.organizationName,
    branchId: user.branchId,
    branchName: user.branchName,
    assignedBranchIds: user.assignedBranchIds,
    permissionScope: user.permissionScope,
  }
}

/** True when the session includes enough data to enforce page permissions. */
export function sessionHasPermissionData(user: AuthUser | null | undefined): boolean {
  if (!user?.email) return false
  if (user.role === 'SuperAdmin') return true
  if (user.pageAccess?.includes('ALL_PAGES')) return true
  return Boolean(user.permissions?.length || user.pageAccess?.length)
}

/** Allow application-relative navigation only; rejects protocol-relative, control chars, and /auth/ loops. */
export function safeInternalPath(value: unknown): string | null {
  const raw = typeof value === 'string' ? value.trim() : ''
  if (!raw.startsWith('/') || raw.startsWith('//') || /[\u0000-\u001f]/.test(raw) || raw.startsWith('/auth/')) return null
  return raw
}

import type { SourcePermission } from '~/types/lcs/domain'
import { SOURCE_PERMISSIONS } from '~/types/lcs/domain'
import type { AuthUser } from '~/types/auth-user'

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

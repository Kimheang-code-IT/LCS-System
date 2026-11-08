import type { SourcePermission } from '~/types/domain'
import { SOURCE_PERMISSIONS } from '~/types/domain'
import type { AuthUser } from '~/types/api'

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

/**
 * Raw check for a server-sent source capability outside the typed union
 * (e.g. legacy aggregates such as `configuration.manage`): the typed filter
 * above would drop them, while the backend still accepts them for the same
 * command.
 */
export function hasRawSourceCapability(user: AuthUser | null | undefined, code: string) {
  const sent = user?.sourcePermissions as string[] | undefined
  return Boolean(sent && sent.includes(code))
}

import type { AppRolePermissionRow } from '~/types/docetra/entities'
import { ROLE_DOCUMENT_TYPES, permissionRowsToFlatKeys } from '~/utils/role/permissions'

/** All permission keys defined by the system matrix. */
export function getAllSystemPermissionKeys(): string[] {
  const rows: AppRolePermissionRow[] = ROLE_DOCUMENT_TYPES.map(definition => ({
    id: `perm_${definition.value}`,
    documentType: definition.value,
    onlyIfCreator: false,
    level: 0,
    actions: [...definition.actions],
  }))
  const keys = permissionRowsToFlatKeys(rows)
  if (!keys.includes('configuration.manage')) keys.push('configuration.manage')
  return keys.sort()
}

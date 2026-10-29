import type { PermissionCatalog, PermissionCatalogPage } from '~/repositories/contracts/lcs'
import { useLcsRepositories } from '~/repositories'
import type { RoleDocumentTypeDefinition } from '~/utils/role/permissions'
import { pagesOf } from '~/utils/role/permissions'

const EMPTY: PermissionCatalog = { pages: [], roles: [], modules: [] }

/**
 * The permission catalog the Roles & Permissions matrix renders.
 *
 * Pages, actions, labels and role options come from `/api/v1/permissions/catalog`
 * so a page added on the backend shows up without a frontend release. The
 * built-in fallback list keeps the matrix usable while the request is in flight.
 */
export function useRolePermissionCatalog() {
  const catalog = useState<PermissionCatalog>('role-permission-catalog', () => EMPTY)
  const pending = useState<boolean>('role-permission-catalog-pending', () => false)
  const failed = useState<boolean>('role-permission-catalog-failed', () => false)

  const pages = computed<readonly RoleDocumentTypeDefinition[]>(() =>
    pagesOf(catalog.value.pages.map(toDefinition)),
  )

  async function load(force = false) {
    if (pending.value) return
    if (!force && (catalog.value.pages.length || failed.value)) return
    pending.value = true
    try {
      catalog.value = await useLcsRepositories().users.permissionCatalog()
      failed.value = false
    }
    catch {
      // The built-in page list still renders; the matrix is read-only metadata,
      // never the authorization decision.
      failed.value = true
    }
    finally {
      pending.value = false
    }
  }

  return { catalog, pages, pending, load }
}

function toDefinition(page: PermissionCatalogPage): RoleDocumentTypeDefinition {
  return {
    value: page.value,
    labelKey: page.labelKey,
    permissionPrefix: page.prefix,
    actions: page.actions,
    group: page.group,
    groupLabelKey: `lcs.rolePermissions.groups.${page.group}`,
  }
}

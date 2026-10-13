import { describe, expect, it } from 'vitest'
import { freightModules } from '../app/config/freight-modules'
import { lcsReferenceModules } from '../app/config/lcs-reference-modules'
import {
  PAGE_PERMISSION_ALIASES,
  ROLE_DOCUMENT_TYPES,
  SOURCE_PERMISSION_PAGE_ACTIONS,
  permissionRowsFromFlatKeys,
  permissionRowsToFlatKeys,
} from '../app/utils/role/permissions'

/** Every permission code a role can end up holding after a full matrix grant. */
function grantableCodes(): Set<string> {
  const rows = ROLE_DOCUMENT_TYPES.map(definition => ({
    id: `perm_${definition.value}`,
    documentType: definition.value,
    onlyIfCreator: false,
    level: 0,
    actions: [...definition.actions],
  }))
  const codes = new Set(permissionRowsToFlatKeys(rows))
  for (const aliases of Object.values(PAGE_PERMISSION_ALIASES)) {
    for (const alias of aliases) codes.add(alias)
  }
  for (const code of Object.keys(SOURCE_PERMISSION_PAGE_ACTIONS)) codes.add(code)
  return codes
}

function pagePermissions(): { path: string, permission: string }[] {
  return [...freightModules, ...lcsReferenceModules]
    .filter(module => Boolean(module.permission))
    .map(module => ({ path: module.path, permission: module.permission as string }))
}

describe('role permission coverage', () => {
  it('can grant the navigation permission of every page in the app', () => {
    const grantable = grantableCodes()
    const missing = pagePermissions().filter(page => !grantable.has(page.permission))
    expect(missing).toEqual([])
  })

  it('grants navigation aliases together with their row', () => {
    const codes = permissionRowsToFlatKeys([
      {
        id: 'perm_master_reference',
        documentType: 'master_reference',
        onlyIfCreator: false,
        level: 0,
        actions: ['view', 'create'],
      },
      {
        id: 'perm_operations_reports',
        documentType: 'operations_reports',
        onlyIfCreator: false,
        level: 0,
        actions: ['view'],
      },
    ])
    expect(codes).toContain('operations.jobs.view')
    expect(codes).toContain('finance.debit_notes.view')
    expect(codes).toContain('reports.view')
  })

  it('shows the row as checked for a role that only holds an alias', () => {
    const rows = permissionRowsFromFlatKeys(['operations.jobs.view', 'reports.view'])
    const masterData = rows.find(row => row.documentType === 'master_reference')
    const reports = rows.find(row => row.documentType === 'operations_reports')
    expect(masterData?.actions).toEqual(['view'])
    expect(reports?.actions).toEqual(['view'])
  })
})
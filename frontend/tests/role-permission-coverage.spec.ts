import { describe, expect, it } from 'vitest'
import { FREIGHT_REPORTS, freightReportPath } from '../app/config/freight-reports'
import { PAGE_ROUTE_PERMISSIONS } from '../app/utils/freight/page-access'
import { reportRoutePermission } from '../app/utils/freight/report-access'
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

describe('role permission coverage', () => {
  it('can grant the permission of every routed page', () => {
    const grantable = grantableCodes()
    const missing = Object.entries(PAGE_ROUTE_PERMISSIONS)
      .filter(([, permission]) => !grantable.has(permission))
    expect(missing).toEqual([])
  })

  it('can grant the permission of every report route', () => {
    const grantable = grantableCodes()
    const missing = FREIGHT_REPORTS
      .filter(report => !grantable.has(reportRoutePermission(report)))
      .map(freightReportPath)
    expect(missing).toEqual([])
  })

  it('hydrates legacy navigation codes onto the current rows', () => {
    const rows = permissionRowsFromFlatKeys(['master.reference.view', 'report.read', 'archive.view'])
    const row = (documentType: string) => rows.find(item => item.documentType === documentType)

    expect(row('master_business_parties')?.actions).toEqual(['view'])
    expect(row('reports_trial_balance')?.actions).toEqual(['view'])
    expect(row('dashboard')?.actions).toEqual(['view'])
    expect(row('admin_archive')?.actions).toEqual(['view'])
  })

  it('grants matrix navigation aliases together with their row', () => {
    const codes = permissionRowsToFlatKeys([
      {
        id: 'perm_reports_accounts_receivable',
        documentType: 'reports_accounts_receivable',
        onlyIfCreator: false,
        level: 0,
        actions: ['view'],
      },
      {
        id: 'perm_reports_service_order_profitability',
        documentType: 'reports_service_order_profitability',
        onlyIfCreator: false,
        level: 0,
        actions: ['view'],
      },
      {
        id: 'perm_admin_archive',
        documentType: 'admin_archive',
        onlyIfCreator: false,
        level: 0,
        actions: ['view', 'restore'],
      },
    ])
    expect(codes).toContain('finance.accounts_receivable.view')
    expect(codes).toContain('finance.job_profitability.view')
    expect(codes).toContain('archive.view')
  })
})

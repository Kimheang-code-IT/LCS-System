import { describe, expect, it } from 'vitest'
import {
  firstPermittedPagePath,
  pageActionPermission,
  pagePermissionCandidatesForPath,
  requiredPagePermissionForPath,
} from '../app/utils/freight/page-access'

describe('page access', () => {
  it('requires the permission of the specific master-data page', () => {
    expect(requiredPagePermissionForPath('/master-data/business-parties')).toBe('master.business_parties.view')
    expect(requiredPagePermissionForPath('/master-data/place-roles/1')).toBe('master.place_roles.view')
  })

  it('uses the create action for new-record routes', () => {
    expect(requiredPagePermissionForPath('/service-orders/new')).toBe('operations.service_orders.create')
    expect(requiredPagePermissionForPath('/service-orders/42')).toBe('operations.service_orders.view')
  })

  it('maps the archive and reports screens to their matrix pages', () => {
    expect(requiredPagePermissionForPath('/administration/archive')).toBe('admin.archive.view')
    expect(requiredPagePermissionForPath('/reports/finance/trial-balance')).toBe('reports.trial_balance.view')
    expect(requiredPagePermissionForPath('/reports/trial-balance')).toBe('reports.trial_balance.view')
  })

  it('keeps the legacy code as a fallback for existing sessions', () => {
    expect(pagePermissionCandidatesForPath('/administration/archive')).toEqual(['admin.archive.view', 'archive.view'])
    expect(pagePermissionCandidatesForPath('/master-data/fee-types')).toContain('master.reference.view')
  })

  it('maps party roles, asset identity types and capacity units explicitly', () => {
    expect(requiredPagePermissionForPath('/master-data/party-roles')).toBe('master.party_roles.view')
    expect(requiredPagePermissionForPath('/master-data/party-roles/7')).toBe('master.party_roles.view')
    expect(requiredPagePermissionForPath('/master-data/asset-identity-types')).toBe('master.transport_assets.view')
    expect(requiredPagePermissionForPath('/master-data/asset-identity-types/new')).toBe('master.transport_assets.view')
    expect(requiredPagePermissionForPath('/master-data/capacity-units')).toBe('master.transport_assets.view')
    expect(requiredPagePermissionForPath('/master-data/capacity-units/3')).toBe('master.transport_assets.view')
    // The transport-asset vocabulary and party roles keep the legacy coarse
    // code alongside their screen code, mirroring the backend collection guard.
    expect(pagePermissionCandidatesForPath('/master-data/asset-identity-types'))
      .toEqual(['master.transport_assets.view', 'master.reference.view'])
    expect(pagePermissionCandidatesForPath('/master-data/capacity-units'))
      .toEqual(['master.transport_assets.view', 'master.reference.view'])
    expect(pagePermissionCandidatesForPath('/master-data/party-roles'))
      .toEqual(['master.party_roles.view', 'master.reference.view'])
  })

  it('derives master action codes from the screen page permission', () => {
    expect(pageActionPermission('master.party_roles.view', 'create')).toBe('master.party_roles.create')
    expect(pageActionPermission('master.transport_assets.view', 'update')).toBe('master.transport_assets.update')
    expect(pageActionPermission('master.transport_assets.view', 'delete')).toBe('master.transport_assets.delete')
    expect(pageActionPermission('master.reference.view', 'update')).toBe('master.reference.update')
  })

  it('finds the first permitted page for accounts without a landing screen', () => {
    const has = (codes: string[]) => (code: string) => codes.includes(code)
    // A narrow account without any privileged landing page still lands somewhere.
    expect(firstPermittedPagePath(has(['master.party_roles.view']))).toBe('/master-data/party-roles')
    expect(firstPermittedPagePath(has(['master.transport_assets.view']))).toBe('/master-data/transport-assets')
    expect(firstPermittedPagePath(has(['reports.cash_flow.view']))).toBe('/reports/finance/cash-flow')
    expect(firstPermittedPagePath(has([]))).toBeUndefined()
  })
})

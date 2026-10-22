import { describe, expect, it } from 'vitest'
import {
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
})

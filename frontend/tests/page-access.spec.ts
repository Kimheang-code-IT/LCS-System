import { describe, expect, it } from 'vitest'
import { requiredPagePermissionForPath } from '../app/utils/freight/page-access'

describe('page access', () => {
  it('requires master permission for master-data routes', () => {
    expect(requiredPagePermissionForPath('/master-data/business-parties')).toBe('master.reference.view')
    expect(requiredPagePermissionForPath('/master-data/places/1')).toBe('master.reference.view')
  })

  it('requires operations permission for service-order routes', () => {
    expect(requiredPagePermissionForPath('/service-orders')).toBe('operations.service_orders.view')
    expect(requiredPagePermissionForPath('/service-orders/42')).toBe('operations.service_orders.view')
  })
})

import { describe, expect, it } from 'vitest'
import { maintenanceRecoveryPath, redirectForMaintenance } from '../app/utils/auth/maintenance'

describe('maintenance navigation and recovery', () => {
  it('directs business refusals to maintenance without confusing generic outages', () => {
    expect(redirectForMaintenance(503, 'MAINTENANCE_MODE', '/quotations/42')).toBe(true)
    expect(redirectForMaintenance(503, 'SESSION_IDENTITY_UNAVAILABLE', '/quotations')).toBe(false)
    expect(redirectForMaintenance(403, 'ACCESS_DENIED', '/quotations')).toBe(false)
  })
  it('preserves exact recovery paths when ancillary branding or shell requests are refused', () => {
    for (const path of ['/maintenance', '/auth/login', '/auth/change-password', '/administration/system-settings/']) {
      expect(maintenanceRecoveryPath(path)).toBe(true)
      expect(redirectForMaintenance(503, 'MAINTENANCE_MODE', path)).toBe(false)
    }
    expect(maintenanceRecoveryPath('/administration/system-settings/other')).toBe(false)
    expect(maintenanceRecoveryPath('/administration/users')).toBe(false)
  })
})

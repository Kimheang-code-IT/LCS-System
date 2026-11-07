import { describe, expect, it } from 'vitest'
import { compactMaintenanceChange } from '../app/utils/settings/maintenance'
import type { MaintenanceSettings } from '../app/types/maintenance'

const stored: MaintenanceSettings = {
  enabled: false, active: false, scheduled: false, forced: false,
  startsAt: '2026-11-05T12:00:00Z', endsAt: '2026-11-05T13:00:00Z',
  reason: 'Old reason', message: 'Public message', estimatedDowntime: 'One hour',
  supportContact: 'Support desk', revision: 7, deploymentStatus: 'pending',
  operationsGroupId: '-10001', developerGroupId: '-10002', history: [],
}

describe('compact maintenance editor payload', () => {
  it('activates immediately while preserving hidden configuration and stale-write revision', () => {
    const input = compactMaintenanceChange(stored, { enabled: true, reason: '  Routine update  ' })
    expect(input).toEqual({
      enabled: true, reason: 'Routine update', startsAt: null,
      endsAt: stored.endsAt, message: stored.message, estimatedDowntime: stored.estimatedDowntime,
      supportContact: stored.supportContact, operationsGroupId: '-10001', developerGroupId: '-10002',
      revision: 7, confirm: 'MAINTENANCE',
    })
    expect(stored.reason).toBe('Old reason')
  })
  it('uses the protected reopen operation without fabricating deployment checks', () => {
    const input = compactMaintenanceChange({ ...stored, enabled: true, active: true }, { enabled: false, reason: 'Recovery complete' })
    expect(input.confirm).toBe('REOPEN')
    expect(input.enabled).toBe(false)
    expect(input).not.toHaveProperty('checks')
    expect(input).not.toHaveProperty('deploymentStatus')
  })
  it('keeps a scheduled start when only Reason changes', () => {
    const input = compactMaintenanceChange({ ...stored, enabled: true, scheduled: true }, { enabled: true, reason: 'Updated reason' })
    expect(input.startsAt).toBe(stored.startsAt)
  })
})

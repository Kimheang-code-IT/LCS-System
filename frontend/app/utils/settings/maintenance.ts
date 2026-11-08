import type { MaintenanceChange, MaintenanceSettings } from '~/types/maintenance'

export function compactMaintenanceChange(stored: MaintenanceSettings, draft: { enabled: boolean, reason: string }): MaintenanceChange {
  return {
    enabled: draft.enabled,
    reason: draft.reason.trim(),
    // A new toggle takes effect immediately; editing Reason preserves an existing schedule.
    startsAt: draft.enabled !== stored.enabled ? null : stored.startsAt,
    endsAt: stored.endsAt,
    message: stored.message,
    estimatedDowntime: stored.estimatedDowntime,
    supportContact: stored.supportContact,
    operationsGroupId: stored.operationsGroupId,
    developerGroupId: stored.developerGroupId,
    revision: stored.revision,
    confirm: draft.enabled ? 'MAINTENANCE' : 'REOPEN',
  }
}

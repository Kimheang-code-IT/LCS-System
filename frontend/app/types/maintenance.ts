export type MaintenanceStatus = {
  active: boolean
  scheduled: boolean
  forced: boolean
  startsAt: string | null
  endsAt: string | null
  message: string
  estimatedDowntime: string
  supportContact: string
}
export type MaintenanceSettings = MaintenanceStatus & {
  enabled: boolean
  revision: number
  reason: string
  operationsGroupId: string
  developerGroupId: string
  deploymentStatus: string
  updatedAt?: string
  updatedBy?: number
  history: { id: number, event: string, at: string, by: number | null, reason: string }[]
}
export type MaintenanceChange = Pick<MaintenanceSettings, 'enabled' | 'startsAt' | 'endsAt' | 'message' | 'estimatedDowntime' | 'supportContact' | 'reason' | 'revision' | 'operationsGroupId' | 'developerGroupId'> & { confirm: string }
export const deploymentChecks = ['drained', 'backup', 'migrations', 'database', 'backend', 'authentication', 'workflows', 'jobs'] as const

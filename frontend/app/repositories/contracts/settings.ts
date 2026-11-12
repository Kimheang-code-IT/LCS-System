import type {
  AppConfig,
  AppConfigPatch,
  AppInfo,
  BackupRunSummary,
  BackupStatus,
  ConnectionStatus,
  StorageJob,
  StorageOverview,
  StorageProviderStatus,
} from '~/types/settings'

export interface AppInfoRepository {
  get: () => Promise<AppInfo>
  update: (input: Partial<AppInfo>) => Promise<AppInfo>
  reset: () => Promise<AppInfo>
}

export interface AppConfigRepository {
  get: () => Promise<AppConfig>
  update: (input: AppConfigPatch) => Promise<AppConfig>
  testEmailConnection: () => Promise<{ status: ConnectionStatus, message: string }>
  sendTestEmail: (to: string) => Promise<{ status: ConnectionStatus, message: string }>
  testTelegramConnection: () => Promise<{ status: ConnectionStatus, message: string }>
  sendTestTelegramMessage: (destinationId?: string) => Promise<{ status: ConnectionStatus, message: string }>
  testTelegramClientConnection: () => Promise<{ status: ConnectionStatus, message: string }>
  sendTestTelegramClientMessage: () => Promise<{ status: ConnectionStatus, message: string }>
  resetData: (confirm: string) => Promise<{ reset: boolean }>
}

export interface BackupRepository {
  status: () => Promise<BackupStatus>
  runs: (params?: { page?: number, pageSize?: number }) => Promise<{ items: BackupRunSummary[], meta: { page: number, page_size: number, total: number } }>
  run: () => Promise<BackupRunSummary>
  restore: (confirm: string, tables?: string[]) => Promise<{ restored: number, inserted: number, updated: number, tables: Array<{ table: string, inserted: number, updated: number }> }>
  testConnection: () => Promise<{ status: ConnectionStatus, message: string, title?: string, sheets?: string[] }>
}

/** Multi-provider file storage (Settings → Storage & Backup). */
export interface StorageRepository {
  status: () => Promise<{ config: AppConfig['storage'], providers: Record<'r2' | 'gdrive', StorageProviderStatus>, overview: StorageOverview }>
  testConnection: (provider: 'r2' | 'gdrive') => Promise<{ status: string, message: string }>
  googleAuthorize: () => Promise<{ url: string }>
  googleDisconnect: () => Promise<{ status: string }>
  backupNow: () => Promise<StorageJob>
  backupJobs: () => Promise<StorageJob[]>
  backupRetry: () => Promise<StorageJob>
  setPrimary: (provider: 'r2' | 'gdrive') => Promise<{ primaryProvider: string }>
  migrationPreview: (target: 'r2' | 'gdrive') => Promise<{ target: string, byProvider: Record<string, number>, files: number, bytes: number, alreadyOnTarget: number, toMigrate: number }>
  migrationStart: (target: 'r2' | 'gdrive', dryRun: boolean) => Promise<StorageJob>
  progress: () => Promise<StorageJob | null>
  migrationCleanup: (confirm: string) => Promise<{ removed: number }>
  restorePreview: () => Promise<{ restorable: number, replicas: number, primary: string }>
  restore: (confirm: string) => Promise<StorageJob>
}

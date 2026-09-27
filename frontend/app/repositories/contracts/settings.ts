import type { AppConfig, AppInfo, BackupRunSummary, BackupStatus, ConnectionStatus } from '~/types/docetra/settings'

export interface AppInfoRepository {
  get: () => Promise<AppInfo>
  update: (input: Partial<AppInfo>) => Promise<AppInfo>
  reset: () => Promise<AppInfo>
}

export interface AppConfigRepository {
  get: () => Promise<AppConfig>
  update: (input: Partial<AppConfig>) => Promise<AppConfig>
  testEmailConnection: () => Promise<{ status: ConnectionStatus, message: string }>
  sendTestEmail: (to: string) => Promise<{ status: ConnectionStatus, message: string }>
  testTelegramConnection: () => Promise<{ status: ConnectionStatus, message: string }>
  sendTestTelegramMessage: (destinationId?: string) => Promise<{ status: ConnectionStatus, message: string }>
  resetData: (confirm: string) => Promise<{ reset: boolean }>
}

export interface BackupRepository {
  status: () => Promise<BackupStatus>
  runs: (params?: { page?: number, pageSize?: number }) => Promise<{ items: BackupRunSummary[], meta: { page: number, page_size: number, total: number } }>
  run: () => Promise<BackupRunSummary>
  restore: (confirm: string, tables?: string[]) => Promise<{ restored: number, inserted: number, updated: number, tables: Array<{ table: string, inserted: number, updated: number }> }>
  testConnection: () => Promise<{ status: ConnectionStatus, message: string, title?: string, sheets?: string[] }>
}

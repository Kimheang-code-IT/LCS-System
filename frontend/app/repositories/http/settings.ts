import type {
  AppConfigRepository,
  AppInfoRepository,
  BackupRepository,
  StorageRepository,
} from '~/repositories/contracts/settings'
import type { ApiResponse } from '~/types/common'
import type {
  AppConfig,
  AppInfo,
  BackupRunSummary,
  BackupStatus,
  ConnectionStatus,
  StorageJob,
  StorageOverview,
  StorageProviderStatus,
} from '~/types/settings'
import { ApiEndpoints } from '~/utils/constants/api-endpoints'
import { unwrapApiData } from './response'

type ConnectionResult = { status: ConnectionStatus; message: string }

export function createHttpAppInfoRepository(): AppInfoRepository {
  const api = useApi()
  return {
    get: async () => unwrapApiData(await api.get<AppInfo | ApiResponse<AppInfo>>(ApiEndpoints.APP_INFO)),
    update: async input => unwrapApiData(await api.patch<AppInfo | ApiResponse<AppInfo>>(ApiEndpoints.APP_INFO, input)),
    reset: async () => unwrapApiData(await api.post<AppInfo | ApiResponse<AppInfo>>(ApiEndpoints.APP_INFO_RESET, {})),
  }
}

export function createHttpAppConfigRepository(): AppConfigRepository {
  const api = useApi()
  const postResult = async (endpoint: string, body: Record<string, unknown> = {}) =>
    unwrapApiData(await api.post<ConnectionResult | ApiResponse<ConnectionResult>>(endpoint, body))

  return {
    get: async () => unwrapApiData(await api.get<AppConfig | ApiResponse<AppConfig>>(ApiEndpoints.APP_CONFIG)),
    update: async input => unwrapApiData(await api.patch<AppConfig | ApiResponse<AppConfig>>(ApiEndpoints.APP_CONFIG, input)),
    testEmailConnection: () => postResult(ApiEndpoints.APP_CONFIG_TEST_EMAIL),
    sendTestEmail: to => postResult(ApiEndpoints.APP_CONFIG_SEND_TEST_EMAIL, { to }),
    testTelegramConnection: () => postResult(ApiEndpoints.APP_CONFIG_TEST_TELEGRAM),
    sendTestTelegramMessage: destinationId => postResult(
      ApiEndpoints.APP_CONFIG_SEND_TEST_TELEGRAM,
      destinationId ? { destinationId } : {},
    ),
    testTelegramClientConnection: () => postResult(ApiEndpoints.APP_CONFIG_TEST_TELEGRAM_CLIENT),
    sendTestTelegramClientMessage: () => postResult(ApiEndpoints.APP_CONFIG_SEND_TEST_TELEGRAM_CLIENT),
    resetData: async confirm =>
      unwrapApiData(await api.post<{ reset: boolean } | ApiResponse<{ reset: boolean }>>(
        ApiEndpoints.SETTINGS_RESET_DATA,
        { confirm },
      )),
  }
}

export function createHttpBackupRepository(): BackupRepository {
  const api = useApi()
  return {
    status: async () =>
      unwrapApiData(await api.get<BackupStatus | ApiResponse<BackupStatus>>(ApiEndpoints.BACKUP_STATUS)),
    runs: async (params = {}) => {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.pageSize) query.set('page_size', String(params.pageSize))
      const suffix = query.toString() ? `?${query.toString()}` : ''
      return unwrapApiData(
        await api.get<{ items: BackupRunSummary[], meta: { page: number, page_size: number, total: number } } | ApiResponse<{ items: BackupRunSummary[], meta: { page: number, page_size: number, total: number } }>>(
          `${ApiEndpoints.BACKUP_RUNS}${suffix}`,
        ),
      )
    },
    run: async () =>
      unwrapApiData(
        await api.post<BackupRunSummary | ApiResponse<BackupRunSummary>>(ApiEndpoints.BACKUP_RUN, {}),
      ),
    restore: async (confirm, tables) =>
      unwrapApiData(
        await api.post<{ restored: number, inserted: number, updated: number, tables: Array<{ table: string, inserted: number, updated: number }> } | ApiResponse<{ restored: number, inserted: number, updated: number, tables: Array<{ table: string, inserted: number, updated: number }> }>>(
          ApiEndpoints.BACKUP_RESTORE,
          { confirm, ...(tables?.length ? { tables } : {}) },
        ),
      ),
    testConnection: async () =>
      unwrapApiData(
        await api.post<{ status: ConnectionStatus, message: string, title?: string, sheets?: string[] } | ApiResponse<{ status: ConnectionStatus, message: string, title?: string, sheets?: string[] }>>(
          ApiEndpoints.BACKUP_TEST_CONNECTION,
          {},
        ),
      ),
  }
}

type StorageStatusResponse = {
  config: AppConfig['storage']
  providers: Record<'r2' | 'gdrive', StorageProviderStatus>
  overview: StorageOverview
}

export function createHttpStorageRepository(): StorageRepository {
  const api = useApi()
  const post = async (endpoint: string, body: Record<string, unknown> = {}) =>
    unwrapApiData(await api.post<StorageJob | ApiResponse<StorageJob>>(endpoint, body))
  const plain = async <T>(endpoint: string, body: Record<string, unknown> = {}) =>
    unwrapApiData(await api.post<T | ApiResponse<T>>(endpoint, body))

  return {
    status: async () =>
      unwrapApiData(await api.get<StorageStatusResponse | ApiResponse<StorageStatusResponse>>(ApiEndpoints.STORAGE_STATUS)),
    testConnection: provider =>
      plain<{ status: string, message: string }>(ApiEndpoints.STORAGE_TEST_CONNECTION, { provider }),
    googleAuthorize: () => plain<{ url: string }>(ApiEndpoints.STORAGE_GOOGLE_AUTHORIZE),
    googleDisconnect: () => plain<{ status: string }>(ApiEndpoints.STORAGE_GOOGLE_DISCONNECT),
    backupNow: () => post(ApiEndpoints.STORAGE_BACKUP_NOW),
    backupJobs: async () => unwrapApiData(await api.get<StorageJob[] | ApiResponse<StorageJob[]>>(ApiEndpoints.STORAGE_BACKUP_JOBS)),
    backupRetry: () => post(ApiEndpoints.STORAGE_BACKUP_RETRY),
    setPrimary: provider => plain<{ primaryProvider: string }>(ApiEndpoints.STORAGE_PRIMARY, { provider }),
    migrationPreview: async target => {
      const query = `?target=${encodeURIComponent(target)}`
      return unwrapApiData(
        await api.get<
          { target: string, byProvider: Record<string, number>, files: number, bytes: number, alreadyOnTarget: number, toMigrate: number } | ApiResponse<{ target: string, byProvider: Record<string, number>, files: number, bytes: number, alreadyOnTarget: number, toMigrate: number }>
        >(`${ApiEndpoints.STORAGE_MIGRATION_PREVIEW}${query}`),
      )
    },
    migrationStart: (target, dryRun) => post(ApiEndpoints.STORAGE_MIGRATION_START, { target, dryRun }),
    progress: async () =>
      unwrapApiData(await api.get<StorageJob | null | ApiResponse<StorageJob | null>>(ApiEndpoints.STORAGE_PROGRESS)),
    migrationCleanup: confirm => plain<{ removed: number }>(ApiEndpoints.STORAGE_MIGRATION_CLEANUP, { confirm }),
    restorePreview: async () =>
      unwrapApiData(
        await api.get<{ restorable: number, replicas: number, primary: string } | ApiResponse<{ restorable: number, replicas: number, primary: string }>>(
          ApiEndpoints.STORAGE_RESTORE_PREVIEW,
        ),
      ),
    restore: confirm => post(ApiEndpoints.STORAGE_RESTORE, { confirm }),
  } as StorageRepository
}

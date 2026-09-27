import type { AppConfigRepository, AppInfoRepository, BackupRepository } from '~/repositories/contracts/settings'
import type { ApiResponse } from '~/types/docetra/common'
import type { AppConfig, AppInfo, BackupRunSummary, BackupStatus, ConnectionStatus } from '~/types/docetra/settings'
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

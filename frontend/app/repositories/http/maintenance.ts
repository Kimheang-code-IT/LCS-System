import type { MaintenanceChange, MaintenanceSettings, MaintenanceStatus } from '~/types/maintenance'
import type { ApiResponse } from '~/types/common'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { unwrapApiData } from './response'

export function useMaintenanceRepository() {
  const api = useApi()
  return {
    status: async () => unwrapApiData(await api.get<ApiResponse<MaintenanceStatus>>(ApiV1Endpoints.MAINTENANCE_STATUS, { suppressErrorToast: true })),
    get: async () => unwrapApiData(await api.get<ApiResponse<MaintenanceSettings>>(ApiV1Endpoints.MAINTENANCE)),
    save: async (body: MaintenanceChange) => unwrapApiData(await api.put<ApiResponse<MaintenanceSettings>>(ApiV1Endpoints.MAINTENANCE, body, { suppressErrorToast: true })),
    deployment: async (body: Record<string, unknown>) => unwrapApiData(await api.post<ApiResponse<MaintenanceSettings>>(ApiV1Endpoints.MAINTENANCE_DEPLOYMENT, body, { suppressErrorToast: true })),
  }
}

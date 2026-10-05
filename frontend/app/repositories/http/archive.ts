import type { ArchiveOptions, ArchiveRecord, ArchiveRepository } from '~/repositories/contracts/archive'
import { unwrapApiData } from '~/repositories/http/response'
import type { ApiResponse } from '~/types/lcs/common'
import type { LcsPaged } from '~/types/lcs/domain'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'

export function createHttpArchiveRepository(): ArchiveRepository {
  const api = useApi()
  return {
    list: async query => unwrapApiData(
      await api.get<ApiResponse<LcsPaged<ArchiveRecord>>>(ApiV1Endpoints.ARCHIVE, { query }),
    ),
    options: async () => unwrapApiData(
      await api.get<ApiResponse<ArchiveOptions>>(ApiV1Endpoints.ARCHIVE_OPTIONS),
    ),
    get: async (entityType, entityId) => unwrapApiData(
      await api.get<ApiResponse<ArchiveRecord>>(ApiV1Endpoints.ARCHIVE_RECORD(entityType, entityId)),
    ),
    restore: async (entityType, entityId) => {
      await api.post(ApiV1Endpoints.ARCHIVE_RESTORE(entityType, entityId), {})
    },
    hardDelete: async (entityType, entityId) => {
      await api.delete(ApiV1Endpoints.ARCHIVE_RECORD(entityType, entityId))
    },
  }
}

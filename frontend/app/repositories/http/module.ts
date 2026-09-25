import type { FreightModule } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import type { ModuleRepository } from '~/repositories/contracts/module'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { unwrapApiData } from '~/repositories/http/response'
import type { ApiResponse } from '~/types/docetra/common'
import type { LcsPaged } from '~/types/lcs/domain'
import { stripOfficialNumberFields } from '~/utils/lcs/sequences'

function asPaged(data: FreightRecord[] | LcsPaged<FreightRecord>): LcsPaged<FreightRecord> {
  if (Array.isArray(data)) {
    return { items: data, meta: { page: 1, page_size: data.length, total: data.length } }
  }
  return data
}

function moduleEndpoint(module: FreightModule) {
  switch (module.collection) {
    case 'quotations': return ApiV1Endpoints.QUOTATIONS
    case 'jobs': return ApiV1Endpoints.SERVICE_ORDERS
    case 'jobCharges': return ApiV1Endpoints.SERVICE_CHARGES
    case 'debitNotes': return ApiV1Endpoints.FINANCIAL_DOCUMENTS
    case 'journals': return ApiV1Endpoints.JOURNALS
    case 'auditLogs': return ApiV1Endpoints.AUDIT_EVENTS
    default: return `/api/v1/${module.collection}`
  }
}

export function createHttpModuleRepository(module: FreightModule): ModuleRepository {
  const api = useApi()
  const base = moduleEndpoint(module)

  return {
    list: async (query = {}) =>
      asPaged(unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(base, { query }))),
    get: async id =>
      unwrapApiData(await api.get<ApiResponse<FreightRecord>>(`${base}/${id}`)),
    create: async (input) => {
      const body = ['quotations', 'jobCharges', 'debitNotes', 'journals'].includes(module.collection)
        ? stripOfficialNumberFields(input, module.collection)
        : input
      return unwrapApiData(await api.post<ApiResponse<FreightRecord>>(base, body))
    },
    update: async (id, input) =>
      unwrapApiData(await api.put<ApiResponse<FreightRecord>>(`${base}/${id}`, { ...input, id })),
    remove: async (ids) => {
      await api.delete<ApiResponse<void>>(base, { body: { ids } })
    },
  }
}

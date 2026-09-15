import type { DynamicRowInput, DynamicTabsRepository } from '~/repositories/contracts/dynamic-tabs'
import type { ApiResponse } from '~/types/docetra/common'
import type {
  DynamicTab,
  DynamicTabColumn,
  DynamicTabRow,
  DynamicTabsBootstrap,
} from '~/types/freight/dynamic-tabs'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { unwrapApiData } from '~/repositories/http/response'

function asArray<T>(data: T[] | { items: T[] }): T[] {
  if (Array.isArray(data)) return data
  return Array.isArray(data?.items) ? data.items : []
}

export function createHttpDynamicTabsRepository(): DynamicTabsRepository {
  const api = useApi()
  return {
    bootstrap: async serviceOrderId =>
      unwrapApiData(await api.get<ApiResponse<DynamicTabsBootstrap>>(ApiV1Endpoints.SERVICE_ORDER_DYNAMIC_TABS(serviceOrderId))),
    listTabs: async (includeArchived = false) =>
      asArray(unwrapApiData(await api.get<ApiResponse<DynamicTab[]>>(ApiV1Endpoints.SERVICE_ORDER_TABS, { query: { include_archived: includeArchived, page_size: 200 } }))),
    createTab: async input =>
      unwrapApiData(await api.post<ApiResponse<DynamicTab>>(ApiV1Endpoints.SERVICE_ORDER_TABS, input)),
    updateTab: async (id, input) =>
      unwrapApiData(await api.patch<ApiResponse<DynamicTab>>(ApiV1Endpoints.SERVICE_ORDER_TAB(id), input)),
    deleteTab: async id =>
      unwrapApiData(await api.delete<ApiResponse<{ archived: boolean, id: string }>>(ApiV1Endpoints.SERVICE_ORDER_TAB(id))),
    listColumns: async (tabId, includeArchived = false) =>
      asArray(unwrapApiData(await api.get<ApiResponse<DynamicTabColumn[]>>(ApiV1Endpoints.SERVICE_ORDER_TAB_COLUMNS(tabId), { query: { include_archived: includeArchived } }))),
    createColumn: async (tabId, input) =>
      unwrapApiData(await api.post<ApiResponse<DynamicTabColumn>>(ApiV1Endpoints.SERVICE_ORDER_TAB_COLUMNS(tabId), input)),
    updateColumn: async (id, input) =>
      unwrapApiData(await api.patch<ApiResponse<DynamicTabColumn>>(ApiV1Endpoints.SERVICE_ORDER_COLUMN(id), input)),
    deleteColumn: async id =>
      unwrapApiData(await api.delete<ApiResponse<{ archived: boolean, id: string }>>(ApiV1Endpoints.SERVICE_ORDER_COLUMN(id))),
    reorderColumns: async (tabId, orderedIds) =>
      asArray(unwrapApiData(await api.post<ApiResponse<DynamicTabColumn[]>>(ApiV1Endpoints.SERVICE_ORDER_TAB_COLUMNS_REORDER(tabId), { orderedIds }))),
    saveRows: async (serviceOrderId, tabId, rows: DynamicRowInput[]) => {
      const result = unwrapApiData(
        await api.post<ApiResponse<{ items: DynamicTabRow[] }>>(
          ApiV1Endpoints.SERVICE_ORDER_DYNAMIC_ROWS_BULK(serviceOrderId, tabId),
          { rows },
        ),
      )
      return result?.items ?? []
    },
  }
}

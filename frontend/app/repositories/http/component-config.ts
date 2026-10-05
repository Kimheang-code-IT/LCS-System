import type { ComponentConfigRepository } from '~/repositories/contracts/component-config'
import type { ApiResponse } from '~/types/lcs/common'
import type {
  ComponentAttribute,
  ComponentGroup,
  ComponentGroupAttribute,
  ComponentGroupRow,
  ComponentTab,
  ComponentTabGroupLink,
  ComponentTabsBootstrap,
} from '~/types/freight/component-config'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { unwrapApiData } from '~/repositories/http/response'

function asArray<T>(data: T[] | { items: T[] }): T[] {
  if (Array.isArray(data)) return data
  return Array.isArray(data?.items) ? data.items : []
}

export function createHttpComponentConfigRepository(): ComponentConfigRepository {
  const api = useApi()
  return {
    listAttributes: async includeArchived =>
      asArray(unwrapApiData(await api.get<ApiResponse<ComponentAttribute[]>>(ApiV1Endpoints.COMPONENT_ATTRIBUTES, { query: { include_archived: includeArchived, page_size: 200 } }))),
    createAttribute: async input =>
      unwrapApiData(await api.post<ApiResponse<ComponentAttribute>>(ApiV1Endpoints.COMPONENT_ATTRIBUTES, input)),
    updateAttribute: async (id, input) =>
      unwrapApiData(await api.patch<ApiResponse<ComponentAttribute>>(ApiV1Endpoints.COMPONENT_ATTRIBUTE(id), input)),
    deleteAttribute: async id =>
      unwrapApiData(await api.delete<ApiResponse<{ archived: boolean, id: string }>>(ApiV1Endpoints.COMPONENT_ATTRIBUTE(id))),

    listGroups: async includeArchived =>
      asArray(unwrapApiData(await api.get<ApiResponse<ComponentGroup[]>>(ApiV1Endpoints.COMPONENT_GROUPS, { query: { include_archived: includeArchived, page_size: 200 } }))),
    createGroup: async input =>
      unwrapApiData(await api.post<ApiResponse<ComponentGroup>>(ApiV1Endpoints.COMPONENT_GROUPS, input)),
    updateGroup: async (id, input) =>
      unwrapApiData(await api.patch<ApiResponse<ComponentGroup>>(ApiV1Endpoints.COMPONENT_GROUP(id), input)),
    deleteGroup: async id =>
      unwrapApiData(await api.delete<ApiResponse<{ archived: boolean, id: string }>>(ApiV1Endpoints.COMPONENT_GROUP(id))),

    listGroupAttributes: async groupId =>
      asArray(unwrapApiData(await api.get<ApiResponse<ComponentGroupAttribute[]>>(ApiV1Endpoints.COMPONENT_GROUP_ATTRIBUTES(groupId)))),
    addGroupAttribute: async (groupId, input) =>
      unwrapApiData(await api.post<ApiResponse<ComponentGroupAttribute>>(ApiV1Endpoints.COMPONENT_GROUP_ATTRIBUTES(groupId), input)),
    updateGroupAttribute: async (id, input) =>
      unwrapApiData(await api.patch<ApiResponse<ComponentGroupAttribute>>(ApiV1Endpoints.COMPONENT_GROUP_ATTRIBUTE(id), input)),
    removeGroupAttribute: async id =>
      unwrapApiData(await api.delete<ApiResponse<{ removed: boolean }>>(ApiV1Endpoints.COMPONENT_GROUP_ATTRIBUTE(id))),
    reorderGroupAttributes: async (groupId, orderedIds) =>
      asArray(unwrapApiData(await api.post<ApiResponse<ComponentGroupAttribute[]>>(ApiV1Endpoints.COMPONENT_GROUP_ATTRIBUTES_REORDER(groupId), { orderedIds }))),

    listTabs: async includeArchived =>
      asArray(unwrapApiData(await api.get<ApiResponse<ComponentTab[]>>(ApiV1Endpoints.COMPONENT_TABS, { query: { include_archived: includeArchived, page_size: 200 } }))),
    createTab: async input =>
      unwrapApiData(await api.post<ApiResponse<ComponentTab>>(ApiV1Endpoints.COMPONENT_TABS, input)),
    updateTab: async (id, input) =>
      unwrapApiData(await api.patch<ApiResponse<ComponentTab>>(ApiV1Endpoints.COMPONENT_TAB(id), input)),
    deleteTab: async id =>
      unwrapApiData(await api.delete<ApiResponse<{ archived: boolean, id: string }>>(ApiV1Endpoints.COMPONENT_TAB(id))),

    listTabGroups: async tabId =>
      asArray(unwrapApiData(await api.get<ApiResponse<ComponentTabGroupLink[]>>(ApiV1Endpoints.COMPONENT_TAB_GROUPS(tabId)))),
    addTabGroup: async (tabId, input) =>
      unwrapApiData(await api.post<ApiResponse<ComponentTab>>(ApiV1Endpoints.COMPONENT_TAB_GROUPS(tabId), input)),
    removeTabGroup: async tabGroupId =>
      unwrapApiData(await api.delete<ApiResponse<{ removed: boolean }>>(ApiV1Endpoints.COMPONENT_TAB_GROUP(tabGroupId))),
    reorderTabGroups: async (tabId, orderedIds) =>
      asArray(unwrapApiData(await api.post<ApiResponse<ComponentTabGroupLink[]>>(ApiV1Endpoints.COMPONENT_TAB_GROUPS_REORDER(tabId), { orderedIds }))),
    setTabDirections: async (tabId, directionIds) =>
      unwrapApiData(await api.post<ApiResponse<string[]>>(ApiV1Endpoints.COMPONENT_TAB_TRADE_DIRECTIONS(tabId), { tradeDirectionIds: directionIds })),

    bootstrap: async (serviceOrderId, directionId) =>
      unwrapApiData(await api.get<ApiResponse<ComponentTabsBootstrap>>(
        ApiV1Endpoints.SERVICE_ORDER_COMPONENT_TABS(serviceOrderId),
        directionId ? { query: { direction_id: directionId } } : undefined,
      )),
    saveGroupRows: async (serviceOrderId, groupId, rows) => {
      const result = unwrapApiData(
        await api.post<ApiResponse<{ items: ComponentGroupRow[] }>>(
          ApiV1Endpoints.SERVICE_ORDER_COMPONENT_GROUP_ROWS_BULK(serviceOrderId, groupId),
          { rows },
        ),
      )
      return result?.items ?? []
    },
  }
}

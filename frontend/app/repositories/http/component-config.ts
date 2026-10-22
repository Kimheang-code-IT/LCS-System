import type { ComponentConfigRepository } from '~/repositories/contracts/component-config'
import type { ApiResponse } from '~/types/common'
import type {
  ComponentAttribute,
  ComponentGroup,
  ComponentGroupAttribute,
  ComponentGroupRow,
  ComponentGroupLayoutInput,
  ComponentTab,
  ComponentTabGroupLink,
  ComponentTabsBootstrap,
  ConfigurationVersion,
  ConfigurationVersionActivationEvent,
  ConfigurationVersionComparison,
  ConfigurationVersionPage,
  ConfigurationVersionPreview,
} from '~/types/component-config'
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
    updateTabGroup: async (tabGroupId, input: ComponentGroupLayoutInput) =>
      unwrapApiData(await api.patch<ApiResponse<ComponentTabGroupLink>>(
        ApiV1Endpoints.COMPONENT_TAB_GROUP(tabGroupId),
        input,
      )),
    removeTabGroup: async tabGroupId =>
      unwrapApiData(await api.delete<ApiResponse<{ removed: boolean }>>(ApiV1Endpoints.COMPONENT_TAB_GROUP(tabGroupId))),
    reorderTabGroups: async (tabId, orderedIds) =>
      asArray(unwrapApiData(await api.post<ApiResponse<ComponentTabGroupLink[]>>(ApiV1Endpoints.COMPONENT_TAB_GROUPS_REORDER(tabId), { orderedIds }))),

    bootstrap: async (serviceOrderId, directionId) =>
      unwrapApiData(await api.get<ApiResponse<ComponentTabsBootstrap>>(
        ApiV1Endpoints.SERVICE_ORDER_COMPONENT_TABS(serviceOrderId),
        directionId ? { query: { direction_id: directionId } } : undefined,
      )),
    saveGroupRows: async (serviceOrderId, groupId, rows, tabGroupId) => {
      const result = unwrapApiData(
        await api.post<ApiResponse<{ items: ComponentGroupRow[] }>>(
          ApiV1Endpoints.SERVICE_ORDER_COMPONENT_GROUP_ROWS_BULK(serviceOrderId, groupId),
          { rows, tabGroupId },
        ),
      )
      return result?.items ?? []
    },

    listConfigurationVersions: async (params = {}) =>
      unwrapApiData(await api.get<ApiResponse<ConfigurationVersionPage>>(
        ApiV1Endpoints.CONFIGURATION_VERSIONS,
        {
          query: {
            page: params.page ?? 1,
            page_size: params.pageSize ?? 20,
            q: params.q || undefined,
            status: params.status || undefined,
            sortKey: params.sortKey || undefined,
            sortDir: params.sortDir || undefined,
          },
        },
      )),
    activeConfigurationVersion: async () =>
      unwrapApiData(await api.get<ApiResponse<ConfigurationVersion | null>>(
        ApiV1Endpoints.CONFIGURATION_VERSION_ACTIVE,
      )),
    getConfigurationVersion: async id =>
      unwrapApiData(await api.get<ApiResponse<ConfigurationVersion>>(
        ApiV1Endpoints.CONFIGURATION_VERSION(id),
      )),
    updateConfigurationVersion: async (id, input) =>
      unwrapApiData(await api.patch<ApiResponse<ConfigurationVersion>>(
        ApiV1Endpoints.CONFIGURATION_VERSION(id),
        input,
      )),
    deleteConfigurationVersion: async id =>
      unwrapApiData(await api.delete<ApiResponse<{ removed: number }>>(
        ApiV1Endpoints.CONFIGURATION_VERSION(id),
      )),
    previewConfigurationVersion: async () =>
      unwrapApiData(await api.get<ApiResponse<ConfigurationVersionPreview>>(
        ApiV1Endpoints.CONFIGURATION_VERSION_PREVIEW,
      )),
    previewConfigurationVersionById: async id =>
      unwrapApiData(await api.get<ApiResponse<ConfigurationVersion>>(
        ApiV1Endpoints.CONFIGURATION_VERSION_PREVIEW_BY_ID(id),
      )),
    compareConfigurationVersions: async (id, otherId) =>
      unwrapApiData(await api.get<ApiResponse<ConfigurationVersionComparison>>(
        ApiV1Endpoints.CONFIGURATION_VERSION_COMPARE(id, otherId),
      )),
    publishConfigurationVersion: async changeNote =>
      unwrapApiData(await api.post<ApiResponse<ConfigurationVersion>>(
        ApiV1Endpoints.CONFIGURATION_VERSIONS,
        { changeNote },
      )),
    activateConfigurationVersion: async id =>
      unwrapApiData(await api.post<ApiResponse<ConfigurationVersion>>(
        ApiV1Endpoints.CONFIGURATION_VERSION_ACTIVATE(id),
        {},
      )),
    rollbackConfigurationVersion: async (id, reason) =>
      unwrapApiData(await api.post<ApiResponse<ConfigurationVersion>>(
        ApiV1Endpoints.CONFIGURATION_VERSION_ROLLBACK(id),
        { reason },
      )),
    configurationActivationHistory: async (params = {}) =>
      unwrapApiData(await api.get<ApiResponse<{ items: ConfigurationVersionActivationEvent[], meta: { page: number, page_size: number, total: number } }>>(
        params.versionId
          ? ApiV1Endpoints.CONFIGURATION_VERSION_ACTIVATION_HISTORY(params.versionId)
          : ApiV1Endpoints.CONFIGURATION_ACTIVATION_HISTORY,
        { query: { page: params.page ?? 1, page_size: params.pageSize ?? 50 } },
      )),
    retireConfigurationVersion: async id =>
      unwrapApiData(await api.post<ApiResponse<ConfigurationVersion>>(
        ApiV1Endpoints.CONFIGURATION_VERSION_RETIRE(id),
        {},
      )),
  }
}

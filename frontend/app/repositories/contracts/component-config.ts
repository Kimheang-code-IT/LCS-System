import type {
  ComponentAttribute,
  ComponentAttributeInput,
  ComponentGroup,
  ComponentGroupAttribute,
  ComponentGroupInput,
  ComponentGroupLayoutInput,
  ComponentGroupRow,
  ComponentTab,
  ComponentTabGroupLink,
  ComponentTabInput,
  ComponentTabsBootstrap,
  ConfigurationVersion,
  ConfigurationVersionActivationEvent,
  ConfigurationVersionComparison,
  ConfigurationVersionListParams,
  ConfigurationVersionPage,
  ConfigurationVersionPreview,
} from '~/types/component-config'

export interface ComponentGroupAttributeInput {
  attributeId?: string
  code?: string
  isRequired?: boolean
  width?: string
  displayOrder?: number
  isVisible?: boolean
  status?: string
}

export interface ComponentConfigRepository {
  listAttributes: (includeArchived?: boolean) => Promise<ComponentAttribute[]>
  createAttribute: (input: ComponentAttributeInput) => Promise<ComponentAttribute>
  updateAttribute: (id: string, input: Partial<ComponentAttributeInput>) => Promise<ComponentAttribute>
  deleteAttribute: (id: string) => Promise<{ archived: boolean, id: string }>
  reorderAttributes: (orderedIds: string[]) => Promise<ComponentAttribute[]>

  listGroups: (includeArchived?: boolean) => Promise<ComponentGroup[]>
  createGroup: (input: ComponentGroupInput) => Promise<ComponentGroup>
  updateGroup: (id: string, input: Partial<ComponentGroupInput>) => Promise<ComponentGroup>
  deleteGroup: (id: string) => Promise<{ archived: boolean, id: string }>

  listGroupAttributes: (groupId: string) => Promise<ComponentGroupAttribute[]>
  addGroupAttribute: (groupId: string, input: ComponentGroupAttributeInput) => Promise<ComponentGroupAttribute>
  updateGroupAttribute: (id: string, input: Partial<ComponentGroupAttributeInput>) => Promise<ComponentGroupAttribute>
  removeGroupAttribute: (id: string) => Promise<{ removed: boolean }>
  reorderGroupAttributes: (groupId: string, orderedIds: string[]) => Promise<ComponentGroupAttribute[]>

  listTabs: (includeArchived?: boolean) => Promise<ComponentTab[]>
  createTab: (input: ComponentTabInput) => Promise<ComponentTab>
  updateTab: (id: string, input: Partial<ComponentTabInput>) => Promise<ComponentTab>
  deleteTab: (id: string) => Promise<{ archived: boolean, id: string }>

  listTabGroups: (tabId: string) => Promise<ComponentTabGroupLink[]>
  addTabGroup: (tabId: string, input: ComponentGroupLayoutInput & { groupId: string }) => Promise<ComponentTab>
  updateTabGroup: (tabGroupId: string, input: ComponentGroupLayoutInput) => Promise<ComponentTabGroupLink>
  removeTabGroup: (tabGroupId: string) => Promise<{ removed: boolean }>
  reorderTabGroups: (tabId: string, orderedIds: string[]) => Promise<ComponentTabGroupLink[]>

  bootstrap: (serviceOrderId: string, directionId?: string) => Promise<ComponentTabsBootstrap>
  saveGroupRows: (
    serviceOrderId: string,
    groupId: string,
    rows: Array<{ id?: string, values: Record<string, unknown> }>,
    tabGroupId?: string,
  ) => Promise<ComponentGroupRow[]>

  listConfigurationVersions: (params?: ConfigurationVersionListParams) => Promise<ConfigurationVersionPage>
  activeConfigurationVersion: () => Promise<ConfigurationVersion | null>
  getConfigurationVersion: (id: string) => Promise<ConfigurationVersion>
  updateConfigurationVersion: (id: string, input: { changeNote: string }) => Promise<ConfigurationVersion>
  deleteConfigurationVersion: (id: string) => Promise<{ removed: number }>
  previewConfigurationVersion: () => Promise<ConfigurationVersionPreview>
  previewConfigurationVersionById: (id: string) => Promise<ConfigurationVersion>
  compareConfigurationVersions: (id: string, otherId: string) => Promise<ConfigurationVersionComparison>
  publishConfigurationVersion: (changeNote?: string) => Promise<ConfigurationVersion>
  activateConfigurationVersion: (id: string) => Promise<ConfigurationVersion>
  rollbackConfigurationVersion: (id: string, reason: string) => Promise<ConfigurationVersion>
  configurationActivationHistory: (params?: ConfigurationVersionListParams & { versionId?: string }) => Promise<{ items: ConfigurationVersionActivationEvent[], meta: { page: number, page_size: number, total: number } }>
  retireConfigurationVersion: (id: string) => Promise<ConfigurationVersion>
}

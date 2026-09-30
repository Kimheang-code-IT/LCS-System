import type {
  ComponentAttribute,
  ComponentAttributeInput,
  ComponentGroup,
  ComponentGroupAttribute,
  ComponentGroupInput,
  ComponentGroupRow,
  ComponentTab,
  ComponentTabGroupLink,
  ComponentTabInput,
  ComponentTabsBootstrap,
} from '~/types/freight/component-config'

export interface ComponentGroupAttributeInput {
  attributeId?: string
  code?: string
  isRequired?: boolean
  width?: string
  displayOrder?: number
  status?: string
}

export interface ComponentConfigRepository {
  listAttributes: (includeArchived?: boolean) => Promise<ComponentAttribute[]>
  createAttribute: (input: ComponentAttributeInput) => Promise<ComponentAttribute>
  updateAttribute: (id: string, input: Partial<ComponentAttributeInput>) => Promise<ComponentAttribute>
  deleteAttribute: (id: string) => Promise<{ archived: boolean, id: string }>

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
  addTabGroup: (tabId: string, input: { groupId: string }) => Promise<ComponentTab>
  removeTabGroup: (tabGroupId: string) => Promise<{ removed: boolean }>
  reorderTabGroups: (tabId: string, orderedIds: string[]) => Promise<ComponentTabGroupLink[]>
  setTabDirections: (tabId: string, directionIds: string[]) => Promise<string[]>

  bootstrap: (serviceOrderId: string, directionId?: string) => Promise<ComponentTabsBootstrap>
  saveGroupRows: (serviceOrderId: string, groupId: string, rows: Array<{ id?: string, values: Record<string, unknown> }>) => Promise<ComponentGroupRow[]>
}

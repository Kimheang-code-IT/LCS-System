import type {
  ComponentAttribute,
  ComponentAttributeInput,
  ComponentGroup,
  ComponentGroupAttribute,
  ComponentGroupInput,
  ComponentTab,
  ComponentTabGroupLink,
  ComponentTabInput,
} from '~/types/freight/component-config'
import type { ComponentGroupAttributeInput } from '~/repositories/contracts/component-config'
import { useLcsRepositories } from '~/repositories'

/** CRUD for the Attribute -> Group -> Tab component configuration. */
export function useComponentConfig() {
  const { componentConfig } = useLcsRepositories()

  const attributes = ref<ComponentAttribute[]>([])
  const groups = ref<ComponentGroup[]>([])
  const groupAttributes = ref<ComponentGroupAttribute[]>([])
  const tabs = ref<ComponentTab[]>([])
  const tabGroups = ref<ComponentTabGroupLink[]>([])

  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  async function run<T>(fn: () => Promise<T>): Promise<T> {
    loading.value = true
    error.value = null
    try {
      return await fn()
    }
    catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    }
    finally {
      loading.value = false
    }
  }

  async function withSaving<T>(fn: () => Promise<T>): Promise<T> {
    saving.value = true
    try {
      return await fn()
    }
    finally {
      saving.value = false
    }
  }

  // --- Attributes -----------------------------------------------------------
  async function loadAttributes(includeArchived = true) {
    return run(async () => { attributes.value = await componentConfig.listAttributes(includeArchived) })
  }

  async function createAttribute(input: ComponentAttributeInput) {
    return withSaving(async () => {
      const created = await componentConfig.createAttribute(input)
      attributes.value = [...attributes.value, created]
      return created
    })
  }

  async function updateAttribute(id: string, input: Partial<ComponentAttributeInput>) {
    return withSaving(async () => {
      const updated = await componentConfig.updateAttribute(id, input)
      attributes.value = attributes.value.map(item => (item.id === id ? updated : item))
      return updated
    })
  }

  async function deleteAttribute(id: string) {
    return withSaving(async () => {
      const result = await componentConfig.deleteAttribute(id)
      if (!result.archived) attributes.value = attributes.value.filter(item => item.id !== id)
      return result
    })
  }

  // --- Groups ---------------------------------------------------------------
  async function loadGroups(includeArchived = true) {
    return run(async () => { groups.value = await componentConfig.listGroups(includeArchived) })
  }

  async function createGroup(input: ComponentGroupInput) {
    return withSaving(async () => {
      const created = await componentConfig.createGroup(input)
      groups.value = [...groups.value, created]
      return created
    })
  }

  async function updateGroup(id: string, input: Partial<ComponentGroupInput>) {
    return withSaving(async () => {
      const updated = await componentConfig.updateGroup(id, input)
      groups.value = groups.value.map(item => (item.id === id ? updated : item))
      return updated
    })
  }

  async function deleteGroup(id: string) {
    return withSaving(async () => {
      const result = await componentConfig.deleteGroup(id)
      if (!result.archived) groups.value = groups.value.filter(item => item.id !== id)
      return result
    })
  }

  // --- Group attributes -----------------------------------------------------
  async function loadGroupAttributes(groupId: string) {
    return run(async () => { groupAttributes.value = await componentConfig.listGroupAttributes(groupId) })
  }

  async function addGroupAttribute(groupId: string, input: ComponentGroupAttributeInput) {
    return withSaving(async () => {
      const created = await componentConfig.addGroupAttribute(groupId, input)
      groupAttributes.value = [...groupAttributes.value, created]
      return created
    })
  }

  async function updateGroupAttribute(id: string, input: Partial<ComponentGroupAttributeInput>) {
    return withSaving(async () => {
      const updated = await componentConfig.updateGroupAttribute(id, input)
      groupAttributes.value = groupAttributes.value.map(item => (item.id === id ? updated : item))
      return updated
    })
  }

  async function removeGroupAttribute(id: string) {
    return withSaving(async () => {
      await componentConfig.removeGroupAttribute(id)
      groupAttributes.value = groupAttributes.value.filter(item => item.id !== id)
    })
  }

  async function reorderGroupAttributes(groupId: string, orderedIds: string[]) {
    return withSaving(async () => { groupAttributes.value = await componentConfig.reorderGroupAttributes(groupId, orderedIds) })
  }

  // --- Tabs -----------------------------------------------------------------
  async function loadTabs(includeArchived = true) {
    return run(async () => { tabs.value = await componentConfig.listTabs(includeArchived) })
  }

  async function createTab(input: ComponentTabInput) {
    return withSaving(async () => {
      const created = await componentConfig.createTab(input)
      tabs.value = [...tabs.value, created]
      return created
    })
  }

  async function updateTab(id: string, input: Partial<ComponentTabInput>) {
    return withSaving(async () => {
      const updated = await componentConfig.updateTab(id, input)
      tabs.value = tabs.value.map(item => (item.id === id ? updated : item))
      return updated
    })
  }

  async function deleteTab(id: string) {
    return withSaving(async () => {
      const result = await componentConfig.deleteTab(id)
      tabs.value = tabs.value.filter(item => item.id !== id)
      return result
    })
  }

  async function loadTabGroups(tabId: string) {
    return run(async () => { tabGroups.value = await componentConfig.listTabGroups(tabId) })
  }

  async function addTabGroup(tabId: string, groupId: string) {
    return withSaving(async () => {
      await componentConfig.addTabGroup(tabId, { groupId })
      tabGroups.value = await componentConfig.listTabGroups(tabId)
    })
  }

  async function removeTabGroup(tabGroupId: string, tabId: string) {
    return withSaving(async () => {
      await componentConfig.removeTabGroup(tabGroupId)
      tabGroups.value = await componentConfig.listTabGroups(tabId)
    })
  }

  async function reorderTabGroups(tabId: string, orderedIds: string[]) {
    return withSaving(async () => { tabGroups.value = await componentConfig.reorderTabGroups(tabId, orderedIds) })
  }

  async function setTabDirections(tabId: string, directionIds: string[]) {
    return withSaving(async () => {
      const ids = await componentConfig.setTabDirections(tabId, directionIds)
      tabs.value = tabs.value.map(item => (item.id === tabId ? { ...item, tradeDirectionIds: ids } : item))
      return ids
    })
  }

  return {
    attributes,
    groups,
    groupAttributes,
    tabs,
    tabGroups,
    loading,
    saving,
    error,
    loadAttributes,
    createAttribute,
    updateAttribute,
    deleteAttribute,
    loadGroups,
    createGroup,
    updateGroup,
    deleteGroup,
    loadGroupAttributes,
    addGroupAttribute,
    updateGroupAttribute,
    removeGroupAttribute,
    reorderGroupAttributes,
    loadTabs,
    createTab,
    updateTab,
    deleteTab,
    loadTabGroups,
    addTabGroup,
    removeTabGroup,
    reorderTabGroups,
    setTabDirections,
  }
}

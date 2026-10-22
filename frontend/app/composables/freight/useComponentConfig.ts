import type {
  ComponentAttribute,
  ComponentAttributeInput,
  ComponentGroup,
  ComponentGroupAttribute,
  ComponentGroupInput,
  ComponentGroupLayoutInput,
  ComponentTab,
  ComponentTabGroupLink,
  ComponentTabInput,
  ConfigurationVersion,
  ConfigurationVersionActivationEvent,
  ConfigurationVersionComparison,
  ConfigurationVersionListParams,
  ConfigurationVersionPreview,
} from '~/types/component-config'
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

  async function addTabGroup(tabId: string, groupId: string, layout?: ComponentGroupLayoutInput) {
    return withSaving(async () => {
      await componentConfig.addTabGroup(tabId, { groupId, ...layout })
      tabGroups.value = await componentConfig.listTabGroups(tabId)
    })
  }

  async function updateTabGroup(tabGroupId: string, input: ComponentGroupLayoutInput) {
    return withSaving(async () => {
      const updated = await componentConfig.updateTabGroup(tabGroupId, input)
      tabGroups.value = tabGroups.value.map(item => (item.tabGroupId === tabGroupId ? updated : item))
      return updated
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

  // --- Published configuration versions -------------------------------------
  // Editing a tab changes the live form; publishing freezes the result so the
  // orders already captured under the old layout keep rendering unchanged.
  const versions = ref<ConfigurationVersion[]>([])
  const versionsMeta = ref({ page: 1, page_size: 20, total: 0 })
  const activeVersion = ref<ConfigurationVersion | null>(null)
  const preview = ref<ConfigurationVersionPreview | null>(null)

  async function loadConfigurationVersions(params: ConfigurationVersionListParams = {}) {
    return run(async () => {
      const page = await componentConfig.listConfigurationVersions(params)
      versions.value = page.items
      versionsMeta.value = page.meta
      return page
    })
  }

  async function fetchConfigurationVersionOptions() {
    return run(async () => componentConfig.listConfigurationVersions({ page: 1, pageSize: 200 }))
  }

  async function loadActiveConfigurationVersion() {
    return run(async () => { activeVersion.value = await componentConfig.activeConfigurationVersion() })
  }

  async function loadConfigurationVersion(id: string) {
    return run(async () => componentConfig.getConfigurationVersion(id))
  }

  async function updateConfigurationVersion(id: string, changeNote: string) {
    return withSaving(async () => {
      const updated = await componentConfig.updateConfigurationVersion(id, { changeNote })
      versions.value = versions.value.map(item => (item.id === id ? updated : item))
      return updated
    })
  }

  async function deleteConfigurationVersion(id: string) {
    return withSaving(async () => {
      const result = await componentConfig.deleteConfigurationVersion(id)
      versions.value = versions.value.filter(item => item.id !== id)
      return result
    })
  }

  async function loadConfigurationPreview() {
    return run(async () => { preview.value = await componentConfig.previewConfigurationVersion() })
  }

  async function previewConfigurationVersion(id: string) {
    return run(async () => componentConfig.previewConfigurationVersionById(id))
  }

  async function compareConfigurationVersions(id: string, otherId: string): Promise<ConfigurationVersionComparison> {
    return run(async () => componentConfig.compareConfigurationVersions(id, otherId))
  }

  async function loadConfigurationActivationHistory(
    params: ConfigurationVersionListParams & { versionId?: string } = {},
  ): Promise<{ items: ConfigurationVersionActivationEvent[], meta: { page: number, page_size: number, total: number } }> {
    return run(async () => componentConfig.configurationActivationHistory(params))
  }

  async function publishConfiguration(changeNote?: string) {
    return withSaving(async () => {
      const published = await componentConfig.publishConfigurationVersion(changeNote)
      versions.value = [published, ...versions.value.map(version => (
        version.status === 'PUBLISHED' ? { ...version, status: 'RETIRED' as const } : version
      ))]
      await Promise.all([loadConfigurationPreview(), loadActiveConfigurationVersion()])
      return published
    })
  }

  async function activateConfiguration(id: string) {
    return withSaving(async () => {
      const activated = await componentConfig.activateConfigurationVersion(id)
      versions.value = versions.value.map(version => {
        if (version.id === id) return activated
        return version.status === 'PUBLISHED' ? { ...version, status: 'RETIRED' as const } : version
      })
      await Promise.all([loadConfigurationPreview(), loadActiveConfigurationVersion()])
      return activated
    })
  }

  async function rollbackConfiguration(id: string, reason: string) {
    return withSaving(async () => {
      const rolled = await componentConfig.rollbackConfigurationVersion(id, reason)
      versions.value = [rolled, ...versions.value.map(version => (
        version.status === 'PUBLISHED' ? { ...version, status: 'RETIRED' as const } : version
      ))]
      await Promise.all([loadConfigurationPreview(), loadActiveConfigurationVersion()])
      return rolled
    })
  }

  async function retireConfiguration(id: string) {
    return withSaving(async () => {
      const retired = await componentConfig.retireConfigurationVersion(id)
      versions.value = versions.value.map(version => (version.id === id ? retired : version))
      return retired
    })
  }

  return {
    attributes,
    groups,
    groupAttributes,
    tabs,
    tabGroups,
    versions,
    versionsMeta,
    activeVersion,
    preview,
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
    updateTabGroup,
    removeTabGroup,
    reorderTabGroups,
    loadConfigurationVersions,
    fetchConfigurationVersionOptions,
    loadActiveConfigurationVersion,
    loadConfigurationVersion,
    updateConfigurationVersion,
    deleteConfigurationVersion,
    loadConfigurationPreview,
    previewConfigurationVersion,
    compareConfigurationVersions,
    loadConfigurationActivationHistory,
    publishConfiguration,
    activateConfiguration,
    rollbackConfiguration,
    retireConfiguration,
  }
}

import type {
  DynamicColumnInput,
  DynamicTab,
  DynamicTabColumn,
  DynamicTabInput,
} from '~/types/freight/dynamic-tabs'
import { useLcsRepositories } from '~/repositories'

/** CRUD for Service Order tab/column configuration (Settings → Service Order Tabs). */
export function useServiceOrderTabConfig() {
  const { dynamicTabs } = useLcsRepositories()
  const tabs = ref<DynamicTab[]>([])
  const columns = ref<DynamicTabColumn[]>([])
  const selectedTabId = ref('')
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  async function loadTabs(includeArchived = true) {
    loading.value = true
    error.value = null
    try {
      tabs.value = await dynamicTabs.listTabs(includeArchived)
      if (!selectedTabId.value && tabs.value.length) await selectTab(tabs.value[0]!.id)
    }
    catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
    finally {
      loading.value = false
    }
  }

  async function selectTab(id: string) {
    selectedTabId.value = id
    if (!id) {
      columns.value = []
      return
    }
    columns.value = await dynamicTabs.listColumns(id, true)
  }

  async function createTab(input: DynamicTabInput) {
    saving.value = true
    try {
      const tab = await dynamicTabs.createTab(input)
      await loadTabs()
      await selectTab(tab.id)
      return tab
    }
    finally {
      saving.value = false
    }
  }

  async function updateTab(id: string, input: DynamicTabInput) {
    saving.value = true
    try {
      const tab = await dynamicTabs.updateTab(id, input)
      await loadTabs()
      if (selectedTabId.value === id) await selectTab(id)
      return tab
    }
    finally {
      saving.value = false
    }
  }

  async function deleteTab(id: string) {
    const result = await dynamicTabs.deleteTab(id)
    await loadTabs()
    if (selectedTabId.value === id) {
      selectedTabId.value = ''
      columns.value = []
      if (tabs.value.length) await selectTab(tabs.value[0]!.id)
    }
    return result
  }

  async function createColumn(tabId: string, input: DynamicColumnInput) {
    const column = await dynamicTabs.createColumn(tabId, input)
    if (selectedTabId.value === tabId) await selectTab(tabId)
    return column
  }

  async function updateColumn(id: string, input: DynamicColumnInput) {
    const column = await dynamicTabs.updateColumn(id, input)
    if (selectedTabId.value === column.tabId) await selectTab(column.tabId)
    return column
  }

  async function deleteColumn(id: string) {
    const result = await dynamicTabs.deleteColumn(id)
    if (selectedTabId.value) await selectTab(selectedTabId.value)
    return result
  }

  async function reorderColumns(tabId: string, orderedIds: string[]) {
    const next = await dynamicTabs.reorderColumns(tabId, orderedIds)
    if (selectedTabId.value === tabId) columns.value = next
    return next
  }

  return {
    tabs,
    columns,
    selectedTabId,
    loading,
    saving,
    error,
    loadTabs,
    selectTab,
    createTab,
    updateTab,
    deleteTab,
    createColumn,
    updateColumn,
    deleteColumn,
    reorderColumns,
  }
}

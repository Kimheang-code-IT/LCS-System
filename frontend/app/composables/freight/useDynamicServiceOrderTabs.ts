import type { DynamicTab } from '~/types/freight/dynamic-tabs'
import { useLcsRepositories } from '~/repositories'
import {
  flatRowToValues,
  isPersistedRowId,
  rowToFlatRow,
} from '~/utils/freight/dynamic-tab-columns'

type FlatRow = Record<string, unknown>

/**
 * Loads and saves the configurable Service Order dynamic-table tabs.
 * Configuration and rows are fetched in one bulk call to avoid N+1 requests.
 */
export function useDynamicServiceOrderTabs(jobNo: MaybeRefOrGetter<string>) {
  const { dynamicTabs } = useLcsRepositories()
  const tabs = ref<DynamicTab[]>([])
  const references = ref<Record<string, Record<string, string>>>({})
  const rowsByTab = ref<Record<string, FlatRow[]>>({})
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const loadedFor = ref('')

  const orderKey = computed(() => String(toValue(jobNo) || '').trim())
  const sections = computed(() => tabs.value.filter(tab => tab.isActive && !tab.isArchived).map(tab => tab.code))

  async function load(force = false) {
    const key = orderKey.value
    if (!key) {
      tabs.value = []
      rowsByTab.value = {}
      references.value = {}
      loadedFor.value = ''
      return
    }
    if (!force && key === loadedFor.value) return
    loading.value = true
    error.value = null
    try {
      const data = await dynamicTabs.bootstrap(key)
      tabs.value = data.tabs || []
      references.value = data.references || {}
      const map: Record<string, FlatRow[]> = {}
      for (const tab of tabs.value) {
        map[tab.code] = (tab.rows || []).map(rowToFlatRow)
      }
      rowsByTab.value = map
      loadedFor.value = key
    }
    catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
    finally {
      loading.value = false
    }
  }

  watch(orderKey, () => { void load() }, { immediate: true })

  function tabByCode(code: string): DynamicTab | null {
    return tabs.value.find(tab => tab.code === code) || null
  }

  function rowsFor(code: string): FlatRow[] {
    return rowsByTab.value[code] || []
  }

  function setRows(code: string, rows: FlatRow[]) {
    rowsByTab.value = { ...rowsByTab.value, [code]: rows }
  }

  function addRow(code: string) {
    const tab = tabByCode(code)
    if (!tab) return
    const blank: FlatRow = {}
    for (const column of tab.columns) {
      if (column.isArchived) continue
      if (column.fieldType === 'checkbox') blank[column.fieldKey] = false
      else if (['number', 'decimal', 'money'].includes(column.fieldType)) blank[column.fieldKey] = column.defaultValue ?? 0
      else blank[column.fieldKey] = column.defaultValue ?? ''
    }
    setRows(code, [...rowsFor(code), blank])
  }

  function removeRow(code: string, index: number) {
    setRows(code, rowsFor(code).filter((_, i) => i !== index))
  }

  async function saveTab(code: string) {
    const tab = tabByCode(code)
    if (!tab) return
    saving.value = true
    error.value = null
    try {
      const payload = rowsFor(code).map(row => ({
        id: isPersistedRowId(row.id) ? String(row.id) : undefined,
        values: flatRowToValues(row),
      }))
      const saved = await dynamicTabs.saveRows(orderKey.value, tab.id, payload)
      setRows(code, saved.map(rowToFlatRow))
    }
    catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      throw err
    }
    finally {
      saving.value = false
    }
  }

  return {
    tabs,
    references,
    rowsByTab,
    sections,
    loading,
    saving,
    error,
    load,
    tabByCode,
    rowsFor,
    setRows,
    addRow,
    removeRow,
    saveTab,
  }
}

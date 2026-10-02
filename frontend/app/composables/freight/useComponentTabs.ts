import type { ComponentTabGroup, ComponentTabRuntime } from '~/types/component-config'
import { useLcsRepositories } from '~/repositories'
import {
  componentFlatRowToValues,
  componentRowToFlatRow,
  isPersistedComponentRowId,
} from '~/utils/freight/component-tabs'

type FlatRow = Record<string, unknown>

/**
 * Loads and saves the configurable component tabs (Attribute -> Group -> Tab)
 * for a Service Order. Tabs are filtered by the order's trade direction and
 * fetched in a single bulk call.
 */
export function useComponentTabs(
  jobNo: MaybeRefOrGetter<string>,
  directionId?: MaybeRefOrGetter<string | number | null | undefined>,
) {
  const { componentConfig } = useLcsRepositories()
  const tabs = ref<ComponentTabRuntime[]>([])
  const references = ref<Record<string, Record<string, string>>>({})
  const rowsByGroup = ref<Record<string, FlatRow[]>>({})
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const loadedFor = ref('')

  const orderKey = computed(() => String(toValue(jobNo) || '').trim())
  const directionKey = computed(() => String(toValue(directionId) || '').trim())
  const cacheKey = computed(() => `${orderKey.value}|${directionKey.value}`)
  const sections = computed(() => tabs.value.map(tab => tab.code))

  async function load(force = false) {
    const key = orderKey.value
    if (!key) {
      tabs.value = []
      rowsByGroup.value = {}
      references.value = {}
      loadedFor.value = ''
      return
    }
    if (!force && cacheKey.value === loadedFor.value) return
    loading.value = true
    error.value = null
    try {
      const data = await componentConfig.bootstrap(key, directionKey.value || undefined)
      tabs.value = data.tabs || []
      references.value = data.references || {}
      const map: Record<string, FlatRow[]> = {}
      for (const tab of tabs.value) {
        for (const group of tab.groups) {
          map[group.id] = (group.rows || []).map(componentRowToFlatRow)
        }
      }
      rowsByGroup.value = map
      loadedFor.value = cacheKey.value
    }
    catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    }
    finally {
      loading.value = false
    }
  }

  watch(cacheKey, () => { void load() }, { immediate: true })

  function tabByCode(code: string): ComponentTabRuntime | null {
    return tabs.value.find(tab => tab.code === code) || null
  }

  function rowsForGroup(groupId: string): FlatRow[] {
    return rowsByGroup.value[groupId] || []
  }

  function setGroupRows(groupId: string, rows: FlatRow[]) {
    rowsByGroup.value = { ...rowsByGroup.value, [groupId]: rows }
  }

  function addRow(group: ComponentTabGroup) {
    const blank: FlatRow = {}
    for (const attribute of group.attributes) {
      if (attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean') blank[attribute.code] = false
      else if (['number', 'decimal', 'money'].includes(attribute.fieldType)) blank[attribute.code] = attribute.defaultValue ?? 0
      else blank[attribute.code] = attribute.defaultValue ?? ''
    }
    setGroupRows(group.id, [...rowsForGroup(group.id), blank])
  }

  function removeRow(groupId: string, index: number) {
    setGroupRows(groupId, rowsForGroup(groupId).filter((_, i) => i !== index))
  }

  async function saveGroup(groupId: string) {
    saving.value = true
    error.value = null
    try {
      const payload = rowsForGroup(groupId).map(row => ({
        id: isPersistedComponentRowId(row.id) ? String(row.id) : undefined,
        values: componentFlatRowToValues(row),
      }))
      const saved = await componentConfig.saveGroupRows(orderKey.value, groupId, payload)
      setGroupRows(groupId, saved.map(componentRowToFlatRow))
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
    rowsByGroup,
    sections,
    loading,
    saving,
    error,
    load,
    tabByCode,
    rowsForGroup,
    setGroupRows,
    addRow,
    removeRow,
    saveGroup,
  }
}

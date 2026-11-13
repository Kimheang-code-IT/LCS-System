import type { ComponentTabGroup, ComponentTabRuntime } from '~/types/component-config'
import { useLcsRepositories } from '~/repositories'
import {
  componentFlatRowToValues,
  componentRowToFlatRow,
  isPersistedComponentRowId,
} from '~/utils/freight/component-tabs'
import { componentGroupIsSingleRecord } from '~/utils/freight/component-layout'

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
  const savedRowsByGroup = ref<Record<string, FlatRow[]>>({})
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const loadedFor = ref('')

  const orderKey = computed(() => String(toValue(jobNo) || '').trim())
  const directionKey = computed(() => String(toValue(directionId) || '').trim())
  const cacheKey = computed(() => `${orderKey.value}|${directionKey.value}`)
  const sections = computed(() => tabs.value.map(tab => tab.code))
  let loadSequence = 0
  let rowsOrder = ''
  const editedGroups = new Set<string>()

  async function load(force = false) {
    const key = orderKey.value
    const requestedCacheKey = cacheKey.value
    const sequence = ++loadSequence
    if (rowsOrder !== key) {
      rowsOrder = key
      rowsByGroup.value = {}
      savedRowsByGroup.value = {}
      editedGroups.clear()
    }
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
      if (sequence !== loadSequence || requestedCacheKey !== cacheKey.value) return
      references.value = data.references || {}
      const map: Record<string, FlatRow[]> = {}
      const baseline: Record<string, FlatRow[]> = {}
      for (const tab of data.tabs || []) {
        for (const group of tab.groups) {
          // A single-record form with no saved row still needs one editable row,
          // otherwise required-field validation would have nothing to inspect.
          baseline[group.id] = ensureCardinality(group, (group.rows || []).map(componentRowToFlatRow))
          map[group.id] = editedGroups.has(group.id)
            ? rowsByGroup.value[group.id] || []
            : baseline[group.id]!
        }
      }
      rowsByGroup.value = map
      savedRowsByGroup.value = baseline
      tabs.value = data.tabs || []
      loadedFor.value = requestedCacheKey
    }
    catch (err) {
      if (sequence === loadSequence) error.value = err instanceof Error ? err.message : String(err)
    }
    finally {
      if (sequence === loadSequence) loading.value = false
    }
  }

  watch(cacheKey, () => { void load() }, { immediate: true })

  // Publishing (or activating/rolling back) a configuration version bumps this
  // shared counter, so an already-open form reloads the newly published layout
  // instead of keeping the pre-publish tabs it loaded earlier.
  const publishedRevision = useState('component-config-published-revision', () => 0)
  watch(publishedRevision, () => { void load(true) })

  function tabByCode(code: string): ComponentTabRuntime | null {
    return tabs.value.find(tab => tab.code === code) || null
  }

  function findGroup(groupId: string): ComponentTabGroup | undefined {
    return tabs.value.flatMap(tab => tab.groups).find(group => group.id === groupId)
  }

  function blankRow(group: ComponentTabGroup): FlatRow {
    const blank: FlatRow = {}
    for (const attribute of group.attributes) {
      if (attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean') blank[attribute.code] = false
      else if (['number', 'integer', 'decimal', 'money'].includes(attribute.fieldType)) blank[attribute.code] = attribute.defaultValue ?? 0
      else if (attribute.fieldType === 'multi_select') blank[attribute.code] = []
      else blank[attribute.code] = attribute.defaultValue ?? ''
    }
    return blank
  }

  /** A single-record group always exposes exactly one editable row. */
  function ensureCardinality(group: ComponentTabGroup, rows: FlatRow[]): FlatRow[] {
    return componentGroupIsSingleRecord(group) && rows.length === 0 ? [blankRow(group)] : rows
  }

  function rowsForGroup(groupId: string): FlatRow[] {
    const existing = rowsByGroup.value[groupId] || []
    const group = findGroup(groupId)
    return group ? ensureCardinality(group, existing) : existing
  }

  function setGroupRows(groupId: string, rows: FlatRow[]) {
    editedGroups.add(groupId)
    const group = findGroup(groupId)
    rowsByGroup.value = { ...rowsByGroup.value, [groupId]: group ? ensureCardinality(group, rows) : rows }
  }

  function addRow(group: ComponentTabGroup) {
    // A single-record group edits its one row instead of appending another.
    if (componentGroupIsSingleRecord(group) && rowsForGroup(group.id).length >= 1) return
    setGroupRows(group.id, [...rowsForGroup(group.id), blankRow(group)])
  }

  function removeRow(groupId: string, index: number) {
    setGroupRows(groupId, rowsForGroup(groupId).filter((_, i) => i !== index))
  }

  async function saveGroup(groupId: string) {
    saving.value = true
    error.value = null
    try {
      const order = orderKey.value
      const submitted = JSON.stringify(rowsForGroup(groupId))
      const payload = rowsForGroup(groupId).map(row => ({
        id: isPersistedComponentRowId(row.id) ? String(row.id) : undefined,
        values: componentFlatRowToValues(row),
      }))
      const saved = await componentConfig.saveGroupRows(
        order,
        groupId,
        payload,
        findGroup(groupId)?.tabGroupId,
      )
      if (order !== orderKey.value) return
      const serverRows = saved.map(componentRowToFlatRow)
      savedRowsByGroup.value = { ...savedRowsByGroup.value, [groupId]: serverRows }
      if (JSON.stringify(rowsForGroup(groupId)) === submitted) {
        setGroupRows(groupId, serverRows)
        editedGroups.delete(groupId)
      }
    }
    finally {
      saving.value = false
    }
  }

  return {
    tabs,
    references,
    rowsByGroup,
    savedRowsByGroup,
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

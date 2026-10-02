<script setup lang="ts">
/**
 * Reusable editable grid on top of the shared `AppLineTable` renderer: it keeps
 * a local draft copy, works out what changed, and only then offers Save/Cancel.
 *
 * Used by the `/configuration/component-*` pages and the service-order Service
 * Charge tab so every such grid saves the same way. The parent owns the API
 * calls; the grid only reports the change set. Deletion is detected by diffing
 * row ids rather than by a bespoke cell, which keeps the renderer generic and
 * lets each parent run its own confirm flow.
 */
import type { FreightTable } from '~/config/freight-modules'
import { FREIGHT_LINE_UTILITY_COLUMN_TYPES } from '~/config/freight-modules'
import type { SaveGridChange } from '~/types/save-grid'
import { isSaveGridNewRow } from '~/types/save-grid'

const props = withDefaults(defineProps<{
  table: FreightTable
  /** Saved rows from the API. Any change here resets the draft. */
  rows: Array<Record<string, unknown>>
  disabled?: boolean
  saving?: boolean
  /** Parent actions shown ahead of Save/Cancel, e.g. an order-level workflow button. */
  headerActions?: Array<{
    label: string
    icon?: string
    color?: 'primary' | 'neutral' | 'error'
    disabled?: boolean
    onClick: () => void
  }>
  /** Forwarded to the renderer for `type: 'action'` cells. */
  rowActions?: (action: string, row: Record<string, unknown>) => {
    label: string
    icon: string
    color?: 'primary' | 'neutral' | 'error'
    onSelect: () => void
  } | null
  /** Called after a `type: 'reorder'` cell moves a row. */
  onReorder?: (rows: Array<Record<string, unknown>>) => void
}>(), {
  disabled: false,
  saving: false,
  headerActions: () => [],
  rowActions: undefined,
  onReorder: undefined,
})

const emit = defineEmits<{
  'save': [change: SaveGridChange]
  'cancel': []
}>()

const { t } = useI18n()

const draft = ref<Array<Record<string, unknown>>>([])

function resetDraft() {
  draft.value = props.rows.map(row => ({ ...row }))
}

watch(() => props.rows, resetDraft, { immediate: true, deep: true })

const originalById = computed(() => new Map(
  props.rows.map(row => [String(row.id ?? ''), row]),
))

const draftIds = computed(() => new Set(draft.value.map(row => String(row.id ?? '')).filter(Boolean)))

const removedIds = computed(() => props.rows
  .map(row => String(row.id ?? ''))
  .filter(Boolean)
  .filter(id => !draftIds.value.has(id)))

const added = computed(() => draft.value.filter(isSaveGridNewRow))

/** Only values the grid actually renders count, so a save is never a false positive. */
function changedKeys(row: Record<string, unknown>) {
  const original = originalById.value.get(String(row.id ?? ''))
  if (!original) return []
  return props.table.columns
    .filter(column => !FREIGHT_LINE_UTILITY_COLUMN_TYPES.has(column.type))
    .filter(column => String(row[column.key] ?? '') !== String(original[column.key] ?? ''))
    .map(column => column.key)
}

const updated = computed(() => draft.value
  .filter(row => !isSaveGridNewRow(row))
  .map(row => ({ row, keys: changedKeys(row) }))
  .filter(entry => entry.keys.length))

const dirty = computed(() => removedIds.value.length > 0
  || added.value.length > 0
  || updated.value.length > 0)

const saveActions = computed(() => {
  if (props.disabled || !dirty.value) return []
  return [
    {
      label: t('actions.cancel'),
      icon: 'i-lucide-x',
      disabled: props.saving,
      onClick: () => {
        resetDraft()
        emit('cancel')
      },
    },
    {
      label: t('freight.ui.saveChanges'),
      icon: 'i-lucide-save',
      color: 'primary' as const,
      disabled: props.saving,
      onClick: () => emit('save', {
        rows: draft.value.map(row => ({ ...row })),
        removedIds: removedIds.value,
        added: added.value.map(row => ({ ...row })),
      }),
    },
  ]
})

// Parent actions stay visible while clean; Save/Cancel only join them once dirty.
const allHeaderActions = computed(() => [
  ...(props.headerActions || []),
  ...saveActions.value,
])
</script>

<template>
  <FreightAppLineTable
    :table="table"
    :model-value="draft"
    :disabled="disabled"
    :header-actions="allHeaderActions"
    :row-actions="rowActions"
    :on-reorder="onReorder"
    @update:model-value="draft = $event" />
</template>
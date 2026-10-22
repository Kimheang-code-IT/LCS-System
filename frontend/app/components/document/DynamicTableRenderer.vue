<script setup lang="ts">
import type { ComponentTabGroup } from '~/types/component-config'
import { componentGroupToFreightTable } from '~/utils/freight/component-tabs'
import { componentGroupIsSingleRecord } from '~/utils/freight/component-layout'

const props = withDefaults(defineProps<{
  group: ComponentTabGroup
  rows: Array<Record<string, unknown>>
  references?: Record<string, Record<string, string>>
  editable?: boolean
  saving?: boolean
  /** Cell errors keyed `<groupId>.<rowIndex>.<attributeCode>`. */
  fieldErrors?: Record<string, string>
  onFieldEdit?: (key: string) => void
  rowInlineActions?: (row: Record<string, unknown>) => Array<{
    label: string
    icon?: string
    color?: 'primary' | 'neutral' | 'error'
    disabled?: boolean
    loading?: boolean
    onSelect: () => void
  }>
}>(), {
  references: () => ({}),
  editable: true,
  saving: false,
  fieldErrors: () => ({}),
  onFieldEdit: undefined,
  rowInlineActions: undefined,
})

const emit = defineEmits<{
  'update:rows': [Array<Record<string, unknown>>]
  'save': []
}>()

const table = computed(() => componentGroupToFreightTable(props.group, props.references, {
  hideTitle: true,
  // A single-record group edits its one row; appending would fail on save.
  hideAddRow: componentGroupIsSingleRecord(props.group),
}))
</script>

<template>
  <div>
    <FreightDynamicDataTable
      v-if="table"
      :table="table"
      :model-value="rows"
      :disabled="!editable"
      :saving="saving"
      :field-errors="fieldErrors"
      :error-key="group.id"
      :on-cell-edit="onFieldEdit"
      :row-inline-actions="rowInlineActions"
      @update:model-value="emit('update:rows', $event)"
      @save="emit('save')"
    />
    <FreightJobEmptyState
      v-else
      :title="$t('freight.ui.noColumnsConfigured')"
      :description="$t('freight.ui.noColumnsConfiguredHint')"
      icon="i-lucide-columns-3"
    />
  </div>
</template>

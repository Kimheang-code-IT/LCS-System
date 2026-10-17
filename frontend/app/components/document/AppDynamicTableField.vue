<script setup lang="ts">
import type { FreightTable } from '~/config/freight-modules'
import { parseDynamicTableRows } from '~/utils/freight/dynamic-table'

withDefaults(defineProps<{
  table: FreightTable
  disabled?: boolean
  /** Cell errors keyed `<errorKey>.<rowIndex>.<column>`. */
  fieldErrors?: Record<string, string>
  errorKey?: string
  onCellEdit?: (cellKey: string) => void
}>(), {
  fieldErrors: undefined,
  errorKey: undefined,
  onCellEdit: undefined,
})

const model = defineModel<Array<Record<string, unknown>>>({ default: () => [] })

const rows = computed({
  get: () => parseDynamicTableRows(model.value),
  set: (value) => {
    model.value = value
  },
})
</script>

<template>
  <div class="space-y-3">
    <FreightAppLineTable
      :table="table"
      :model-value="rows"
      :disabled="disabled"
      :field-errors="fieldErrors"
      :error-key="errorKey"
      :on-cell-edit="onCellEdit"
      @update:model-value="rows = $event"
    />
  </div>
</template>
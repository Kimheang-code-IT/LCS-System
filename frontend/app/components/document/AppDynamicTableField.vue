<script setup lang="ts">
import type { FreightTable } from '~/config/freight-modules'
import { parseDynamicTableRows } from '~/utils/freight/dynamic-table'

const props = defineProps<{
  table: FreightTable
  disabled?: boolean
}>()

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
    <TableAppLineTable
      :table="table"
      :model-value="rows"
      :disabled="disabled"
      @update:model-value="rows = $event"
    />
  </div>
</template>

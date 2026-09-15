<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'

const props = defineProps<{
  columns: TableColumn<Record<string, string>>[]
  rows: Array<Record<string, string>>
  variant?: 'default' | 'tax-invoice'
}>()

const tableUi = computed(() => ({
  root: 'overflow-visible',
  base: 'min-w-full border-collapse',
  thead: '',
  tbody: 'divide-y-0',
  tr: '',
  th: props.variant === 'tax-invoice'
    ? 'border border-black px-1 py-2 text-[9px] font-semibold text-black whitespace-pre-line text-center align-middle leading-tight min-h-[14mm]'
    : 'border border-gray-300 bg-gray-100 px-2 py-1 text-[11px] font-semibold text-gray-900',
  td: props.variant === 'tax-invoice'
    ? 'border border-black px-1.5 py-2 text-[10px] text-black whitespace-normal align-top min-h-[14mm]'
    : 'border border-gray-300 px-2 py-1 text-[11px] text-gray-900 whitespace-normal',
}))
</script>

<template>
  <UTable
    :data="props.rows"
    :columns="props.columns"
    :ui="tableUi"
    class="print-table"
    :class="variant === 'tax-invoice' ? 'print-table--tax' : ''"
  />
</template>

<style scoped>
:deep(table) {
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
}

.print-table--tax :deep(table) {
  table-layout: fixed;
  width: 100%;
}

.print-table--tax :deep(thead th) {
  text-align: center;
}
</style>

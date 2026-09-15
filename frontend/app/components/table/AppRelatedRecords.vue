<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { FreightRelated } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import { useFreightLabel } from '~/composables/freight/useFreight'
import { freightTableUiCompact } from '~/utils/table/theme'

defineProps<{
  groups: Array<FreightRelated & { rows: FreightRecord[] }>
}>()

const { t } = useI18n()
const { relatedTitle } = useFreightLabel()

function titleOf(row: FreightRecord) {
  return String(row.jobNo || row.quotationNo || row.debitNoteNo || row.documentNo || row.paymentNo || row.name || row.id)
}

const columns = computed<TableColumn<FreightRecord>[]>(() => [
  {
    id: 'title',
    header: t('freight.ui.record'),
    accessorFn: row => titleOf(row),
    enableSorting: false,
  },
  {
    accessorKey: 'status',
    header: t('freight.ui.cols.status'),
    enableSorting: false,
    cell: ({ row }) => String(row.original.status || row.original.containerNo || row.original.date || '—'),
  },
])

function openRelated(path: string) {
  return (_event: Event, row: TableRow<FreightRecord>) => {
    navigateTo(`${path}/${row.original.id}`)
  }
}
</script>

<template>
  <div class="space-y-6">
    <section v-for="group in groups" :key="group.path" class="space-y-2">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-medium text-highlighted">{{ relatedTitle(group) }}</h3>
        <UButton size="xs" color="neutral" variant="ghost" :to="group.path" trailing-icon="i-lucide-arrow-up-right">
          {{ t('freight.ui.viewAll') }}
        </UButton>
      </div>
      <div v-if="group.rows.length" class="overflow-x-auto">
        <UTable :data="group.rows.slice(0, 20)" :columns="columns"
          :get-row-id="(row: FreightRecord) => row.id" class="freight-table freight-table-compact min-w-max"
          :ui="freightTableUiCompact" @select="openRelated(group.path)" />
      </div>
      <div v-else class="rounded-md border border-dashed border-default px-3 py-4 text-sm text-muted">
        {{ t('freight.ui.noRelated') }}
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { h, type Component } from 'vue'
import { UBadge, UButton, UDropdownMenu, ULink } from '#components'
import type { FreightRecord } from '~/types/freight/record'
import { codeTitle, formatMoney, freightStatusBadge, shortDay } from '~/composables/freight/useFreight'
import { outstandingOf, postedDocumentTotal } from '~/utils/freight/finance'
import { buildPrintRoute } from '~/utils/freight/print-navigation'
import { freightTableUiReadonly } from '~/utils/table/theme'

const props = defineProps<{
  jobNo: string
  customer: string
  documents: FreightRecord[]
  supplierCosts: FreightRecord[]
  receivables: FreightRecord[]
}>()

const { t } = useI18n()
const route = useRoute()
const toast = useToast()

const customerInvoices = computed(() =>
  props.documents.filter(row => String(row.documentType || 'CUSTOMER_INVOICE').toUpperCase() === 'CUSTOMER_INVOICE'),
)

const latestCustomerInvoice = computed(() => {
  const rows = [...customerInvoices.value]
  if (!rows.length) return null
  rows.sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')) || String(b.debitNoteNo || '').localeCompare(String(a.debitNoteNo || '')))
  return rows[0] || null
})

async function printLatestInvoice() {
  const invoice = latestCustomerInvoice.value
  if (!invoice?.id) {
    toast.add({ title: t('freight.ui.noCustomerInvoicesToPrint'), color: 'warning' })
    return
  }
  await navigateTo(buildPrintRoute({
    collection: 'debitNotes',
    recordId: String(invoice.id),
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/finance/documents',
  }))
}

const TableBadge = UBadge as Component
const TableButton = UButton as Component
const TableLink = ULink as Component
const TableMenu = UDropdownMenu as Component

const summary = computed(() => {
  const revenue = Math.round(postedDocumentTotal(props.documents) * 100) / 100
  const cost = Math.round(props.supplierCosts.reduce((sum, row) => sum + Number(row.amount || 0), 0) * 100) / 100
  const outstanding = Math.round(props.receivables.reduce((sum, row) => sum + Number(row.outstanding || 0), 0) * 100) / 100
  return {
    revenue,
    cost,
    profit: Math.round((revenue - cost) * 100) / 100,
    outstanding,
  }
})

const jobCurrency = computed(() =>
  String(props.documents[0]?.currency || props.receivables[0]?.currency || props.supplierCosts[0]?.currency || '').trim() || undefined,
)

const summaryItems = computed(() => [
  { label: t('freight.ui.revenue'), value: formatMoney(summary.value.revenue, jobCurrency.value) },
  { label: t('freight.ui.costLabel'), value: formatMoney(summary.value.cost, jobCurrency.value) },
  { label: t('freight.ui.grossProfit'), value: formatMoney(summary.value.profit, jobCurrency.value) },
  { label: t('freight.ui.outstandingAmount'), value: formatMoney(summary.value.outstanding, jobCurrency.value) },
])

function rowMenuItems(row: FreightRecord) {
  const items: Array<{ label: string, icon: string, onSelect: () => void }> = [{
    label: t('freight.ui.viewDocument'),
    icon: 'i-lucide-eye',
    onSelect: () => { void navigateTo(`/finance/documents/${row.id}`) },
  }]
  if (String(row.documentType || 'CUSTOMER_INVOICE').toUpperCase() === 'CUSTOMER_INVOICE' && row.id) {
    items.push({
      label: t('freight.ui.printInvoice'),
      icon: 'i-lucide-printer',
      onSelect: () => {
        void navigateTo(buildPrintRoute({
          collection: 'debitNotes',
          recordId: String(row.id),
          template: 'tax-invoice',
          returnTo: route.fullPath,
          modulePath: '/finance/documents',
        }))
      },
    })
  }
  return [items]
}

const tableColumns = computed<TableColumn<FreightRecord>[]>(() => [
  {
    accessorKey: 'debitNoteNo',
    header: t('freight.ui.cols.documentNo'),
    cell: ({ row }) => h(TableLink, {
      to: `/finance/documents/${row.original.id}`,
      class: 'font-medium text-highlighted hover:text-primary hover:underline',
    }, () => String(row.original.debitNoteNo || row.original.paymentNo || '—')),
  },
  {
    accessorKey: 'documentType',
    header: t('freight.ui.cols.type'),
    cell: ({ row }) => h(TableBadge, {
      color: 'neutral',
      variant: 'subtle',
      size: 'xs',
    }, () => codeTitle(row.original.documentType)),
  },
  {
    accessorKey: 'date',
    header: t('freight.ui.cols.date'),
    cell: ({ row }) => h('span', { class: 'tabular-nums text-muted' }, shortDay(row.original.date)),
  },
  {
    accessorKey: 'total',
    header: t('freight.ui.cols.total'),
    meta: { class: { td: 'text-end tabular-nums whitespace-nowrap', th: 'text-end' } },
    cell: ({ row }) => h('span', { class: 'tabular-nums font-medium' }, formatMoney(row.original.total ?? row.original.amount, String(row.original.currency || jobCurrency.value || ''))),
  },
  {
    accessorKey: 'outstanding',
    header: t('freight.ui.outstandingAmount'),
    meta: { class: { td: 'text-end tabular-nums whitespace-nowrap', th: 'text-end' } },
    cell: ({ row }) => h('span', {
      class: outstandingOf(row.original) > 0 ? 'tabular-nums text-warning' : 'tabular-nums text-muted',
    }, formatMoney(outstandingOf(row.original), String(row.original.currency || jobCurrency.value || ''))),
  },
  {
    accessorKey: 'status',
    header: t('freight.ui.status'),
    cell: ({ row }) => freightStatusBadge(row.original.status),
  },
  {
    id: 'actions',
    header: '',
    meta: { class: { th: 'w-12 text-end', td: 'text-end w-12' } },
    cell: ({ row }) => h(TableMenu, {
      content: { align: 'end' },
      items: rowMenuItems(row.original),
      'aria-label': t('freight.ui.actions'),
    }, () => h(TableButton, {
      icon: 'i-lucide-ellipsis',
      color: 'neutral',
      variant: 'ghost',
      size: 'xs',
      'aria-label': t('freight.ui.actions'),
    })),
  },
])
</script>

<template>
  <div class="space-y-4">
    <FreightJobSectionHeader :title="t('freight.jobSections.finance')">
      <template #actions>
        <UButton size="xs" color="neutral" variant="soft" icon="i-lucide-printer"
          :disabled="!latestCustomerInvoice" :label="t('freight.ui.printInvoice')"
          @click="printLatestInvoice" />
        <UButton size="xs" color="neutral" variant="ghost" icon="i-lucide-arrow-up-right"
          :to="{ path: '/finance/documents', query: { jobNo } }" :label="t('freight.ui.openFinance')" />
      </template>
    </FreightJobSectionHeader>

    <FreightJobSummaryStrip :items="summaryItems" />

    <section class="space-y-2">
      <h4 class="text-xs font-semibold uppercase tracking-wide text-muted">
        {{ t('freight.ui.financialDocuments') }}
      </h4>
      <div v-if="documents.length" class="overflow-hidden rounded-md border border-default">
        <div class="overflow-x-auto">
          <UTable :data="documents" :columns="tableColumns" :get-row-id="(row: FreightRecord) => String(row.id || '')"
            class="freight-table min-w-max" :ui="freightTableUiReadonly" />
        </div>
      </div>
      <FreightJobEmptyState v-else :title="t('freight.ui.noFinancialDocuments')" icon="i-lucide-banknote" />
    </section>
  </div>
</template>

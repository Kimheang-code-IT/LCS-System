<script setup lang="ts">
import { UButton } from '#components'
import type { FreightRecord } from '~/types/record'
import { JOB_FINANCE_LINES_TABLE } from '~/config/job-workspace-forms'
import { formatMoney } from '~/composables/freight/useFreight'
import { createClientId } from '~/utils/client-id'
import { postedDocumentTotal } from '~/utils/freight/finance'
import {
  JOB_FINANCE_LINE_LABEL_KEYS,
  isJobFinanceRowEditable,
  jobFinanceChargeLines,
  jobFinanceExpenseRows,
  jobFinanceLineTotals,
  jobFinanceLines,
  normalizeJobFinanceExpense,
  type JobFinanceLine,
} from '~/utils/freight/job-finance'
import { buildPrintRoute } from '~/utils/freight/print-navigation'
import { JOB_FINANCE_LINE_KIND, type JobFinanceLineKind } from '~/utils/table/line-table-rules'

const props = withDefaults(defineProps<{
  job: FreightRecord
  jobNo: string
  customer: string
  documents: FreightRecord[]
  supplierCosts: FreightRecord[]
  receivables: FreightRecord[]
  editable?: boolean
}>(), {
  editable: false,
})

const emit = defineEmits<{
  'update:job': [patch: Record<string, unknown>]
}>()

const { t } = useI18n()
const route = useRoute()
const toast = useToast()
const store = useFreightStore()

const expenseRows = ref<JobFinanceLine[]>([])

function loadExpenses() {
  expenseRows.value = (Array.isArray(props.job.expenses) ? props.job.expenses as JobFinanceLine[] : [])
    .map(row => ({ ...normalizeJobFinanceExpense(row), id: String(row.id || '').trim() || createClientId('exp') }))
}

function setFinanceLines(value: JobFinanceLine[]) {
  const expenses = jobFinanceExpenseRows(value)
    .map(row => ({ ...row, id: String(row.id || '').trim() || createClientId('exp') }))
  expenseRows.value = expenses
  const patch = { expenses }
  emit('update:job', patch)
  if (props.job.id) {
    store.save('jobs', { ...props.job, ...patch, updatedAt: new Date().toISOString() } as FreightRecord)
  }
}

watch(() => props.job.id, loadExpenses, { immediate: true })

const charges = computed(() => jobFinanceChargeLines(props.job, String(props.customer || '')))

const lines = computed(() => jobFinanceLines({
  charges: charges.value,
  expenses: expenseRows.value,
  documents: props.documents,
  typeLabel: kind => (kind ? t(JOB_FINANCE_LINE_LABEL_KEYS[kind]) : ''),
}))

const rowLocked = (row: JobFinanceLine) => !isJobFinanceRowEditable(row, props.editable)

const latestCustomerInvoice = computed(() => {
  const rows = [...props.documents]
  if (!rows.length) return null
  rows.sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')) || String(b.debitNoteNo || '').localeCompare(String(a.debitNoteNo || '')))
  return rows[0] || null
})

function documentPrintRoute(documentId: string) {
  return buildPrintRoute({
    collection: 'debitNotes',
    recordId: documentId,
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/finance/documents',
  })
}

async function printLatestInvoice() {
  const invoice = latestCustomerInvoice.value
  if (!invoice?.id) {
    toast.add({ title: t('freight.ui.noCustomerInvoicesToPrint'), color: 'warning' })
    return
  }
  await navigateTo(documentPrintRoute(String(invoice.id)))
}

/** Per-row actions: only the source documents are navigable / printable. */
function rowMenuItems(row: JobFinanceLine) {
  const documentId = String(row._documentId || '')
  if (row._kind !== JOB_FINANCE_LINE_KIND.document || !documentId) return []
  const items = [{
    label: t('freight.ui.viewDocument'),
    icon: 'i-lucide-eye',
    onSelect: () => { void navigateTo(`/finance/documents/${documentId}`) },
  }]
  const source = props.documents.find(document => String(document.id) === documentId)
  if (String(source?.documentType || 'CUSTOMER_INVOICE').toUpperCase() === 'CUSTOMER_INVOICE') {
    items.push({
      label: t('freight.ui.printInvoice'),
      icon: 'i-lucide-printer',
      onSelect: () => { void navigateTo(documentPrintRoute(documentId)) },
    })
  }
  return items
}

const jobCurrency = computed(() =>
  String(props.documents[0]?.currency || props.receivables[0]?.currency || props.supplierCosts[0]?.currency || '').trim() || undefined,
)

const expenseTotal = computed(() => Math.round(expenseRows.value.reduce((sum, row) => sum + Number(row.amount || 0), 0) * 100) / 100)

const summary = computed(() => {
  const revenue = Math.round(postedDocumentTotal(props.documents) * 100) / 100
  // Supplier bills are posted costs; the expense grid is the job's manual cost.
  const supplierBills = props.supplierCosts.reduce((sum, row) => sum + Number(row.amount || 0), 0)
  const cost = Math.round((supplierBills + expenseTotal.value) * 100) / 100
  const outstanding = Math.round(props.receivables.reduce((sum, row) => sum + Number(row.outstanding || 0), 0) * 100) / 100
  return {
    revenue,
    cost,
    profit: Math.round((revenue - cost) * 100) / 100,
    outstanding,
  }
})

const summaryItems = computed(() => [
  { label: t('freight.ui.revenue'), value: formatMoney(summary.value.revenue, jobCurrency.value) },
  { label: t('freight.ui.costLabel'), value: formatMoney(summary.value.cost, jobCurrency.value) },
  { label: t('freight.ui.grossProfit'), value: formatMoney(summary.value.profit, jobCurrency.value) },
  { label: t('freight.ui.outstandingAmount'), value: formatMoney(summary.value.outstanding, jobCurrency.value) },
])

const kindTotals = computed(() => {
  const totals = jobFinanceLineTotals(lines.value)
  return (Object.keys(JOB_FINANCE_LINE_LABEL_KEYS) as JobFinanceLineKind[])
    .map(kind => ({ kind, value: totals[kind] }))
})
</script>

<template>
  <div class="space-y-4">
    <FreightJobSectionHeader :title="t('freight.jobSections.finance')">
      <template #actions>
        <UButton
          size="xs"
          color="neutral"
          variant="soft"
          icon="i-lucide-printer"
          :disabled="!latestCustomerInvoice"
          :label="t('freight.ui.printInvoice')"
          @click="printLatestInvoice" />
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-arrow-up-right"
          :to="{ path: '/finance/documents', query: { jobNo } }"
          :label="t('freight.ui.openFinance')" />
      </template>
    </FreightJobSectionHeader>

    <FreightJobSummaryStrip :items="summaryItems" />

    <div class="space-y-2">
      <FreightJobLineTable
        :table="JOB_FINANCE_LINES_TABLE"
        :model-value="lines"
        :row-disabled="rowLocked"
        :extra-row-menu-items="rowMenuItems"
        @update:model-value="setFinanceLines" />
      <div
        v-if="lines.length"
        class="ms-auto flex w-full max-w-sm flex-wrap items-center justify-end gap-x-4 gap-y-1 rounded-md border border-default px-3 py-2 text-sm"
      >
        <template v-for="entry in kindTotals" :key="entry.kind">
          <span class="text-muted">{{ t(JOB_FINANCE_LINE_LABEL_KEYS[entry.kind]) }}</span>
          <span class="font-semibold tabular-nums text-highlighted">{{ formatMoney(entry.value, jobCurrency) }}</span>
        </template>
      </div>
    </div>
  </div>
</template>

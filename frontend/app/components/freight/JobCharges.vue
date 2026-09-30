<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { FreightRecord } from '~/types/freight/record'
import { useLcs } from '~/composables/lcs/useLcs'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'

const props = defineProps<{
  job: FreightRecord
  jobNo: string
  editable?: boolean
}>()

const { t } = useI18n()
const toast = useToast()
const lcs = useLcs()
const route = useRoute()
const { formatDate, formatMoney, localization } = useAppLocalization()

type Row = FreightRecord & { _draft?: boolean }

const rows = ref<FreightRecord[]>([])
const invoice = ref<FreightRecord | null>(null)
const loading = ref(false)
const saving = ref(false)
const draft = ref<{ description: string, quantity: number, unitPrice: number, tax: number } | null>(null)

const orderId = computed(() => String(props.job.id || props.jobNo || ''))
const canCreateInvoice = computed(() => props.editable && rows.value.length > 0 && !invoice.value)
const draftTotal = computed(() => {
  if (!draft.value) return 0
  const base = (Number(draft.value.quantity) || 0) * (Number(draft.value.unitPrice) || 0)
  return base + base * ((Number(draft.value.tax) || 0) / 100)
})
const currency = computed(() => String(props.job.currency || localization.value.currency))

const columns: TableColumn<Row>[] = [
  { id: 'description', header: 'Description' },
  { accessorKey: 'documentDate', header: 'Date' },
  { accessorKey: 'documentType', header: 'Type' },
  { accessorKey: 'status', header: 'Status' },
  { accessorKey: 'total', header: 'Total' },
  { accessorKey: 'invoiceNo', header: 'Invoice' },
  { id: 'actions', header: '' },
]

const displayRows = computed<Row[]>(() => (draft.value ? [{ id: '__draft__', _draft: true } as Row, ...rows.value] : rows.value))

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    rows.value = await lcs.charges.listForOrder(orderId.value)
    invoice.value = await lcs.charges.getOrderInvoice(orderId.value)
  }
  catch {
    rows.value = []
    invoice.value = null
  }
  finally {
    loading.value = false
  }
}

watch(() => props.jobNo, () => { void load() }, { immediate: true })

function startAdd() {
  draft.value = { description: '', quantity: 1, unitPrice: 0, tax: 0 }
}

function cancelDraft() {
  draft.value = null
}

async function saveDraft() {
  const current = draft.value
  if (!current || !current.description.trim()) return
  saving.value = true
  try {
    await lcs.charges.createForOrder(orderId.value, {
      documentType: 'SERVICE_NOTE',
      documentDate: new Date().toISOString().slice(0, 10),
      currency: currency.value,
      lines: [{
        description: current.description,
        quantity: Number(current.quantity) || 1,
        unitPrice: Number(current.unitPrice) || 0,
        tax: Number(current.tax) || 0,
      }],
    })
    draft.value = null
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    await load()
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

async function createInvoice() {
  saving.value = true
  try {
    invoice.value = await lcs.charges.createOrderInvoice(orderId.value, `order-invoice-${orderId.value}`)
    toast.add({ title: t('freight.ui.draftInvoiceCreated'), color: 'success' })
    await load()
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

function printInvoice() {
  if (!invoice.value?.id) return
  void navigateTo(buildPrintRoute({
    collection: 'debitNotes',
    recordId: String(invoice.value.id),
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/service-orders',
  }))
}

function printCharge(row: FreightRecord) {
  void navigateTo(buildPrintRoute({
    collection: 'jobCharges',
    recordId: String(row.id),
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/service-orders',
  }))
}

function chargeDescription(row: FreightRecord): string {
  const lines = Array.isArray(row.feeLines) ? row.feeLines as Array<Record<string, unknown>> : []
  return String(lines[0]?.description || row.chargeNo || '')
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          v-if="editable"
          icon="i-lucide-plus"
          color="primary"
          variant="soft"
          :label="t('freight.ui.addCharge')"
          :disabled="Boolean(draft)"
          @click="startAdd" />
        <UButton
          v-if="editable"
          icon="i-lucide-file-plus"
          color="primary"
          :loading="saving"
          :disabled="!canCreateInvoice"
          :label="t('freight.ui.createFinanceInvoice')"
          @click="createInvoice" />
      </div>
      <div class="flex items-center gap-2">
        <UBadge v-if="invoice" color="success" variant="subtle">
          {{ invoice.documentNo || invoice.invoiceNo }} · {{ invoice.status }}
        </UBadge>
        <UButton
          icon="i-lucide-printer"
          color="neutral"
          variant="soft"
          :disabled="!invoice"
          :label="t('freight.ui.printInvoice')"
          @click="printInvoice" />
      </div>
    </div>

    <UTable :data="displayRows" :columns="columns" :loading="loading">
      <template #description-cell="{ row }">
        <UInput
          v-if="row.original._draft"
          v-model="draft!.description"
          placeholder="Description"
          size="sm"
          class="w-full"
          @keyup.enter="saveDraft" />
        <span v-else class="text-sm font-medium text-highlighted">
          {{ chargeDescription(row.original) }}
        </span>
      </template>
      <template #documentDate-cell="{ row }">
        <span class="text-sm text-muted">{{ formatDate(row.original._draft ? new Date().toISOString().slice(0, 10) : row.original.documentDate) }}</span>
      </template>
      <template #documentType-cell="{ row }">
        <span v-if="row.original._draft" class="text-xs text-muted">SERVICE NOTE</span>
        <UBadge
v-else
color="neutral"
variant="subtle"
size="sm">{{ String(row.original.documentType || '').replace(/_/g, ' ') }}</UBadge>
      </template>
      <template #status-cell="{ row }">
        <UBadge
v-if="row.original._draft"
color="neutral"
variant="subtle"
size="sm">DRAFT</UBadge>
        <UBadge
v-else
:color="row.original.status === 'ISSUED' ? 'success' : 'neutral'"
variant="subtle"
size="sm">{{ row.original.status }}</UBadge>
      </template>
      <template #total-cell="{ row }">
        <span v-if="row.original._draft" class="tabular-nums text-muted">{{ formatMoney(draftTotal, currency) }}</span>
        <span v-else class="tabular-nums">{{ formatMoney(row.original.total, String(row.original.currency || currency)) }}</span>
      </template>
      <template #invoiceNo-cell="{ row }">
        <span class="text-sm text-muted">{{ row.original.invoiceNo || '—' }}</span>
      </template>
      <template #actions-cell="{ row }">
        <div class="flex items-center justify-end gap-1">
          <template v-if="row.original._draft">
            <div class="mr-2 grid grid-cols-3 gap-1">
              <UInputNumber
v-model="draft!.quantity"
:min="0"
size="sm"
class="w-20"
placeholder="Qty" />
              <UInputNumber
v-model="draft!.unitPrice"
:min="0"
size="sm"
class="w-24"
placeholder="Price" />
              <UInputNumber
v-model="draft!.tax"
:min="0"
size="sm"
class="w-20"
placeholder="Tax %" />
            </div>
            <UButton
size="xs"
color="primary"
icon="i-lucide-check"
aria-label="Save"
:loading="saving"
@click="saveDraft" />
            <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-x"
aria-label="Cancel"
@click="cancelDraft" />
          </template>
          <UButton
            v-else
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-printer"
            aria-label="Print"
            @click="printCharge(row.original)" />
        </div>
      </template>
    </UTable>

    <FreightJobEmptyState
      v-if="!loading && !displayRows.length"
      :title="t('freight.ui.noServiceCharges')"
      :description="t('freight.ui.addCharge')"
      icon="i-lucide-receipt-text" />
  </div>
</template>

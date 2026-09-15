<script setup lang="ts">
import type { FreightRecord } from '~/types/freight/record'
import type { FreightTable } from '~/config/freight-modules'
import {
  JOB_ACTUAL_CONTAINER_TABLE,
  JOB_CONTAINER_PAYMENT_TABLE,
  JOB_CONTAINER_REQUIREMENT_TABLE,
} from '~/config/job-workspace-forms'
import { formatMoney } from '~/composables/freight/useFreight'
import { buildPrintRoute } from '~/utils/freight/print-navigation'
import {
  duplicateContainerNumber,
  firstOpenRequirement,
  invalidGrossWeight,
  jobActualContainers,
  jobContainerPaymentRows,
  jobContainerPaymentTotals,
  jobContainerRequirements,
  missingContainerNumber,
  newLineId,
  persistableActuals,
  persistablePayments,
  persistableRequirements,
  requirementOptionLabel,
  withRequirementProgress,
} from '~/utils/freight/job-containers'

const props = withDefaults(defineProps<{
  job: FreightRecord
  shipments?: FreightRecord[]
  charges?: FreightRecord[]
  containerRequirements?: FreightRecord[]
  actualContainers?: FreightRecord[]
  isCreate: boolean
  editable?: boolean
  editablePayments?: boolean
}>(), {
  shipments: () => [],
  charges: () => [],
  containerRequirements: () => [],
  actualContainers: () => [],
  editable: false,
  editablePayments: undefined,
})

const emit = defineEmits<{
  'update:job': [patch: Record<string, unknown>]
}>()

const { t } = useI18n()
const route = useRoute()
const store = useFreightStore()
const toast = useToast()
const requirementRows = ref<Array<Record<string, unknown>>>([])
const actualRows = ref<Array<Record<string, unknown>>>([])
const paymentRows = ref<Array<Record<string, unknown>>>([])

const totals = computed(() => jobContainerPaymentTotals(paymentRows.value, props.job.vatRate))
const currency = computed(() => String(props.job.currency || 'USD'))
const canEdit = computed(() => props.editable || props.isCreate)
const canEditPayments = computed(() =>
  props.editablePayments !== undefined ? (props.editablePayments || props.isCreate) : canEdit.value)

const quotation = computed(() => {
  const no = String(props.job.quotationNo || '').trim()
  if (!no) return null
  return store.list('quotations').find(row => String(row.quotationNo || '') === no) || null
})

const requirementDisplayRows = computed(() => withRequirementProgress(requirementRows.value, actualRows.value))

const feeOptions = computed(() => {
  const rows = store.list('feeTypes').length ? store.list('feeTypes') : store.list('chargeTypes')
  return rows.map(row => String(row.name || row.code || '').trim()).filter(Boolean)
})

const requirementTable = JOB_CONTAINER_REQUIREMENT_TABLE

const actualTable = computed<FreightTable>(() => ({
  ...JOB_ACTUAL_CONTAINER_TABLE,
  columns: JOB_ACTUAL_CONTAINER_TABLE.columns.map((column) => {
    if (column.key !== 'containerRequirementId') return column
    return {
      ...column,
      optionItems: requirementRows.value.map(row => ({
        label: requirementOptionLabel(row),
        value: String(row.id || ''),
      })).filter(item => item.value),
    }
  }),
}))

const paymentTable = computed<FreightTable>(() => {
  const containers = actualRows.value
    .map(row => String(row.containerNo || '').trim())
    .filter(Boolean)
  return {
    ...JOB_CONTAINER_PAYMENT_TABLE,
    columns: JOB_CONTAINER_PAYMENT_TABLE.columns.map((column) => {
      if (column.key === 'feeType') {
        return { ...column, type: feeOptions.value.length ? 'select' : 'text', options: feeOptions.value }
      }
      if (column.key === 'containerNo') {
        return {
          ...column,
          type: containers.length ? 'select' : 'text',
          optionItems: actualRows.value
            .filter(row => String(row.containerNo || '').trim())
            .map(row => ({
              label: [String(row.containerNo || '').trim(), String(row.containerType || '').trim()].filter(Boolean).join(' · '),
              value: String(row.containerNo || '').trim(),
            })),
        }
      }
      return column
    }),
  }
})

function money(value: number) {
  return formatMoney(value, currency.value)
}

function withIds(rows: Array<Record<string, unknown>>, prefix: string) {
  return rows.map(row => String(row.id || '').trim() ? row : { ...row, id: newLineId(prefix) })
}

function loadRows() {
  requirementRows.value = jobContainerRequirements(props.job, {
    requirements: props.containerRequirements,
    quotation: quotation.value,
  })
  actualRows.value = jobActualContainers(props.job, {
    actuals: props.actualContainers,
    shipments: props.shipments,
  })
  paymentRows.value = jobContainerPaymentRows(props.job, {
    shipments: props.shipments,
    charges: props.charges,
    quotation: quotation.value,
  })
}

function syncCollection(collection: string, rows: Array<Record<string, unknown>>) {
  const jobNo = String(props.job.jobNo || '')
  if (!jobNo) return
  const existing = store.list(collection).filter(row => String(row.jobNo || '') === jobNo)
  const nextIds = new Set(rows.map(row => String(row.id || '')).filter(Boolean))
  const removeIds = existing.filter(row => !nextIds.has(row.id)).map(row => row.id)
  if (removeIds.length) store.remove(collection, removeIds)
  for (const row of rows) {
    store.save(collection, {
      ...row,
      jobNo,
      serviceOrderId: props.job.id,
      id: String(row.id),
    } as FreightRecord)
  }
}

function persist() {
  const requirements = persistableRequirements(requirementRows.value)
  const actuals = persistableActuals(actualRows.value)
  const payments = persistablePayments(paymentRows.value)
  const nextTotals = jobContainerPaymentTotals(payments, props.job.vatRate)
  const firstActual = actuals[0] || {}
  const patch = {
    containerRequirements: requirements,
    actualContainers: actuals,
    containerPayments: payments,
    containerNo: String(firstActual.containerNo || props.job.containerNo || ''),
    containerType: String(firstActual.containerType || requirements[0]?.containerType || props.job.containerType || ''),
    sealNo: String(firstActual.sealNo || props.job.sealNo || ''),
    subtotal: nextTotals.subtotal,
    vat: nextTotals.vat,
    total: nextTotals.total,
    amount: nextTotals.total,
  }
  emit('update:job', patch)
  if (!props.isCreate && props.job.id) {
    store.save('jobs', {
      ...props.job,
      ...patch,
      updatedAt: new Date().toISOString(),
    })
    syncCollection('containerRequirements', requirements)
    syncCollection('actualContainers', actuals)
  }
}

function setRequirements(value: Array<Record<string, unknown>>) {
  requirementRows.value = persistableRequirements(withIds(value, 'cr'))
  persist()
}

function setActuals(value: Array<Record<string, unknown>>) {
  const next = withIds(value, 'ac').map((row) => {
    if (row.containerType || row.containerRequirementId) return row
    const open = firstOpenRequirement(requirementDisplayRows.value)
    if (!open) return { ...row, status: row.status || 'Expected' }
    return {
      ...row,
      containerType: open.containerType,
      containerRequirementId: open.id,
      status: row.status || 'Expected',
    }
  })
  if (missingContainerNumber(next)) {
    toast.add({ title: t('freight.ui.containerNoRequired'), color: 'error' })
    return
  }
  if (invalidGrossWeight(next)) {
    toast.add({ title: t('freight.ui.grossLessThanNet'), color: 'error' })
    return
  }
  const others = store.list('actualContainers').filter(row => String(row.jobNo || '') !== String(props.job.jobNo || ''))
  const duplicate = duplicateContainerNumber(next, others)
  if (duplicate) {
    toast.add({ title: t('freight.ui.duplicateContainerNo'), color: 'error' })
    return
  }
  actualRows.value = next
  persist()
}

function setPayments(value: Array<Record<string, unknown>>) {
  paymentRows.value = withIds(value, 'cp')
  persist()
}

function debitInvoicePrintRoute(containerIndex: number) {
  return buildPrintRoute({
    collection: 'jobs',
    recordId: String(props.job.id),
    template: 'debit-note',
    container: containerIndex,
    returnTo: route.fullPath,
    modulePath: '/service-orders',
    autoPrint: true,
  })
}

function actualContainerPrintActions(row: Record<string, unknown>) {
  if (props.isCreate || !props.job.id) return []
  const containerNo = String(row.containerNo || '').trim()
  if (!containerNo) return []

  const index = actualRows.value.findIndex(item => String(item.id || '') === String(row.id || ''))
  if (index < 0) return []

  return [{
    label: t('freight.print.job.printDebitInvoice'),
    icon: 'i-lucide-credit-card',
    color: 'primary' as const,
    onSelect: () => {
      persist()
      void navigateTo(debitInvoicePrintRoute(index))
    },
  }]
}

watch(() => props.job.id, loadRows, { immediate: true })
</script>

<template>
  <div class="space-y-6">
    <FreightJobLineTable
      :table="requirementTable"
      :model-value="requirementDisplayRows"
      :disabled="!canEdit"
      @update:model-value="setRequirements"
    />
    <FreightJobLineTable
      :table="actualTable"
      :model-value="actualRows"
      :disabled="!canEdit"
      :extra-row-menu-items="actualContainerPrintActions"
      @update:model-value="setActuals"
    />
    <FreightJobLineTable
      :table="paymentTable"
      :model-value="paymentRows"
      :disabled="!canEditPayments"
      @update:model-value="setPayments"
    />
    <div class="ms-auto grid w-full max-w-sm gap-1 px-1 py-1.5 text-xs">
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.subtotal') }}</span>
        <span class="font-medium tabular-nums text-highlighted">{{ money(totals.subtotal) }}</span>
      </div>
      <div v-if="totals.discount" class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.discount') }}</span>
        <span class="font-medium tabular-nums text-highlighted">{{ money(totals.discount) }}</span>
      </div>
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.tax') }}</span>
        <span class="font-medium tabular-nums text-highlighted">{{ money(totals.vat) }}</span>
      </div>
      <div class="mt-1 flex items-center justify-between gap-4 border-t border-default pt-2 text-base">
        <span class="font-semibold text-highlighted">{{ t('freight.fields.total') }}</span>
        <span class="font-bold tabular-nums text-primary">{{ money(totals.total) }}</span>
      </div>
    </div>
  </div>
</template>

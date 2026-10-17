<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import type { FreightTable } from '~/config/freight-modules'
import {
  JOB_ACTUAL_CONTAINER_TABLE,
  JOB_CONTAINER_PAYMENT_TABLE,
} from '~/config/job-workspace-forms'
import { formatMoney } from '~/composables/freight/useFreight'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { createClientId } from '~/utils/client-id'
import { focusField } from '~/utils/validation/focus'
import { buildPrintRoute } from '~/utils/freight/print-navigation'
import {
  containerRowIssues,
  firstOpenRequirement,
  jobActualContainers,
  jobContainerPaymentRows,
  jobContainerPaymentTotals,
  jobContainerRequirements,
  persistableActuals,
  persistablePayments,
  persistableRequirements,
  requirementOptionLabel,
  withRequirementProgress,
  type ContainerRowIssue,
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
const { localization } = useAppLocalization()
const requirementRows = ref<Array<Record<string, unknown>>>([])
const actualRows = ref<Array<Record<string, unknown>>>([])
const paymentRows = ref<Array<Record<string, unknown>>>([])

const totals = computed(() => jobContainerPaymentTotals(paymentRows.value, props.job.vatRate, props.job.discount))
const currency = computed(() => String(props.job.currency || localization.value.currency))
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
  return rows.map(row => String(row.id || '').trim() ? row : { ...row, id: createClientId(prefix) })
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
  const nextTotals = jobContainerPaymentTotals(payments, props.job.vatRate, props.job.discount)
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

const ISSUE_MESSAGES: Record<ContainerRowIssue['code'], string> = {
  missingContainerNo: 'freight.ui.containerNoRequired',
  grossLessThanNet: 'freight.ui.grossLessThanNet',
  duplicateContainerNo: 'freight.ui.duplicateContainerNo',
  containerNoInUse: 'freight.ui.containerNoInUse',
}

/** Inline cell errors for the actual-container grid (`actualContainers.<row>.<column>`). */
const actualFieldErrors = ref<Record<string, string>>({})

function validateActualRows(rows: Array<Record<string, unknown>>) {
  const others = store.list('actualContainers').filter(row => String(row.jobNo || '') !== String(props.job.jobNo || ''))
  const issues = containerRowIssues(rows, others)
  const errors: Record<string, string> = {}
  for (const issue of issues) {
    const key = `actualContainers.${issue.index}.${issue.column}`
    if (!(key in errors)) errors[key] = t(ISSUE_MESSAGES[issue.code])
  }
  actualFieldErrors.value = errors
  return errors
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
  const errors = validateActualRows(next)
  // Block the write: the invalid row stays on screen with its message and no
  // valid row is discarded. This grid only renders inside the Containers tab,
  // so the field is already on screen and only needs scrolling + focus.
  if (Object.keys(errors).length) {
    void focusField(Object.keys(errors)[0]!)
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

/** Per-row invoice button on the container payment grid. */
function paymentRowAction(action: string, row: Record<string, unknown>) {
  if (action !== 'invoice' || props.isCreate || !props.job.id) return null

  const index = Number(row._rowIndex)
  if (!Number.isInteger(index) || index < 0 || index >= paymentRows.value.length) return null

  return {
    label: t('freight.print.job.printPaymentInvoice'),
    icon: 'i-lucide-receipt-text',
    color: 'primary' as const,
    onSelect: () => {
      persist()
      const { path, query } = buildPrintRoute({
        collection: 'jobs',
        recordId: String(props.job.id),
        template: 'debit-note',
        returnTo: route.fullPath,
        modulePath: '/service-orders',
        lineIndex: index,
        autoPrint: true,
      })
      void navigateTo({ path, query })
    },
  }
}

watch(() => props.job.id, loadRows, { immediate: true })
</script>

<template>
  <div class="space-y-6">
    <FreightAppLineTable
      :table="actualTable"
      :model-value="actualRows"
      :disabled="!canEdit"
      :extra-row-menu-items="actualContainerPrintActions"
      :field-errors="actualFieldErrors"
      @update:model-value="setActuals"
    />
    <FreightAppLineTable
      :table="paymentTable"
      :model-value="paymentRows"
      :disabled="!canEditPayments"
      :row-actions="paymentRowAction"
      @update:model-value="setPayments"
    />
    <div class="ms-auto grid w-full max-w-sm gap-1.5 px-1 py-2 text-sm">
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.subtotal') }}</span>
        <span class="font-medium tabular-nums text-highlighted">{{ money(totals.subtotal) }}</span>
      </div>
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.discount') }}</span>
        <UInputNumber
          :model-value="Number(props.job.discount || 0)"
          :min="0"
          :increment="false"
          :decrement="false"
          :disabled="!canEditPayments"
          size="md"
          class="w-40 text-right"
          :aria-label="t('freight.fields.discount')"
          @update:model-value="value => emit('update:job', { discount: value ?? 0 })"
        />
      </div>
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('containerPaymentTaxRate') }}</span>
        <div class="flex w-40 items-center gap-2">
          <UInputNumber
            :model-value="Number(props.job.vatRate || 0)"
            :min="0"
            :max="100"
            :increment="false"
            :decrement="false"
            :disabled="!canEditPayments"
            size="md"
            class="w-full text-right"
            :aria-label="t('containerPaymentTaxRate')"
            @update:model-value="value => emit('update:job', { vatRate: value ?? 0 })"
          />
          <span class="text-muted">%</span>
        </div>
      </div>
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.tax') }}</span>
        <span class="font-medium tabular-nums text-highlighted">{{ money(totals.vat) }}</span>
      </div>
      <div class="mt-1 flex items-center justify-between gap-4 border-t border-default pt-2 text-base">
        <span class="font-semibold text-highlighted">{{ t('freight.fields.grandTotal') }}</span>
        <span class="font-bold tabular-nums text-primary">{{ money(totals.total) }}</span>
      </div>
    </div>
  </div>
</template>

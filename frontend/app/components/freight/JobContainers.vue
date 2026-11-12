<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import type { FreightTable } from '~/config/freight-modules'
import {
  JOB_ACTUAL_CONTAINER_TABLE,
  JOB_CONTAINER_PAYMENT_TABLE,
} from '~/config/job-workspace-forms'
import { formatMoney } from '~/composables/freight/useFreight'
import { useLcs } from '~/composables/freight/useLcs'
import { useAutosave } from '~/composables/common/useAutosave'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { apiErrorMessage } from '~/utils/validation/api-error'
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
  syncPaymentContainerReferences,
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
const lcs = useLcs()
const { localization } = useAppLocalization()
const requirementRows = ref<Array<Record<string, unknown>>>([])
const actualRows = ref<Array<Record<string, unknown>>>([])
const paymentRows = ref<Array<Record<string, unknown>>>([])
/** Page-level refusal from the container API — never a toast. */
const syncError = ref('')

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
    actuals: actualRows.value,
  })
}

function serverContainerId(value: unknown) {
  const id = String(value ?? '').trim()
  return /^\d+$/.test(id) ? id : ''
}

/**
 * Write prepared and numbered rows to the container API.
 *
 * A prepared row (`pending`, no number) already exists server-side and needs no
 * write until a number is entered. Numbered rows are upserted, and rows the user
 * removed are deleted — the backend refuses that deletion while a payment still
 * references the container, and the row is restored on the next load.
 */
async function syncActualContainers(rows: Array<Record<string, unknown>>) {
  const orderId = String(props.job.id || '')
  if (props.isCreate || !orderId) return rows
  const before = new Set(
    (props.actualContainers || []).map(row => serverContainerId(row.id)).filter(Boolean),
  )
  const next = [...rows]
  for (let index = 0; index < next.length; index += 1) {
    const row = next[index]!
    const id = serverContainerId(row.id)
    const containerNo = String(row.containerNo || '').trim()
    if (!containerNo) {
      if (id) before.delete(id)
      continue
    }
    const containerTypeId = Number(row.containerTypeId || 0)
    const payload: Record<string, unknown> = {
      containerNumber: containerNo,
      containerTypeId: containerTypeId > 0 ? containerTypeId : undefined,
      containerType: containerTypeId > 0 ? undefined : String(row.containerType || ''),
      sealSerial: String(row.sealNo || ''),
      status: String(row.status || 'Expected'),
      netWeightKg: Number(row.netWeightKg || 0) || undefined,
      grossWeightKg: Number(row.grossWeightKg || 0) || undefined,
      containerRequirementId: String(row.containerRequirementId || '') || undefined,
    }
    if (id) payload.id = id
    const saved = await lcs.jobs.addActualContainer(orderId, payload)
    next[index] = {
      ...row,
      id: String(saved.id || row.id),
      pending: false,
      containerType: String(saved.containerType || row.containerType || ''),
      containerTypeId: saved.containerTypeId ?? row.containerTypeId ?? '',
    }
    if (id) before.delete(id)
  }
  if (before.size) {
    await lcs.jobs.deleteActualContainers(orderId, [...before])
  }
  return next
}

function buildPatch(actuals: Array<Record<string, unknown>>) {
  const requirements = persistableRequirements(requirementRows.value)
  const payments = persistablePayments(paymentRows.value)
  const nextTotals = jobContainerPaymentTotals(payments, props.job.vatRate, props.job.discount)
  const firstActual = actuals[0] || {}
  return {
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
}

/**
 * Numbered containers are written immediately (the API owns their ids); the
 * requirement/payment rows only update the page model, so the order Save and
 * its local draft own them. Nothing here writes the whole order per keystroke.
 */
async function persist(): Promise<Record<string, unknown>> {
  syncError.value = ''
  let actuals = persistableActuals(actualRows.value)
  if (!props.isCreate && props.job.id) {
    try {
      actuals = await syncActualContainers(actuals)
      // Mutate the existing row objects in place so Vue does not rebuild the
      // table rows: keystrokes typed while a write was in flight used to be
      // wiped by the row replacement. Only the server-owned fields (id, type,
      // pending) are synced; whatever the operator typed stays on the row.
      const savedById = new Map(actuals.map(row => [String(row.id || ''), row]))
      for (let index = 0; index < actualRows.value.length; index += 1) {
        const row = actualRows.value[index]!
        const saved = savedById.get(String(row.id || '')) || savedById.get(String((row as Record<string, unknown>).previousId || ''))
        if (!saved) continue
        if (saved.id) row.id = String(saved.id)
        row.containerTypeId = saved.containerTypeId ?? row.containerTypeId
        row.containerType = String(saved.containerType || row.containerType || '')
        row.pending = false
      }
      void divergeCheck()
      function divergeCheck() {
        // Typing may have advanced past what was written; one trailing write
        // guarantees the stored number ends up the full entered value.
        for (const row of actualRows.value) {
          const typed = String(row.containerNo || '').trim()
          const saved = savedById.get(String(row.id || ''))
          if (typed && saved && typed !== String(saved.containerNo ?? saved.containerNumber ?? '').trim()) {
            schedulePersist()
            return
          }
        }
      }
      paymentRows.value = syncPaymentContainerReferences(paymentRows.value, actuals)
    }
    catch (error) {
      // Keep the typed rows and the parent model: a failed sync must not discard
      // an operator's input. The next save retries the write.
      syncError.value = apiErrorMessage(error, t('freight.ui.saveFailed'))
    }
  }
  const patch = buildPatch(actuals)
  emit('update:job', patch)
  return patch
}

/** Print reads the server copy, so persist the model patch first (explicit action). */
async function persistForPrint() {
  await autosave.flush()
  const patch = buildPatch(persistableActuals(actualRows.value))
  if (!props.isCreate && props.job.id) {
    store.save('jobs', {
      ...props.job,
      ...patch,
      updatedAt: new Date().toISOString(),
    })
  }
  return patch
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

async function setActuals(value: Array<Record<string, unknown>>) {
  // Patch the child's row objects in place when a prepared row needs its
  // requirement default: rebuilding the rows array per keystroke re-renders
  // the table and drops the focused input's in-flight typing.
  let structural = false
  for (const row of value) {
    if (row.containerType || row.containerRequirementId) continue
    const open = firstOpenRequirement(requirementDisplayRows.value)
    if (open) {
      row.containerType = open.containerType
      row.containerRequirementId = open.id
      structural = true
    }
    if (!row.status) row.status = 'Expected'
  }
  const next = structural ? [...value] : value
  const errors = validateActualRows(next)
  // Block the write: the invalid row stays on screen with its message and no
  // valid row is discarded. This grid only renders inside the Containers tab,
  // so the field is already on screen and only needs scrolling + focus.
  if (Object.keys(errors).length) {
    void focusField(Object.keys(errors)[0]!)
    return
  }
  actualRows.value = next
  schedulePersist()
}

/**
 * Single-flight trailing write: keystrokes coalesce into one POST and a second
 * run waits for the first, so responses cannot land out of order.
 */
const autosave = useAutosave(async () => {
  await persist()
  return true
}, { delay: 400 })

function schedulePersist() {
  autosave.schedule()
}

onBeforeUnmount(() => {
  // A quick navigation must not drop the last typed container.
  void autosave.flush()
  autosave.dispose()
})

async function setPayments(value: Array<Record<string, unknown>>) {
  paymentRows.value = withIds(value, 'cp')
  schedulePersist()
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
    onSelect: async () => {
      await persistForPrint()
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
    onSelect: async () => {
      await persistForPrint()
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
    <CommonAppFormErrorSummary v-if="syncError" :form-errors="[syncError]" />
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
          :step-snapping="false"
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
            :step-snapping="false"
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

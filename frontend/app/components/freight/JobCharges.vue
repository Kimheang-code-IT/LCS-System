<script setup lang="ts">
/**
 * Service-order Service Charge tab. Renders through the shared `AppLineTable`
 * via `AppSaveGrid`: one row per charge, edited in place. The grid has no save
 * of its own — the page header's Save changes writes the pending change set
 * (`savePending`) and the totals below the grid follow the unsaved rows live.
 */
import type { FreightRecord } from '~/types/record'
import type { SaveGridChange } from '~/types/save-grid'
import { useLcs } from '~/composables/freight/useLcs'
import { useConfirm } from '~/composables/common/useConfirm'
import { formatMoney } from '~/composables/freight/useFreight'
import { apiErrorMessage } from '~/utils/validation/api-error'
import { validateTableRows } from '~/utils/validation/record-validation'
import { SAVE_GRID_NEW_PREFIX, rowsBeingSaved as selectRowsBeingSaved } from '~/types/save-grid'
import {
  isDeletableCharge,
  serviceChargeIsCreatable,
  serviceChargePayload,
  serviceChargeRows,
  serviceChargeRowDisabled,
  serviceChargeTable,
  serviceChargeTotals,
  type ServiceChargeRow,
} from '~/utils/freight/job-charges'
import { chargeDomainStatus } from '~/utils/freight/states'

const props = defineProps<{
  job: FreightRecord
  jobNo: string
  editable?: boolean
}>()

const emit = defineEmits<{
  'update:job': [patch: Record<string, unknown>]
  'update:dirty': [dirty: boolean]
}>()

const { t } = useI18n()
const toast = useToast()
const lcs = useLcs()
const route = useRoute()
const { confirm } = useConfirm()

const charges = ref<FreightRecord[]>([])
const loading = ref(false)
const saving = ref(false)
/** Page-level refusal (business rule, dependency, network) — never a toast. */
const formErrors = ref<string[]>([])

const orderId = computed(() => String(props.job.id || props.jobNo || ''))
const currency = computed(() => String(props.job.currency || ''))
const rows = computed(() => serviceChargeRows(charges.value))
const table = computed(() => serviceChargeTable())

/** The grid's working rows: totals include edits that are not saved yet. */
const draftRows = ref<ServiceChargeRow[]>([])
const summaryRows = computed(() => draftRows.value.length ? draftRows.value : rows.value)
const totals = computed(() => serviceChargeTotals(summaryRows.value, props.job.vatRate, props.job.discount))

/**
 * The single rate behind the summary Tax line — or "Mixed" when the lines carry
 * several different rates, so one wrong percentage is never displayed.
 */
const summaryTaxRate = computed(() => {
  const rates = new Set(summaryRows.value
    .map(row => Number(row.taxRate ?? row.tax ?? 0))
    .filter(rate => rate > 0))
  return rates.size > 1 ? null : Number(props.job.vatRate || 0)
})

function money(value: number) {
  return formatMoney(value, currency.value)
}

/** Additional Details dialog: the sheet-level discount and tax rate. */
const additionalOpen = ref(false)

function applyAdditionalDetails(values: { discount: number, taxRate: number }) {
  emit('update:job', { discount: values.discount, vatRate: values.taxRate })
}

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    charges.value = await lcs.charges.listForOrder(orderId.value)
  }
  catch {
    charges.value = []
  }
  finally {
    loading.value = false
  }
}

watch(() => props.jobNo, () => { void load() }, { immediate: true })

/**
 * Per-row menu. Additional Details and Delete are the shared renderer's own
 * entries; this supplies Print Invoice: an already-invoiced charge opens its
 * existing finance invoice, an issued one is confirmed then converted through
 * the existing bill-once endpoint (the backend returns the same document on a
 * retry, so no duplicate is possible).
 */
function rowMenuItems(row: Record<string, unknown>) {
  const id = String(row.id ?? '')
  if (!id || id.startsWith(SAVE_GRID_NEW_PREFIX)) return []
  return [
    {
      label: t('freight.ui.printInvoice'),
      icon: 'i-lucide-printer',
      onSelect: () => { void printRowInvoice(row) },
    },
  ]
}

/** The print preview of the finance invoice that owns `invoiceId`. */
function invoicePrintRoute(invoiceId: string) {
  return buildPrintRoute({
    collection: 'debitNotes',
    recordId: invoiceId,
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/finance/documents',
  })
}

async function printRowInvoice(row: Record<string, unknown>) {
  const charge = charges.value.find(item => String(item.id ?? '') === String(row.id ?? ''))
  if (!charge) return
  formErrors.value = []
  const invoiceId = String(charge.financialDocumentId || '')
  if (invoiceId) {
    await navigateTo(invoicePrintRoute(invoiceId))
    return
  }
  if (chargeDomainStatus(charge.status) !== 'ISSUED') {
    formErrors.value = [t('freight.ui.chargeNotIssued')]
    return
  }
  const accepted = await confirm({
    kind: 'submit',
    descriptionKey: 'freight.ui.createInvoiceConfirm',
    descriptionParams: { name: String(charge.chargeNo || charge.id || '') },
  })
  if (!accepted) return
  try {
    const invoice = await lcs.runCommand('charge.invoice', String(charge.id), key =>
      lcs.charges.createFinanceInvoice(String(charge.id), key))
    toast.add({ title: t('freight.ui.draftInvoiceCreated'), color: 'success' })
    await load()
    await navigateTo(invoicePrintRoute(String(invoice.id)))
  }
  catch (error) {
    formErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

/** The charges eligible for a combined invoice: issued and not yet invoiced. */
const eligibleForCombinedInvoice = computed(() => charges.value.filter(charge =>
  chargeDomainStatus(charge.status) === 'ISSUED'
  && !charge.financialDocumentId))

const combinedInvoiceBusy = ref(false)

/**
 * Top Print Invoice: one combined invoice for every eligible charge of this
 * order. Lines that already belong to an invoice are excluded; when every line
 * shares one invoice it is opened instead of drafting another. The backend
 * re-validates the same customer/currency/not-invoiced rules per charge.
 */
async function printCombinedInvoice() {
  formErrors.value = []
  const eligible = eligibleForCombinedInvoice.value
  if (!eligible.length) {
    const invoiceIds = new Set(charges.value
      .map(charge => String(charge.financialDocumentId || ''))
      .filter(Boolean))
    if (invoiceIds.size === 1) {
      await navigateTo(invoicePrintRoute([...invoiceIds][0]!))
      return
    }
    formErrors.value = [invoiceIds.size > 1
      ? t('freight.ui.chargesInMultipleInvoices')
      : t('freight.ui.noEligibleCharges')]
    return
  }
  const ids = eligible.map(charge => String(charge.id))
  const accepted = await confirm({
    kind: 'submit',
    descriptionKey: 'freight.ui.combinedInvoiceConfirm',
    descriptionParams: {
      count: eligible.length,
      names: eligible.map(charge => String(charge.chargeNo || charge.id || '')).join(', '),
    },
  })
  if (!accepted) return
  combinedInvoiceBusy.value = true
  try {
    const invoice = await lcs.runCommand('charge.combined-invoice', ids.join(','), key =>
      lcs.charges.createCombinedInvoice(ids, key))
    toast.add({ title: t('freight.ui.draftInvoiceCreated'), color: 'success' })
    await load()
    await navigateTo(invoicePrintRoute(String(invoice.id)))
  }
  catch (error) {
    formErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
  finally {
    combinedInvoiceBusy.value = false
  }
}

const headerActions = computed(() => [
  {
    label: t('freight.ui.printInvoice'),
    icon: 'i-lucide-printer',
    disabled: charges.value.length === 0 || combinedInvoiceBusy.value,
    onClick: printCombinedInvoice,
  },
])

/**
 * The rows this save will actually write, with their position in the grid.
 *
 * A change set carries every row in display order, so validating it directly
 * would block on pre-existing rows this user never touched. Keeping the grid
 * position alongside each row means an error still addresses `feeLines.3.x`
 * and not `feeLines.0.x`.
 */
function rowsBeingSaved(change: SaveGridChange, savedById: Map<string, FreightRecord>) {
  const columns = table.value.columns
  return selectRowsBeingSaved(change, savedById, columns).map(({ row, index }) => ({
    row,
    index,
  }))
}

async function save(change: SaveGridChange): Promise<boolean> {
  if (!orderId.value) return true
  const savedById = new Map(charges.value.map(charge => [String(charge.id ?? ''), charge]))
  saving.value = true
  formErrors.value = []
  const pending = rowsBeingSaved(change, savedById)
  // Inline gate: an incomplete row is reported on its own cell and never sent.
  const failures = validateTableRows({
    table: table.value,
    rows: pending.map(entry => entry.row),
    rowIndices: pending.map(entry => entry.index),
    label: key => key,
    columnLabel: column => column.label || column.key,
  })
  if (failures.length) {
    formErrors.value = failures.map(failure => `${failure.label}: ${t(`validation.${failure.code}`, {
      field: failure.label,
      ...(failure.params || {}),
    })}`)
    saving.value = false
    return false
  }
  try {
    for (const id of change.removedIds) {
      const charge = savedById.get(id)
      if (charge && await removeCharge(charge)) continue
      // A refused delete is put back so the grid keeps matching the server.
      change.rows.push({ ...savedById.get(id) })
    }
    for (const row of change.rows) {
      const id = String(row.id ?? '')
      const saved = savedById.get(id)
      const payload = serviceChargePayload(row, currency.value)
      if (!saved) {
        // A new row is a one-line charge; the grid already holds its values.
        if (serviceChargeIsCreatable(row)) await lcs.charges.createForOrder(orderId.value, payload)
        continue
      }
      if (!isDeletableCharge(saved)) continue
      await lcs.charges.saveDraft({ ...saved, ...payload } as FreightRecord)
    }
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    await load()
    return true
  }
  catch (error) {
    formErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
    await load()
    return false
  }
  finally {
    saving.value = false
  }
}

/**
 * Write the grid's pending rows. The page header's Save changes calls this, so
 * the tab has no save button of its own; `false` stops the page save.
 */
const grid = ref<{ pendingChange: () => SaveGridChange | null } | null>(null)

async function savePending(): Promise<boolean> {
  const change = grid.value?.pendingChange()
  if (!change) return true
  return await save(change)
}

defineExpose({ savePending })

/** Returns false when the user cancels, so the grid can restore the row. */
async function removeCharge(charge: FreightRecord): Promise<boolean> {
  const accepted = await confirm({
    kind: 'delete',
    descriptionKey: 'freight.ui.delete',
    descriptionParams: { name: String(charge.chargeNo || charge.id || '') },
  })
  if (!accepted) return false
  await lcs.charges.delete([String(charge.id ?? '')])
  toast.add({ title: t('actions.delete'), color: 'success' })
  return true
}
</script>

<template>
  <div class="space-y-4">
    <CommonAppFormErrorSummary class="pt-4" :form-errors="formErrors" />

    <TableAppSaveGrid
      v-if="rows.length || editable"
      ref="grid"
      :table="table"
      :rows="rows"
      :disabled="editable !== true"
      :row-disabled="serviceChargeRowDisabled"
      :saving="saving"
      :header-actions="headerActions"
      :extra-row-menu-items="rowMenuItems"
      hide-save-actions
      @update:draft="draftRows = $event"
      @update:dirty="emit('update:dirty', $event)"
      @save="save" />

    <FreightJobEmptyState
      v-else-if="!loading"
      :title="t('freight.ui.noServiceCharges')"
      :description="t('freight.ui.addCharge')"
      icon="i-lucide-receipt-text" />

    <div
      v-if="summaryRows.length"
      class="ms-auto grid w-full max-w-sm gap-1.5 px-1 py-2 text-sm">
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.subtotal') }}</span>
        <span class="font-medium tabular-nums text-highlighted">{{ money(totals.subtotal) }}</span>
      </div>
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('freight.fields.discount') }}</span>
        <button
          type="button"
          :disabled="editable !== true"
          class="flex items-center gap-1 rounded font-medium tabular-nums text-highlighted hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
          :aria-label="t('freight.ui.lineAdditionalDetails')"
          @click="additionalOpen = true"
        >
          {{ money(totals.discount) }}
          <UIcon v-if="editable" name="i-lucide-pencil" class="size-3.5 text-muted" />
        </button>
      </div>
      <div class="flex items-center justify-between gap-4">
        <span class="text-muted">{{ t('containerPaymentTaxRate') }}</span>
        <button
          type="button"
          :disabled="editable !== true"
          class="flex items-center gap-1 rounded font-medium tabular-nums text-highlighted hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
          :aria-label="t('freight.ui.lineAdditionalDetails')"
          @click="additionalOpen = true"
        >
          {{ summaryTaxRate === null ? t('freight.ui.mixedTaxRates') : `${summaryTaxRate}%` }}
          <UIcon v-if="editable" name="i-lucide-pencil" class="size-3.5 text-muted" />
        </button>
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
    <FreightAppLineDetailsDialog
      v-model:open="additionalOpen"
      :max-discount="totals.subtotal"
      :discount="Number(props.job.discount || 0)"
      :tax-rate="Number(props.job.vatRate || 0)"
      :disabled="editable !== true"
      @save="applyAdditionalDetails" />
  </div>
</template>
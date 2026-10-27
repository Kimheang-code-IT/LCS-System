<script setup lang="ts">
/**
 * Service-order Service Charge tab. Renders through the shared `AppLineTable`
 * via `AppSaveGrid`: one row per charge, edited in place and saved as one
 * change set. Creating the order's finance invoice stays a header action
 * because it is an order-level workflow, not a row edit.
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
  serviceChargeTable,
  serviceChargeTotals,
} from '~/utils/freight/job-charges'

const props = defineProps<{
  job: FreightRecord
  jobNo: string
  editable?: boolean
}>()

const emit = defineEmits<{
  'update:job': [patch: Record<string, unknown>]
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
const totals = computed(() => serviceChargeTotals(rows.value, props.job.vatRate, props.job.discount))

function money(value: number) {
  return formatMoney(value, currency.value)
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
 * Per-row menu: open the charge document and print its invoice. Delete is added
 * by the shared table as the last menu entry, so the grid stays narrow.
 */
function rowMenuItems(row: Record<string, unknown>) {
  const id = String(row.id ?? '')
  if (!id || id.startsWith(SAVE_GRID_NEW_PREFIX)) return []
  return [
    {
      label: t('freight.ui.viewDocument'),
      icon: 'i-lucide-arrow-up-right',
      onSelect: () => { void navigateTo(`/service-charges/${id}`) },
    },
    {
      label: t('freight.ui.printInvoice'),
      icon: 'i-lucide-printer',
      onSelect: () => {
        const charge = charges.value.find(item => String(item.id ?? '') === id)
        const line = Array.isArray(charge?.feeLines) ? (charge!.feeLines as Array<Record<string, unknown>>)[0] : undefined
        void navigateTo(buildPrintRoute({
          collection: 'jobCharges',
          recordId: id,
          template: 'tax-invoice',
          returnTo: route.fullPath,
          modulePath: '/service-orders',
          lineIndex: 0,
          lineId: line?.id ? String(line.id) : undefined,
        }))
      },
    },
  ]
}

/** Combined statement for every charge of this order (read-only). */
function printAllCharges() {
  const first = charges.value[0]
  if (!first?.id) return
  void navigateTo(buildPrintRoute({
    collection: 'jobCharges',
    recordId: String(first.id),
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/service-orders',
    statementOrderId: orderId.value,
  }))
}

const printAllActions = computed(() => [{
  label: t('freight.ui.printAll'),
  icon: 'i-lucide-printer',
  disabled: charges.value.length === 0,
  onClick: printAllCharges,
}])

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

async function save(change: SaveGridChange) {
  if (!orderId.value) return
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
    return
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
  }
  catch (error) {
    formErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
    await load()
  }
  finally {
    saving.value = false
  }
}

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
      :table="table"
      :rows="rows"
      :disabled="editable !== true"
      :saving="saving"
      :header-actions="printAllActions"
      :extra-row-menu-items="rowMenuItems"
      @save="save" />

    <FreightJobEmptyState
      v-else-if="!loading"
      :title="t('freight.ui.noServiceCharges')"
      :description="t('freight.ui.addCharge')"
      icon="i-lucide-receipt-text" />

    <div
      v-if="rows.length"
      class="ms-auto grid w-full max-w-sm gap-1.5 px-1 py-2 text-sm">
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
          :disabled="editable !== true"
          size="md"
          class="w-40 text-right"
          :aria-label="t('freight.fields.discount')"
          @update:model-value="value => emit('update:job', { discount: value ?? 0 })" />
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
            :disabled="editable !== true"
            size="md"
            class="w-full text-right"
            :aria-label="t('containerPaymentTaxRate')"
            @update:model-value="value => emit('update:job', { vatRate: value ?? 0 })" />
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
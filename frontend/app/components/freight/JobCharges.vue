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
import { SAVE_GRID_NEW_PREFIX } from '~/types/save-grid'
import {
  isDeletableCharge,
  serviceChargeIsCreatable,
  serviceChargePayload,
  serviceChargeRows,
  serviceChargeTable,
} from '~/utils/freight/job-charges'

const props = defineProps<{
  job: FreightRecord
  jobNo: string
  editable?: boolean
}>()

const { t } = useI18n()
const toast = useToast()
const lcs = useLcs()
const route = useRoute()
const { confirm } = useConfirm()

const charges = ref<FreightRecord[]>([])
const invoice = ref<FreightRecord | null>(null)
const loading = ref(false)
const saving = ref(false)

const orderId = computed(() => String(props.job.id || props.jobNo || ''))
const currency = computed(() => String(props.job.currency || ''))
const rows = computed(() => serviceChargeRows(charges.value))
const table = computed(() => serviceChargeTable())
const canCreateInvoice = computed(() => props.editable === true && rows.value.length > 0 && !invoice.value)

const headerActions = computed(() => (props.editable !== true
  ? []
  : [{
      label: t('freight.ui.createFinanceInvoice'),
      icon: 'i-lucide-file-plus',
      disabled: saving.value || !canCreateInvoice.value,
      onClick: () => { void createInvoice() },
    }]))

async function load() {
  if (!orderId.value) return
  loading.value = true
  try {
    charges.value = await lcs.charges.listForOrder(orderId.value)
    invoice.value = await lcs.charges.getOrderInvoice(orderId.value)
  }
  catch {
    charges.value = []
    invoice.value = null
  }
  finally {
    loading.value = false
  }
}

watch(() => props.jobNo, () => { void load() }, { immediate: true })

/** Per-row print icon. Hidden for rows that are still being composed locally. */
function rowAction(action: string, row: Record<string, unknown>) {
  if (action !== 'print') return null
  const id = String(row.id ?? '')
  if (!id || id.startsWith(SAVE_GRID_NEW_PREFIX)) return null
  return {
    label: t('freight.ui.printInvoice'),
    icon: 'i-lucide-printer',
    color: 'primary' as const,
    onSelect: () => { void navigateTo(buildPrintRoute({
      collection: 'jobCharges',
      recordId: id,
      template: 'tax-invoice',
      returnTo: route.fullPath,
      modulePath: '/service-orders',
    })) },
  }
}

async function save(change: SaveGridChange) {
  if (!orderId.value) return
  const savedById = new Map(charges.value.map(charge => [String(charge.id ?? ''), charge]))
  saving.value = true
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
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
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
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-end gap-2">
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

    <TableAppSaveGrid
      v-if="rows.length || editable"
      :table="table"
      :rows="rows"
      :disabled="editable !== true"
      :saving="saving"
      :header-actions="headerActions"
      :row-actions="rowAction"
      @save="save" />

    <FreightJobEmptyState
      v-else-if="!loading"
      :title="t('freight.ui.noServiceCharges')"
      :description="t('freight.ui.addCharge')"
      icon="i-lucide-receipt-text" />
  </div>
</template>
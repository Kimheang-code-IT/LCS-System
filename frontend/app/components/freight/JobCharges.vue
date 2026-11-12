<script setup lang="ts">
/**
 * Service Order's Service Charge tab.
 *
 * The tab is an adapter around the *same* Service Charge form the standalone
 * module uses (`ServiceChargeForm` → `DocumentAppForm` + the `jobCharges`
 * module config): the same fields, fee lines, validation, discount/tax rules
 * and totals. This component only supplies the Service Order context, the
 * linked-charge list, its own save boundary and a per-order draft.
 */
import type { FreightRecord } from '~/types/record'
import { useLcs } from '~/composables/freight/useLcs'
import {
  clearRecordDraft,
  readRecordDraft,
  readRecordDraftsByPrefix,
  recordDraftKey,
  sanitizeDraftModel,
} from '~/composables/common/useRecordDraft'
import { useRecordFormDraft } from '~/composables/common/useRecordFormDraft'
import { apiErrorMessage } from '~/utils/validation/api-error'
import { isDeletableCharge } from '~/utils/freight/job-charges'
import {
  SERVICE_CHARGE_DRAFT_COLLECTION,
  emptyLinkedServiceCharge,
  serviceChargeDraftRecordId,
  serviceChargeFormPayload,
} from '~/utils/freight/service-charge-form'

const props = defineProps<{
  job: FreightRecord
  jobNo: string
  editable?: boolean
}>()

const emit = defineEmits<{
  'update:dirty': [dirty: boolean]
  'update:charges': [charges: FreightRecord[]]
  'saved': [charge: FreightRecord]
}>()

const { t } = useI18n()
const toast = useToast()
const lcs = useLcs()
const auth = useAuthStore()

const charges = ref<FreightRecord[]>([])
const selectedId = ref('')
const model = ref<FreightRecord | null>(null)
const loading = ref(false)
const saving = ref(false)
const formErrors = ref<string[]>([])
const loadFailed = ref(false)
const form = ref<{
  validate: () => boolean
  payload: () => FreightRecord
  applyServerError: (error: unknown) => void
  resetErrors: () => void
} | null>(null)

const orderId = computed(() => String(props.job.id || props.jobNo || ''))
const savedSnapshot = ref('')
const draftBase = ref('')
const status = computed(() => String(model.value?.status || 'Draft'))
const isInternal = computed(() => String(model.value?.chargeSide || '').toUpperCase() === 'INTERNAL')
const canCreate = computed(() => props.editable === true && lcs.can('service_charge.create'))
const canUpdate = computed(() => props.editable === true && lcs.can('service_charge.update'))
const canEditCurrent = computed(() => {
  const record = model.value
  if (!record || status.value.toLowerCase() !== 'draft') return false
  return record.id
    ? canUpdate.value && isDeletableCharge(record)
    : canCreate.value
})
const dirty = computed(() => Boolean(model.value)
  && JSON.stringify(sanitizeDraftModel(model.value)) !== savedSnapshot.value)

const userScope = computed(() => String(auth.user?.id || auth.user?.email || 'anon'))

/**
 * Saved linked charges plus the selected charge's unsaved total. The Finance
 * tab consumes this projection, so its preview follows fee-line/discount/tax
 * edits without duplicating the charge calculation there.
 */
const summaryCharges = computed<FreightRecord[]>(() => {
  const rows = charges.value.map(charge => ({
    id: String(charge.id || ''),
    clientRowId: String(charge.clientRowId || ''),
    status: charge.status,
    chargeSide: charge.chargeSide || 'CUSTOMER',
    currency: charge.currency,
    total: charge.total,
    costTotal: charge.costTotal,
    supplierPartyId: charge.supplierPartyId,
    financialDocumentId: charge.financialDocumentId,
    supplierDocumentId: charge.supplierDocumentId,
  }))
  const current = model.value
  if (!current) return rows
  const preview = {
    id: String(current.id || ''),
    clientRowId: String(current.clientRowId || ''),
    status: current.status,
    chargeSide: current.chargeSide || 'CUSTOMER',
    currency: current.currency,
    total: Number(serviceChargeFormPayload(current).total || 0),
    costTotal: Number(
      (Array.isArray(current.feeLines) ? current.feeLines as Array<Record<string, unknown>> : [])
        .reduce((sum, line) => sum + Number(line.costAmount ?? (Number(line.quantity || 0) * Number(line.costUnitPrice || 0))), 0)
        .toFixed(2),
    ),
    supplierPartyId: current.supplierPartyId,
    financialDocumentId: current.financialDocumentId,
    supplierDocumentId: current.supplierDocumentId,
  }
  const index = rows.findIndex(row =>
    (preview.id && row.id === preview.id)
    || (preview.clientRowId && row.clientRowId === preview.clientRowId),
  )
  if (index >= 0) {
    rows[index] = preview
    return rows
  }
  // An unsaved new charge still contributes to the preview total.
  return dirty.value ? [...rows, preview] : rows
})

watch(summaryCharges, value => emit('update:charges', value), { immediate: true, deep: true })

function draftRecordId(record: FreightRecord): string {
  // A charge carries its own order link, so a draft flushed while the page is
  // moving to another order is still filed under the order it belongs to.
  return serviceChargeDraftRecordId(String(record.serviceOrderId || orderId.value), record)
}

function snapshot(record: FreightRecord) {
  return JSON.stringify(sanitizeDraftModel(record))
}

const draftable = computed(() => Boolean(model.value) && status.value.toLowerCase() === 'draft')

/** Per user/order/charge draft; a new charge keys on its stable client marker. */
const formDraft = useRecordFormDraft<FreightRecord>({
  collection: () => SERVICE_CHARGE_DRAFT_COLLECTION,
  scope: () => userScope.value,
  recordId: () => model.value ? draftRecordId(model.value) : '',
  baseUpdatedAt: () => draftBase.value,
  model: () => model.value ?? { id: '' },
  apply: (stored) => { model.value = { ...(model.value ?? {}), ...stored } as FreightRecord },
  isDirty: () => dirty.value,
  canDraft: () => draftable.value,
  suspend: () => saving.value,
})

async function loadCharges(soft = false) {
  if (!orderId.value) return
  if (!soft) {
    loading.value = true
    loadFailed.value = false
  }
  try {
    charges.value = await lcs.charges.listForOrder(orderId.value)
  }
  catch (error) {
    if (soft) return
    formErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
    // Do not offer "Add charge" against an unknown list: that could create a
    // duplicate. The retry re-reads the order's charges first.
    loadFailed.value = true
    charges.value = []
  }
  finally {
    if (!soft) loading.value = false
  }
}

/** Select a saved charge and restore its compatible draft, if any. */
function selectCharge(charge: FreightRecord | null) {
  // Keep the row that is leaving the form, not just the one arriving.
  formDraft.flush()
  formErrors.value = []
  selectedId.value = charge ? String(charge.id) : ''
  if (!charge) {
    model.value = null
    savedSnapshot.value = ''
    draftBase.value = ''
    formDraft.bind()
    emit('update:dirty', false)
    return
  }
  model.value = { ...charge }
  savedSnapshot.value = snapshot(charge)
  draftBase.value = String(charge.updatedAt || '')
  formDraft.bind()
  if (draftable.value) formDraft.restore()
  else formDraft.clear()
  emit('update:dirty', dirty.value)
}

async function load() {
  const target = orderId.value
  // Flush the previous order's draft and drop its rows before the new list
  // arrives, so the Finance summary never shows the old order's charges.
  selectCharge(null)
  charges.value = []
  await loadCharges()
  if (orderId.value !== target) return
  if (!charges.value.length && canCreate.value) {
    const prefix = recordDraftKey(
      userScope.value,
      SERVICE_CHARGE_DRAFT_COLLECTION,
      `${orderId.value}:new:`,
    )
    const latest = readRecordDraftsByPrefix(prefix, 'local')[0]
    if (latest) {
      restoreNewDraft(latest.draft.model)
      return
    }
    // Backward compatibility: earlier builds kept one `:new` slot per order.
    const legacy = readRecordDraft(
      recordDraftKey(userScope.value, SERVICE_CHARGE_DRAFT_COLLECTION, `${orderId.value}:new`),
      'local',
    )
    if (legacy) {
      restoreNewDraft(legacy.model)
      return
    }
  }
  selectCharge(charges.value[0] || null)
}

watch(orderId, load, { immediate: true })

/** Rebuild the unsaved new charge stored under one of the order's new slots. */
function restoreNewDraft(stored: Record<string, unknown>) {
  const side = String(stored.chargeSide || '').toUpperCase() === 'INTERNAL' ? 'INTERNAL' : 'CUSTOMER'
  const empty = emptyLinkedServiceCharge(props.job as Record<string, unknown>, {
    chargeSide: side,
    clientRowId: String(stored.clientRowId || ''),
  })
  selectedId.value = ''
  model.value = { ...empty, ...stored } as FreightRecord
  savedSnapshot.value = snapshot(empty)
  draftBase.value = ''
  formDraft.bind()
  emit('update:dirty', dirty.value)
}

function startNew(side: 'CUSTOMER' | 'INTERNAL' = 'CUSTOMER') {
  if (!canCreate.value) return
  formDraft.flush()
  formErrors.value = []
  const empty = emptyLinkedServiceCharge(props.job as Record<string, unknown>, { chargeSide: side })
  selectedId.value = ''
  model.value = empty
  savedSnapshot.value = snapshot(empty)
  draftBase.value = ''
  formDraft.bind()
  formDraft.restore()
  emit('update:dirty', dirty.value)
}

watch(model, () => {
  emit('update:dirty', dirty.value)
  if (dirty.value) formDraft.schedule()
  // A reverted edit must not leave a stale local copy behind.
  else formDraft.flush()
}, { deep: true })

async function save() {
  const record = model.value
  if (!record || saving.value || !canEditCurrent.value) return
  if (!form.value?.validate()) return
  const targetOrder = orderId.value
  const targetId = String(record.id || '')
  const marker = String(record.clientRowId || '')
  saving.value = true
  formErrors.value = []
  try {
    const payload = form.value.payload()
    let saved: FreightRecord
    if (!targetId) {
      // A lost response may already have created this row: adopt it by its
      // stable marker instead of creating the same charge twice.
      const existing = charges.value.find(charge => marker && String(charge.clientRowId || '') === marker)
      saved = existing
        ? await lcs.charges.saveDraft({ ...existing, ...payload } as FreightRecord)
        : await lcs.charges.createForOrder(targetOrder, payload)
    }
    else {
      saved = await lcs.charges.saveDraft({ ...record, ...payload } as FreightRecord)
    }
    // The saved copy is authoritative: clear its draft (and the pre-create slot)
    // even if the operator moved to another order while the request was open.
    const scope = String(saved.serviceOrderId || targetOrder)
    clearRecordDraft(
      recordDraftKey(userScope.value, SERVICE_CHARGE_DRAFT_COLLECTION, serviceChargeDraftRecordId(scope, saved)),
      'local',
    )
    if (!targetId) {
      clearRecordDraft(recordDraftKey(userScope.value, SERVICE_CHARGE_DRAFT_COLLECTION, `${scope}:new`), 'local')
    }
    if (orderId.value !== targetOrder) return
    selectedId.value = String(saved.id || '')
    model.value = saved
    savedSnapshot.value = snapshot(saved)
    draftBase.value = String(saved.updatedAt || '')
    // Clears the saved slot and the pre-create slot the form was bound to.
    formDraft.clear()
    await loadCharges(true)
    // Refresh the summaries that read the shared store (Finance/register); a
    // failed refresh must not turn a confirmed save into a failed one.
    try {
      await useFreightStore().ensure('jobCharges', true)
    }
    catch { /* the next navigation reloads it */ }
    emit('saved', saved)
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch (error) {
    // The shared form renders field and form-level messages itself; the working
    // rows and the local draft are left exactly as the operator typed them.
    form.value?.applyServerError(error)
  }
  finally {
    saving.value = false
  }
}

defineExpose({ flushDraft: formDraft.flush, save })
</script>

<template>
  <div class="space-y-4">
    <CommonAppFormErrorSummary class="pt-4" :form-errors="formErrors" />

    <CommonAppDraftConflictAlert
      v-if="formDraft.conflict.value"
      :saved-at="formDraft.conflict.value.savedAt"
      @restore="formDraft.restoreConflict()"
      @discard="formDraft.discardConflict()" />

    <div v-if="loading" class="flex items-center gap-2 py-6 text-sm text-muted">
      <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" />
      {{ t('freight.ui.loadingData') }}
    </div>

    <template v-else>
      <UButton
        v-if="loadFailed"
        size="sm"
        color="neutral"
        variant="soft"
        icon="i-lucide-refresh-cw"
        :label="t('lcs.common.retry')"
        @click="load" />
      <div v-if="!loadFailed && (charges.length || model || canCreate)" class="flex flex-wrap items-end gap-2">
        <UFormField v-if="charges.length" :label="t('freight.pages.serviceCharges')" class="min-w-64 flex-1">
          <USelect
            :model-value="selectedId"
            :items="charges.map(charge => ({
              label: [
                String(charge.chargeNo || charge.id || ''),
                String(charge.chargeSide || 'CUSTOMER').toUpperCase() === 'INTERNAL'
                  ? t('freight.ui.internalCharge')
                  : t('freight.ui.customerCharge'),
                String(charge.total ?? ''),
              ].filter(Boolean).join(' · '),
              value: String(charge.id),
            }))"
            :placeholder="t('freight.ui.noServiceCharges')"
            value-key="value"
            class="w-full"
            @update:model-value="(value: unknown) => selectCharge(charges.find(charge => String(charge.id) === String(value)) || null)" />
        </UFormField>
        <UButton
          v-if="canCreate"
          icon="i-lucide-plus"
          color="neutral"
          variant="outline"
          :label="t('freight.ui.addCharge')"
          :disabled="saving"
          @click="startNew('CUSTOMER')" />
        <UButton
          v-if="canCreate"
          icon="i-lucide-receipt"
          color="neutral"
          variant="outline"
          :label="t('freight.ui.addInternalCharge')"
          :disabled="saving"
          @click="startNew('INTERNAL')" />
        <UButton
          v-if="model"
          icon="i-lucide-save"
          color="primary"
          :label="model.id ? t('freight.ui.saveChanges') : t('freight.ui.saveCharge')"
          :loading="saving"
          :disabled="!canEditCurrent || !dirty"
          @click="save" />
      </div>

      <div v-if="model" class="space-y-2">
        <FreightJobSectionHeader
          :title="`${t('freight.pages.serviceCharges')} — ${t('freight.tables.feeLines')}`" />
        <FreightServiceChargeForm
          ref="form"
          :model="model"
          fee-lines-only
          :internal="isInternal"
          :read-only="!canEditCurrent || saving"
          wide
          @update:model="model = $event" />
      </div>

      <FreightJobEmptyState
        v-else-if="!loadFailed"
        :title="t('freight.ui.noServiceCharges')"
        :description="t('freight.ui.addCharge')"
        icon="i-lucide-receipt-text" />
    </template>
  </div>
</template>

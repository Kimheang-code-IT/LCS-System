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
import { recalculateFreightRecord } from '~/utils/freight/document-calculations'
import { createClientId } from '~/utils/client-id'
import {
  SERVICE_CHARGE_DRAFT_COLLECTION,
  emptyLinkedServiceCharge,
  serviceChargeDraftRecordId,
  serviceChargeModule,
} from '~/utils/freight/service-charge-form'

const props = defineProps<{
  job: FreightRecord
  jobNo: string
  editable?: boolean
}>()

const emit = defineEmits<{
  'update:dirty': [dirty: boolean]
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

/**
 * "Add Fee Line": the tab's one add action. With no charge yet it initializes
 * the linked charge (which seeds one blank line); otherwise it appends a blank
 * editable row to the active draft charge and recalculates its totals. A
 * posted charge is never touched.
 */
function addFeeLine() {
  if (!model.value) {
    startNew('CUSTOMER')
    return
  }
  if (!canEditCurrent.value) return
  const lines = Array.isArray(model.value.feeLines)
    ? [...(model.value.feeLines as Array<Record<string, unknown>>)]
    : []
  lines.push({ clientRowId: createClientId('feeLine'), feeType: '', description: '', quantity: 1, unitAmount: 0 })
  model.value = recalculateFreightRecord(serviceChargeModule(), { ...model.value, feeLines: lines })
}

const canAddFeeLine = computed(() => (model.value ? canEditCurrent.value : canCreate.value))

watch(model, () => {
  emit('update:dirty', dirty.value)
  if (dirty.value) formDraft.schedule()
  // A reverted edit must not leave a stale local copy behind.
  else formDraft.flush()
}, { deep: true })

async function save() {
  const record = model.value
  if (!record || !dirty.value) return true
  if (saving.value || !canEditCurrent.value) return false
  if (!form.value?.validate()) return false
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
    return true
  }
  catch (error) {
    // The shared form renders field and form-level messages itself; the working
    // rows and the local draft are left exactly as the operator typed them.
    form.value?.applyServerError(error)
    return false
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
      <!-- One heading line: the tab title and its single add action. -->
      <div v-if="!loadFailed" class="flex items-center justify-between gap-2">
        <FreightJobSectionHeader :title="t('freight.pages.serviceCharges')" />
        <UButton
          v-if="canAddFeeLine"
          icon="i-lucide-plus"
          color="neutral"
          variant="soft"
          :label="t('freight.ui.addFeeLine')"
          :disabled="saving"
          @click="addFeeLine" />
      </div>
      <!-- Several charges (customer + internal) stay distinct: compact chips,
           no dropdown. Each keeps its own party, currency and totals. -->
      <div v-if="!loadFailed && charges.length > 1" class="flex flex-wrap items-center gap-1.5">
        <UButton
          v-for="charge in charges"
          :key="String(charge.id)"
          size="xs"
          :color="String(charge.id) === selectedId ? 'primary' : 'neutral'"
          :variant="String(charge.id) === selectedId ? 'soft' : 'outline'"
          :label="[
            String(charge.chargeNo || charge.id || ''),
            String(charge.chargeSide || 'CUSTOMER').toUpperCase() === 'INTERNAL'
              ? t('freight.ui.internalCharge')
              : t('freight.ui.customerCharge'),
          ].filter(Boolean).join(' · ')"
          :disabled="saving"
          @click="selectCharge(charge)" />
      </div>

      <div v-if="model" class="space-y-2">
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
        :description="canCreate ? t('freight.ui.addFeeLine') : ''"
        icon="i-lucide-receipt-text" />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import type { FreightTable } from '~/config/freight-modules'
import { JOB_FINANCE_LINES_TABLE } from '~/config/job-workspace-forms'
import { formatMoney } from '~/composables/freight/useFreight'
import { useLcs } from '~/composables/freight/useLcs'
import { useConfirm } from '~/composables/common/useConfirm'
import { getFreightModule } from '~/config/freight-modules'
import { useModuleRepository } from '~/repositories'
import { codeTitle } from '~/utils/freight/format'
import { FINANCE_ENTRY_BEHAVIORS } from '~/utils/constants/document-types'

const props = withDefaults(defineProps<{
  job: FreightRecord
  jobNo: string
  customer: string
  documents: FreightRecord[]
  supplierCosts?: FreightRecord[]
  receivables?: FreightRecord[]
  editable?: boolean
}>(), {
  editable: false,
  supplierCosts: () => [],
  receivables: () => [],
})

const { t } = useI18n()
const toast = useToast()
const store = useFreightStore()
const lcs = useLcs()
const { confirm } = useConfirm()

const settlementTypes = new Set(['CUSTOMER_RECEIPT', 'SUPPLIER_PAYMENT'])

/** Active Document Types the Service Order Finance tab may create. */
const entryTypes = computed(() => store.list('documentTypes')
  .filter((row) => {
    if (String(row.status || 'ACTIVE').toUpperCase() !== 'ACTIVE') return false
    const available = Array.isArray(row.availableIn) ? row.availableIn as string[] : []
    if (!available.includes('service_order_finance')) return false
    return FINANCE_ENTRY_BEHAVIORS.has(String(row.accountingBehavior || '').toUpperCase())
  }))

const typeItems = computed(() => [...entryTypes.value]
  .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
  .map(row => ({ label: String(row.name || row.code || ''), value: String(row.code) })))

const typeLabel = (document: FreightRecord) => {
  const name = String(document.documentTypeName || '').trim()
  if (name) return name
  return codeTitle(document.documentType)
}

const canCreate = computed(() => props.editable && lcs.can('financial_document.create'))
const canEdit = computed(() => lcs.can('financial_document.update_draft'))
const canPost = computed(() => lcs.can('financial_document.post'))
const canReverse = computed(() => lcs.can('financial_document.reverse'))
const canDelete = computed(() => lcs.can('financial_document.delete'))
const canAllocate = computed(() => lcs.can('financial_document.allocate'))

function isLinkedToJob(row: FreightRecord) {
  const orderId = String(props.job.id || '').trim()
  if (orderId && row.serviceOrderId != null) return String(row.serviceOrderId) === orderId
  return Boolean(props.jobNo) && String(row.jobNo || '') === props.jobNo
}

const rows = computed(() => props.documents
  .filter(isLinkedToJob)
  .map(document => ({
    id: String(document.id || ''),
    _documentId: String(document.id || ''),
    _source: document,
    type: typeLabel(document),
    date: String(document.date || document.documentDate || ''),
    description: String(document.description || document.remark || document.documentNo || ''),
    party: String(document.customer || ''),
    amount: Number(document.total ?? 0),
    status: codeTitle(document.status),
    currency: String(document.currency || ''),
  })))

const table = computed<FreightTable>(() => ({
  ...JOB_FINANCE_LINES_TABLE,
  hideAddRow: true,
}))

function isDraft(document?: FreightRecord) {
  return String(document?.status || '').toUpperCase() === 'DRAFT'
}

function isPosted(document?: FreightRecord) {
  return String(document?.status || '').toUpperCase() === 'POSTED'
}

function rowMenuItems(row: Record<string, unknown>) {
  const document = row._source as FreightRecord | undefined
  const id = String(row._documentId || '')
  if (!document || !id) return []
  const items: Array<{ label: string, icon: string, color?: 'error', onSelect: () => void }> = [{
    label: t('freight.ui.viewDocument'),
    icon: 'i-lucide-eye',
    onSelect: () => { void navigateTo(`/finance/documents/${id}`) },
  }]
  if (isDraft(document) && canEdit.value) {
    items.push({ label: t('freight.ui.edit'), icon: 'i-lucide-pencil', onSelect: () => openEdit(document) })
  }
  if (isDraft(document) && canPost.value) {
    items.push({ label: t('freight.ui.post'), icon: 'i-lucide-check-circle', onSelect: () => { void postDocument(id) } })
  }
  if (isPosted(document) && canReverse.value) {
    items.push({ label: t('freight.ui.reverse'), icon: 'i-lucide-undo-2', onSelect: () => { void reverseDocument(id) } })
  }
  if (isPosted(document) && canAllocate.value && settlementTypes.has(String(document.documentType || '').toUpperCase())) {
    items.push({ label: t('freight.ui.allocate'), icon: 'i-lucide-link', onSelect: () => openAllocation(document) })
  }
  if (isDraft(document) && canDelete.value) {
    items.push({ label: t('freight.ui.delete'), icon: 'i-lucide-trash-2', color: 'error', onSelect: () => { void deleteDocument(id) } })
  }
  return items
}

const dialogOpen = ref(false)
const saving = ref(false)
const dialogError = ref('')
const actionError = ref('')
const fieldErrors = ref<Record<string, string>>({})
const editingId = ref('')

type EntryDraft = {
  documentType: string
  date: string
  description: string
  partyId: string
  amount: number | null
  currency: string
  feeTypeId: string
  financialAccountId: string
  relatedDocumentId: string
  referenceNumber: string
  remark: string
}

const draft = ref<EntryDraft>(blankDraft())

function blankDraft(): EntryDraft {
  return {
    documentType: entryTypes.value[0]?.code ? String(entryTypes.value[0]!.code) : '',
    date: new Date().toISOString().slice(0, 10),
    description: '',
    partyId: '',
    amount: null,
    currency: String(props.job.currency || '') || 'USD',
    feeTypeId: '',
    financialAccountId: '',
    relatedDocumentId: '',
    referenceNumber: '',
    remark: '',
  }
}

const partyItems = computed(() => store.list('businessParties')
  .filter(row => String(row.status || 'ACTIVE').toUpperCase() === 'ACTIVE')
  .map(row => ({ label: String(row.legalName || row.displayName || ''), value: String(row.id) })))

const currencyItems = computed(() => store.list('currencies')
  .filter(row => String(row.status || 'ACTIVE').toUpperCase() === 'ACTIVE')
  .map(row => ({ label: `${row.code}`, value: String(row.code) })))

const feeTypeItems = computed(() => store.list('feeTypes')
  .filter(row => String(row.status || 'ACTIVE').toUpperCase() === 'ACTIVE')
  .map(row => ({ label: String(row.name || row.code || ''), value: String(row.id) })))

const accountItems = computed(() => store.list('financialAccounts')
  .filter(row => String(row.status || 'ACTIVE').toUpperCase() === 'ACTIVE')
  .map(row => ({ label: String(row.accountName || ''), value: String(row.id) })))

const activeRules = computed(() => store.list('postingRules')
  .filter(row => String(row.status || 'ACTIVE').toUpperCase() === 'ACTIVE'))

const selectedTypeRecord = computed(() => entryTypes.value
  .find(row => String(row.code || '') === draft.value.documentType) || null)
const selectedBehavior = computed(() =>
  String(selectedTypeRecord.value?.accountingBehavior || draft.value.documentType || '').toUpperCase())
const needsSettlement = computed(() => settlementTypes.has(selectedBehavior.value))
const missingRule = computed(() => {
  if (!selectedBehavior.value) return false
  return !activeRules.value.some((rule) => {
    if (String(rule.documentType || '').toUpperCase() !== selectedBehavior.value) return false
    const ruleFee = String(rule.feeTypeId || '').trim()
    return !ruleFee || !draft.value.feeTypeId || ruleFee === String(draft.value.feeTypeId)
  })
})

function openCreate() {
  editingId.value = ''
  draft.value = blankDraft()
  fieldErrors.value = {}
  dialogError.value = ''
  dialogOpen.value = true
}

function openEdit(document: FreightRecord) {
  const lines = Array.isArray(document.lines) ? document.lines as Array<Record<string, unknown>> : []
  editingId.value = String(document.id || '')
  draft.value = {
    documentType: String(document.documentTypeCode || document.documentType || '').toUpperCase(),
    date: String(document.documentDate || document.date || '').slice(0, 10),
    description: String(document.description || lines[0]?.description || ''),
    partyId: String(document.partyId || ''),
    amount: Number(lines[0]?.unitAmount ?? lines[0]?.unitPrice ?? document.total ?? 0),
    currency: String(document.currency || 'USD'),
    feeTypeId: String(lines[0]?.feeTypeId || ''),
    financialAccountId: String(document.financialAccountId || ''),
    relatedDocumentId: '',
    referenceNumber: String(document.referenceNumber || document.referenceNo || ''),
    remark: String(document.remark || ''),
  }
  fieldErrors.value = {}
  dialogError.value = ''
  dialogOpen.value = true
}

function validateDraft() {
  const errors: Record<string, string> = {}
  if (!draft.value.documentType) errors.documentType = t('validation.required', { field: t('freight.ui.cols.type') })
  if (!draft.value.date) errors.date = t('validation.required', { field: t('freight.ui.cols.date') })
  if (!draft.value.description.trim()) errors.description = t('validation.required', { field: t('freight.ui.cols.description') })
  if (!draft.value.partyId) errors.partyId = t('validation.required', { field: t('freight.fields.businessParty') })
  if (!draft.value.currency) errors.currency = t('validation.required', { field: t('freight.ui.cols.currency') })
  const amount = Number(draft.value.amount)
  if (!Number.isFinite(amount) || amount <= 0) errors.amount = t('validation.positive', { field: t('freight.ui.cols.amount') })
  if (needsSettlement.value && !draft.value.financialAccountId) {
    errors.financialAccountId = t('validation.required', { field: t('freight.fields.financialAccount') })
  }
  fieldErrors.value = errors
  return !Object.keys(errors).length
}

async function saveEntry() {
  if (!validateDraft() || saving.value) return
  saving.value = true
  dialogError.value = ''
  try {
    const amount = Number(draft.value.amount)
    const line = {
      description: draft.value.description,
      quantity: 1,
      unitPrice: amount,
      feeTypeId: draft.value.feeTypeId || undefined,
    }
    if (editingId.value) {
      const source = rows.value.find(row => row.id === editingId.value)?._source
      await lcs.finance.saveDraft({
        ...(source || {}),
        id: editingId.value,
        date: draft.value.date,
        documentDate: draft.value.date,
        description: draft.value.description,
        partyId: draft.value.partyId,
        currency: draft.value.currency,
        referenceNumber: draft.value.referenceNumber,
        remark: draft.value.remark,
        lines: [line],
      })
    }
    else {
      await lcs.finance.createDocument({
        documentType: draft.value.documentType,
        documentTypeId: selectedTypeRecord.value?.id ? String(selectedTypeRecord.value.id) : undefined,
        date: draft.value.date,
        documentDate: draft.value.date,
        description: draft.value.description,
        partyId: draft.value.partyId,
        serviceOrderId: String(props.job.id || ''),
        currency: draft.value.currency,
        referenceNumber: draft.value.referenceNumber,
        remark: draft.value.remark,
        financialAccountId: needsSettlement.value ? draft.value.financialAccountId : undefined,
        lines: [line],
      })
    }
    store.reload()
    toast.add({ title: t('lcs.common.saved'), color: 'success' })
    dialogOpen.value = false
  }
  catch (error) {
    dialogError.value = lcs.errorMessage(error)
  }
  finally {
    saving.value = false
  }
}

const allocOpen = ref(false)
const allocSaving = ref(false)
const allocError = ref('')
const allocSource = ref<FreightRecord | null>(null)
const allocTargetId = ref('')
const allocAmount = ref<number | null>(null)

const allocTargets = computed(() => {
  const source = allocSource.value
  if (!source) return []
  const targetType = String(source.documentType || '').toUpperCase() === 'CUSTOMER_RECEIPT'
    ? 'CUSTOMER_INVOICE'
    : 'SUPPLIER_BILL'
  return store.list('debitNotes')
    .filter((row) => {
      if (String(row.documentType || '').toUpperCase() !== targetType) return false
      if (String(row.status || '').toUpperCase() !== 'POSTED') return false
      if (Number(row.outstanding ?? 0) <= 0) return false
      return String(row.partyId || '') === String(source.partyId || '')
    })
    .map(row => ({
      label: `${row.documentNo} · ${formatMoney(Number(row.outstanding ?? 0), String(row.currency || ''))}`,
      value: String(row.id),
    }))
})

function openAllocation(document: FreightRecord) {
  allocSource.value = document
  allocTargetId.value = ''
  allocAmount.value = Number(document.outstanding ?? 0) || null
  allocError.value = ''
  allocOpen.value = true
}

async function saveAllocation() {
  const source = allocSource.value
  const amount = Number(allocAmount.value)
  if (!source || !allocTargetId.value || !Number.isFinite(amount) || amount <= 0) {
    allocError.value = t('validation.positive', { field: t('freight.ui.cols.amount') })
    return
  }
  allocSaving.value = true
  allocError.value = ''
  try {
    const id = String(source.id)
    await lcs.runCommand('finance-allocate', `${id}-${allocTargetId.value}`, key =>
      lcs.finance.allocate(id, allocTargetId.value, amount, key))
    toast.add({ title: t('freight.ui.allocate'), color: 'success' })
    allocOpen.value = false
  }
  catch (error) {
    allocError.value = lcs.errorMessage(error)
  }
  finally {
    allocSaving.value = false
  }
}

async function postDocument(id: string) {
  try {
    await lcs.runCommand('finance-post', id, key => lcs.finance.post(id, key))
    actionError.value = ''
    toast.add({ title: t('freight.ui.post'), color: 'success' })
  }
  catch (error) {
    actionError.value = lcs.errorMessage(error)
  }
}

async function reverseDocument(id: string) {
  const accepted = await confirm({ kind: 'update', descriptionKey: 'lcs.finance.reverseReason' })
  if (!accepted) return
  try {
    await lcs.runCommand('finance-reverse', id, key => lcs.finance.reverse(id, 'Reversal from the service order finance tab.', key))
    actionError.value = ''
    toast.add({ title: t('freight.ui.reverse'), color: 'success' })
  }
  catch (error) {
    actionError.value = lcs.errorMessage(error)
  }
}

async function deleteDocument(id: string) {
  const accepted = await confirm({ kind: 'delete', count: 1 })
  if (!accepted) return
  try {
    const module = getFreightModule('/finance/documents')
    if (!module) return
    await useModuleRepository(module).remove([id])
    store.reload()
    actionError.value = ''
    toast.add({ title: t('actions.delete'), color: 'success' })
  }
  catch (error) {
    actionError.value = lcs.errorMessage(error)
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <FreightJobSectionHeader :title="t('freight.jobSections.finance')" />
      <UButton
        v-if="canCreate"
        icon="i-lucide-plus"
        color="neutral"
        variant="soft"
        :label="t('freight.ui.addEntry')"
        @click="openCreate" />
    </div>

    <CommonAppFormErrorSummary v-if="actionError" :form-errors="[actionError]" />

    <FreightAppLineTable
      v-if="rows.length"
      :table="table"
      :model-value="rows"
      disabled
      :extra-row-menu-items="rowMenuItems" />

    <FreightJobEmptyState
      v-else
      :title="t('freight.ui.noFinanceEntries')"
      :description="t('freight.ui.addEntry')"
      icon="i-lucide-banknote" />

    <CommonAppEntityDialog
      v-model:open="dialogOpen"
      :title="editingId ? t('freight.ui.edit') : t('freight.ui.addEntry')"
      :saving="saving"
      :confirm-label="t('lcs.common.save')"
      :form-errors="dialogError ? [dialogError] : []"
      @confirm="saveEntry">
      <div class="space-y-4">
        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.ui.cols.type')" required :error="fieldErrors.documentType">
            <USelect
              v-model="draft.documentType"
              :items="typeItems"
              :disabled="Boolean(editingId)"
              class="w-full" />
          </UFormField>
          <UFormField :label="t('freight.ui.cols.date')" required :error="fieldErrors.date">
            <UInput v-model="draft.date" type="date" class="w-full" />
          </UFormField>
        </div>

        <UAlert
          v-if="missingRule"
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :description="t('freight.ui.postingRuleMissing')" />

        <UFormField :label="t('freight.ui.cols.description')" required :error="fieldErrors.description">
          <UInput v-model="draft.description" class="w-full" maxlength="1000" />
        </UFormField>

        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.fields.businessParty')" required :error="fieldErrors.partyId">
            <USelect v-model="draft.partyId" :items="partyItems" class="w-full" />
          </UFormField>
          <UFormField :label="t('freight.ui.cols.amount')" required :error="fieldErrors.amount">
            <UInputNumber
              v-model="draft.amount"
              :min="0"
              :step-snapping="false"
              :increment="false"
              :decrement="false"
              class="w-full"
              :ui="{ base: 'text-right tabular-nums' }" />
          </UFormField>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.ui.cols.currency')" required :error="fieldErrors.currency">
            <USelect v-model="draft.currency" :items="currencyItems" class="w-full" />
          </UFormField>
          <UFormField :label="t('freight.fields.feeType')">
            <USelect v-model="draft.feeTypeId" :items="feeTypeItems" class="w-full" />
          </UFormField>
        </div>

        <template v-if="needsSettlement">
          <UFormField :label="t('freight.fields.financialAccount')" required :error="fieldErrors.financialAccountId">
            <USelect v-model="draft.financialAccountId" :items="accountItems" class="w-full" />
          </UFormField>
        </template>

        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.fields.referenceNo')">
            <UInput v-model="draft.referenceNumber" class="w-full" maxlength="128" />
          </UFormField>
          <UFormField :label="t('freight.fields.remark')">
            <UInput v-model="draft.remark" class="w-full" maxlength="1000" />
          </UFormField>
        </div>
      </div>
    </CommonAppEntityDialog>

    <CommonAppEntityDialog
      v-model:open="allocOpen"
      :title="t('freight.ui.allocate')"
      :saving="allocSaving"
      :confirm-label="t('freight.ui.allocate')"
      :form-errors="allocError ? [allocError] : []"
      @confirm="saveAllocation">
      <div class="space-y-4">
        <p v-if="allocSource" class="text-sm text-muted">
          {{ allocSource.documentNo }} · {{ formatMoney(Number(allocSource.outstanding ?? 0), String(allocSource.currency || '')) }}
        </p>
        <UFormField :label="t('freight.ui.relatedDocument')" required>
          <USelect v-model="allocTargetId" :items="allocTargets" class="w-full" />
        </UFormField>
        <UFormField :label="t('freight.ui.cols.amount')" required>
          <UInputNumber
            v-model="allocAmount"
            :min="0"
            :step-snapping="false"
            :increment="false"
            :decrement="false"
            class="w-full"
            :ui="{ base: 'text-right tabular-nums' }" />
        </UFormField>
      </div>
    </CommonAppEntityDialog>
  </div>
</template>

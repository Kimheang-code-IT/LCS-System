<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import type { FreightTable } from '~/config/freight-modules'
import { JOB_FINANCE_LINES_TABLE } from '~/config/job-workspace-forms'
import { formatMoney } from '~/composables/freight/useFreight'
import { useLcs } from '~/composables/freight/useLcs'
import { useConfirm } from '~/composables/common/useConfirm'
import { getFreightModule } from '~/config/freight-modules'
import { useModuleRepository } from '~/repositories'
import { apiErrorMessage, normalizeApiError } from '~/utils/validation/api-error'
import { FINANCE_ENTRY_BEHAVIORS } from '~/utils/constants/document-types'
import { todayIso } from '~/utils/format/format-service'

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

/**
 * The Service Order customer's Business Party id, resolved from the party the
 * order stores by name. Income entries default to it; an unresolved customer
 * still blocks nothing — the entry dialog collects the party by hand.
 */
const customerPartyId = computed(() => {
  if (!props.customer) return ''
  const match = store.list('businessParties')
    .find(row => String(row.legalName || row.displayName || '') === props.customer)
  return match ? String(match.id) : ''
})

function money(value: number, currency: string) {
  return formatMoney(value, currency)
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

function isDraft(document?: FreightRecord) {
  return String(document?.status || '').toUpperCase() === 'DRAFT'
}

function isPosted(document?: FreightRecord) {
  return String(document?.status || '').toUpperCase() === 'POSTED'
}

// --- Editable finance grid -----------------------------------------------------

type FinanceRow = {
  /** Existing document id, or a `new-*` temporary id for an unsaved row. */
  id: string
  _isNew?: boolean
  _source?: FreightRecord
  type: string
  description: string
  partyId: string
  amount: number
  currency: string
  /** Preserved extended fields — edited through the entry dialog. */
  date: string
  feeTypeId: string
  referenceNumber: string
  remark: string
  financialAccountId: string
}

const entries = ref<FinanceRow[]>([])
const cellErrors = ref<Record<string, string>>({})
const actionError = ref('')
let newRowSeq = 0

function rowFromDocument(document: FreightRecord): FinanceRow {
  const lines = Array.isArray(document.lines) ? document.lines as Array<Record<string, unknown>> : []
  return {
    id: String(document.id || ''),
    _source: document,
    type: String(document.documentTypeCode || document.documentType || '').toUpperCase(),
    description: String(document.description || lines[0]?.description || ''),
    partyId: String(document.partyId || ''),
    amount: Number(document.total ?? 0),
    currency: String(document.currency || ''),
    date: String(document.documentDate || document.date || '').slice(0, 10),
    feeTypeId: String(lines[0]?.feeTypeId || ''),
    referenceNumber: String(document.referenceNumber || document.referenceNo || ''),
    remark: String(document.remark || ''),
    financialAccountId: String(document.financialAccountId || ''),
  }
}

/**
 * Rebuild the working rows from the loaded documents, keeping unsaved cell
 * edits of draft rows and every not-yet-saved inline row. Posted/reversed rows
 * are always re-read: they can never be edited here.
 */
function syncRows() {
  const previous = new Map(entries.value.map(row => [row.id, row]))
  const saved = props.documents
    .filter(isLinkedToJob)
    .map((document) => {
      const row = rowFromDocument(document)
      const prior = previous.get(row.id)
      if (prior && isDraft(row._source)) {
        // A draft the user is editing inline keeps their cell values, the
        // edited date included: a reload never silently moves it.
        return { ...row, date: prior.date, type: prior.type, description: prior.description, partyId: prior.partyId, amount: prior.amount, currency: prior.currency }
      }
      return row
    })
  const pending = entries.value.filter(row => row._isNew)
  entries.value = [...saved, ...pending]
}

watch(
  () => props.documents.map(document => String(document.id || '')).join(','),
  syncRows,
  { immediate: true },
)

/** One unsaved inline row: today's date in the configured timezone, the Service Order currency. */
function newFinanceRow(): FinanceRow {
  return {
    id: `new-${++newRowSeq}`,
    _isNew: true,
    type: '',
    description: '',
    partyId: '',
    amount: 0,
    currency: String(props.job.currency || '') || 'USD',
    date: todayIso(),
    feeTypeId: '',
    referenceNumber: '',
    remark: '',
    financialAccountId: '',
  }
}

/** Add Entry appends one editable row immediately; nothing is saved until Save. */
function addEntry() {
  actionError.value = ''
  entries.value = [...entries.value, newFinanceRow()]
}

const table = computed<FreightTable>(() => ({
  ...JOB_FINANCE_LINES_TABLE,
  columns: JOB_FINANCE_LINES_TABLE.columns.map(column => column.key === 'type'
    ? {
        ...column,
        optionItems: typeItems.value,
        // The document type identifies the created record: only an unsaved
        // inline row may still choose it.
        lockCell: (row: Record<string, unknown>) => !row._isNew,
      }
    : column),
  rowDefaults: () => newFinanceRow(),
}))

/**
 * Posted, reversed, cancelled or multi-line documents are locked: financial
 * immutability and the reversal workflow own them. Draft documents with more
 * than one line are opened and edited on their own document page, where their
 * lines are visible.
 */
function rowDisabled(row: Record<string, unknown>): boolean {
  const document = row._source as FreightRecord | undefined
  if (!document) return false
  const status = String(document.status || '').toUpperCase()
  if (status !== 'DRAFT') return true
  const lines = Array.isArray(document.lines) ? document.lines : []
  return lines.length > 1
}

function rowMenuItems(row: Record<string, unknown>) {
  const entry = row as FinanceRow
  const document = entry._source as FreightRecord | undefined
  const id = String(entry.id || '')
  if (entry._isNew) {
    return [
      {
        label: t('lcs.common.save'),
        icon: 'i-lucide-check',
        onSelect: () => { void saveRow(entry) },
      },
      {
        label: t('actions.cancel'),
        icon: 'i-lucide-x',
        onSelect: () => {
          entries.value = entries.value.filter(item => item.id !== id)
        },
      },
    ]
  }
  if (!document || !id) return []
  const items: Array<{ label: string, icon: string, color?: 'error', onSelect: () => void }> = [{
    label: t('freight.ui.viewDocument'),
    icon: 'i-lucide-eye',
    onSelect: () => { void navigateTo(`/finance/documents/${id}`) },
  }]
  if (isDraft(document) && canEdit.value) {
    items.push({ label: t('freight.ui.additionalDetails'), icon: 'i-lucide-pencil', onSelect: () => openDetails(document) })
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

// --- Inline row validation & save ----------------------------------------------

const savingRowId = ref('')

const COLUMN_FOR_FIELD: Record<string, string> = {
  documentType: 'type',
  documentTypeId: 'type',
  date: 'date',
  documentDate: 'date',
  partyId: 'partyId',
  currency: 'currency',
  description: 'description',
  amount: 'amount',
  unitPrice: 'amount',
}

function validateRow(row: FinanceRow, index: number): boolean {
  const prefix = `financeLines.${index}.`
  // Rebuild the map without the row's own keys (no dynamic deletes).
  const errors: Record<string, string> = Object.fromEntries(
    Object.entries(cellErrors.value).filter(([key]) => !key.startsWith(prefix)),
  )
  const requireField = (column: string, field: string) => {
    errors[`${prefix}${column}`] = t('validation.required', { field })
  }
  if (!row.type) requireField('type', t('freight.ui.cols.type'))
  if (!String(row.description || '').trim()) requireField('description', t('freight.ui.cols.description'))
  if (!row.date) requireField('date', t('freight.ui.cols.date'))
  else if (!/^\d{4}-\d{2}-\d{2}$/.test(row.date)) {
    errors[`${prefix}date`] = t('validation.date', { field: t('freight.ui.cols.date') })
  }
  if (!row.currency) requireField('currency', t('freight.ui.cols.currency'))
  const amount = Number(row.amount)
  if (!Number.isFinite(amount) || amount <= 0) {
    errors[`${prefix}amount`] = t('validation.positive', { field: t('freight.ui.cols.amount') })
  }
  cellErrors.value = errors
  return !Object.keys(errors).some(key => key.startsWith(prefix))
}

function entryLine(row: FinanceRow) {
  return {
    description: row.description,
    quantity: 1,
    unitPrice: Number(row.amount),
    feeTypeId: row.feeTypeId || undefined,
  }
}

function documentTypeRecord(code: string) {
  return entryTypes.value.find(row => String(row.code || '').toUpperCase() === String(code || '').toUpperCase()) || null
}

function behaviorOfCode(code: string) {
  return String(documentTypeRecord(code)?.accountingBehavior || code || '').toUpperCase()
}

async function saveRow(row: FinanceRow) {
  if (savingRowId.value || !props.editable) return
  const index = entries.value.findIndex(item => item.id === row.id)
  if (index < 0) return
  if (!validateRow(row, index)) return
  const behavior = behaviorOfCode(row.type)
  // A settlement needs its financial account, which has no inline cell: the
  // existing entry dialog owns that field and completes the row.
  if (settlementTypes.has(behavior) && !row.financialAccountId) {
    openEntryDialog(row)
    return
  }
  // Income entries default to the Service Order customer; any other party
  // (a supplier payee, an unresolvable customer) is chosen in the entry
  // dialog, and the backend re-validates the party relationship.
  if (!row.partyId && INCOME_BEHAVIORS.has(behavior)) row.partyId = customerPartyId.value
  if (!row.partyId) {
    openEntryDialog(row)
    return
  }
  savingRowId.value = row.id
  actionError.value = ''
  try {
    const payload = {
      ...(row._source || {}),
      id: row.id,
      documentType: row.type,
      documentTypeId: documentTypeRecord(row.type)?.id ? String(documentTypeRecord(row.type)!.id) : undefined,
      date: row.date || todayIso(),
      documentDate: row.date || todayIso(),
      description: row.description,
      partyId: row.partyId,
      serviceOrderId: String(props.job.id || ''),
      currency: row.currency,
      referenceNumber: row.referenceNumber,
      remark: row.remark,
      financialAccountId: row.financialAccountId || undefined,
      lines: [entryLine(row)],
    }
    if (row._isNew) {
      await lcs.finance.createDocument(payload)
      entries.value = entries.value.filter(item => item.id !== row.id)
    }
    else {
      await lcs.finance.saveDraft(payload as FreightRecord)
    }
    cellErrors.value = {}
    store.reload()
    toast.add({ title: t('lcs.common.saved'), color: 'success' })
  }
  catch (error) {
    const normalized = normalizeApiError(error)
    const mapped: Record<string, string> = { ...cellErrors.value }
    let rowLevel = ''
    for (const [field, message] of Object.entries(normalized.fieldErrors)) {
      const column = COLUMN_FOR_FIELD[field] || field
      const key = `financeLines.${index}.${column}`
      // The party is no longer an inline column; its errors surface at row level.
      if (['type', 'description', 'date', 'amount', 'currency'].includes(column)) mapped[key] = message
      else rowLevel = rowLevel || message
    }
    if (rowLevel || (!normalized.fieldErrors.length && normalized.message)) {
      rowLevel = rowLevel || normalized.message || apiErrorMessage(error, t('freight.ui.saveFailed'))
      actionError.value = rowLevel
    }
    cellErrors.value = mapped
  }
  finally {
    savingRowId.value = ''
  }
}

// --- Entry dialog (extended fields, settlements, full creation) ------------------

const dialogOpen = ref(false)
const saving = ref(false)
const dialogError = ref('')
const fieldErrors = ref<Record<string, string>>({})
const editingId = ref('')
/** The unsaved inline row the dialog is completing, if any. */
const dialogRowId = ref('')

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
    date: todayIso(),
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

/** The dialog completing an unsaved inline row: values are kept, the account is added. */
function openEntryDialog(row: FinanceRow) {
  editingId.value = ''
  dialogRowId.value = row.id
  draft.value = {
    documentType: row.type,
    date: row.date || todayIso(),
    description: row.description,
    partyId: row.partyId,
    amount: Number(row.amount) || null,
    currency: row.currency,
    feeTypeId: row.feeTypeId || '',
    financialAccountId: '',
    relatedDocumentId: '',
    referenceNumber: row.referenceNumber || '',
    remark: row.remark || '',
  }
  fieldErrors.value = {}
  dialogError.value = ''
  dialogOpen.value = true
}

function openDetails(document: FreightRecord) {
  const row = entries.value.find(item => item.id === String(document.id || ''))
  if (row && !row._isNew) {
    editingId.value = row.id
    dialogRowId.value = ''
    draft.value = {
      documentType: row.type,
      date: row.date,
      description: row.description,
      partyId: row.partyId,
      amount: Number(row.amount) || null,
      currency: row.currency,
      feeTypeId: row.feeTypeId,
      financialAccountId: row.financialAccountId,
      relatedDocumentId: '',
      referenceNumber: row.referenceNumber,
      remark: row.remark,
    }
  }
  else {
    openEdit(document)
  }
  fieldErrors.value = {}
  dialogError.value = ''
  dialogOpen.value = true
}

function openEdit(document: FreightRecord) {
  const lines = Array.isArray(document.lines) ? document.lines as Array<Record<string, unknown>> : []
  editingId.value = String(document.id || '')
  dialogRowId.value = ''
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
      const source = entries.value.find(row => row.id === editingId.value)?._source
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
      if (dialogRowId.value) {
        // The inline row this dialog completed now exists as a real document.
        entries.value = entries.value.filter(item => item.id !== dialogRowId.value)
        dialogRowId.value = ''
      }
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

// --- Allocation, posting, reversal, deletion -----------------------------------

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
    entries.value = entries.value.filter(row => row.id !== id)
    store.reload()
    actionError.value = ''
    toast.add({ title: t('actions.delete'), color: 'success' })
  }
  catch (error) {
    actionError.value = lcs.errorMessage(error)
  }
}

// --- Finance summary -------------------------------------------------------------

/**
 * Income / expense summary, grouped by currency. Posted documents only:
 * drafts are amounts not yet accounted for, so they appear as a separately
 * labelled preview when present. Settlements (receipts/payments) are never
 * counted — they move cash, they are not income — and reversed or cancelled
 * documents are excluded by the existing status rules. Currencies are never
 * silently converted.
 */
const INCOME_BEHAVIORS = new Set(['CUSTOMER_INVOICE', 'OTHER_INCOME'])
const EXPENSE_BEHAVIORS = new Set(['SUPPLIER_BILL', 'OTHER_EXPENSE'])
const EXCLUDED_SUMMARY_STATUSES = new Set(['REVERSED', 'CANCELLED'])

function documentBehavior(document: FreightRecord) {
  const code = String(document.documentType || '').toUpperCase()
  const typeRecord = store.list('documentTypes')
    .find(row => String(row.code || '').toUpperCase() === code)
  return String(typeRecord?.accountingBehavior || code).toUpperCase()
}

type SummaryGroup = { currency: string, income: number, expense: number, net: number, draftNet: number }

const financeSummary = computed<SummaryGroup[]>(() => {
  const byCurrency = new Map<string, SummaryGroup>()
  const group = (currency: string) => {
    const entry = byCurrency.get(currency) || { currency, income: 0, expense: 0, net: 0, draftNet: 0 }
    byCurrency.set(currency, entry)
    return entry
  }
  for (const row of entries.value) {
    const document = row._source
    if (!document) continue
    const status = String(document.status || '').toUpperCase()
    if (EXCLUDED_SUMMARY_STATUSES.has(status)) continue
    const behavior = documentBehavior(document)
    const isIncome = INCOME_BEHAVIORS.has(behavior)
    const isExpense = EXPENSE_BEHAVIORS.has(behavior)
    if (!isIncome && !isExpense) continue
    const entry = group(String(document.currency || ''))
    const amount = Number(document.total ?? 0)
    if (status === 'POSTED') {
      if (isIncome) entry.income += amount
      else entry.expense += amount
    }
    else {
      entry.draftNet += isIncome ? amount : -amount
    }
  }
  return [...byCurrency.values()].map(entry => ({
    ...entry,
    income: Number(entry.income.toFixed(2)),
    expense: Number(entry.expense.toFixed(2)),
    net: Number((entry.income - entry.expense).toFixed(2)),
    draftNet: Number(entry.draftNet.toFixed(2)),
  }))
})

function clearCellError(cellKey: string) {
  if (!cellErrors.value[cellKey]) return
  cellErrors.value = Object.fromEntries(
    Object.entries(cellErrors.value).filter(([key]) => key !== cellKey),
  )
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
        @click="addEntry" />
    </div>

    <CommonAppFormErrorSummary v-if="actionError" :form-errors="[actionError]" />

    <FreightAppLineTable
      v-if="entries.length || canCreate"
      v-model="entries"
      :table="table"
      :disabled="editable !== true"
      :row-disabled="rowDisabled"
      :extra-row-menu-items="rowMenuItems"
      :field-errors="cellErrors"
      :on-cell-edit="clearCellError" />

    <FreightJobEmptyState
      v-else
      :title="t('freight.ui.noFinanceEntries')"
      :description="t('freight.ui.addEntry')"
      icon="i-lucide-banknote" />

    <div
      v-if="financeSummary.length"
      class="ms-auto grid w-full max-w-sm gap-1.5 px-1 py-2 text-sm">
      <template v-for="group in financeSummary" :key="group.currency">
        <div class="flex items-center justify-between gap-4">
          <span class="text-muted">{{ t('freight.ui.totalIncome') }} ({{ group.currency }})</span>
          <span class="font-medium tabular-nums text-highlighted">{{ money(group.income, group.currency) }}</span>
        </div>
        <div class="flex items-center justify-between gap-4">
          <span class="text-muted">{{ t('freight.ui.totalExpenses') }} ({{ group.currency }})</span>
          <span class="font-medium tabular-nums text-highlighted">{{ money(group.expense, group.currency) }}</span>
        </div>
        <div class="mb-1 flex items-center justify-between gap-4 border-t border-default pt-2 text-base">
          <span class="font-semibold text-highlighted">{{ t('freight.ui.netAmount') }} ({{ group.currency }})</span>
          <span
            class="font-bold tabular-nums"
            :class="group.net < 0 ? 'text-error' : 'text-primary'"
          >{{ money(group.net, group.currency) }}</span>
        </div>
        <div v-if="group.draftNet" class="flex items-center justify-between gap-4">
          <span class="text-muted">{{ t('freight.ui.unpostedDrafts') }}</span>
          <span class="tabular-nums text-muted">{{ money(group.draftNet, group.currency) }}</span>
        </div>
      </template>
    </div>

    <CommonAppEntityDialog
      v-model:open="dialogOpen"
      :title="editingId || dialogRowId ? t('freight.ui.additionalDetails') : t('freight.ui.addEntry')"
      :saving="saving"
      :confirm-label="t('lcs.common.save')"
      :form-errors="dialogError ? [dialogError] : []"
      @confirm="saveEntry">
      <div class="space-y-4">
        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.ui.cols.type')" required :error="fieldErrors.documentType">
            <CommonAppReferenceSelect
              v-model="draft.documentType"
              reference-key="documentType"
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
            <CommonAppReferenceSelect
v-model="draft.partyId"
reference-key="partyId"
:items="partyItems"
class="w-full" />
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
            <CommonAppReferenceSelect
v-model="draft.currency"
reference-key="currency"
:items="currencyItems"
class="w-full" />
          </UFormField>
          <UFormField :label="t('freight.fields.feeType')">
            <CommonAppReferenceSelect
v-model="draft.feeTypeId"
reference-key="feeTypeId"
:items="feeTypeItems"
class="w-full" />
          </UFormField>
        </div>

        <template v-if="needsSettlement">
          <UFormField :label="t('freight.fields.financialAccount')" required :error="fieldErrors.financialAccountId">
            <CommonAppReferenceSelect
v-model="draft.financialAccountId"
reference-key="financialAccountId"
:items="accountItems"
class="w-full" />
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

<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import type { FreightTable } from '~/config/freight-modules'
import { JOB_FINANCE_LINES_TABLE } from '~/config/job-workspace-forms'
import { jobContainerPaymentTotals } from '~/utils/freight/job-containers'
import { formatMoney } from '~/composables/freight/useFreight'
import { useLcs } from '~/composables/freight/useLcs'
import { useConfirm } from '~/composables/common/useConfirm'
import { getFreightModule } from '~/config/freight-modules'
import { useModuleRepository } from '~/repositories'
import { apiErrorMessage, normalizeApiError } from '~/utils/validation/api-error'
import {
  FINANCE_ENTRY_BEHAVIORS,
  INCOME_BEHAVIORS,
} from '~/utils/constants/document-types'
import { todayIso, formatConfigVersion, getFormatConfig } from '~/utils/format/format-service'
import { createIdempotencyKey } from '~/utils/freight/idempotency'
import {
  buildFinanceSummary,
  convertScaled,
  financeDocumentBehavior,
  scaledDecimal,
  type FinanceSummaryEntry,
  type FinanceSummaryGroup,
} from '~/utils/freight/finance-summary'
import {
  FINANCE_DRAFT_FIELDS,
  financeDocumentFingerprint,
  financeDraftSnapshot,
  mergeFinanceDraftRows,
  reconcileReceiptAllocations,
  type FinanceDraftRow,
} from '~/utils/freight/finance-draft'
import { useRecordFormDraft } from '~/composables/common/useRecordFormDraft'

const props = withDefaults(defineProps<{
  job: FreightRecord
  jobNo: string
  customer: string
  documents: FreightRecord[]
  supplierCosts?: FreightRecord[]
  receivables?: FreightRecord[]
  /** Linked Service Charges, including the Service Charge tab's live preview. */
  charges?: FreightRecord[]
  /** True until the Service Order itself is loaded (summary shows placeholders). */
  summaryLoading?: boolean
  editable?: boolean
  active?: boolean
}>(), {
  editable: false,
  active: true,
  supplierCosts: () => [],
  receivables: () => [],
  charges: () => [],
  summaryLoading: false,
})

const { t } = useI18n()
const toast = useToast()
const store = useFreightStore()
const lcs = useLcs()
const auth = useAuthStore()
const { confirm } = useConfirm()

/**
 * Every financial document linked to this order. The two store projections
 * cover customer invoices and supplier bills; one cached list fills in the
 * remaining configured behaviours (other income/expense, settlements) without
 * asking the API again on each render.
 */
const remoteDocuments = ref<FreightRecord[]>([])
const remoteDocumentsOrder = ref('')
const savedCharges = ref<FreightRecord[] | null>(null)
const chargeLoadError = ref('')
let chargeRequest = 0
async function loadOrderCharges() {
  const orderId = String(props.job.id || '')
  if (!orderId) return
  const request = ++chargeRequest
  try {
    const rows = await lcs.charges.listForOrder(orderId)
    if (request !== chargeRequest || orderId !== String(props.job.id || '')) return
    savedCharges.value = rows
    chargeLoadError.value = ''
  }
  catch (error) {
    if (request === chargeRequest) {
      savedCharges.value = null
      chargeLoadError.value = lcs.errorMessage(error)
    }
  }
}
const financeLoading = ref(false)
const financeLoadError = ref('')
let financeRequest = 0
let financeSync: Promise<void> | null = null
let financeSyncPending = false
const FINANCE_COLLECTIONS = ['debitNotes', 'supplierCosts', 'receivables', 'jobCharges']
const financeDocuments = computed<FreightRecord[]>(() => remoteDocumentsOrder.value === String(props.job.id || '')
  ? remoteDocuments.value : [])

async function loadFinanceDocuments(force = false) {
  const orderId = String(props.job.id || '')
  if (!orderId || (!force && remoteDocumentsOrder.value === orderId)) return
  const request = ++financeRequest
  financeLoading.value = true
  financeLoadError.value = ''
  try {
    const items: FreightRecord[] = []
    let page = 1
    let total = 0
    do {
      const result = await lcs.finance.listDocuments({ page, page_size: 200, service_order_id: orderId })
      if (request !== financeRequest || orderId !== String(props.job.id || '')) return
      items.push(...result.items)
      total = result.meta.total
      if (!result.items.length) break
      page += 1
    } while (items.length < total)
    remoteDocuments.value = items
    remoteDocumentsOrder.value = orderId
  }
  catch (error) {
    if (request === financeRequest) financeLoadError.value = lcs.errorMessage(error)
  }
  finally {
    if (request === financeRequest) financeLoading.value = false
  }
}

async function synchronizeFinance() {
  financeSyncPending = true
  if (financeSync) return financeSync
  financeSync = (async () => {
    while (financeSyncPending) {
      financeSyncPending = false
      await loadFinanceDocuments(true)
    }
  })().finally(() => { financeSync = null })
  return financeSync
}

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
  if (props.job.customerPartyId) return String(props.job.customerPartyId)
  if (!props.customer) return ''
  const match = store.list('businessParties')
    .find(row => String(row.legalName || row.displayName || '') === props.customer)
  return match ? String(match.id) : ''
})

function money(value: number, currency: string) {
  return formatMoney(value, currency)
}

const canCreate = computed(() => Boolean(props.job.id) && lcs.can('financial_document.create'))
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
  /** Server stamp of the draft document this row was edited against. */
  _baseUpdatedAt?: string
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

function rowFromDocument(document: FreightRecord): FinanceRow {
  const lines = Array.isArray(document.lines) ? document.lines as Array<Record<string, unknown>> : []
  return {
    id: String(document.id || ''),
    _source: document,
    _baseUpdatedAt: String(document.updatedAt || financeDocumentFingerprint(document)),
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
  for (const prior of entries.value) {
    if (prior._isNew || !rowDraftChanged(prior)) continue
    const source = financeDocuments.value.find(row => String(row.id) === prior.id)
    const stamp = source ? String(source.updatedAt || financeDocumentFingerprint(source)) : ''
    if (!source || !isDraft(source) || stamp !== prior._baseUpdatedAt) {
      if (!conflictingRows.value.some(row => row.id === prior.id)) {
        conflictingRows.value.push(...financeDraftSnapshot([prior]))
      }
      previous.delete(prior.id)
    }
  }
  const saved = financeDocuments.value
    .filter(isLinkedToJob)
    .map((document) => {
      const row = rowFromDocument(document)
      const prior = previous.get(row.id)
      if (prior && rowDraftChanged(prior) && isDraft(row._source)) {
        // A draft the user is editing keeps every edited field: a reload never
        // silently moves a date, party, reference or remark.
        const kept = Object.fromEntries(FINANCE_DRAFT_FIELDS.map(field => [field, prior[field]]))
        return { ...row, ...kept, _baseUpdatedAt: prior._baseUpdatedAt }
      }
      return row
    })
  const pending = entries.value.filter(row => row._isNew)
  entries.value = [...saved, ...pending]
}

// --- Finance entries draft -----------------------------------------------------
// The table keeps unsaved new rows and edits to DRAFT financial documents in a
// versioned local draft, keyed by user + order. Posted documents are never
// restored from a local copy: their server values stay authoritative.
const financeDraftRestored = ref(false)
const conflictingRows = ref<FinanceDraftRow[]>([])
const paymentPending = ref(false)

function rowDraftChanged(row: FinanceRow): boolean {
  if (row._isNew) return true
  const source = row._source
  if (!source) return false
  if (String(source.status || '').toUpperCase() !== 'DRAFT') return false
  const canonical = rowFromDocument(source)
  return FINANCE_DRAFT_FIELDS.some(field =>
    String(row[field] ?? '') !== String(canonical[field] ?? ''))
}

const financeDraftDirty = computed(() => entries.value.some(rowDraftChanged) || conflictingRows.value.length > 0 || paymentPending.value)

const formDraft = useRecordFormDraft<Record<string, unknown>>({
  collection: () => 'serviceOrderFinance',
  scope: () => String(auth.user?.id || 'anon'),
  recordId: () => String(props.job.id || props.jobNo || ''),
  baseUpdatedAt: () => '',
  model: financeDraftModel,
  sanitize: financeDraftModel,
  apply: (stored) => {
    if (stored.payment && typeof stored.payment === 'object') {
      const payment = stored.payment as { draft: PayDraft, key: string, receiptId: string }
      if (payment.draft && payment.key) {
        payDraft.value = payment.draft
        paymentKey.value = payment.key
        savedReceiptId.value = payment.receiptId || ''
        paymentPending.value = true
      }
    }
    const rows = (stored as { rows?: unknown }).rows
    if (!Array.isArray(rows) || !rows.length) return
    const merged = mergeFinanceDraftRows(entries.value, rows as FinanceDraftRow[], row => ({
      id: row.id,
      status: rowDisabled(row) ? 'LOCKED' : row._source?.status,
      // `_baseUpdatedAt` holds the server stamp or a content fingerprint.
      updatedAt: row._baseUpdatedAt,
    }))
    entries.value = merged.rows
    conflictingRows.value = merged.rejected
    if (merged.skipped) {
      actionError.value = t('freight.ui.financeDraftPartial', { count: merged.skipped })
    }
  },
  isDirty: () => financeDraftDirty.value,
  canDraft: () => (canCreate.value || canEdit.value) && financeDraftRestored.value,
})

function financeDraftModel() {
  return {
    rows: [...financeDraftSnapshot(entries.value.filter(rowDraftChanged)), ...conflictingRows.value],
    ...(paymentPending.value ? { payment: {
      draft: payDraft.value, key: paymentKey.value, receiptId: savedReceiptId.value,
    } } : {}),
  }
}

function restoreFinanceDraft() {
  if (financeDraftRestored.value) return
  if (!canCreate.value && !canEdit.value) {
    financeDraftRestored.value = true
    return
  }
  const key = formDraft.key.value
  if (!key) return
  // Wait for the related collections before declaring "no draft": an empty
  // first render must not consume the recovery slot.
  if (remoteDocumentsOrder.value !== String(props.job.id || '')) return
  financeDraftRestored.value = true
  formDraft.bind()
  formDraft.restore()
}

watch(
  entries,
  () => {
    if (!financeDraftRestored.value) restoreFinanceDraft()
    if (!financeDraftRestored.value) return
    if (financeDraftDirty.value) formDraft.schedule()
    else formDraft.flush()
  },
  { deep: true },
)

watch(
  () => financeDocuments.value,
  () => {
    syncRows()
    restoreFinanceDraft()
  },
  { immediate: true },
)

/** Navigating to another order keeps the tab mounted: file the old draft under
 *  its own key before switching to the new order's entries. */
watch(() => props.job.id, () => {
  formDraft.flush()
  financeDraftRestored.value = false
  actionError.value = ''
  entries.value = []
  dialogOpen.value = false
  payOpen.value = false
  void synchronizeFinance()
}, { flush: 'sync' })
onMounted(() => { void loadFinanceDocuments(); void loadOrderCharges() })
watch(() => props.active, (active) => {
  if (active) { void synchronizeFinance(); void loadOrderCharges() }
})
watch(() => store.financialRevision, () => {
  if (props.active && !saving.value && !savingRowId.value && !paySaving.value && !postingId.value && !allocSaving.value) {
    void synchronizeFinance()
    void loadOrderCharges()
  }
})

/** One unsaved inline row: today's date in the configured timezone, the Service Order currency. */
function newFinanceRow(): FinanceRow {
  return {
    id: `new-${createIdempotencyKey()}`,
    _isNew: true,
    type: '',
    description: '',
    partyId: '',
    amount: 0,
    currency: String(props.job.currency || '') || baseCurrencyCode.value,
    date: todayIso(),
    feeTypeId: '',
    referenceNumber: '',
    remark: '',
    financialAccountId: '',
  }
}

/** Add Entry appends one editable row immediately; nothing is saved until Save. */
function addEntry(type = '') {
  if (!canCreate.value) return
  if (behaviorOfCode(type) === 'CUSTOMER_RECEIPT') {
    openReceivePayment()
    return
  }
  actionError.value = ''
  const row = { ...newFinanceRow(), type }
  if (INCOME_BEHAVIORS.has(behaviorOfCode(type))) row.partyId = customerPartyId.value
  entries.value = [...entries.value, row]
  openEntryDialog(row)
}

const addEntryItems = computed(() => [entryTypes.value.map(type => ({
  label: String(type.name || type.code),
  onSelect: () => addEntry(String(type.code)),
}))])

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
  if (!document) return !canCreate.value
  const status = String(document.status || '').toUpperCase()
  if (status !== 'DRAFT' || !canEdit.value || document.generatedDocument) return true
  const lines = Array.isArray(document.lines) ? document.lines : []
  return lines.length !== 1 || (lines as Array<Record<string, unknown>>).some(line =>
    Number(line.quantity ?? 1) !== 1 || Number(line.discount || line.taxAmount || line.taxRate || 0) !== 0
    || Boolean(line.accountId || line.serviceOrderContainerId || line.serviceOrderId))
}

function rowMenuItems(row: Record<string, unknown>) {
  const entry = row as FinanceRow
  const document = entry._source as FreightRecord | undefined
  const id = String(entry.id || '')
  if (entry._isNew && canCreate.value) {
    return [
      {
        label: t('freight.ui.additionalDetails'),
        icon: 'i-lucide-pencil',
        onSelect: () => openEntryDialog(entry),
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
  if (postingId.value === id) return items
  items.push({ label: t('freight.ui.additionalDetails'), icon: 'i-lucide-info', onSelect: () => { void viewDetails(document) } })
  if (isDraft(document) && canEdit.value && !rowDisabled(entry)) {
    items.push({ label: t('actions.edit'), icon: 'i-lucide-pencil', onSelect: () => openDetails(document) })
    items.push({ label: t('lcs.common.save'), icon: 'i-lucide-check', onSelect: () => { void saveRow(entry) } })
  }
  else if (isDraft(document) && canEdit.value && !document.generatedDocument) {
    items.push({ label: t('actions.edit'), icon: 'i-lucide-pencil', onSelect: () => { void navigateTo(`/finance/documents/${id}`) } })
  }
  if (isDraft(document) && canPost.value) {
    items.push({ label: t('freight.ui.post'), icon: 'i-lucide-check-circle', onSelect: () => { void postDocument(id) } })
  }
  if (isPosted(document) && canReverse.value) {
    items.push({ label: t('freight.ui.reverse'), icon: 'i-lucide-undo-2', onSelect: () => { void reverseDocument(id) } })
  }
  if (canReceivePayment(document)) items.push({ label: t('freight.ui.receivePayment'), icon: 'i-lucide-hand-coins', onSelect: () => openReceivePayment(document) })
  if (isPosted(document) && lcs.can('journal_entry.read')) {
    items.push({ label: t('freight.ui.viewJournal'), icon: 'i-lucide-book-open', onSelect: () => { void viewJournal(document) } })
  }
  if (isPosted(document) && canAllocate.value && settlementTypes.has(documentBehavior(document))) {
    items.push({ label: t('freight.ui.allocate'), icon: 'i-lucide-link', onSelect: () => openAllocation(document) })
  }
  if (isDraft(document) && canDelete.value) {
    items.push({ label: t('freight.ui.delete'), icon: 'i-lucide-trash-2', color: 'error', onSelect: () => { void deleteDocument(id) } })
  }
  return items
}

// --- Inline row validation & save ----------------------------------------------

const savingRowId = ref('')
const postingId = ref('')

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
  if (savingRowId.value || rowDisabled(row) || (row._isNew ? !canCreate.value : !canEdit.value)) return
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
  const submitted = { ...row }
  const orderId = String(props.job.id || '')
  savingRowId.value = row.id
  actionError.value = ''
  try {
    const payload = {
      ...(row._source || {}),
      ...(row._isNew ? {} : { id: row.id }),
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
    const saved = row._isNew
      ? await lcs.finance.createDocument(payload, row.id)
      : await lcs.finance.saveDraft(payload as FreightRecord)
    if (orderId !== String(props.job.id || '')) return false
    if (saved?.id) {
      // A delayed response must not replace a cell edited while the request was
      // in flight. Adopt the server identity/stamp only; newer local values stay.
      const current = entries.value.find(item => item.id === row.id)
      const changedSinceRequest = current
        ? FINANCE_DRAFT_FIELDS.some(field => String(current[field] ?? '') !== String(submitted[field] ?? ''))
        : false
      if (!current) {
        // Nothing to adopt.
      }
      else if (row._isNew) {
        entries.value = changedSinceRequest
          ? entries.value.map(item => item.id === row.id
            ? { ...item, id: String(saved.id), _isNew: false, _source: saved, _baseUpdatedAt: String(saved.updatedAt || '') }
            : item)
          : entries.value.filter(item => item.id !== row.id)
      }
      else if (!changedSinceRequest) {
        entries.value = entries.value.map(item =>
          item.id === row.id ? rowFromDocument(saved) : item)
      }
      else {
        entries.value = entries.value.map(item => item.id === row.id
          ? { ...item, _source: saved, _baseUpdatedAt: String(saved.updatedAt || '') }
          : item)
      }
    }
    cellErrors.value = {}
    store.reload(FINANCE_COLLECTIONS)
    void synchronizeFinance()
    toast.add({ title: t('lcs.common.saved'), color: 'success' })
    return true
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
    if (rowLevel || (!Object.keys(normalized.fieldErrors).length && normalized.message)) {
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
    currency: String(props.job.currency || '') || baseCurrencyCode.value,
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
    financialAccountId: row.financialAccountId || '',
    relatedDocumentId: '',
    referenceNumber: row.referenceNumber || '',
    remark: row.remark || '',
  }
  fieldErrors.value = {}
  dialogError.value = ''
  dialogOpen.value = true
}

function openDetails(document: FreightRecord) {
  if (postingId.value === String(document.id)) return
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
    currency: String(document.currency || '') || baseCurrencyCode.value,
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

watch(draft, (value) => {
  if (!dialogOpen.value || saving.value) return
  const id = dialogRowId.value || editingId.value
  entries.value = entries.value.map(row => row.id === id && !rowDisabled(row)
    ? { ...row, ...value, type: value.documentType, amount: Number(value.amount || 0) }
    : row)
}, { deep: true, flush: 'sync' })

async function saveEntry() {
  if (saving.value || !validateDraft()) return
  const row = entries.value.find(item => item.id === (dialogRowId.value || editingId.value))
  if (!row || rowDisabled(row)) return
  saving.value = true
  try {
    if (await saveRow(row)) dialogOpen.value = false
    else dialogError.value = actionError.value
  }
  finally { saving.value = false }
}

const detailOpen = ref(false)
const detailDocument = ref<FreightRecord | null>(null)
async function viewDetails(document: FreightRecord) {
  detailDocument.value = document
  detailOpen.value = true
  try {
    const loaded = await lcs.finance.getDocument(String(document.id))
    if (detailDocument.value?.id === loaded.id) detailDocument.value = loaded
  }
  catch (error) { actionError.value = lcs.errorMessage(error) }
}
async function viewJournal(document: FreightRecord) {
  try {
    const detail = await lcs.finance.getDocument(String(document.id))
    if (detail.journalId) await navigateTo(`/finance/journals/${detail.journalId}`)
  }
  catch (error) { actionError.value = lcs.errorMessage(error) }
}
const additionalDetails = computed(() => {
  const doc = detailDocument.value
  if (!doc) return []
  return [
    ['freight.fields.documentNo', doc.documentNo],
    ['freight.fields.businessParty', partyLabel(doc.partyId)],
    ['freight.ui.cols.currency', doc.currency],
    ['freight.fields.financialAccount', accountLabel(doc.financialAccountId)],
    ['freight.fields.paymentMethod', doc.paymentMethod],
    ['freight.fields.referenceNo', doc.referenceNumber],
    ['freight.fields.createdBy', doc.createdBy],
    ['freight.fields.remark', doc.remark],
  ]
})

// --- Allocation, posting, reversal, deletion -----------------------------------

const allocOpen = ref(false)
const allocSaving = ref(false)
const allocError = ref('')
const allocSource = ref<FreightRecord | null>(null)
const allocTargets = computed(() => {
  const source = allocSource.value
  if (!source) return []
  const targetType = documentBehavior(source) === 'CUSTOMER_RECEIPT'
    ? 'CUSTOMER_INVOICE'
    : 'SUPPLIER_BILL'
  return financeDocuments.value.filter((row) => {
    if (documentBehavior(row) !== targetType) return false
    if (String(row.status || '').toUpperCase() !== 'POSTED') return false
    if (Number(row.outstanding ?? 0) <= 0) return false
    return String(row.partyId || '') === String(source.partyId || '')
  })
})

function openAllocation(document: FreightRecord) {
  allocSource.value = document
  allocError.value = ''
  allocOpen.value = true
}

async function allocate({ targetId, amount }: { targetId: string, amount: number }) {
  const source = allocSource.value
  if (!source) return
  allocSaving.value = true
  allocError.value = ''
  try {
    const id = String(source.id)
    await lcs.runCommand('finance-allocate', `${id}-${targetId}`, key =>
      lcs.finance.allocate(id, targetId, amount, key), FINANCE_COLLECTIONS)
    toast.add({ title: t('freight.ui.allocate'), color: 'success' })
    allocOpen.value = false
    void synchronizeFinance()
  }
  catch (error) {
    allocError.value = lcs.errorMessage(error)
  }
  finally {
    allocSaving.value = false
  }
}

async function postDocument(id: string) {
  if (saving.value || savingRowId.value || postingId.value) return
  postingId.value = id
  try {
    const entry = entries.value.find(row => row.id === id)
    if (entry && rowDraftChanged(entry) && !await saveRow(entry)) return
    const current = entries.value.find(row => row.id === id)
    if (current && rowDraftChanged(current)) {
      actionError.value = t('lcs.document.unsavedConfirm')
      return
    }
    await lcs.runCommand('finance-post', id, key => lcs.finance.post(id, key), FINANCE_COLLECTIONS)
    await synchronizeFinance()
    actionError.value = ''
    toast.add({ title: t('freight.ui.post'), color: 'success' })
  }
  catch (error) {
    actionError.value = lcs.errorMessage(error)
  }
  finally { postingId.value = '' }
}

async function reverseDocument(id: string) {
  const accepted = await confirm({ kind: 'update', descriptionKey: 'lcs.finance.reverseReason' })
  if (!accepted) return
  try {
    await lcs.runCommand('finance-reverse', id, key => lcs.finance.reverse(id, 'Reversal from the service order finance tab.', key), FINANCE_COLLECTIONS)
    await synchronizeFinance()
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
    store.reload(FINANCE_COLLECTIONS)
    void synchronizeFinance()
    actionError.value = ''
    toast.add({ title: t('actions.delete'), color: 'success' })
  }
  catch (error) {
    actionError.value = lcs.errorMessage(error)
  }
}

// --- Finance summary -------------------------------------------------------------

/**
 * Summary inputs use the same rows the table shows. Posted documents contribute
 * their authoritative `total`/`outstanding`; only DRAFT rows use a live edited
 * amount. Linked Service Charges already include their approved discount/tax
 * totals (and the Service Charge tab's unsaved preview when it is mounted).
 */
function documentBehavior(document: FreightRecord) {
  return financeDocumentBehavior(document, store.list('documentTypes'))
}

const summaryEntries = computed<FinanceSummaryEntry[]>(() => financeDocuments.value.map(source => ({
  id: String(source.id), status: source.status, currency: source.currency,
  behavior: documentBehavior(source), total: source.total,
  paidAmount: source.paidAmount, outstanding: source.outstanding,
  // The rate this document stored when it was saved/posted — the only rate its
  // base-currency value may use.
  exchangeRate: source.exchangeRate,
  baseTotalAmount: source.baseTotalAmount,
})))

/** The Containers tab's payment sheet is a customer charge too. */
const containerCharge = computed(() => {
  const order = store.get('jobs', String(props.job.id || '')) || props.job
  const rows = Array.isArray(order.containerPayments)
    ? order.containerPayments as Array<Record<string, unknown>>
    : []
  if (!rows.length) return null
  const totals = jobContainerPaymentTotals(rows, order.vatRate, order.discount)
  return { currency: String(order.currency || ''), total: totals.total }
})

const financeSummary = computed(() => buildFinanceSummary({
  charges: savedCharges.value || [],
  entries: summaryEntries.value,
  containerCharge: containerCharge.value,
  internalCharges: (savedCharges.value || [])
    .filter(charge => String(charge.chargeSide || 'CUSTOMER').toUpperCase() === 'INTERNAL')
    .map((charge) => {
      const currency = String(charge.currency || props.job.currency || '')
      const generatedKey = `SO:${String(props.job.id || '')}:SUP:${String(charge.supplierPartyId || '')}:${currency}:SUPPLIER_BILL`
      const generated = entries.value.some(row =>
        String(row._source?.generatedKey || '') === generatedKey)
      return {
        currency,
        costTotal: charge.costTotal,
        supplierDocumentId: charge.supplierDocumentId || (generated ? generatedKey : ''),
      }
    }),
  primaryCurrency: String(props.job.currency || ''),
}))

const summaryMetrics = [
  { key: 'totalCharges', labelKey: 'freight.ui.totalCharges' },
  { key: 'totalExpenses', labelKey: 'freight.ui.totalExpenses' },
  { key: 'totalCustomerPayments', labelKey: 'freight.ui.totalCustomerPayments' },
  { key: 'outstandingReceivable', labelKey: 'freight.ui.outstandingReceivable' },
] as const

/** The one configured base currency (System Settings → Localization). */
const baseCurrencyCode = computed(() => {
  void formatConfigVersion.value
  return String(getFormatConfig().currency || '').trim().toUpperCase()
})

/**
 * Per-currency conversion factors taken from the rows themselves: a document's
 * stored rate, or a charge's approved rate resolved by the API. A currency with
 * mixed historical rates (or any row without a usable rate) is `null`, so the
 * summary is never merged through a guessed or averaged rate.
 */
const summaryRates = computed(() => {
  const rates = new Map<string, number | null>()
  const add = (currency: unknown, rate: unknown) => {
    const code = String(currency || '').trim().toUpperCase()
    if (!code) return
    const value = Number(rate)
    const usable = Number.isFinite(value) && value > 0 ? value : null
    if (!rates.has(code)) {
      rates.set(code, usable)
      return
    }
    const existing = rates.get(code) ?? null
    if (existing === null || usable === null || Math.abs(existing - usable) > 1e-9) rates.set(code, null)
  }
  for (const entry of summaryEntries.value) add(entry.currency, entry.exchangeRate)
  for (const charge of savedCharges.value || []) add(charge.currency, charge.exchangeRate)
  return rates
})

/**
 * The four summary cards in the base currency. Converted only when every
 * contributing currency either *is* the base currency or has one stored rate;
 * otherwise the existing per-currency groups are shown, so no amount is ever
 * converted with today's rate or a blend of historical ones.
 */
const summaryDisplay = computed<FinanceSummaryGroup[]>(() => {
  const groups = financeSummary.value
  const base = baseCurrencyCode.value
  if (!base || !groups.length) return groups
  const rates = summaryRates.value
  const convertible = groups.every((group) => {
    const code = String(group.currency || '').trim().toUpperCase()
    return !code || code === base || rates.get(code) != null
  })
  if (!convertible) return groups
  const merged: FinanceSummaryGroup = { ...groups[0]!, currency: base }
  const keys = [
    'totalCharges', 'chargedAmount', 'unchargedAmount', 'totalExpenses', 'netAmount',
    'outstandingReceivable', 'totalInvoiced', 'unbilledCharges', 'totalCustomerPayments',
    'supplierPayments', 'outstandingPayable', 'estimatedProfit', 'actualProfit',
    'draftCharges', 'draftExpenses',
  ] as const
  for (const key of keys) {
    merged[key] = groups.reduce((sum, group) => {
      const code = String(group.currency || '').trim().toUpperCase()
      if (!code || code === base) return sum + group[key]
      return sum + convertScaled(group[key], rates.get(code)!)
    }, 0)
  }
  merged.estimated = groups.some(group => group.estimated)
  return [merged]
})

/** Do not keep a permanent skeleton if a supplemental collection is denied or
 *  unreachable; after this window the available (possibly empty) data is shown. */
const summaryWaitExpired = ref(false)
const summaryWaitTimer = setTimeout(() => { summaryWaitExpired.value = true }, 8000)
onBeforeUnmount(() => clearTimeout(summaryWaitTimer))

const summaryLoading = computed(() => !summaryWaitExpired.value && (props.summaryLoading
  || (!(props.charges || []).length && !store.isLoaded('jobCharges'))
  || !store.isLoaded('debitNotes')
  || !store.isLoaded('supplierCosts')))
const multiCurrencySummary = computed(() => summaryDisplay.value.length > 1)

// --- Customer invoices & payments ------------------------------------------------

/** Customer invoices linked to this order (draft previews and posted documents). */
const customerInvoices = computed(() => financeDocuments.value.filter((row) => {
  const status = String(row.status || '').toUpperCase()
  if (status !== 'POSTED' && status !== 'DRAFT') return false
  return documentBehavior(row) === 'CUSTOMER_INVOICE'
}))

/** Posted, unpaid customer invoices: the only legal allocation targets. */
const payableInvoices = computed(() => customerInvoices.value.filter(row =>
  isPosted(row) && Number(row.outstanding ?? 0) > 0))

/** Draft invoices are previews; posted ones use the authoritative balance. */
function outstandingOf(row: FreightRecord) {
  if (!isPosted(row)) return Number(row.total ?? 0)
  const total = Number(row.total ?? 0)
  const paid = Number(row.paidAmount ?? 0)
  return Number(row.outstanding ?? (total - paid))
}

function partyLabel(id: unknown) {
  const match = store.list('businessParties').find(row => String(row.id) === String(id ?? ''))
  return match ? String(match.legalName || match.displayName || '') : ''
}

function accountLabel(id: unknown) {
  const match = store.list('financialAccounts').find(row => String(row.id) === String(id ?? ''))
  return match ? String(match.accountName || '') : ''
}

function canReceivePayment(row: FreightRecord) {
  return documentBehavior(row) === 'CUSTOMER_INVOICE' && isPosted(row) && Number(row.outstanding ?? 0) > 0 && canReceive.value
}

// --- Receive Payment dialog ------------------------------------------------------

type PayAllocation = {
  id: string
  documentNo: string
  partyId: string
  currency: string
  outstanding: number
  checked: boolean
  amount: number | null
  completed?: boolean
}

type PayDraft = {
  partyId: string
  date: string
  currency: string
  financialAccountId: string
  paymentMethod: string
  amount: number | null
  referenceNumber: string
  remark: string
  allocations: PayAllocation[]
}

const canReceive = computed(() => canCreate.value && canAllocate.value)

const receiptTypeCode = computed(() => {
  const match = store.list('documentTypes').find((row) =>
    String(row.status || 'ACTIVE').toUpperCase() === 'ACTIVE'
    && String(row.accountingBehavior || '').toUpperCase() === 'CUSTOMER_RECEIPT')
  return match ? String(match.code || 'CUSTOMER_RECEIPT') : 'CUSTOMER_RECEIPT'
})

const payOpen = ref(false)
const paySaving = ref(false)
const payError = ref('')
const payFieldErrors = ref<Record<string, string>>({})
const payDraft = ref<PayDraft>(blankPayDraft())
const paymentKey = ref(createIdempotencyKey())
const savedReceiptId = ref('')

function blankPayDraft(): PayDraft {
  return {
    partyId: customerPartyId.value,
    date: todayIso(),
    currency: String(props.job.currency || '') || baseCurrencyCode.value,
    financialAccountId: '',
    paymentMethod: '',
    amount: null,
    referenceNumber: '',
    remark: '',
    allocations: [],
  }
}

function openReceivePayment(invoice?: FreightRecord) {
  if (!canReceive.value || paySaving.value) return
  if (paymentPending.value) {
    payOpen.value = true
    return
  }
  const suggested = invoice || payableInvoices.value.find(row =>
    String(row.partyId || '') === customerPartyId.value && String(row.currency || '') === String(props.job.currency || ''))
  paymentKey.value = createIdempotencyKey()
  savedReceiptId.value = ''
  payDraft.value = {
    ...blankPayDraft(),
    partyId: String(suggested?.partyId || customerPartyId.value),
    currency: String(suggested?.currency || props.job.currency || '') || baseCurrencyCode.value,
    amount: suggested ? outstandingOf(suggested) : null,
    allocations: payableInvoices.value.map((row) => {
      const selected = Boolean(suggested && String(row.id) === String(suggested.id))
      return {
        id: String(row.id),
        documentNo: String(row.documentNo || ''),
        partyId: String(row.partyId || ''),
        currency: String(row.currency || ''),
        outstanding: outstandingOf(row),
        checked: selected,
        amount: selected ? outstandingOf(row) : null,
      }
    }),
  }
  payFieldErrors.value = {}
  payError.value = ''
  payOpen.value = true
  paymentPending.value = true
  formDraft.schedule()
}
watch(payDraft, () => { if (paymentPending.value) formDraft.schedule() }, { deep: true })

/** Allocations the dialog shows: posted invoices for the selected customer. */
function payDialogAllocations(): PayAllocation[] {
  return payDraft.value.allocations.filter(alloc => !alloc.completed && alloc.partyId === payDraft.value.partyId && alloc.currency === payDraft.value.currency)
}

function validatePayment(): boolean {
  const errors: Record<string, string> = {}
  if (!payDraft.value.partyId) errors.partyId = t('validation.required', { field: t('freight.fields.businessParty') })
  if (!payDraft.value.date) errors.date = t('validation.required', { field: t('freight.ui.cols.date') })
  if (!payDraft.value.currency) errors.currency = t('validation.required', { field: t('freight.ui.cols.currency') })
  if (!payDraft.value.financialAccountId) errors.financialAccountId = t('validation.required', { field: t('freight.fields.financialAccount') })
  if (!payDraft.value.paymentMethod.trim()) errors.paymentMethod = t('validation.required', { field: t('freight.fields.paymentMethod') })
  const amount = Number(payDraft.value.amount)
  if (!Number.isFinite(amount) || amount <= 0) errors.amount = t('validation.positive', { field: t('freight.ui.cols.amount') })
  let allocated = 0n
  for (const alloc of payDialogAllocations()) {
    if (!alloc.checked) continue
    const value = Number(alloc.amount)
    if (!Number.isFinite(value) || value <= 0) {
      errors[`alloc-${alloc.id}`] = t('validation.positive', { field: t('freight.ui.cols.amount') })
      continue
    }
    if (value > alloc.outstanding) {
      errors[`alloc-${alloc.id}`] = t('freight.ui.allocationExceedsInvoice')
      continue
    }
    // Cross-currency allocations convert on the server; only same-currency
    // totals are checked against the receipt funds here.
    if (alloc.currency === payDraft.value.currency) allocated += scaledDecimal(value)
  }
  if (allocated > scaledDecimal(amount)) errors.amount = t('freight.ui.allocationExceedsReceipt')
  payFieldErrors.value = errors
  return !Object.keys(errors).length
}

async function reconcilePayment() {
  if (!savedReceiptId.value) return
  const receipt = await lcs.finance.getDocument(savedReceiptId.value)
  const allocations = Array.isArray(receipt.allocations) ? receipt.allocations as Array<Record<string, unknown>> : []
  payDraft.value.allocations = reconcileReceiptAllocations(payDraft.value.allocations, allocations)
}

async function savePayment() {
  if (paySaving.value || !canReceive.value) return
  paySaving.value = true
  payError.value = ''
  try {
    // A lost allocation response may already have settled the invoice. Reconcile
    // the receipt before bounds validation so its keyed retry never gets stuck.
    await reconcilePayment()
    if (!validatePayment()) return
    const payment = structuredClone(toRaw(payDraft.value))
    const amount = Number(payDraft.value.amount)
    const remark = payDraft.value.remark.trim()
    const created = savedReceiptId.value
      ? await lcs.finance.getDocument(savedReceiptId.value)
      : await lcs.finance.createDocument({
      documentType: receiptTypeCode.value,
      date: payDraft.value.date,
      documentDate: payDraft.value.date,
      description: remark || payDraft.value.referenceNumber.trim() || 'Customer receipt',
      partyId: payDraft.value.partyId,
      serviceOrderId: String(props.job.id || ''),
      currency: payDraft.value.currency,
      referenceNumber: payDraft.value.referenceNumber.trim() || undefined,
      remark: remark || undefined,
      paymentMethod: payDraft.value.paymentMethod.trim(),
      financialAccountId: payDraft.value.financialAccountId,
      lines: [{ description: remark || 'Customer receipt', quantity: 1, unitPrice: amount }],
    }, paymentKey.value)
    savedReceiptId.value = String(created.id || '')
    const receiptId = String(created.id || '')
    // Posting makes the receipt allocatable; a closed period leaves it as a
    // draft that can be posted later — allocations are skipped, not lost.
    let posted = isPosted(created)
    if (receiptId && !posted && canPost.value) {
      await lcs.runCommand('finance-post', receiptId, key => lcs.finance.post(receiptId, key), FINANCE_COLLECTIONS)
      posted = true
    }
    for (const alloc of posted ? payment.allocations : []) {
      if (alloc.completed || !alloc.checked || alloc.partyId !== payment.partyId || alloc.currency !== payment.currency) continue
      const allocAmount = Number(alloc.amount)
      if (!Number.isFinite(allocAmount) || allocAmount <= 0) continue
      // Keep a stable allocation key throughout a retry of this payment workflow.
      await lcs.finance.allocate(receiptId, alloc.id, allocAmount, `${paymentKey.value}:${alloc.id}`)
      const completed = payDraft.value.allocations.find(row => row.id === alloc.id)
      if (completed) completed.completed = true
    }
    payOpen.value = false
    paymentPending.value = false
    formDraft.schedule()
    toast.add({ title: t('lcs.common.saved'), color: 'success' })
  }
  catch (error) {
    payError.value = lcs.errorMessage(error)
  }
  finally {
    paySaving.value = false
    try { await reconcilePayment() }
    catch (error) { payError.value ||= lcs.errorMessage(error) }
    store.reload(FINANCE_COLLECTIONS)
    await synchronizeFinance()
    for (const allocation of payDraft.value.allocations) {
      const invoice = financeDocuments.value.find(row => String(row.id) === allocation.id)
      if (invoice) allocation.outstanding = isPosted(invoice) ? outstandingOf(invoice) : 0
    }
    formDraft.schedule()
    formDraft.flush()
  }
}

function clearCellError(cellKey: string) {
  if (!cellErrors.value[cellKey]) return
  cellErrors.value = Object.fromEntries(
    Object.entries(cellErrors.value).filter(([key]) => key !== cellKey),
  )
}
</script>

<template>
  <div class="space-y-4">
    <CommonAppFormErrorSummary v-if="actionError" :form-errors="[actionError]" />
    <UAlert v-if="chargeLoadError" color="error" :description="chargeLoadError">
      <template #actions><UButton :label="t('lcs.common.retry')" @click="loadOrderCharges" /></template>
    </UAlert>
    <UAlert v-if="conflictingRows.length" color="warning" :title="t('freight.ui.draftConflictTitle')">
      <template #actions>
        <UButton color="neutral" :label="t('freight.ui.discardDraft')" @click="conflictingRows = []; formDraft.schedule()" />
      </template>
    </UAlert>
    <UAlert v-if="financeLoadError" color="error" :description="financeLoadError">
      <template #actions>
        <UButton :label="t('actions.retry')" :loading="financeLoading" @click="synchronizeFinance" />
      </template>
    </UAlert>

    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <DashboardAppSummaryCard
        v-for="metric in summaryMetrics"
        :key="metric.key"
        :title="t(metric.labelKey)"
        :value="!remoteDocumentsOrder || ((metric.key === 'totalCharges' || metric.key === 'totalExpenses') && !savedCharges) ? '—' : summaryDisplay.map(group => money(group[metric.key], group.currency)).join(' · ') || '—'"
        :loading="summaryLoading || financeLoading"
        @refresh="synchronizeFinance">
        <span v-if="metric.key === 'totalExpenses' && summaryDisplay.some(group => group.draftExpenses)" class="text-xs text-muted">
          {{ t('freight.ui.estimated') }}
        </span>
      </DashboardAppSummaryCard>
    </div>
    <p v-if="multiCurrencySummary" class="text-xs text-muted">{{ t('freight.ui.summaryPerCurrency') }}</p>

    <div class="flex items-center justify-between gap-2">
      <FreightJobSectionHeader :title="t('freight.ui.financialEntries')" />
      <div class="flex flex-wrap items-center justify-end gap-2">
        <UButton
v-if="canReceive"
icon="i-lucide-hand-coins"
color="neutral"
variant="soft"
          :label="t('freight.ui.receivePayment')"
@click="openReceivePayment()" />
        <UDropdownMenu v-if="canCreate" :items="addEntryItems">
          <UButton
icon="i-lucide-plus"
color="neutral"
variant="soft"
:label="t('freight.ui.addEntry')" />
        </UDropdownMenu>
      </div>
    </div>

    <FreightAppLineTable
      v-if="entries.length || canCreate"
      v-model="entries"
      :table="table"
      :disabled="true"
      :row-disabled="rowDisabled"
      :extra-row-menu-items="rowMenuItems"
      :field-errors="cellErrors"
      :on-cell-edit="clearCellError"
      :empty-text="t('freight.ui.noFinanceEntries')">
      <template #cell-description="{ row }">
        <div class="space-y-1">
          <span>{{ row.description || '—' }}</span>
          <UBadge size="sm" variant="subtle" :color="isPosted(row._source) ? 'success' : 'neutral'">
            {{ row._source?.status || t('freight.reportCatalog.statuses.draft') }}
          </UBadge>
        </div>
      </template>
    </FreightAppLineTable>

    <FreightJobEmptyState
      v-else
      :title="t('freight.ui.noFinanceEntries')"
      :description="t('freight.ui.addEntry')"
      icon="i-lucide-banknote" />

    <UModal v-model:open="detailOpen" :title="t('freight.ui.additionalDetails')">
      <template #body>
        <UBadge v-if="detailDocument" variant="subtle">{{ detailDocument.status }}</UBadge>
        <dl class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div v-for="[label, value] in additionalDetails" :key="String(label)">
            <dt class="text-xs text-muted">{{ t(String(label)) }}</dt>
            <dd class="break-words text-sm">{{ value || '—' }}</dd>
          </div>
        </dl>
        <div v-if="detailDocument?.allocations" class="mt-3 space-y-2">
          <p class="text-sm font-medium">{{ t('freight.ui.invoiceAllocation') }}</p>
          <div v-for="(allocation, index) in (detailDocument.allocations as Array<Record<string, unknown>>)" :key="index" class="text-sm">
            {{ allocation.targetDocumentNo || allocation.targetDocumentId }} · {{ allocation.amount }}
          </div>
        </div>
      </template>
    </UModal>

    <CommonAppEntityDialog
      v-model:open="dialogOpen"
      :title="editingId || dialogRowId ? t('freight.ui.additionalDetails') : t('freight.ui.addEntry')"
      :saving="saving"
      :confirm-label="t('lcs.common.save')"
      :form-errors="dialogError ? [dialogError] : []"
      @confirm="saveEntry">
      <fieldset class="space-y-4" :disabled="saving">
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
      </fieldset>
    </CommonAppEntityDialog>

    <CommonAppEntityDialog
      v-model:open="payOpen"
      :title="t('freight.ui.receivePayment')"
      :saving="paySaving"
      :confirm-label="t('lcs.common.save')"
      :form-errors="payError ? [payError] : []"
      @confirm="savePayment">
      <fieldset class="space-y-4" :disabled="paySaving || Boolean(savedReceiptId)">
        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.fields.businessParty')" required :error="payFieldErrors.partyId">
            <CommonAppReferenceSelect
              v-model="payDraft.partyId"
              reference-key="partyId"
              :items="partyItems"
              class="w-full" />
          </UFormField>
          <UFormField :label="t('freight.pages.serviceOrders')">
            <UInput :model-value="props.jobNo" disabled class="w-full" />
          </UFormField>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.ui.cols.date')" required :error="payFieldErrors.date">
            <UInput v-model="payDraft.date" type="date" class="w-full" />
          </UFormField>
          <UFormField :label="t('freight.ui.cols.currency')" required :error="payFieldErrors.currency">
            <CommonAppReferenceSelect
              v-model="payDraft.currency"
              reference-key="currency"
              :items="currencyItems"
              class="w-full" />
          </UFormField>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.fields.financialAccount')" required :error="payFieldErrors.financialAccountId">
            <CommonAppReferenceSelect
              v-model="payDraft.financialAccountId"
              reference-key="financialAccountId"
              :items="accountItems"
              class="w-full" />
          </UFormField>
          <UFormField :label="t('freight.fields.paymentMethod')" required :error="payFieldErrors.paymentMethod">
            <UInput v-model="payDraft.paymentMethod" class="w-full" maxlength="64" />
          </UFormField>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.ui.cols.amount')" required :error="payFieldErrors.amount">
            <UInputNumber
              v-model="payDraft.amount"
              :min="0"
              :step-snapping="false"
              :increment="false"
              :decrement="false"
              class="w-full"
              :ui="{ base: 'text-right tabular-nums' }" />
          </UFormField>
          <UFormField :label="t('freight.fields.referenceNo')">
            <UInput v-model="payDraft.referenceNumber" class="w-full" maxlength="128" />
          </UFormField>
        </div>

        <UFormField :label="t('freight.fields.remark')">
          <UInput v-model="payDraft.remark" class="w-full" maxlength="1000" />
        </UFormField>
      </fieldset>
      <fieldset class="mt-4 space-y-4" :disabled="paySaving">
        <div v-if="payDialogAllocations().length" class="space-y-2">
          <p class="text-sm font-medium">{{ t('freight.ui.invoiceAllocation') }}</p>
          <div
            v-for="alloc in payDialogAllocations()"
            :key="alloc.id"
            class="flex flex-wrap items-center gap-2 rounded-md border border-default px-3 py-2">
            <UCheckbox v-model="alloc.checked" :label="alloc.documentNo" />
            <span class="text-xs text-muted tabular-nums">
              {{ money(alloc.outstanding, alloc.currency) }} · {{ alloc.currency }}
            </span>
            <UInputNumber
              v-if="alloc.checked"
              v-model="alloc.amount"
              :min="0"
              :max="alloc.outstanding"
              :step-snapping="false"
              :increment="false"
              :decrement="false"
              class="ml-auto w-36"
              :ui="{ base: 'text-right tabular-nums' }" />
            <p v-if="payFieldErrors[`alloc-${alloc.id}`]" class="w-full text-xs text-error">
              {{ payFieldErrors[`alloc-${alloc.id}`] }}
            </p>
          </div>
        </div>
      </fieldset>
      <div class="mt-3 flex justify-end gap-2">
        <UButton
v-if="savedReceiptId"
color="neutral"
:label="t('freight.ui.viewDocument')"
          :to="`/finance/documents/${savedReceiptId}`" />
        <UButton
color="neutral"
:disabled="paySaving"
:label="t('freight.ui.discardDraft')"
          @click="paymentPending = false; payOpen = false; formDraft.schedule()" />
      </div>
    </CommonAppEntityDialog>

    <FreightAllocationDialog
      v-model:open="allocOpen"
      :source="allocSource"
      :targets="allocTargets"
      :saving="allocSaving"
      :errors="allocError ? [allocError] : []"
      @confirm="allocate" />
  </div>
</template>

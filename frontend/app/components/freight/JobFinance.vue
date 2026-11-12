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
import {
  FINANCE_ENTRY_BEHAVIORS,
  INCOME_BEHAVIORS,
} from '~/utils/constants/document-types'
import { todayIso } from '~/utils/format/format-service'
import {
  buildFinanceSummary,
  financeDocumentBehavior,
  type FinanceSummaryEntry,
  type FinanceSummaryGroup,
} from '~/utils/freight/finance-summary'
import {
  FINANCE_DRAFT_FIELDS,
  financeDocumentFingerprint,
  financeDraftSnapshot,
  mergeFinanceDraftRows,
  type FinanceDraftRow,
} from '~/utils/freight/finance-draft'
import { readRecordDraft } from '~/composables/common/useRecordDraft'
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
}>(), {
  editable: false,
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
const financeDocuments = computed<FreightRecord[]>(() => {
  const rows = [...props.documents, ...(props.supplierCosts || []), ...remoteDocuments.value]
  const seen = new Set<string>()
  return rows.filter((row) => {
    const id = String(row.id || '')
    if (!id || seen.has(id) || !isLinkedToJob(row)) return false
    seen.add(id)
    return true
  })
})

async function loadFinanceDocuments(force = false) {
  const orderId = String(props.job.id || '')
  if (!orderId || (!force && remoteDocumentsOrder.value === orderId)) return
  remoteDocumentsOrder.value = orderId
  try {
    const page = await lcs.finance.listDocuments({ page_size: 500 })
    remoteDocuments.value = page.items.filter(isLinkedToJob)
  }
  catch {
    // The invoice/bill projections still render the common cases; a failed
    // supplemental read must not break the Finance tab. Leave it retryable.
    remoteDocuments.value = []
    remoteDocumentsOrder.value = ''
  }
}

watch(() => props.job.id, () => { void loadFinanceDocuments() }, { immediate: true })

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
/** Draft generation is also available after Finish (financial work continues). */
const canGenerateDocuments = computed(() => Boolean(props.job.id) && lcs.can('financial_document.create'))
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
let newRowSeq = 0

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
  const saved = financeDocuments.value
    .filter(isLinkedToJob)
    .map((document) => {
      const row = rowFromDocument(document)
      const prior = previous.get(row.id)
      if (prior && isDraft(row._source)) {
        // A draft the user is editing keeps every edited field: a reload never
        // silently moves a date, party, reference or remark.
        const kept = Object.fromEntries(FINANCE_DRAFT_FIELDS.map(field => [field, prior[field]]))
        return { ...row, ...kept }
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

function rowDraftChanged(row: FinanceRow): boolean {
  if (row._isNew) return true
  const source = row._source
  if (!source) return false
  if (String(source.status || '').toUpperCase() !== 'DRAFT') return false
  const canonical = rowFromDocument(source)
  return FINANCE_DRAFT_FIELDS.some(field =>
    String(row[field] ?? '') !== String(canonical[field] ?? ''))
}

const financeDraftDirty = computed(() => entries.value.some(rowDraftChanged))

const formDraft = useRecordFormDraft<Record<string, unknown>>({
  collection: () => 'serviceOrderFinance',
  scope: () => String(auth.user?.id || 'anon'),
  recordId: () => String(props.job.id || props.jobNo || ''),
  baseUpdatedAt: () => '',
  model: () => ({ rows: financeDraftSnapshot(entries.value.filter(rowDraftChanged)) }),
  apply: (stored) => {
    const rows = (stored as { rows?: unknown }).rows
    if (!Array.isArray(rows) || !rows.length) return
    const merged = mergeFinanceDraftRows(entries.value, rows as FinanceDraftRow[], row => ({
      id: row.id,
      status: row._source?.status,
      // `_baseUpdatedAt` holds the server stamp or a content fingerprint.
      updatedAt: row._baseUpdatedAt,
    }))
    entries.value = merged.rows
    if (merged.skipped) {
      actionError.value = t('freight.ui.financeDraftPartial', { count: merged.skipped })
    }
  },
  isDirty: () => financeDraftDirty.value,
  canDraft: () => props.editable && financeDraftRestored.value,
})

function restoreFinanceDraft() {
  if (financeDraftRestored.value) return
  if (!props.editable) {
    financeDraftRestored.value = true
    return
  }
  const key = formDraft.key.value
  if (!key) return
  const stored = readRecordDraft(key, 'local')
  // Wait for the related collections before declaring "no draft": an empty
  // first render must not consume the recovery slot.
  if (!stored && !financeDocuments.value.length && !entries.value.some(row => row._isNew)) return
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
  () => financeDocuments.value.map(document => `${String(document.id || '')}:${String(document.updatedAt || '')}`).join(','),
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
  syncRows()
  restoreFinanceDraft()
})

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
    const saved = row._isNew
      ? await lcs.finance.createDocument(payload)
      : await lcs.finance.saveDraft(payload as FreightRecord)
    if (saved?.id) {
      // A delayed response must not replace a cell edited while the request was
      // in flight. Adopt the server identity/stamp only; newer local values stay.
      const current = entries.value.find(item => item.id === row.id)
      const changedSinceRequest = current
        ? FINANCE_DRAFT_FIELDS.some(field => String(current[field] ?? '') !== String(row[field] ?? ''))
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
    store.reload()
    void loadFinanceDocuments(true)
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
      const saved = await lcs.finance.saveDraft({
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
      if (saved?.id) {
        entries.value = entries.value.map(item =>
          item.id === editingId.value ? rowFromDocument(saved) : item)
      }
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
    void loadFinanceDocuments(true)
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
    void loadFinanceDocuments(true)
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

const summaryEntries = computed<FinanceSummaryEntry[]>(() => entries.value.map((row) => {
  const source = row._source
  const status = source ? financeDomainStatus(source.status) : 'DRAFT'
  const behavior = source ? documentBehavior(source) : behaviorOfCode(row.type)
  const authoritative = status === 'POSTED'
  const total = authoritative ? Number(source?.total ?? row.amount) : Number(row.amount)
  const paid = authoritative ? Number(source?.paidAmount ?? 0) : 0
  const outstanding = authoritative
    ? Number(source?.outstanding ?? (total - paid))
    : 0
  return {
    id: row.id,
    status,
    currency: row.currency || String(source?.currency || ''),
    behavior,
    total,
    paidAmount: paid,
    outstanding,
  }
}))

const financeSummary = computed(() => buildFinanceSummary({
  charges: props.charges || [],
  entries: summaryEntries.value,
  internalCharges: (props.charges || [])
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

type SummaryMetricKey =
  | 'totalCharges'
  | 'chargedAmount'
  | 'unchargedAmount'
  | 'totalExpenses'
  | 'netAmount'
  | 'outstandingBalance'

const summaryMetrics: Array<{ key: SummaryMetricKey, labelKey: string }> = [
  { key: 'totalCharges', labelKey: 'freight.ui.totalCharges' },
  { key: 'chargedAmount', labelKey: 'freight.ui.chargedAmount' },
  { key: 'unchargedAmount', labelKey: 'freight.ui.unchargedAmount' },
  { key: 'totalExpenses', labelKey: 'freight.ui.totalExpenses' },
  { key: 'netAmount', labelKey: 'freight.ui.netAmount' },
  { key: 'outstandingBalance', labelKey: 'freight.ui.outstandingBalance' },
]

function metricValue(group: FinanceSummaryGroup, key: SummaryMetricKey) {
  return group[key]
}

function metricTone(group: FinanceSummaryGroup, key: SummaryMetricKey) {
  const value = group[key]
  if (key === 'netAmount') return value < 0 ? 'text-error' : 'text-primary'
  if (key === 'unchargedAmount') return value < 0 ? 'text-warning' : 'text-highlighted'
  return 'text-highlighted'
}

/** Do not keep a permanent skeleton if a supplemental collection is denied or
 *  unreachable; after this window the available (possibly empty) data is shown. */
const summaryWaitExpired = ref(false)
const summaryWaitTimer = setTimeout(() => { summaryWaitExpired.value = true }, 8000)
onBeforeUnmount(() => clearTimeout(summaryWaitTimer))

const summaryLoading = computed(() => !summaryWaitExpired.value && (props.summaryLoading
  || (!(props.charges || []).length && !store.isLoaded('jobCharges'))
  || !store.isLoaded('debitNotes')
  || !store.isLoaded('supplierCosts')))
const multiCurrencySummary = computed(() => financeSummary.value.length > 1)

// --- Generated draft documents -------------------------------------------------
const refreshingDocuments = ref(false)

/** Explicit retry/generation; ordinary Save never calls this. */
async function refreshFinancialDocuments() {
  if (refreshingDocuments.value || !props.job.id) return
  refreshingDocuments.value = true
  actionError.value = ''
  try {
    const result = await lcs.jobs.refreshFinancialDocuments(String(props.job.id))
    if (result.warnings?.length) actionError.value = result.warnings.join(' ')
    toast.add({ title: t('freight.ui.financialDraftsRefreshed'), color: 'success' })
    store.reload()
    await loadFinanceDocuments(true)
  }
  catch (error) {
    actionError.value = apiErrorMessage(error, t('freight.ui.saveFailed'))
  }
  finally {
    refreshingDocuments.value = false
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
    <div class="flex flex-wrap items-center justify-between gap-2">
      <FreightJobSectionHeader :title="t('freight.jobSections.finance')" />
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          v-if="canGenerateDocuments"
          icon="i-lucide-refresh-cw"
          color="neutral"
          variant="outline"
          :label="t('freight.ui.refreshFinancialDrafts')"
          :loading="refreshingDocuments"
          @click="refreshFinancialDocuments" />
        <UButton
          v-if="canCreate"
          icon="i-lucide-plus"
          color="neutral"
          variant="soft"
          :label="t('freight.ui.addEntry')"
          @click="addEntry" />
      </div>
    </div>

    <CommonAppFormErrorSummary v-if="actionError" :form-errors="[actionError]" />

    <section class="space-y-2">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="text-sm font-semibold text-highlighted">
          {{ t('freight.ui.financeSummary') }}
        </h3>
        <UBadge
          v-if="!summaryLoading && financeSummary.some(group => group.estimated)"
          color="warning"
          variant="subtle"
          size="sm">
          {{ t('freight.ui.estimated') }}
        </UBadge>
      </div>

      <div
        v-if="summaryLoading"
        class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6"
        aria-busy="true">
        <div
          v-for="metric in summaryMetrics"
          :key="metric.key"
          class="min-h-[4.5rem] rounded-lg border border-default bg-elevated/50 p-3">
          <p class="truncate text-xs text-muted">{{ t(metric.labelKey) }}</p>
          <p class="mt-1 text-lg font-semibold tabular-nums text-muted">—</p>
        </div>
      </div>

      <div
        v-else-if="!financeSummary.length"
        class="rounded-lg border border-default bg-elevated/50 p-3 text-sm text-muted">
        {{ t('freight.ui.summaryUnavailable') }}
      </div>

      <div v-else class="space-y-3">
        <div v-for="group in financeSummary" :key="group.currency" class="space-y-1.5">
          <p v-if="multiCurrencySummary" class="text-xs font-medium text-muted">
            {{ group.currency || t('freight.ui.cols.currency') }}
          </p>
          <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <div
              v-for="metric in summaryMetrics"
              :key="metric.key"
              class="min-h-[4.5rem] rounded-lg border border-default bg-elevated/50 p-3">
              <p class="truncate text-xs text-muted">{{ t(metric.labelKey) }}</p>
              <p
                class="mt-1 truncate text-lg font-semibold tabular-nums"
                :class="metricTone(group, metric.key)">
                {{ money(metricValue(group, metric.key), group.currency) }}
              </p>
              <p
                v-if="metric.key === 'netAmount'"
                class="mt-0.5 truncate text-[11px] text-muted">
                {{ group.estimated ? t('freight.ui.estimatedMargin') : t('freight.ui.postedMargin') }}
              </p>
              <p
                v-else-if="metric.key === 'outstandingBalance'"
                class="mt-0.5 truncate text-[11px] text-muted">
                {{ t('freight.ui.posted') }}
              </p>
            </div>
          </div>
        </div>
        <p v-if="multiCurrencySummary" class="text-[11px] text-muted">
          {{ t('freight.ui.summaryPerCurrency') }}
        </p>
      </div>
    </section>

    <FreightAppLineTable
      v-if="entries.length || canCreate"
      v-model="entries"
      :table="table"
      :disabled="editable !== true"
      :row-disabled="rowDisabled"
      :extra-row-menu-items="rowMenuItems"
      :field-errors="cellErrors"
      :on-cell-edit="clearCellError"
      :empty-text="t('freight.ui.noFinanceEntries')" />

    <FreightJobEmptyState
      v-else
      :title="t('freight.ui.noFinanceEntries')"
      :description="t('freight.ui.addEntry')"
      icon="i-lucide-banknote" />

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

<script setup lang="ts">
import type { DropdownMenuItem, TableColumn } from '@nuxt/ui'
import type { PaginationState } from '@tanstack/vue-table'
import { h } from 'vue'
import { UBadge, ULink } from '#components'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import {
  formatFreightCell,
  freightStatusBadge,
  useFreightLabel,
  useFreightRouteModule, formatMoney 
} from '~/composables/freight/useFreight'
import { useLcs } from '~/composables/freight/useLcs'
import type { FreightRecord } from '~/types/record'
import type { ExportFilters, ExportRequest } from '~/types/export'
import type { SourcePermission } from '~/types/domain'
import { freightModules, type FreightField, type FreightSelectOption } from '~/config/freight-modules'
import type { ExcelModuleInfo } from '~/composables/useExcelIo'
import { chargeDomainStatus, financeDomainStatus } from '~/utils/freight/states'
import { quotationActionAvailability } from '~/utils/freight/quotation-actions'
import { formatRevisionNo } from '~/utils/freight/quotation-revisions'
import { isMoneyKey, isNumericKey, jobForQuotation, jobWorkspacePath, workspaceSectionForPath } from '~/utils/freight/job-workspace'
import { enrichJobListRows } from '~/utils/freight/job-list'
import { limitFilterSelects, matchesFilter, parseFilterQuery } from '~/utils/filter/values'
import { isFilterValueActive } from '~/utils/filter/select-ui'
import { pageActionPermission } from '~/utils/freight/page-access'
import { listTableRowMetaColumn, listTableSelectColumn } from '~/utils/table/list-columns'
import { listTablePageSummary, listTableSelectedIds } from '~/utils/table/list-table'
import { type ListSortKind, type ListSortSelection, listSortKindFor } from '~/utils/table/list-sort'
import { documentSequenceTypeLabel, isDocumentSequenceType } from '~/utils/document-sequences'
import { normalizeAuditLog, resolveAuditEntityPath } from '~/utils/freight/audit-logs'
import { useModuleList } from '~/composables/freight/useModuleList'
import { useModuleRecord } from '~/composables/freight/useModuleRecord'
import { useRequotation } from '~/composables/freight/useRequotation'
import { useRecordStatus } from '~/composables/freight/useRecordStatus'
import { useLcsRepositories } from '~/repositories'
import { referenceOptionSource, referenceSelectItems } from '~/utils/freight/reference-options'
import { isProtectedManagementRecord } from '~/utils/auth/protected-system-records'

const { module, route } = useFreightRouteModule()
const store = useFreightStore()
const auth = useAuthStore()
const lcs = useLcs()
const { t } = useI18n()
const { fieldLabel, moduleTitle, moduleSingular } = useFreightLabel()
const { setTitle, setBreadcrumbs, clear } = useAppHeader()
const { confirm, setLoading: setConfirmLoading, dismiss: dismissConfirm } = useConfirm()
const toast = useToast()

const q = ref('')
const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 20 })
const filters = reactive<Record<string, string[]>>({})
const rowSelection = ref<Record<string, boolean>>({})
/** Page-level refusals from row / bulk commands (never a toast). */
const pageErrors = ref<string[]>([])

// Background (fire-and-forget) writes publish their failure on the store.
watch(() => store.lastError, (message) => {
  if (message && !pageErrors.value.includes(message)) pageErrors.value = [...pageErrors.value, message]
})
const pending = ref(false)
const dateFrom = ref('')
const dateTo = ref('')
const sort = ref<ListSortSelection>(null)

const current = computed(() => module.value)
const moduleList = useModuleList(current)
const moduleRecord = useModuleRecord(current)

/**
 * Status changes are policy-driven: the backend says which transitions exist
 * from the record's current status and which of them this caller may run, so
 * the row menu can only ever offer a legal action.
 */
const {
  busyId,
  menuItem: statusMenuItem,
  transitionsOf,
  run: statusRun,
} = useRecordStatus(module, {
  onError: (message) => { pageErrors.value = [message] },
  onChanged: refreshList,
})
const isJobList = computed(() => current.value?.collection === 'jobs')
const dateField = computed(() => {
  const fields = current.value?.fields || []
  return fields.find(field => field.type === 'date' || field.type === 'datetime' || field.key === 'date' || /date$/i.test(field.key))?.key
    || current.value?.columns.find(column => /date/i.test(column.key))?.key
})
/** The sort key must exist on the current module or the backend would ignore it. */
const sortKey = computed(() => {
  const active = sort.value
  if (!active || !current.value) return undefined
  return current.value.columns.some(column => column.key === active.key) ? active.key : undefined
})
const sortDir = computed(() => (sortKey.value ? sort.value?.dir : undefined))

// --- Period closing validation ------------------------------------------------
// Read-side panel: closing stays a status transition; this only renders the
// backend's own pre-closing checks, warnings and base-currency balances.
const validationOpen = ref(false)
const validatingId = ref('')
const validationRow = ref<Record<string, unknown> | null>(null)
const validationReport = ref<Record<string, unknown> | null>(null)
const validationError = ref('')

const financeRepo = useLcsRepositories().finance
const { requoteFromServiceOrder } = useRequotation({
  confirm,
  setConfirmLoading,
  dismissConfirm,
  toast,
  onError: message => { pageErrors.value = [message] },
})

/** Collection-scoped empty state copy (e.g. "No accounting periods found"). */
const emptyTitle = computed(() =>
  current.value?.collection === 'accountingPeriods' ? t('freight.ui.periodClosing.noPeriods') : '')

async function runValidationForRow(row: Record<string, unknown>) {
  validationRow.value = row
  validationOpen.value = true
  validatingId.value = String(row.id || '')
  validationError.value = ''
  try {
    validationReport.value = (await financeRepo.closingValidation(String(row.id))) as unknown as Record<string, unknown>
  }
  catch (cause) {
    validationError.value = lcs.errorMessage(cause)
  }
  finally {
    validatingId.value = ''
  }
}

const manualRefreshing = ref(false)

async function refreshList(quiet = false) {
  if (!current.value) return
  // A manual reload keeps the table data visible; only the header icon spins.
  if (quiet) manualRefreshing.value = true
  else pending.value = true
  try {
    await moduleList.refresh({
      q: q.value,
      filters,
      paginate: false,
      dateField: dateField.value,
      dateFrom: dateFrom.value,
      dateTo: dateTo.value,
      sortKey: sortKey.value,
      sortDir: sortDir.value,
    })
  }
  finally {
    manualRefreshing.value = false
    pending.value = false
  }
}

watch([current, q, filters, dateFrom, dateTo, dateField, sort], () => { void refreshList() }, { immediate: true, deep: true })

function rowMatchesToolbarFilters(row: FreightRecord): boolean {
  const source = current.value?.collection === 'auditLogs' ? normalizeAuditLog(row) : row
  if (q.value) {
    const needle = q.value.toLowerCase()
    if (!Object.values(source).join(' ').toLowerCase().includes(needle)) return false
  }
  for (const [key, selected] of Object.entries(filters)) {
    if (!isFilterValueActive(selected)) continue
    const value = source[key] ?? source[key.toLowerCase()] ?? source[key.toUpperCase()]
    if (!matchesFilter(value, selected)) return false
  }
  const field = dateField.value
  if (field && (dateFrom.value || dateTo.value)) {
    const day = String(source[field] ?? '').slice(0, 10)
    if (!day) return false
    if (dateFrom.value && day < dateFrom.value) return false
    if (dateTo.value && day > dateTo.value) return false
  }
  return true
}

const result = computed(() => {
  if (!current.value) return { rows: [], total: 0, all: [] }
  let all = moduleList.items.value
  if (isJobList.value) {
    all = enrichJobListRows(all, {
      containers: store.list('actualContainers'),
      tasks: store.list('serviceComponents'),
      charges: store.list('jobCharges'),
      shipments: store.list('shipments'),
    })
  }
  // The Service Charges page lists standalone charges only: linked charges
  // belong to their Service Order's Service Charge tab.
  if (current.value?.collection === 'jobCharges') {
    all = all.filter(row => !String(row.jobNo || '').trim())
  }
  // The backend module list endpoints don't understand the toolbar filter
  // fields, so apply them (and the search box) on the loaded page client-side.
  all = all.filter(rowMatchesToolbarFilters)
  return { rows: all, total: all.length, all }
})
const isTableOnly = computed(() => Boolean(current.value?.tableOnly))
/**
 * Master Data write gate. Narrow matrix roles hold per-screen action codes
 * (`master.party_roles.create`, `master.transport_assets.update` — the latter
 * also covers the asset identity types and capacity units pages, mirroring the
 * backend collection map); the legacy coarse aggregate stays accepted. The
 * backend guards remain authoritative — a UI without the codes only hides
 * actions it could not perform.
 */
function canMasterAction(action: 'create' | 'update' | 'delete'): boolean {
  if (auth.user?.pageAccess?.includes('ALL_PAGES')) return true
  const module = current.value
  if (!module || module.group !== 'master') return false
  if (lcs.can('master.reference.manage')) return true
  // Document types keep the coarse reference guard (backend write commands
  // accept only `master.reference.manage` / `configuration.manage`).
  const perPageCode = module.collection === 'documentTypes'
    ? ''
    : pageActionPermission(module.permission, action)
  const code = perPageCode != '' ? perPageCode : 'master.reference.manage'
  return code !== '' && auth.canAccessPage(code)
}
const canManageModule = computed(() => {
  if (!current.value) return false
  if (auth.user?.pageAccess?.includes('ALL_PAGES')) return true
  if (current.value.collection === 'chartOfAccounts' || current.value.collection === 'financialAccounts') return lcs.can('chart_of_accounts.manage')
  if (current.value.collection === 'users') return lcs.can('user.manage')
  if (current.value.collection === 'roles') return lcs.can('role.manage')
  if (current.value.group === 'master') return canMasterAction('create') || canMasterAction('update') || canMasterAction('delete')
  if (current.value.group === 'configuration') return auth.canAccessPage('configuration.manage')
  return true
})
/**
 * Business/finance/administration create flows that are not otherwise gated:
 * the New button follows the same per-page create code (matrix) the backend
 * collection command enforces, with the entity capability code (or the legacy
 * aggregate capability that predates the matrix) still accepted. Accounting
 * periods have no capability code — the generate/POST command is
 * `accounting_period.update` and the matrix code is authoritative.
 */
const PAGE_CREATE_GATES: Record<string, { capability: SourcePermission | '', legacy?: readonly string[] }> = {
  quotations: { capability: 'quotation.create' },
  jobCharges: { capability: 'service_charge.create' },
  debitNotes: { capability: 'financial_document.create' },
  journals: { capability: 'journal_entry.create' },
  accountingPeriods: { capability: '' },
  postingRules: { capability: 'posting_rule.create' },
  documentSequences: { capability: 'document_sequence.create', legacy: ['configuration.manage'] },
}

const canCreate = computed(() => {
  if (!current.value?.canCreate || current.value.readOnly) return false
  if (current.value.group === 'master') return canMasterAction('create')
  const gate = PAGE_CREATE_GATES[current.value.collection]
  if (gate) {
    const matrixCode = pageActionPermission(current.value.permission, 'create')
    return (gate.capability ? lcs.can(gate.capability) : false)
      || (gate.legacy?.some(code => hasRawSourceCapability(auth.user, code)) ?? false)
      || (matrixCode ? auth.canAccessPage(matrixCode) : false)
  }
  if (!canManageModule.value) return false
  return true
})
const canMutate = computed(() => {
  if (!current.value || current.value.readOnly || !canManageModule.value) return false
  if (current.value.group !== 'master') return true
  return canMasterAction('update') || canMasterAction('delete')
})
const deactivationOnly = computed(() => current.value?.group === 'master' || current.value?.collection === 'documentSequences')

const selectedIds = computed(() => listTableSelectedIds(rowSelection.value))

const selectedRecords = computed(() => {
  const ids = new Set(selectedIds.value)
  return current.value ? store.list(current.value.collection).filter(row => ids.has(String(row.id))) : []
})

/** Bulk action mirrors the row rule: active records deactivate, inactive records delete. */
const bulkAction = computed<{ kind: 'delete' | 'deactivate', label: string, icon: string, color: 'error' | 'warning' } | null>(() => {
  if (!selectedIds.value.length || !canMutate.value) return null
  const rows = selectedRecords.value
  if (rows.some(row => isProtectedManagementRecord(current.value?.collection, row))) return null
  const statuses = rows.map(recordStatusValue)
  const statusBased = rows.length > 0 && statuses.every(status => status === 'ACTIVE' || status === 'INACTIVE')
  if (statusBased && statuses.some(status => status === 'ACTIVE')) {
    // Deactivating is a status update; a delete-only grant must not be offered it.
    if (current.value?.group === 'master' && !canMasterAction('update')) return null
    return { kind: 'deactivate', label: t('freight.ui.deactivate'), icon: 'i-lucide-circle-off', color: 'warning' }
  }
  if (statusBased) {
    return { kind: 'delete', label: t('freight.ui.delete'), icon: 'i-lucide-trash-2', color: 'error' }
  }
  return deactivationOnly.value
    ? { kind: 'deactivate', label: t('freight.ui.deactivate'), icon: 'i-lucide-circle-off', color: 'warning' }
    : { kind: 'delete', label: t('freight.ui.delete'), icon: 'i-lucide-trash-2', color: 'error' }
})

// --- Excel Import & Export (allowlisted by the backend catalog) ---
const excelIo = useExcelIo()
const excelModules = ref<ExcelModuleInfo[]>([])
const excelLoaded = ref(false)

async function loadExcelModules() {
  // The catalog answers 401 until the session is restored and one-shot loading
  // left the ⋯ menu empty forever after any transient failure, so an empty
  // retry: once the user becomes known, and when the page re-activates.
  if (!auth.user) return
  try {
    excelModules.value = await excelIo.modules()
    excelLoaded.value = true
  }
  catch {
    excelLoaded.value = false
  }
}
void loadExcelModules()
watch(() => auth.user?.id, id => { if (id && !excelLoaded.value) void loadExcelModules() })
onActivated(() => { if (!excelLoaded.value) void loadExcelModules() })
const excelModule = computed(() => excelModules.value.find(item => item.key === current.value?.collection) ?? null)

const exportOpen = ref(false)
const exporting = ref(false)
const matchingCount = ref<number | null>(null)
const counting = ref(false)
let countTimer: ReturnType<typeof setTimeout> | undefined
let countToken = 0

const exportUsers = computed(() => store.list('users').map(user => ({
  label: String(user.displayName || user.username || user.id),
  value: String(user.id),
})))
const exportStatuses = computed(() => {
  const filter = current.value?.filters?.find(item => item.key === 'status')
  return filter ? filterItems(filter) : []
})

function exportFilterParams(filters: ExportFilters): Record<string, string> {
  // Only the export filter keys are sent; scope/fieldCodes stay out.
  const map: Record<string, string> = {
    dateFrom: 'date_from',
    dateTo: 'date_to',
    updatedBy: 'updated_by',
    status: 'status',
  }
  return Object.fromEntries(Object.entries(filters).map(([key, value]) => [map[key], value]).filter(([key]) => Boolean(key)))
}

/** Debounced matching-record count for the dialog (cancelled by a newer change). */
function requestExportCount(filters: ExportFilters) {
  matchingCount.value = null
  counting.value = Boolean(excelModule.value)
  if (countTimer) clearTimeout(countTimer)
  const token = ++countToken
  countTimer = setTimeout(async () => {
    if (!excelModule.value) return
    try {
      const data = await excelIo.exportCount(excelModule.value.key, exportFilterParams(filters))
      if (token === countToken) {
        matchingCount.value = data.count
        counting.value = false
      }
    }
    catch {
      if (token === countToken) {
        counting.value = false
        matchingCount.value = null
      }
    }
  }, 400)
}

const currentPageIds = computed(() => {
  const start = pagination.value.pageIndex * pagination.value.pageSize
  return result.value.rows.slice(start, start + pagination.value.pageSize).map(row => String(row.id))
})

async function runExport(request: ExportRequest) {
  if (!excelModule.value) return
  exporting.value = true
  pageErrors.value = []
  try {
    const ids = request.scope === 'selected' ? selectedIds.value : request.scope === 'current_page' ? currentPageIds.value : []
    await excelIo.exportRows(excelModule.value.key, ids, {
      format: request.format,
      filters: exportFilterParams(request.filters ?? {}),
    })
    exportOpen.value = false
    toast.add({ title: t('lcs.exportDialog.completed'), color: 'success' })
  }
  catch (error) {
    pageErrors.value = [lcs.errorMessage(error)]
  }
  finally {
    exporting.value = false
  }
}

const importOpen = ref(false)

/**
 * Header ⋯ menu. One Export entry opens the filter dialog; Import keeps its
 * own dialog. Creating a record keeps its primary header button.
 */
const headerMenuItems = computed<DropdownMenuItem[][]>(() => {
  const module_ = excelModule.value
  const io: DropdownMenuItem[] = []
  if (module_?.exportEnabled && lcs.can(module_.viewPermission as never)) {
    io.push({ label: t('actions.exportData'), icon: 'i-lucide-download', onSelect: () => { exportOpen.value = true } })
  }
  if (module_?.importEnabled && lcs.can(module_.managePermission as never)) {
    io.push({ label: t('actions.importData'), icon: 'i-lucide-upload', onSelect: () => { importOpen.value = true } })
  }
  return io.length ? [io] : []
})

function runBulkAction() {
  const action = bulkAction.value
  if (!action) return
  if (action.kind === 'delete') void deleteIds(selectedIds.value)
  else void deactivateIds(selectedIds.value)
}

/** Service Charges page: one combined finance invoice from the selected charges. */
const showCombinedInvoice = computed(() =>
  current.value?.collection === 'jobCharges'
  && selectedIds.value.length > 0
  && lcs.can('service_charge.convert_to_invoice'))

const combinedInvoiceBusy = ref(false)

async function createCombinedInvoiceForSelection() {
  pageErrors.value = []
  const ids = selectedIds.value
  combinedInvoiceBusy.value = true
  try {
    const invoice = await lcs.runCommand('charge.combined-invoice', ids.join(','), key =>
      lcs.charges.createCombinedInvoice(ids, key))
    rowSelection.value = {}
    toast.add({ title: t('freight.ui.draftInvoiceCreated'), color: 'success' })
    await navigateTo(`/finance/documents/${String(invoice.id)}`)
  }
  catch (error) {
    pageErrors.value = [lcs.errorMessage(error)]
  }
  finally {
    combinedInvoiceBusy.value = false
  }
}

/** Lights the collapsed filter-menu button when any toolbar filter is set. */
const hasActiveFilters = computed(() => Boolean(
  Object.values(filters).some(value => isFilterValueActive(value))
  || isFilterValueActive(dateFrom.value)
  || isFilterValueActive(dateTo.value),
))

/** Toolbar shows at most 3 selects beside the date range, 4 without it. */
const visibleFilters = computed(() => limitFilterSelects(
  current.value?.filters || [],
  Boolean(dateField.value),
  filter => filter.key === 'status' || filter.key === 'workflowStatus',
))

watch(current, (value) => {
  if (!value) return
  setTitle(moduleTitle(value))
  setBreadcrumbs([{ label: moduleTitle(value) }])
  rowSelection.value = {}
  for (const key of Object.keys(filters)) Reflect.deleteProperty(filters, key)
  for (const filter of value.filters || []) {
    filters[filter.key] = parseFilterQuery(route.query[filter.key])
  }
}, { immediate: true })

onBeforeUnmount(clear)

usePageSeo({
  title: () => current.value ? moduleTitle(current.value) : t('freight.pages.dashboard'),
})

watch([q, filters, dateFrom, dateTo, sort], () => {
  rowSelection.value = {}
  pagination.value = { ...pagination.value, pageIndex: 0 }
}, { deep: true })

const jobsByNo = computed(() => {
  const map = new Map<string, string>()
  for (const job of store.list('jobs')) {
    map.set(String(job.jobNo || ''), String(job.id))
  }
  return map
})

function jobLinkFor(jobNo: unknown) {
  if (!auth.canAccessPage('operations.service_orders.view')) return ''
  const id = jobsByNo.value.get(String(jobNo || ''))
  if (!id || !current.value) return ''
  return jobWorkspacePath(id, workspaceSectionForPath(current.value.path))
}

function recordPath(id: unknown) {
  if (!current.value) return '/'
  return `${current.value.path}/${id}`
}

function cellText(row: Record<string, unknown>, key: string) {
  const source = current.value?.collection === 'auditLogs' ? normalizeAuditLog(row as FreightRecord) : row
  if (key === 'revisionNo') return formatRevisionNo(source[key])
  // The revision roll-up is authoritative; older JSON copies may only carry `amount`.
  const value = key === 'total' && source.total == null ? source.amount : source[key]
  return formatFreightCell(value, key, String(source.currency || '').trim() || undefined)
}

/** Service Order number: direct id first, then the job list by number. */
function serviceOrderLinkFor(row: Record<string, unknown>) {
  if (!auth.canAccessPage('operations.service_orders.view')) return ''
  const id = String(row.serviceOrderId || '').trim()
  if (id) return `/service-orders/${id}`
  return jobLinkFor(row.serviceOrderNo)
}

/** Linked finance invoice, when the charge has one and the user may open it. */
function invoiceLinkFor(row: Record<string, unknown>) {
  if (!auth.canAccessPage('finance.financial_documents.view')) return ''
  const id = String(row.financialDocumentId || '').trim()
  return id ? `/finance/documents/${id}` : ''
}

/** Source financial document of a journal entry. */
function sourceDocumentLinkFor(row: Record<string, unknown>) {
  if (!auth.canAccessPage('finance.financial_documents.view')) return ''
  const id = String(row.sourceDocumentId || '').trim()
  return id ? `/finance/documents/${id}` : ''
}

/** Source quotation of a service order: real id from the API, number as fallback. */
function quotationLinkFor(row: Record<string, unknown>) {
  if (!auth.canAccessPage('sales.quotations.view')) return ''
  const id = String(row.quotationId || '').trim()
  if (id) return `/quotations/${id}`
  const quotationNo = String(row.quotationNo || '').trim()
  if (!quotationNo) return ''
  const found = store.list('quotations').find(item => String(item.quotationNo || '') === quotationNo)
  return found?.id ? `/quotations/${String(found.id)}` : ''
}

function auditEntityLinkFor(row: Record<string, unknown>) {
  if (current.value?.collection !== 'auditLogs') return ''
  return resolveAuditEntityPath(
    normalizeAuditLog(row as FreightRecord),
    freightModules,
    collection => store.list(collection),
    permission => auth.canAccessPage(permission),
  )
}

const pageSummary = computed(() =>
  listTablePageSummary(t, result.value.total, pagination.value),
)

function rowMenuItems(row: Record<string, unknown>): DropdownMenuItem[][] {
  const collection = current.value?.collection
  // Quotations (Edit / Convert / Delete / Duplicate) and Service Orders
  // (Edit / Finish / Re-Quotation) own their exact action sets.
  const items: DropdownMenuItem[] = collection === 'quotations' || collection === 'jobs'
    ? []
    : [
        {
          label: t('freight.ui.open'),
          icon: 'i-lucide-eye',
          onSelect: () => openRow(row),
        },
      ]
  if (collection === 'documentSequences') {
    items[0] = {
      label: t('lcs.rowActions.detail'),
      icon: 'i-lucide-eye',
      onSelect: () => openRow(row),
    }
    if (canMutate.value) {
      items.push({
        label: t('freight.ui.edit'),
        icon: 'i-lucide-pencil',
        onSelect: () => openRow(row),
      })
    }
  }
  if (collection === 'quotations') {
    const relatedJob = jobForQuotation(store.list('jobs'), row)
    const availability = quotationActionAvailability(
      row.status,
      {
        updateDraft: lcs.can('quotation.update_draft'),
        submit: lcs.can('quotation.submit'),
        convert: lcs.can('quotation.convert'),
      },
      { hasServiceOrder: Boolean(relatedJob) },
    )
    if (availability.edit) {
      items.push({ label: t('freight.ui.editDraft'), icon: 'i-lucide-pencil', onSelect: () => openRow(row) })
    }
    // A quotation stays a reusable commercial reference: "Convert to Service
    // Order" confirms, then creates the order directly (the shared backend
    // conversion also backs the Service Order form's quotation selector).
    if (availability.convert && lcs.can('service_order.create')) {
      items.push({ label: t('freight.ui.convertServiceOrder'), icon: 'i-lucide-arrow-right', onSelect: () => { void convertRowToServiceOrder(row) } })
    }
    // Deletion is refused by the backend while a service order depends on the
    // quotation; the refusal message renders above the list.
    if (canMutate.value && lcs.can('quotation.delete')) {
      items.push({ label: t('lcs.rowActions.delete'), icon: 'i-lucide-trash-2', color: 'error', onSelect: () => { void runRowAction('delete', row) } })
    }
    // Duplicate opens the existing New Quotation form prefilled from this
    // quotation; a new Quotation No. is allocated only on save.
    if (lcs.can('quotation.create')) {
      items.push({ label: t('lcs.rowActions.duplicate'), icon: 'i-lucide-copy', onSelect: () => { void navigateTo(`/quotations/new?duplicate=${row.id}`) } })
    }
  }
  else if (collection === 'jobs') {
    // Exactly three actions: Edit, Finish, Re-Quotation. Finish is the record's
    // own status transition (its confirmation, validation and permission come
    // from the backend policy); it is disabled when the order is already
    // finished, so no other status action is offered here.
    items.push({ label: t('freight.ui.edit'), icon: 'i-lucide-pencil', onSelect: () => openRow(row) })
    const finishTransition = transitionsOf(row).find(transition => transition.action === 'finish')
    items.push({
      label: t('freight.statusActions.finish'),
      icon: 'i-lucide-flag',
      color: 'primary',
      disabled: !finishTransition,
      onSelect: () => { if (finishTransition) void statusRun(row, finishTransition) },
    })
    if (lcs.can('quotation.revise')) {
      items.push({ label: t('freight.ui.requote'), icon: 'i-lucide-git-branch', onSelect: () => { void requoteRowFromServiceOrder(row) } })
    }
  }
  else if (collection === 'jobCharges') {
    const status = chargeDomainStatus(row.status)
    if (status === 'DRAFT' && lcs.can('service_charge.create')) items.push({ label: t('freight.ui.editDraft'), icon: 'i-lucide-pencil', onSelect: () => openRow(row) })
    if (status === 'ISSUED' && !row.financialDocumentId && lcs.can('service_charge.convert_to_invoice')) items.push({ label: t('freight.ui.createFinanceInvoice'), icon: 'i-lucide-file-plus-2', onSelect: () => { void runRowAction('createInvoice', row) } })
  }
  else if (collection === 'accountingPeriods') {
    // Review-only: the backend's own pre-closing checks; the actual close is a
    // separate, explicitly confirmed status transition.
    items.push({ label: t('freight.ui.periodClosing.runValidation'), icon: 'i-lucide-shield-check', onSelect: () => { void runValidationForRow(row) } })
  }
  else if (collection === 'debitNotes') {
    const status = financeDomainStatus(row.status)
    if (status === 'DRAFT' && lcs.can('financial_document.update_draft')) items.push({ label: t('freight.ui.editDraft'), icon: 'i-lucide-pencil', onSelect: () => openRow(row) })
    if (status === 'POSTED' && lcs.can('financial_document.allocate')) items.push({ label: t('freight.ui.allocate'), icon: 'i-lucide-split', onSelect: () => openRow(row) })
  }
  if (collection !== 'quotations' && collection !== 'jobs' && !isProtectedManagementRecord(collection, row)) {
    // Change Status. The transitions come from the backend policy — legal from
    // this record's status and permitted for this caller — so an action can
    // never be offered that the API would refuse for being invalid. This also
    // keeps the read-only Accounting Periods list actionable: closing and
    // reopening are status transitions, not record edits.
    const statusItem = statusMenuItem(row, {
      confirmDescription: transition =>
        transition.action === 'close' ? periodCloseSummary(row) : undefined,
    })
    if (statusItem) items.push(statusItem)
  }
  if (canMutate.value && collection !== 'quotations' && collection !== 'jobs' && !isProtectedManagementRecord(collection, row)
    && recordStatusValue(row) === 'INACTIVE') {
    // Active records must be deactivated first; only inactive records can be deleted.
    items.push({
      label: t('freight.ui.delete'),
      icon: 'i-lucide-trash-2',
      color: 'error',
      onSelect: () => { void deleteIds([String(row.id)]) },
    })
  }
  return [items]
}

/** The closing check the period confirm used to describe inline. */function periodCloseSummary(row: Record<string, unknown>) {
  const start = String(row.startDate || '').slice(0, 10)
  const end = String(row.endDate || '').slice(0, 10)
  const draftDocuments = store.list('debitNotes').filter(item =>
    String(item.status).toUpperCase() === 'DRAFT'
    && String(item.date || '').slice(0, 10) >= start
    && String(item.date || '').slice(0, 10) <= end,
  ).length
  const unallocated = store.list('customerPayments').filter(item => Number(item.unallocatedAmount || 0) > 0).length
  const unbalanced = store.list('journals').filter(item =>
    String(item.status).toUpperCase() === 'DRAFT' && Number(item.balanceDifference || 0) !== 0,
  ).length
  return `${draftDocuments} unposted documents · ${unallocated} unallocated payments · ${unbalanced} journal issues. Closed periods reject new postings.`
}

/**
 * "Convert to Service Order" from the row menu: confirm, then create the order
 * immediately through the same backend conversion the Service Order form's
 * quotation selector copies from. The remembered idempotency key survives a
 * failed request, so a retry is answered with the order already created
 * instead of a second copy; a later deliberate conversion runs with a fresh key.
 */
async function convertRowToServiceOrder(row: Record<string, unknown>) {
  pageErrors.value = []
  const revisionId = String(row.revisionId || row.id || '')
  const ok = await confirm({
    kind: 'submit',
    title: t('freight.ui.quotationConvertTitle'),
    description: t('freight.ui.quotationConvertDescription', { quotationNo: String(row.quotationNo || '') }),
    confirmLabel: t('freight.ui.convertServiceOrder'),
    confirmColor: 'primary',
    keepOpenOnConfirm: true,
  })
  if (!ok) return
  setConfirmLoading(true)
  try {
    const job = await lcs.runCommand('quotation.convert', revisionId, keyValue =>
      lcs.quotations.convert(revisionId, keyValue),
    )
    dismissConfirm()
    toast.add({ title: t('freight.ui.convertedToJob'), color: 'success' })
    await navigateTo(`/service-orders/${String(job.serviceOrderId || job.id)}`)
  }
  catch (error) {
    dismissConfirm()
    pageErrors.value = [lcs.errorMessage(error)]
  }
  finally {
    setConfirmLoading(false)
  }
}

/**
 * "Re-Quotation" from the Service Order row menu — the shared flow (confirm →
 * create → toast → navigate) lives in useRequotation, so the list and the
 * detail header offer the same operation.
 */
function requoteRowFromServiceOrder(row: Record<string, unknown>) {
  pageErrors.value = []
  void requoteFromServiceOrder(String(row.id || ''), String(row.jobNo || ''))
}

async function runRowAction(action: string, row: Record<string, unknown>) {
  pageErrors.value = []
  try {
    const id = String(row.id || '')
    if (action === 'createRevision') {
      const ok = await confirm({ kind: 'submit', title: t('freight.ui.quotationRequoteTitle'), description: t('freight.ui.quotationRequoteDescription'), confirmLabel: t('freight.ui.requote') })
      if (!ok) return
      const created = await lcs.quotations.createRevision(id)
      store.reload()
      await navigateTo(`/quotations/${created.id}`)
      return
    }
    else if (action === 'delete') {
      const ok = await confirm({ kind: 'delete', count: 1 })
      if (!ok) return
      await moduleRecord.remove([id])
      toast.add({ title: t('lcs.actions.deletedItems', { n: 1 }), color: 'success' })
      return
    }
    else if (action === 'createInvoice') {
      const invoice = await lcs.runCommand('charge.create-invoice', id, key => lcs.charges.createFinanceInvoice(id, key))
      await navigateTo(`/finance/documents/${invoice.id}`)
      return
    }
    store.reload()
    toast.add({ title: t('freight.ui.actionCompleted'), color: 'success' })
  }
  catch (error) {
    // Workflow refusals (locked revision, closed period, dependency) are shown
    // above the list — never as a toast.
    pageErrors.value = [lcs.errorMessage(error)]
  }
}

/** Declared field type wins; otherwise infer from the column key (dates, sequence numbers…). */
function columnSortKind(column: FreightField): ListSortKind {
  const declared = column.type || current.value?.fields.find(field => field.key === column.key)?.type
  if (declared === 'date' || declared === 'datetime') return 'date'
  if (declared === 'number') return 'number'
  return listSortKindFor(column.key)
}

/**
 * Column keys that identify the row's own record. A cell holding one of them
 * renders as the row's primary link (Code / Name / document-number family);
 * every other cell is plain text.
 */
const IDENTITY_LINK_KEYS = new Set(['code', 'partyCode', 'assetCode', 'assetName', 'displayName'])

const columns = computed<TableColumn<Record<string, unknown>>[]>(() => {
  if (!current.value) return []
  const titleKey = current.value.titleField
  const dataColumns = current.value.columns.map((column) => ({
    accessorKey: column.key,
    enableSorting: true,
    header: fieldLabel(column),
    meta: {
      sortKind: columnSortKind(column),
      ...(isNumericKey(column.key) || isMoneyKey(column.key) || column.key === 'tasksProgress' || column.key === 'containersCount'
        ? { class: { td: 'text-end tabular-nums whitespace-nowrap', th: 'text-end' } }
        : {}),
    },
    cell: ({ row }: { row: { original: Record<string, unknown> } }) => {
      const text = cellText(row.original, column.key)
      const jobTo = column.key === 'jobNo' && current.value!.collection !== 'jobs'
        ? jobLinkFor(row.original.jobNo)
        : ''
      const entityTo = (column.key === 'entity' || column.key === 'entityId') ? auditEntityLinkFor(row.original) : ''
      const serviceOrderTo = column.key === 'serviceOrderNo' ? serviceOrderLinkFor(row.original) : ''
      const invoiceTo = column.key === 'invoiceNo' ? invoiceLinkFor(row.original) : ''
      const quotationTo = column.key === 'quotationNo' ? quotationLinkFor(row.original) : ''
      const sourceDocTo = column.key === 'sourceDocumentNo' ? sourceDocumentLinkFor(row.original) : ''
      if (entityTo) {
        return h(ULink, {
          to: entityTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (serviceOrderTo) {
        return h(ULink, {
          to: serviceOrderTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (invoiceTo) {
        return h(ULink, {
          to: invoiceTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (quotationTo) {
        return h(ULink, {
          to: quotationTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (sourceDocTo) {
        return h(ULink, {
          to: sourceDocTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      // Outstanding only means something for an invoice/bill or its credit note.
      if (column.key === 'outstanding') {
        const type = String(row.original.documentType || '').toUpperCase()
        const meaningful = ['CUSTOMER_INVOICE', 'SUPPLIER_BILL', 'CREDIT_NOTE', 'SUPPLIER_CREDIT_NOTE']
        if (type && !meaningful.includes(type)) return h('span', { class: 'text-muted' }, '—')
      }
      if (jobTo) {
        return h(ULink, {
          to: jobTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      // Identity cells: the row's own Code/Name/document-number links to the
      // record (the module's titleField plus its Code-family columns).
      // Cross-record links above (jobNo, invoiceNo…) keep taking precedence.
      if (!isTableOnly.value && row.original.id && text && text !== '—'
        && (IDENTITY_LINK_KEYS.has(column.key) || column.key === titleKey)) {
        return h(ULink, {
          to: recordPath(row.original.id),
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (column.key === 'status' || column.key.toLowerCase().includes('status')) {
        return freightStatusBadge(
          row.original[column.key] || row.original.workflowStatus || row.original.status,
          column.key,
          text,
        )
      }
      if (column.key === 'direction' || column.key === 'stage') {
        return h(UBadge, { color: 'info', variant: 'subtle', size: 'sm' }, () => text)
      }
      if (column.key === 'customer' || column.key === 'createdBy') {
        return h('span', { class: 'block max-w-48 truncate text-default', title: text }, text)
      }
      return h('span', { class: 'text-sm text-default' }, text)
    },
  }))

  return [
    ...(!isTableOnly.value ? [listTableSelectColumn<Record<string, unknown>>(t)] : []),
    ...dataColumns,
    ...(!isTableOnly.value
      ? [listTableRowMetaColumn<Record<string, unknown>>({
          summary: pageSummary.value,
          items: rowMenuItems,
          loadingId: busyId.value,
        })]
      : []),
  ]
})

function openCreate() {
  if (!current.value) return
  navigateTo(`${current.value.path}/new`)
}

function openRow(row: Record<string, unknown>) {
  if (!current.value || !row.id) return
  navigateTo(recordPath(row.id))
}

/**
 * Row clicks navigate nothing: the record opens from the identity links
 * (Code / Name / document number cells) and the row's ⋯ menu, ERPNext-style.
 */

async function deleteIds(ids: string[]) {
  if (!current.value || !canMutate.value || !ids.length) return
  const ok = await confirm({ kind: 'delete', count: ids.length })
  if (!ok) return
  pageErrors.value = []
  try {
    await moduleRecord.remove(ids)
  }
  catch (error) {
    pageErrors.value = [lcs.errorMessage(error)]
    return
  }
  rowSelection.value = {}
  toast.add({ title: t('lcs.actions.deletedItems', { n: ids.length }), color: 'success' })
  await refreshList()
}

async function deactivateIds(ids: string[]) {
  if (!current.value || !canMutate.value || !ids.length) return
  pageErrors.value = []
  try {
    for (const id of ids) {
      const record = moduleList.items.value.find(row => String(row.id) === String(id))
      if (!record) continue
      // The bulk action runs the same policy transition as the row menu, so it
      // is validated and audited exactly like a single-row change.
      const transition = transitionsOf(record).find(item => item.action === 'deactivate' && item.kind === 'status')
      if (!transition) continue
      await moduleRecord.changeStatus(String(id), transition.to)
    }
  }
  catch (error) {
    pageErrors.value = [lcs.errorMessage(error)]
    return
  }
  rowSelection.value = {}
  toast.add({ title: t('freight.ui.deactivated'), color: 'success' })
  await refreshList()
}

function recordStatusValue(row: Record<string, unknown>) {
  return String(row.status || '').trim().toUpperCase()
}

function refresh() {
  void refreshList(true)
  store.reload()
}

function optionValue(option: FreightSelectOption) {
  return typeof option === 'string' ? option : option.value
}

function filterItems(filter: { options?: readonly FreightSelectOption[] | FreightSelectOption[], key: string }) {
  const source = referenceOptionSource(filter.key)
  if (source) return referenceSelectItems(store.list(source.collection), source)
  const fromOptions = (filter.options || []).map(optionValue)
  const sourceRows = current.value
    ? store.list(current.value.collection).map(row => current.value?.collection === 'auditLogs' ? normalizeAuditLog(row) : row)
    : []
  const fromData = [...new Set(sourceRows.map(row => String(row[filter.key] ?? '').trim()).filter(Boolean))]
  return [...new Set([...fromOptions, ...fromData])]
    .map(value => String(value).trim())
    .filter(Boolean)
    .map((value) => {
      const label = filter.key === 'documentType' && isDocumentSequenceType(value)
        ? documentSequenceTypeLabel(value)
        : filter.key === 'workflowStatus'
          ? value.replaceAll('_', ' ')
          : value
      return { label, value }
    })
}
</script>

<template>
  <div v-if="current" class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-create="canCreate"
      :create-label="t('freight.ui.newEntity', { entity: moduleSingular(current) })"
      :more-items="headerMenuItems"
      :refreshing="pending || manualRefreshing"
      @create="openCreate"
      @refresh="refresh"
    >
      <!-- Period Closing never creates periods: send users to Accounting Periods. -->
      <CommonAppDocumentActionButton
        v-if="current.path === '/finance/period-closing'"
        :label="t('freight.pages.accountingPeriods')"
        icon="i-lucide-calendar-range"
        color="secondary"
        @click="navigateTo('/finance/accounting-periods')"
      />
    </LayoutAppHeaderPageActions>

    <CommonAppExportDialog
      v-model:open="exportOpen"
      :loading="exporting"
      :users="exportUsers"
      :statuses="exportStatuses"
      :updated-by-supported="Boolean(excelModule?.updatedBySupported)"
      :matching-count="matchingCount"
      :counting="counting"
      @submit="runExport"
      @filters-change="requestExportCount"
    />

    <ExcelImportExportDialog
      v-model:open="importOpen"
      :collection="current.collection"
      @imported="refreshList"
    />

    <CommonAppFormErrorSummary class="px-4 pt-3" :form-errors="pageErrors" />

    <TableAppListTable
      v-model:search="q"
      v-model:date-start="dateFrom"
      v-model:date-end="dateTo"
      v-model:row-selection="rowSelection"
      v-model:pagination="pagination"
      v-model:sort="sort"
      :data="result.all"
      :columns="columns"
      :loading="pending"
      :show-date-range="Boolean(dateField)"
      :filters-active="hasActiveFilters"
      :empty-title="emptyTitle"
    >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-for="filter in visibleFilters"
          :key="filter.key"
          :model-value="filters[filter.key] ?? []"
          :items="filterItems(filter)"
          :placeholder="fieldLabel(filter)"
          :class="compact ? 'w-full' : 'w-40'"
          @update:model-value="filters[filter.key] = parseFilterQuery($event)"
        />
      </template>
      <template #actions>
        <UButton
          v-if="showCombinedInvoice"
          color="primary"
          variant="soft"
          size="sm"
          icon="i-lucide-receipt-text"
          class="shrink-0"
          :loading="combinedInvoiceBusy"
          :label="t('freight.ui.createCombinedInvoice')"
          @click="createCombinedInvoiceForSelection"
        />
        <template v-if="bulkAction">
          <UButton
            :color="bulkAction.color"
            variant="soft"
            size="sm"
            :icon="bulkAction.icon"
            class="shrink-0"
            :label="`${bulkAction.label} (${selectedIds.length})`"
            @click="runBulkAction"
          />
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            class="shrink-0"
            :label="t('freight.ui.clear')"
            @click="rowSelection = {}"
          />
        </template>
      </template>
    </TableAppListTable>

    <!-- Pre-closing validation: backend checks, warnings and base-currency balances. -->
    <UModal v-model:open="validationOpen" :title="t('freight.ui.periodClosing.validation')">
      <template #body>
        <div class="space-y-3 text-sm">
          <UAlert v-if="validationError" color="error" :description="validationError" />
          <div v-else-if="!validationReport && validatingId" class="flex items-center gap-2 text-muted" role="status">
            <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" aria-hidden="true" />
            <span>{{ t('common.loading') }}</span>
          </div>
          <template v-else-if="validationReport">
            <div class="flex flex-wrap items-center gap-2">
              <UBadge color="success">
                {{ ((validationReport.checks as Array<Record<string, unknown>>) || []).filter(c => c.status === 'PASS').length }} {{ t('freight.ui.periodClosing.passed') }}
              </UBadge>
              <UBadge v-if="((validationReport.checks as Array<Record<string, unknown>>) || []).some(c => c.status === 'WARNING')" color="warning">
                {{ ((validationReport.checks as Array<Record<string, unknown>>) || []).filter(c => c.status === 'WARNING').length }} {{ t('freight.ui.periodClosing.warnings') }}
              </UBadge>
              <UBadge v-if="Number(validationReport.blockingCount)" color="error">
                {{ t('freight.ui.periodClosing.blocking', { count: Number(validationReport.blockingCount) }) }}
              </UBadge>
              <span v-if="validationRow" class="text-xs text-muted">{{ validationRow.name }} · {{ validationRow.startDate }} — {{ validationRow.endDate }}</span>
            </div>
            <ul class="space-y-1.5">
              <li
                v-for="check in (validationReport.checks as Array<Record<string, unknown>>) || []"
                :key="String(check.code)"
                class="flex flex-wrap items-center gap-2 rounded-sm border border-default px-2.5 py-1.5 text-xs"
              >
                <UBadge :color="check.status === 'PASS' ? 'success' : check.status === 'WARNING' ? 'warning' : check.status === 'BLOCKED' ? 'error' : 'neutral'">
                  {{ String(check.code) }}
                </UBadge>
                <span class="font-medium">{{ String(check.name) }}</span>
                <span class="text-muted">{{ String(check.message) }}</span>
                <span v-if="check.recommendedAction" class="text-highlighted">→ {{ String(check.recommendedAction) }}</span>
              </li>
            </ul>
            <div class="grid grid-cols-2 gap-2 text-xs md:grid-cols-3">
              <div class="rounded-sm border border-default px-2.5 py-2">
                <div class="text-muted">{{ t('freight.ui.periodClosing.revenue') }}</div>
                <b class="tabular-nums">{{ formatMoney((validationReport.summary as Record<string, unknown>)?.revenue) }}</b>
              </div>
              <div class="rounded-sm border border-default px-2.5 py-2">
                <div class="text-muted">{{ t('freight.ui.periodClosing.expenses') }}</div>
                <b class="tabular-nums">{{ formatMoney((validationReport.summary as Record<string, unknown>)?.expenses) }}</b>
              </div>
              <div class="rounded-sm border border-default px-2.5 py-2">
                <div class="text-muted">{{ t('freight.ui.periodClosing.unapplied') }}</div>
                <b class="tabular-nums">{{ formatMoney((validationReport.summary as Record<string, unknown>)?.unappliedPayments) }}</b>
              </div>
            </div>
            <p class="text-xs text-muted">{{ t('freight.ui.periodClosing.inBase') }} {{ String(validationReport.baseCurrency || '—') }}</p>
          </template>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full items-center justify-end gap-2">
          <UButton
            :label="t('lcs.common.close')"
color="neutral"
variant="ghost"
            @click="validationOpen = false"
          />
        </div>
      </template>
    </UModal>
  </div>
  <div v-else class="grid h-full min-h-0 flex-1 place-items-center p-8">
    <UEmpty
      variant="naked"
      icon="i-lucide-unplug"
      :title="t('freight.ui.pageNotWired')"
      :description="t('freight.ui.pageNotWiredHint')"
    />
  </div>
</template>

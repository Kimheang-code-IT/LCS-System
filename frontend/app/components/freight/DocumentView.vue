<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import {
  asNumber,
  emptyFreightRecord,
  formatMoney,
  statusColor,
  useFreightLabel,
  useFreightRouteModule,
} from '~/composables/freight/useFreight'
import { FINANCE_REVERSE_FORM_FIELDS } from '~/config/job-workspace-forms'
import type { FreightRecord } from '~/types/record'
import { useFreightRecordChrome } from '~/composables/freight/useFreightRecordChrome'
import { useLcs } from '~/composables/freight/useLcs'
import { isLcsDomainError } from '~/utils/freight/errors'
import { financeDomainStatus, isRecordReadOnly, quotationDomainStatus } from '~/utils/freight/states'
import { normalizePermissionRows, permissionRowsFromFlatKeys, permissionRowsToFlatKeys } from '~/utils/role/permissions'
import type { AppRolePermissionRow } from '~/types/entities'
import { documentSequencePreview, documentSequenceTypeLabel } from '~/utils/document-sequences'
import { recalculateFreightRecord } from '~/utils/freight/document-calculations'
import { jobForQuotation } from '~/utils/freight/job-workspace'
import { referenceOptionSource } from '~/utils/freight/reference-options'
import {
  freightDocumentLineActionKey,
  freightDocumentLineTableHeaderKey,
  freightDocumentModelKey,
  moduleDocumentTabs,
  RELATED_FIELD_KEY,
  supportsCommentActivity,
} from '~/utils/freight/document-tabs'
import {
  linkedFinanceInvoiceForCharge,
  resolveDocumentTraceability,
  serviceChargeInvoiceAction,
  sourceChargeForFinanceDocument,
  type TraceLinkKind,
} from '~/utils/freight/traceability'
import {
  normalizeComponentAssignmentRecord,
  normalizeComponentTemplateRecord,
} from '~/utils/freight/component-instance-mode'
import type { PrintTemplateId } from '~/config/print-templates'
import { buildPrintRoute } from '~/utils/freight/print-navigation'
import { splitDocumentHeaderActions } from '~/utils/layout/document-header-actions'
import type { FreightAction } from '~/config/freight-modules'
import { useModuleRecord } from '~/composables/freight/useModuleRecord'
import { useDocumentActions } from '~/composables/freight/useDocumentActions'
import { useQuotationCommands } from '~/composables/freight/useQuotationCommands'
import { useFinanceCommands } from '~/composables/freight/useFinanceCommands'

const { module, isCreate, recordId, route } = useFreightRouteModule()
const store = useFreightStore()
const auth = useAuthStore()
const { t } = useI18n()
const toast = useToast()
const { moduleTitle, moduleSingular, fieldLabel, actionLabel } = useFreightLabel()
const { setBreadcrumbs, setBadges, clear } = useAppHeader()
const { confirm } = useConfirm()
const lcs = useLcs()
const { localization } = useAppLocalization()
const moduleRecord = useModuleRecord(module)

const saving = ref(false)
const activeTab = ref('general')
const printOpen = ref(false)
const model = ref<FreightRecord>({ id: '' } as FreightRecord)
const originalModel = ref<FreightRecord | null>(null)
const notFound = ref(false)

const {
  commentBody,
  submittingComment,
  currentUser,
  listTo,
  canNavigatePrevious,
  canNavigateNext,
  navigatePrevious,
  navigateNext,
  comments,
  attachments,
  tags,
  activity,
  metaOwner,
  metaAssignee,
  setChromeField,
  submitComment,
  updateComment,
  deleteComment,
} = useFreightRecordChrome({ module, isCreate, recordId, model })

function applyRoleMatrix() {
  if (module.value?.collection !== 'roles') return
  const existing = model.value.permissionRows as AppRolePermissionRow[] | undefined
  // Existing roles return flat `permissions`; build the matrix from them the
  // first time. Once edited, `permissionRows` is authoritative.
  const rows = existing?.length
    ? normalizePermissionRows(existing)
    : permissionRowsFromFlatKeys(model.value.permissions as string[] | undefined)
  const keys = permissionRowsToFlatKeys(rows)
  model.value = {
    ...model.value,
    permissionRows: rows,
    permissionCount: keys.length,
    permissions: keys,
  }
}

async function load() {
  if (!module.value) return
  if (isCreate.value) {
    model.value = emptyFreightRecord(module.value) as FreightRecord
    if (module.value.collection === 'documentSequences') {
      model.value.nextNumberPreview = documentSequencePreview(model.value)
    }
    originalModel.value = null
    notFound.value = false
    const query = route.query
    for (const [key, value] of Object.entries(query)) {
      if (typeof value === 'string' && value) model.value[key] = value
    }
    applyRoleMatrix()
    return
  }
  try {
    const found = await moduleRecord.get(recordId.value)
    notFound.value = false
    const normalized = module.value.collection === 'users'
      ? { ...found, role: found.role || (Array.isArray(found.roles) ? found.roles[0] : '') }
      : found
    model.value = { ...normalized } as FreightRecord
    originalModel.value = { ...normalized } as FreightRecord
  }
  catch {
    notFound.value = true
    model.value = emptyFreightRecord(module.value) as FreightRecord
    originalModel.value = null
  }
  applyRoleMatrix()
}

watch(
  [() => module.value?.path, recordId, isCreate],
  () => { void load() },
  { immediate: true },
)

// User Code is read-only and auto-generated from the username.
watch(
  [() => module.value?.collection, () => model.value.username],
  ([collection]) => {
    if (collection !== 'users') return
    const username = String(model.value.username || '').trim()
    const existing = String(model.value.userCode || '').trim()
    if (!username || (!isCreate.value && existing)) return
    const generated = username.toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 50)
    if (generated && generated !== existing) {
      model.value = { ...model.value, userCode: generated }
    }
  },
  { immediate: true },
)

const title = computed(() => {
  if (!module.value) return ''
  if (isCreate.value) return t('freight.ui.newEntity', { entity: moduleSingular(module.value) })
  const value = model.value[module.value.titleField]
  return module.value.collection === 'documentSequences'
    ? documentSequenceTypeLabel(value || moduleSingular(module.value))
    : String(value || moduleSingular(module.value))
})

watch([title, () => module.value, () => model.value.status], () => {
  if (!module.value) return
  setBreadcrumbs([
    { label: moduleTitle(module.value), to: module.value.path },
    { label: title.value },
  ])
  setBadges(model.value.status ? [{ label: String(model.value.status), color: statusColor(String(model.value.status)) }] : [])
}, { immediate: true })

onBeforeUnmount(clear)
usePageSeo({ title: () => title.value })

/** Comments & activity are only shown on quotations, service orders and service charges. */
const showRecordChrome = computed(() => supportsCommentActivity(module.value?.collection))
const compactBusinessDocument = computed(() => false)
const chargeLinkedToJob = computed(() => module.value?.collection === 'jobCharges' && Boolean(String(model.value.jobNo || '').trim()))
const related = computed(() => module.value && !isCreate.value ? store.related(module.value, model.value) : [])
const readOnly = computed(() => {
  if (!module.value) return true
  if (module.value.readOnly) return true
  if (!auth.user?.pageAccess?.includes('ALL_PAGES')) {
    if ((module.value.collection === 'chartOfAccounts' || module.value.collection === 'financialAccounts') && !lcs.can('chart_of_accounts.manage')) return true
    if (module.value.collection === 'users' && !lcs.can('user.manage')) return true
    if (module.value.collection === 'roles' && !lcs.can('role.manage')) return true
    if (module.value.group === 'master' && !lcs.can('master.reference.manage')) return true
    if (module.value.group === 'configuration' && !auth.canAccessPage('configuration.manage')) return true
  }
  if (isRecordReadOnly(module.value.collection, model.value)) return true
  if (module.value.collection === 'quotations' && !lcs.can('quotation.update_draft') && quotationDomainStatus(model.value.status) === 'DRAFT' && !isCreate.value) return true
  if (module.value.collection === 'debitNotes' && !lcs.can('financial_document.update_draft')) return true
  return false
})
const periodClosed = computed(() => {
  if (module.value?.collection !== 'debitNotes') return false
  const period = store.list('accountingPeriods').find(row => row.id === model.value.periodId)
    || store.list('accountingPeriods').find((row) => {
      const day = String(model.value.date || '').slice(0, 10)
      return day && day >= String(row.startDate || '') && day <= String(row.endDate || '')
    })
  return String(period?.status || '') === 'CLOSED'
})
const postingPreview = computed(() => {
  if (module.value?.collection !== 'debitNotes') return null
  const period = store.list('accountingPeriods').find(row => row.id === model.value.periodId)
  const total = asNumber(model.value.total || model.value.amount)
  const type = String(model.value.documentType || 'CUSTOMER_INVOICE')
  return {
    periodName: String(period?.name || period?.code || model.value.periodId || ''),
    total,
    type,
    difference: 0,
  }
})

function postingAccountLabels(type: string) {
  if (type === 'SUPPLIER_BILL') {
    return { debit: t('lcs.finance.accounts.expense'), credit: t('lcs.finance.accounts.ap') }
  }
  if (type === 'CUSTOMER_RECEIPT') {
    return { debit: t('lcs.finance.accounts.cashBank'), credit: t('lcs.finance.accounts.ar') }
  }
  return { debit: t('lcs.finance.accounts.ar'), credit: t('lcs.finance.accounts.revenue') }
}

const postingPreviewItems = computed(() => {
  const preview = postingPreview.value
  if (!preview) return []
  const accounts = postingAccountLabels(preview.type)
  return [
    { label: t('lcs.finance.documentTotal'), value: formatMoney(preview.total), strong: false },
    { label: t('freight.fields.debitAccount'), value: accounts.debit, strong: false },
    { label: t('freight.fields.creditAccount'), value: accounts.credit, strong: false },
    { label: t('freight.fields.balanceDifference'), value: preview.difference.toFixed(2), strong: true },
  ]
})

const reverseOpen = ref(false)
const reverseDraft = reactive<Record<string, unknown>>({ reason: '' })
const reversing = ref(false)
const canMutateRecord = computed(() => {
  if (!module.value || readOnly.value || isCreate.value || !model.value.id) return false
  if (module.value.collection === 'users') return lcs.can('user.manage')
  if (module.value.collection === 'roles') return lcs.can('role.manage')
  return true
})
const deactivationOnly = computed(() => module.value?.group === 'master' || module.value?.collection === 'documentSequences')

function headerActionMenuItem(action: FreightAction): DropdownMenuItem {
  return {
    label: actionLabel(action),
    icon: action.icon,
    ...(action.color ? { color: action.color } : {}),
    onSelect: () => { void runAction(action.key) },
  }
}

function quotationDraftSnapshot(record: FreightRecord) {
  const { comments, activity, updatedAt, createdAt, ...rest } = record
  return JSON.stringify(rest)
}

const quotationDraftDirty = computed(() => {
  if (module.value?.collection !== 'quotations') return false
  if (isCreate.value || !originalModel.value) return true
  return quotationDraftSnapshot(model.value) !== quotationDraftSnapshot(originalModel.value)
})

// Simplified quotation flow: Save (create/edit/delete the draft) -> Accept,
// which sends (when needed), accepts and converts to a service order in one go.
// A dirty draft shows only Save; once saved it shows Accept. Editing again
// hides Accept until the changes are saved.
const quotationHeaderActions = computed<FreightAction[]>(() => {
  if (module.value?.collection !== 'quotations') return []
  if (isCreate.value) {
    if (!lcs.can('quotation.create')) return []
    return [{ key: 'submitQuotation', label: 'Save', labelKm: 'រក្សាទុក', icon: 'i-lucide-save', color: 'primary' }]
  }
  const status = quotationDomainStatus(model.value.status)
  const actions: FreightAction[] = []
  if (status === 'DRAFT') {
    if (quotationDraftDirty.value) {
      if (lcs.can('quotation.update_draft')) {
        actions.push({ key: 'saveQuotationChanges', label: 'Save changes', labelKm: 'រក្សាទុកការផ្លាស់ប្តូរ', icon: 'i-lucide-save', color: 'primary' })
      }
    }
    else if (lcs.can('quotation.send') && lcs.can('quotation.accept') && lcs.can('quotation.convert')) {
      actions.push({ key: 'acceptJob', label: 'Accept', labelKm: 'ទទួលយក', icon: 'i-lucide-check', color: 'success' })
    }
  }
  if (status === 'SENT' && lcs.can('quotation.accept') && lcs.can('quotation.convert')) {
    actions.push({ key: 'acceptJob', label: 'Accept', labelKm: 'ទទួលយក', icon: 'i-lucide-check', color: 'success' })
  }
  if (status === 'ACCEPTED' && lcs.can('quotation.convert')) {
    actions.push({ key: 'convertJob', label: 'Convert to Service Order', labelKm: 'បម្លែងទៅបញ្ជាសេវាកម្ម', icon: 'i-lucide-arrow-right', color: 'primary' })
  }
  return actions
})

const headerActions = computed(() => {
  if (module.value?.collection === 'quotations') return quotationHeaderActions.value
  // Service charge pages keep a single header action: save/submit.
  if (module.value?.collection === 'jobCharges') return []
  const collection = module.value?.collection
  const status = String(model.value.status || '')
  return (module.value?.actions || []).filter((action) => {
    if (['save', 'delete'].includes(action.key)) return false
    if (collection === 'debitNotes') {
      const domain = financeDomainStatus(status)
      if (action.key === 'print') return false
      if (action.key === 'save') return domain === 'DRAFT' && lcs.can('financial_document.update_draft')
      if (action.key === 'post') return domain === 'DRAFT' && lcs.can('financial_document.post') && !periodClosed.value
      if (action.key === 'reverse') return domain === 'POSTED' && lcs.can('financial_document.reverse')
      if (action.key === 'recordPayment') return domain === 'POSTED'
      if (action.key === 'backToServiceCharge') {
        return Boolean(sourceChargeForFinanceDocument(model.value, traceLookups()))
          && auth.canAccessPage('finance.service_charges.view')
      }
    }
    if (collection === 'jobCharges') {
      const linkedInvoice = linkedFinanceInvoiceForCharge(model.value, traceLookups())
      const invoiceAction = serviceChargeInvoiceAction({
        status,
        hasInvoice: Boolean(linkedInvoice),
        canCreate: lcs.can('service_charge.convert_to_invoice'),
        canView: auth.canAccessPage('finance.financial_documents.view'),
      })
      if (action.key === 'saveDraft') return (status === 'Draft' || isCreate.value) && lcs.can('service_charge.create')
      if (action.key === 'issue') return !isCreate.value && Boolean(model.value.id) && status === 'Draft' && lcs.can('service_charge.issue')
      if (action.key === 'createInvoice') return !isCreate.value && invoiceAction === 'create'
      if (action.key === 'viewInvoice') return !isCreate.value && invoiceAction === 'view'
      if (action.key === 'print') return false
    }
    if (collection === 'journals') {
      if (action.key === 'postJournal') {
        const lines = Array.isArray(model.value.lines) ? model.value.lines : []
        return String(status).toUpperCase() === 'DRAFT' && lcs.can('journal_entry.post') && lines.length > 0 && asNumber(model.value.debitTotal) > 0 && asNumber(model.value.balanceDifference) === 0
      }
    }
    return true
  })
})

const splitHeaderActions = computed(() => splitDocumentHeaderActions(headerActions.value))
const primaryHeaderActions = computed(() => splitHeaderActions.value.primary)
const overflowHeaderActions = computed(() => splitHeaderActions.value.overflow)

const documentSaveLabel = computed(() => {
  if (module.value?.collection === 'jobCharges') {
    return isCreate.value ? t('freight.ui.submit') : t('freight.ui.saveChanges')
  }
  return t('docetra.common.save')
})

/** Role names from the Roles & Permissions page, used by the users role select. */
const roleFieldOptions = computed(() => store.list('roles')
  .filter(role => String(role.status || 'ACTIVE').toUpperCase() !== 'INACTIVE')
  .map(role => ({
    label: String(role.name || role.code || ''),
    value: String(role.code || role.name || ''),
  })))

const tabs = computed(() => {
  if (!module.value) return []
  const compiled = moduleDocumentTabs(module.value, {
    isCreate: isCreate.value,
    includeRelated: related.value.length > 0,
    compact: compactBusinessDocument.value,
    chargeLinkedToJob: chargeLinkedToJob.value,
    chargeManualNumber: module.value?.collection === 'jobCharges'
      && !chargeLinkedToJob.value
      && (isCreate.value || String(model.value.status || 'Draft') === 'Draft'),
    readOnlyKeys: module.value.collection === 'documentSequences' && !isCreate.value
      ? ['documentType', 'year']
      : [],
  })
  if (module.value.collection !== 'users') return compiled
  // Source the role field from existing roles so users pick instead of typing.
  return compiled.map(tab => ({
    ...tab,
    sections: tab.sections.map(section => ({
      ...section,
      fields: section.fields.map(field =>
        field.key === 'role'
          ? { ...field, type: 'select' as const, options: roleFieldOptions.value }
          : field,
      ),
    })),
  }))
})

watch(tabs, (value) => {
  if (!value.some(tab => tab.id === activeTab.value)) activeTab.value = value[0]?.id || 'general'
}, { immediate: true })

provide(freightDocumentLineActionKey, (action, row) => {
  void onLineRowAction(action, row)
})

function printServiceChargeInvoice() {
  if (!model.value.id) return
  void navigateTo(buildPrintRoute({
    collection: 'jobCharges',
    recordId: String(model.value.id),
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/service-charges',
  }))
}

provide(freightDocumentLineTableHeaderKey, (tableKey) => {
  if (module.value?.collection !== 'jobCharges' || tableKey !== 'feeLines' || isCreate.value) return []
  const feeLines = Array.isArray(model.value.feeLines) ? model.value.feeLines : []
  return [{
    label: t('freight.ui.printInvoice'),
    icon: 'i-lucide-printer',
    disabled: feeLines.length === 0,
    onClick: printServiceChargeInvoice,
  }]
})
provide(freightDocumentModelKey, model)

function traceLookups() {
  return {
    jobs: store.list('jobs'),
    quotations: store.list('quotations'),
    charges: store.list('jobCharges'),
    documents: store.list('debitNotes'),
    journals: store.list('journals'),
  }
}

function documentTrace() {
  const collection = module.value?.collection
  if (collection === 'jobCharges') return resolveDocumentTraceability(model.value, 'charge', traceLookups())
  if (collection === 'debitNotes') return resolveDocumentTraceability(model.value, 'finance', traceLookups())
  return null
}

function traceLink(kind: TraceLinkKind) {
  return documentTrace()?.links.find(row => row.sourceTypeKey === kind)
}

function labeledTraceRows() {
  const trace = documentTrace()
  if (!trace) return []
  const canSeeQuotation = auth.canAccessPage('sales.quotations.view')
  const canSeeServiceOrder = auth.canAccessPage('operations.service_orders.view')
  return trace.links
    .filter((row) => {
      if (row.sourceTypeKey === 'quotation') return canSeeQuotation
      if (row.sourceTypeKey === 'serviceOrder') return canSeeServiceOrder
      return true
    })
    .map(row => ({
      ...row,
      sourceType: t(`freight.traceability.${row.sourceTypeKey}`),
    }))
}

function tableRows(tableKey: string) {
  if (tableKey === 'sourceRelationships' && documentTrace()) return labeledTraceRows()
  if (module.value?.collection !== 'quotations' || tableKey !== 'revisionHistory') {
    return Array.isArray(model.value[tableKey])
      ? model.value[tableKey] as Array<Record<string, unknown>>
      : []
  }
  const quotationId = String(model.value.quotationId || model.value.id || '')
  const revisions = store.list('quotations')
    .filter(row => String(row.quotationId || row.id) === quotationId)
    .map(row => String(row.id) === String(model.value.id) ? { ...row, ...model.value } : row)
    .sort((a, b) => Number(b.revisionNo || 0) - Number(a.revisionNo || 0))
  if (!revisions.some(row => String(row.id) === String(model.value.id))) revisions.unshift(model.value)
  return revisions.map(row => ({
    id: row.id,
    revisionNo: row.revisionNo,
    status: row.status,
    quotationDate: row.date,
    validUntil: row.validUntil,
    currency: row.currency,
    total: row.total,
    createdBy: row.createdBy,
    createdAt: row.createdAt,
    sentAt: row.sentAt,
    acceptedAt: row.acceptedAt,
  }))
}

async function onLineRowAction(action: 'view', row: Record<string, unknown>) {
  if (action !== 'view' || !row.id) return
  const path = String(row.path || '').replace(/\/$/, '')
  if (path) {
    await navigateTo(`${path}/${String(row.id)}`)
    return
  }
  if (module.value?.collection === 'quotations') await navigateTo(`/quotations/${String(row.id)}`)
}

function relatedServiceOrder() {
  return jobForQuotation(store.list('jobs'), model.value)
}

async function openRelatedServiceOrder() {
  const job = relatedServiceOrder()
  if (!job?.id) {
    toast.add({ title: t('docetra.states.notFound'), color: 'warning' })
    return
  }
  await navigateTo(`/service-orders/${String(job.id)}`)
}

const documentActions = useDocumentActions({
  module,
  model,
  store,
  lcs,
  route,
  confirm,
  toast: toast.add,
  t,
  canMutateRecord,
  deactivationOnly,
  printOpen,
})

const quotationCommands = useQuotationCommands({
  lcs,
  model,
  store,
  confirm,
  toast: toast.add,
  t,
  quotationDraftDirty,
  relatedServiceOrder: () => relatedServiceOrder() as FreightRecord | null | undefined,
})

const financeCommands = useFinanceCommands({
  lcs,
  model,
  store,
  toast: toast.add,
  t,
  currentUserName: computed(() => String(currentUser.value?.name || 'Current User')),
  periodClosed,
  recalculate,
  traceLink,
  openReverse: () => { reverseOpen.value = true },
})

const moreItems = computed<DropdownMenuItem[][]>(() => {
  // Service charge pages: no overflow (⋯) actions.
  if (module.value?.collection === 'jobCharges') return []
  const items: DropdownMenuItem[] = []
  if (module.value?.collection === 'quotations' && !isCreate.value && model.value.id && relatedServiceOrder()) {
    items.push({
      label: t('freight.ui.openServiceOrder'),
      icon: 'i-lucide-briefcase',
      onSelect: () => { void openRelatedServiceOrder() },
    })
  }

  for (const action of overflowHeaderActions.value) {
    items.push(headerActionMenuItem(action))
  }

  if (canMutateRecord.value || (module.value?.collection === 'quotations' && !isCreate.value && Boolean(model.value.id))) {
    if (canMutateRecord.value) {
      const status = String(model.value.status || '').trim().toUpperCase()
      if (status === 'ACTIVE' || status === 'INACTIVE') {
        const active = status === 'ACTIVE'
        items.push({
          label: t(active ? 'freight.ui.deactivate' : 'freight.ui.activate'),
          icon: active ? 'i-lucide-circle-off' : 'i-lucide-circle-check',
          color: active ? 'warning' as const : 'success' as const,
          onSelect: () => { void setRecordStatus(active ? 'INACTIVE' : 'ACTIVE') },
        })
        // Active records must be deactivated first; only inactive records can be deleted.
        if (!active) {
          items.push({
            label: t('freight.ui.delete'),
            icon: 'i-lucide-trash-2',
            color: 'error' as const,
            onSelect: () => { void deleteRecord() },
          })
        }
      }
      else {
        items.push({
          label: t(deactivationOnly.value ? 'freight.ui.deactivate' : 'freight.ui.delete'),
          icon: deactivationOnly.value ? 'i-lucide-circle-off' : 'i-lucide-trash-2',
          color: deactivationOnly.value ? 'warning' as const : 'error' as const,
          onSelect: () => { void deleteRecord() },
        })
      }
    }
  }

  return items.length ? [items] : []
})

function setRolePermissions(rows: AppRolePermissionRow[]) {
  const normalized = normalizePermissionRows(rows)
  model.value = {
    ...model.value,
    permissionRows: normalized,
    permissionCount: permissionRowsToFlatKeys(normalized).length,
  }
}

function setField(key: string, value: unknown) {
  const next: Record<string, unknown> = { ...model.value, [key]: value }
  if (module.value?.collection === 'jobCharges' && key === 'jobNo') {
    const jobNo = String(value || '').trim()
    const job = jobNo
      ? store.list('jobs').find(row => String(row.jobNo || '') === jobNo)
      : null
    if (job) {
      next.customer = job.customer || next.customer
      next.currency = job.currency || next.currency || localization.value.currency
      delete next.chargeNo
    }
  }
  model.value = next as FreightRecord
  recalculate()
}

function fieldValue(key: string) {
  if (key === RELATED_FIELD_KEY) return related.value
  const trace = documentTrace()
  if (trace) {
    if (key === 'invoiceNo' && trace.invoiceNo) return trace.invoiceNo
    if (key === 'journalId' && trace.journalNo) return trace.journalNo
    if (key === 'sourceChargeId' && trace.sourceChargeNo) return trace.sourceChargeNo
  }
  if (module.value?.tables?.some(table => table.key === key)) return tableRows(key)
  return model.value[key]
}

function setFieldValue(key: string, value: unknown) {
  if (key === RELATED_FIELD_KEY) return
  if (key === 'permissionRows') {
    setRolePermissions(value as AppRolePermissionRow[])
    return
  }
  if (key === 'tags' || key === 'assignee' || key === 'attachments' || key === 'favorite') {
    setChromeField(key, value)
    return
  }
  if (module.value?.tables?.some(table => table.key === key) && Array.isArray(value)) {
    setTable(key, value as Array<Record<string, unknown>>)
    return
  }
  setField(key, value)
}

function setTable(key: string, rows: Array<Record<string, unknown>>) {
  if (key === 'allocations') {
    const paymentTotal = asNumber(model.value.total || model.value.amount || model.value.received)
    const allocated = rows.reduce((sum, row) => sum + asNumber(row.amount), 0)
    const exceedsTarget = rows.some(row => asNumber(row.amount) > asNumber(row.targetOutstanding || row.outstandingAmount))
    if (allocated > paymentTotal || exceedsTarget) {
      toast.add({ title: t('freight.ui.allocationExceeds'), color: 'error' })
      return
    }
  }
  model.value = { ...model.value, [key]: rows }
  recalculate()
}

function recalculate() {
  if (!module.value) return
  model.value = recalculateFreightRecord(module.value, model.value)
}

async function save(status?: string) {
  if (!module.value || readOnly.value) return
  saving.value = true
  try {
    recalculate()
    const payload = { ...model.value }
    if (status) payload.status = status
    if (module.value.collection === 'componentTemplates') {
      Object.assign(payload, normalizeComponentTemplateRecord(payload))
      const minimum = Number(payload.minimumInstances || 0)
      const maximum = Number(payload.maximumInstances || 0)
      if (minimum < 0 || maximum < 0 || (maximum > 0 && maximum < minimum)) {
        toast.add({ title: t('freight.ui.invalidInstanceLimits'), color: 'error' })
        return
      }
      if (!isCreate.value && originalModel.value
        && String(payload.instanceMode) !== String(originalModel.value.instanceMode || 'SINGLE')) {
        const used = store.list('serviceComponents').some(row =>
          String(row.templateCode) === String(payload.code)
          && String(row.templateVersion) === String(payload.version),
        )
        if (used) {
          toast.add({ title: t('freight.ui.cardinalityVersionRequired'), color: 'error' })
          return
        }
      }
    }
    if (module.value.collection === 'tradeDirectionComponents') {
      Object.assign(payload, normalizeComponentAssignmentRecord(payload))
    }
    if (module.value.collection === 'roles') {
      const rows = normalizePermissionRows(payload.permissionRows as AppRolePermissionRow[] | undefined)
      const keys = permissionRowsToFlatKeys(rows)
      payload.permissionRows = rows
      payload.permissions = keys
      payload.permissionCount = keys.length
    }
    if (module.value.collection === 'documentSequences') {
      payload.prefix = String(payload.prefix || '').trim()
      const sequenceYear = Number(payload.year)
      const lastValue = Number(payload.lastValue)
      const paddingLength = Number(payload.paddingLength)
      payload.year = sequenceYear
      payload.lastValue = lastValue
      payload.paddingLength = paddingLength
      payload.status = String(payload.status || 'ACTIVE').toUpperCase()
      payload.nextNumberPreview = documentSequencePreview(payload)

      if (!Number.isInteger(sequenceYear) || sequenceYear < 1000 || sequenceYear > 9999) {
        toast.add({ title: 'Year must be a positive 4-digit year.', color: 'error' })
        return
      }
      if (!Number.isInteger(lastValue) || lastValue < 0) {
        toast.add({ title: 'Last Value must be a whole number greater than or equal to 0.', color: 'error' })
        return
      }
      if (!Number.isInteger(paddingLength) || paddingLength <= 0) {
        toast.add({ title: 'Padding Length must be a whole number greater than 0.', color: 'error' })
        return
      }
      if (!['ACTIVE', 'INACTIVE'].includes(String(payload.status))) {
        toast.add({ title: 'Status must be ACTIVE or INACTIVE.', color: 'error' })
        return
      }
      const duplicate = store.list('documentSequences').find(row =>
        String(row.id) !== String(payload.id || '')
        && String(row.documentType) === String(payload.documentType)
        && Number(row.year) === Number(payload.year),
      )
      if (duplicate) {
        toast.add({
          title: 'A document sequence already exists for this document type and year.',
          description: `${documentSequenceTypeLabel(payload.documentType)} / ${payload.year}`,
          color: 'error',
        })
        return
      }
      if (!isCreate.value && originalModel.value && Number(payload.lastValue) !== Number(originalModel.value.lastValue)) {
        const ok = await confirm({
          kind: 'generic',
          title: 'Change the last sequence value?',
          description: 'Changing the last value can create duplicate or skipped document numbers. Continue only after verifying the numbering history.',
          confirmLabel: 'Change Last Value',
          confirmColor: 'warning',
        })
        if (!ok) return
      }
    }
    const missing = module.value.fields.filter((field) => {
      if (module.value?.collection === 'jobCharges' && field.key === 'chargeNo' && !String(payload.jobNo || '').trim()) {
        return !String(payload.chargeNo ?? '').trim()
      }
      return field.required && !field.computed && !String(payload[field.key] ?? '').trim()
    })
    if (missing.length) {
      toast.add({ title: t('freight.ui.missingRequired'), description: missing.map(fieldLabel).join(', '), color: 'error' })
      return
    }
    if (isCreate.value || !payload.id) {
      payload.createdAt ||= new Date().toISOString()
      payload.createdBy ||= String(currentUser.value?.name || 'Current User')
      payload.status ||= module.value.collection === 'journals' ? 'DRAFT' : 'Draft'
      payload.currency ||= localization.value.currency
    }
    const isNew = isCreate.value || !payload.id
    const saved = await documentActions.persistRecord(payload, isNew)
    if (!saved) return
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    // "Add new" from a reference select: return to the originating document and
    // hand back the created value so the field can auto-select it.
    const pickField = String(route.query.pickField || '')
    const returnTo = String(route.query.returnTo || '')
    if (pickField && returnTo) {
      const source = referenceOptionSource(pickField)
      const record = saved as Record<string, unknown>
      const raw = record[source?.valueField || 'code'] ?? record.name ?? ''
      const params = new URLSearchParams(returnTo.split('?')[1] || '')
      params.set('pickField', pickField)
      params.set('pickedValue', raw === null || raw === undefined ? '' : String(raw))
      const pickRow = String(route.query.pickRow || '')
      if (pickRow) params.set('pickRow', pickRow)
      await navigateTo(`${returnTo.split('?')[0] || module.value.path}?${params.toString()}`)
      return
    }
    // Every save (create or update) returns to the list so the refreshed table
    // is visible immediately.
    await navigateTo(module.value.path)
  }
  catch (error) {
    if (isLcsDomainError(error)) toast.add({ title: error.message, color: 'error' })
    else throw error
  }
  finally {
    saving.value = false
  }
}

async function setRecordStatus(next: 'ACTIVE' | 'INACTIVE') {
  if (!module.value || !canMutateRecord.value) return
  const status = module.value.collection === 'documentSequences'
    ? next
    : (next === 'ACTIVE' ? 'Active' : 'Inactive')
  model.value = { ...model.value, status } as FreightRecord
  await moduleRecord.update(String(model.value.id || ''), model.value)
  originalModel.value = { ...model.value }
  toast.add({ title: t(next === 'ACTIVE' ? 'docetra.common.activated' : 'docetra.common.deactivated'), color: 'success' })
}

async function openPrint(templateId: PrintTemplateId) {
  await documentActions.openPrint(templateId)
}

async function runAction(key: string) {
  if (!module.value) return
  try {
    if (key === 'save' || key === 'saveDraft' || key === 'submitQuotation' || key === 'saveQuotationChanges') {
      return save(key === 'saveDraft' ? 'Draft' : undefined)
    }
    if (key === 'print') return documentActions.openPrintPicker()
    if (key === 'send' && module.value.collection === 'quotations') return quotationCommands.send()
    if (key === 'submit' && module.value.collection === 'quotations') return quotationCommands.submit()
    if (key === 'accept' && module.value.collection === 'quotations') return quotationCommands.accept()
    if (key === 'acceptJob' && module.value.collection === 'quotations') return quotationCommands.acceptAndConvert()
    if ((key === 'reject' || key === 'cancel') && module.value.collection === 'quotations') {
      return quotationCommands.rejectOrCancel(key)
    }
    if (key === 'createRevision' && module.value.collection === 'quotations') return quotationCommands.createRevision()
    if (key === 'convertJob') return quotationCommands.convertJob()
    if (key === 'issue' && module.value.collection === 'jobCharges') return financeCommands.issueCharge()
    if (key === 'createInvoice' && module.value.collection === 'jobCharges') return financeCommands.createInvoiceFromCharge()
    if (key === 'viewInvoice' && module.value.collection === 'jobCharges') return financeCommands.viewInvoiceFromCharge()
    if (key === 'backToServiceCharge' && module.value.collection === 'debitNotes') return financeCommands.backToServiceCharge()
    if (key === 'post' && module.value.collection === 'debitNotes') return financeCommands.postDocument()
    if (key === 'postJournal' && module.value.collection === 'journals') return financeCommands.postJournal()
    if (key === 'reverse' && module.value.collection === 'debitNotes') return financeCommands.reverseDocument()
    if (key === 'delete') return documentActions.deleteRecord()
    if (key === 'recordPayment') return financeCommands.recordPayment()
  }
  catch (error) {
    lcs.reportError(error)
  }
}

async function deleteRecord() {
  await documentActions.deleteRecord()
}

async function confirmReverse() {
  if (!module.value) return
  const reason = String(reverseDraft.reason || '').trim()
  if (!reason) {
    toast.add({ title: t('freight.ui.missingRequired'), color: 'error' })
    return
  }
  reversing.value = true
  try {
    const saved = await lcs.runCommand('finance.reverse', String(model.value.id), keyValue =>
      lcs.finance.reverse(String(model.value.id), reason, keyValue),
    )
    model.value = saved
    reverseOpen.value = false
    toast.add({ title: t('freight.ui.documentReversed'), color: 'success' })
  }
  catch (error) {
    lcs.reportError(error)
  }
  finally {
    reversing.value = false
  }
}
</script>

<template>
  <template v-if="module && !notFound">
    <DocumentAppDocumentPage
:tabs="tabs"
:active-tab="activeTab"
:field-value="fieldValue"
      :set-field-value="setFieldValue"
:saving="saving"
:read-only="readOnly"
      :can-save="!readOnly && module.collection !== 'quotations'"
      :save-label="documentSaveLabel"
      :confirm-save="false"
:show-cancel="false"
:show-comments="showRecordChrome"
:show-tabs="tabs.length > 1"
show-list-nav
content-wide
      :can-navigate-previous="canNavigatePrevious"
:can-navigate-next="canNavigateNext"
:list-to="listTo"
      :is-create="isCreate"
:can-comment="showRecordChrome && !isCreate"
:comments="comments"
:activity="showRecordChrome ? activity : []"
      :attachments="attachments"
:comment-body="commentBody"
:submitting-comment="submittingComment"
      :current-user="currentUser"
:meta-title="title"
:meta-subtitle="module.collection === 'quotations'
        ? [model.customer, model.direction, model.currency].filter(Boolean).join(' · ')
        : moduleSingular(module)"
:meta-icon="module.icon"
:meta-status="String(model.status || '')"
      :meta-owner="metaOwner"
:meta-assignee="metaAssignee"
:meta-tags="tags"
      :meta-created-at="String(model.createdAt || '')"
:meta-updated-at="String(model.updatedAt || '')"
      :more-items="moreItems"
:can-export="false"
@update:active-tab="activeTab = $event"
      @update:comment-body="commentBody = $event"
@update:attachments="setChromeField('attachments', $event)"
      @save="save()"
@refresh="load"
@submit-comment="submitComment"
@update-comment="updateComment"
      @delete-comment="deleteComment"
@navigate-previous="navigatePrevious"
@navigate-next="navigateNext">
      <template #actions>
        <CommonAppDocumentActionButton
          v-for="action in primaryHeaderActions"
          :key="action.key"
          :icon="action.icon"
          :label="actionLabel(action)"
          :color="action.color"
          :loading="saving"
          @click="runAction(action.key)"
        />
      </template>

      <template #before-form>
        <DocumentAppDocumentContentShell
v-if="(postingPreview && String(model.status) === 'Draft')
          || (module.collection === 'debitNotes' && (periodClosed || String(model.status) === 'Posted'))"
wide
          class="space-y-4 pt-6">
          <UCard v-if="postingPreview && String(model.status) === 'Draft'" variant="subtle">
            <template #header>
              <div class="flex items-center justify-between gap-3">
                <div>
                  <p class="font-semibold text-highlighted">{{ $t('lcs.finance.postingConfirmation') }}</p>
                  <p class="text-xs text-muted">{{ $t('lcs.finance.postingConfirmationHint') }}</p>
                </div>
                <UBadge :color="periodClosed ? 'error' : 'success'" variant="subtle">
                  {{ periodClosed ? $t('lcs.finance.periodClosed') : postingPreview.periodName }}
                </UBadge>
              </div>
            </template>
            <dl class="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-5">
              <div v-for="item in postingPreviewItems" :key="item.label">
                <dt class="text-xs text-muted">{{ item.label }}</dt>
                <dd class="font-medium text-highlighted" :class="item.strong ? 'font-semibold text-success' : ''">
                  {{ item.value }}
                </dd>
              </div>
            </dl>
          </UCard>
          <UAlert
v-if="module.collection === 'debitNotes' && periodClosed"
color="error"
variant="subtle"
            icon="i-lucide-calendar-off"
:title="$t('lcs.finance.periodClosed')" />
        </DocumentAppDocumentContentShell>
      </template>
    </DocumentAppDocumentPage>
    <UModal
:open="reverseOpen"
:title="$t('lcs.finance.reverseReason')"
:dismissible="false"
      :close="{ color: 'primary', variant: 'outline', class: 'rounded-full' }"
      :ui="{ content: 'w-[calc(100%-2rem)] max-w-md sm:max-w-md' }"
      @update:open="value => !value && (reverseOpen = false)">
      <template #body>
        <FreightFieldGrid
:fields="FINANCE_REVERSE_FORM_FIELDS"
:model="reverseDraft"
          @update="(key, value) => { reverseDraft[key] = value }" />
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
color="neutral"
variant="ghost"
size="sm"
:label="$t('actions.cancel')"
            @click="reverseOpen = false" />
          <UButton
color="error"
size="sm"
:loading="reversing"
:label="$t('freight.ui.actions.reverse')"
            @click="confirmReverse" />
        </div>
      </template>
    </UModal>
    <PrintTemplateModal
v-if="module"
v-model:open="printOpen"
:collection="module.collection"
:record="model"
      @print="openPrint" />
  </template>
  <div v-else class="p-6 text-sm text-muted">{{ t('docetra.document.notFound') || 'Record not found.' }}</div>
</template>

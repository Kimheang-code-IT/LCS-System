<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import {
  asNumber,
  defaultStatusForModule,
  emptyFreightRecord,
  statusColor,
  useFreightLabel,
  useFreightRouteModule,
} from '~/composables/freight/useFreight'
import { FINANCE_REVERSE_FORM_FIELDS } from '~/config/job-workspace-forms'
import { FINANCIAL_DOCUMENT_TYPES } from '~/config/freight-options'
import type { FreightRecord } from '~/types/record'
import { useFreightRecordChrome } from '~/composables/freight/useFreightRecordChrome'
import { useLcs } from '~/composables/freight/useLcs'
import { financeDomainStatus, isRecordReadOnly, quotationDomainStatus } from '~/utils/freight/states'
import { normalizePermissionRows, permissionRowsFromFlatKeys, permissionRowsToFlatKeys } from '~/utils/role/permissions'
import type { AppRolePermissionRow } from '~/types/entities'
import { documentSequencePreview, documentSequenceTypeLabel } from '~/utils/document-sequences'
import { recalculateFreightRecord } from '~/utils/freight/document-calculations'
import { jobForQuotation } from '~/utils/freight/job-workspace'
import { quotationActionAvailability } from '~/utils/freight/quotation-actions'
import { revisionGridRows } from '~/utils/freight/quotation-revisions'
import { identityTypeRowOf, matchesIdentityPattern, referenceOptionSource } from '~/utils/freight/reference-options'
import {
  freightDocumentLineActionKey,
  freightDocumentLineTableHeaderKey,
  freightDocumentLineTableRowMenuKey,
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
import type { RecordStatusTransition } from '~/types/status'
import { buildPrintRoute } from '~/utils/freight/print-navigation'
import { splitDocumentHeaderActions } from '~/utils/layout/document-header-actions'
import type { FreightAction, FreightField, FreightTable } from '~/config/freight-modules'
import { useModuleRecord } from '~/composables/freight/useModuleRecord'
import { useDocumentActions } from '~/composables/freight/useDocumentActions'
import { useRecordStatus } from '~/composables/freight/useRecordStatus'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateDocumentFields, validateTableRows } from '~/utils/validation/record-validation'
import { focusField } from '~/utils/validation/focus'
import { parseRowKey } from '~/utils/validation/error-paths'
import { apiErrorMessage } from '~/utils/validation/api-error'
import type { ValidationFailure } from '~/utils/validation/field-rules'
import { validatePasswordStrength } from '~/utils/validation/field-rules'
import { isProtectedManagementRecord } from '~/utils/auth/protected-system-records'
import { useQuotationCommands } from '~/composables/freight/useQuotationCommands'
import { useFinanceCommands } from '~/composables/freight/useFinanceCommands'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { unwrapApiData } from '~/repositories/http/response'
import type { ApiResponse } from '~/types/common'

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
const api = useApi()

const saving = ref(false)
const activeTab = ref('general')
const printOpen = ref(false)
const model = ref<FreightRecord>({ id: '' } as FreightRecord)
const originalModel = ref<FreightRecord | null>(null)
const notFound = ref(false)
const revisionHistory = ref<Array<Record<string, unknown>>>([])
const duplicatingRole = ref(false)

/** Locate a rendered field so validation copy and the summary share one label. */
function findField(key: string) {
  for (const tab of tabs.value) {
    for (const section of tab.sections) {
      const field = section.fields.find(item => item.key === key)
      if (field) return { tab, section, field }
    }
  }
  return undefined
}

/** Row-scoped keys (`lines.1.amount`) resolve back to their table field. */
function findFieldOwner(key: string) {
  return findField(key) ?? findField(key.split('.')[0]!)
}

/**
 * Validate one field when the user leaves it.
 *
 * The submit pass remains authoritative (it also runs cross-field and table
 * rules), but checking on blur reports a malformed email or an over-long code
 * while the user is still on the input instead of only after a save attempt.
 * The message is rendered by the same `fieldErrors` map the submit pass uses,
 * so there is exactly one place an error can appear.
 */
function validateFieldOnBlur(key: string) {
  const owner = findField(key)
  if (!owner || ('computed' in owner.field && owner.field.computed)) return
  const failures = validateDocumentFields({
    // The tab schema is compiled from a FreightField; the renderer's wider
    // field union also covers system-settings widgets that never reach here.
    fields: [owner.field as unknown as FreightField],
    model: model.value as Record<string, unknown>,
    isCreate: isCreate.value || !model.value.id,
    label: fieldKeyLabel,
  })
  validation.clearFieldError(key)
  const failure = failures.find(item => item.key === key)
  if (failure) validation.setFieldError(key, validation.message(failure, fieldKeyLabel(key)))
}

/** Locally translated label for a rendered document field, including a cell. */
function fieldKeyLabel(key: string) {
  const row = parseRowKey(key)
  const owner = findFieldOwner(key)
  if (!owner) return ''
  if (row) {
    // A cell message names its column, never the composite model key.
    const columns = (owner.field.meta?.table as FreightTable | undefined)?.columns || []
    const column = columns.find(item => item.key === row.column)
    return column
      ? fieldLabel({ ...column, label: column.label || column.key })
      : fieldLabel({ key: row.column, label: row.column })
  }
  const field = owner.field
  return fieldLabel({
    key: field.key,
    label: field.label || field.key,
    ...(field.labelKey ? { labelKey: field.labelKey } : {}),
  })
}

/**
 * Shared validation. `order` follows the rendered tab → section → field order
 * so "first invalid field" is the first one the user can actually see.
 */
const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  label: fieldKeyLabel,
  order: () => tabs.value.flatMap(tab => tab.sections.flatMap(section => section.fields.map(field => field.key))),
  reveal: (key) => {
    const owner = findFieldOwner(key)
    if (!owner) return false
    if (activeTab.value === owner.tab.id) return true
    activeTab.value = owner.tab.id
    return true
  },
})

const fieldErrors = validation.fieldErrors

function clearFieldError(key: string) {
  validation.clearFieldError(key)
}

/**
 * Status changes (activate / deactivate / mark / finish / issue / post /
 * reverse / close / reopen) run through the shared status manager, so the
 * record page and the list offer exactly the same legal transitions.
 */
const { menuItem: statusMenuItem } = useRecordStatus(module, {
  onError: (message) => { validation.addFormError(message) },
  onChanged: () => load(),
})

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
  activity,
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
    // A financial document is an invoice unless the caller asked for another type,
    // which is also the type the backend defaults to. The Overview fields, the
    // settlement group and the tab set all depend on it, so an empty document type
    // must never reach the renderer.
    if (module.value.collection === 'debitNotes' && !model.value.documentType) {
      model.value.documentType = FINANCIAL_DOCUMENT_TYPES[0]
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

// User Code is editable; seed it from the username only while it is still empty.
watch(
  [() => module.value?.collection, () => model.value.username],
  ([collection]) => {
    if (collection !== 'users') return
    const username = String(model.value.username || '').trim()
    const existing = String(model.value.userCode || '').trim()
    if (!username || existing) return
    const generated = username.toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 50)
    if (generated) {
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
const reverseOpen = ref(false)
const reverseDraft = reactive<Record<string, unknown>>({ reason: '' })
const reverseErrors = ref<string[]>([])
const reversing = ref(false)

/**
 * Password dialog. One instance serves both jobs: choosing a new password for an
 * existing account, and showing the password of a just-created one before it
 * leaves the screen. `handoverLeaving` holds the post-save navigation until the
 * administrator has dismissed the reveal, so the password cannot be lost behind
 * a route change.
 */
const passwordDialog = reactive({
  open: false,
  mode: 'set' as 'set' | 'handover',
  userId: '',
  userLabel: '',
  revealedPassword: '',
})
const handoverLeaving = ref(false)
const canMutateRecord = computed(() => {
  if (!module.value || readOnly.value || isCreate.value || !model.value.id) return false
  if (module.value.collection === 'users') return lcs.can('user.manage')
  if (module.value.collection === 'roles') return lcs.can('role.manage')
  return true
})

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

// Quotation workflow: Draft -> Sent (send) -> Accepted (accept) -> Service
// Order (convert). Re-quotation clones the latest revision into a new draft.
// A dirty draft only offers Save so every transition runs on persisted data.
const quotationAvailability = computed(() => quotationActionAvailability(
  model.value.status,
  {
    updateDraft: lcs.can('quotation.update_draft'),
    send: lcs.can('quotation.send'),
    accept: lcs.can('quotation.accept'),
    convert: lcs.can('quotation.convert'),
  },
  { hasServiceOrder: Boolean(relatedServiceOrder()) },
))

/**
 * The quotation status transitions keep their availability rules (a converted
 * quotation must not offer Convert again, and a dirty draft is saved first), so
 * the shared status menu offers exactly what those rules allow.
 */
function transitionsAvailableForQuotation(transition: RecordStatusTransition): boolean {
  const availability = quotationAvailability.value
  if (transition.action === 'send') return availability.send && !quotationDraftDirty.value
  if (transition.action === 'accept') return availability.accept && !quotationDraftDirty.value
  if (transition.action === 'convert') return availability.convert && !quotationDraftDirty.value
  if (transition.action === 'reject') return lcs.can('quotation.accept')
  if (transition.action === 'cancel') return lcs.can('quotation.update_draft')
  return true
}

const quotationHeaderActions = computed<FreightAction[]>(() => {
  if (module.value?.collection !== 'quotations') return []
  if (isCreate.value) {
    if (!lcs.can('quotation.create')) return []
    return [{ key: 'submitQuotation', label: 'Save', labelKm: 'រក្សាទុក', icon: 'i-lucide-save', color: 'primary' }]
  }
  const availability = quotationAvailability.value
  const actions: FreightAction[] = []
  if (availability.status === 'DRAFT' && quotationDraftDirty.value) {
    if (availability.edit) {
      actions.push({ key: 'saveQuotationChanges', label: 'Save changes', labelKm: 'រក្សាទុកការផ្លាស់ប្តូរ', icon: 'i-lucide-save', color: 'primary' })
    }
    return actions
  }
  if (availability.send) {
    actions.push({ key: 'send', label: t('freight.ui.send'), icon: 'i-lucide-send' })
  }
  if (availability.accept) {
    actions.push({ key: 'accept', label: t('freight.ui.accept'), icon: 'i-lucide-check', color: 'success' })
  }
  if (availability.revise) {
    actions.push({ key: 'createRevision', label: t('freight.ui.requote'), icon: 'i-lucide-git-branch' })
  }
  if (availability.convert) {
    actions.push({ key: 'convertJob', label: t('freight.ui.convertServiceOrder'), icon: 'i-lucide-arrow-right', color: 'primary' })
  }
  return actions
})

const headerActions = computed(() => {
  if (module.value?.collection === 'quotations') return quotationHeaderActions.value
  // Service charge pages keep a single header action: save/submit.
  if (module.value?.collection === 'jobCharges') return []
  const collection = module.value?.collection
  const status = String(model.value.status || '')
  const actions = (module.value?.actions || []).filter((action) => {
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
    if (collection === 'users') {
      // An unsaved account has nothing to set a password on, and a delegated
      // reader without user.manage cannot reach the endpoint anyway.
      if (action.key === 'setPassword') {
        return !isCreate.value && Boolean(model.value.id) && lcs.can('user.manage')
      }
    }
    return true
  })
  // A service order can always be re-quoted into a fresh offer; the order itself
  // is read only, so this is safe in every status.
  if (collection === 'serviceOrders' && serviceOrderRequotationAvailability({
    isCreate: isCreate.value,
    hasRecord: Boolean(model.value.id),
    canRevise: lcs.can('quotation.revise'),
  })) {
    actions.push({ key: 'requoteFromServiceOrder', label: t('freight.ui.requoteFromServiceOrder'), icon: 'i-lucide-file-plus' })
  }
  return actions
})

const splitHeaderActions = computed(() => splitDocumentHeaderActions(headerActions.value))
const primaryHeaderActions = computed(() => splitHeaderActions.value.primary)
const overflowHeaderActions = computed(() => splitHeaderActions.value.overflow)

const documentSaveLabel = computed(() => {
  if (module.value?.collection === 'jobCharges') {
    return isCreate.value ? t('freight.ui.submit') : t('freight.ui.saveChanges')
  }
  return t('lcs.common.save')
})

/**
 * Creating a user chooses that account's password, so Save stays disabled until
 * the initial password satisfies the shared policy. Other modules are unaffected.
 */
const canSave = computed(() => {
  if (readOnly.value || module.value?.collection === 'quotations') return false
  if (isCreate.value && module.value?.collection === 'users') {
    return !validatePasswordStrength(String(model.value?.password ?? ''))
  }
  return true
})

/** Role names from the Roles & Permissions page, used by the users role select. */
const roleFieldOptions = computed(() => store.list('roles')
  .filter(role => String(role.status || 'ACTIVE').toUpperCase() !== 'INACTIVE')
  .map(role => ({
    label: String(role.name || role.code || ''),
    value: String(role.code || role.name || ''),
  })))

const protectedSystemRecord = computed(() =>
  isProtectedManagementRecord(module.value?.collection, model.value),
)

const formTabs = computed(() => {
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
      : module.value.collection === 'users' && model.value.isProtectedSystemAccount === true
        ? ['role']
        : module.value.collection === 'debitNotes' && !isCreate.value
          // The document number was allocated from this type's sequence and the
          // backend refuses a later switch, so it is not editable once created.
          ? ['documentType']
          : [],
    // Tabs and fields are scoped to the document type and status, both of which the
    // user can change while the form is open, so they are inputs to this computed.
    documentType: String(model.value.documentType || ''),
    status: String(model.value.status || ''),
    // ...and the record itself, so a `visibleWhen` rule (the exchange rate while
    // the document currency is not the base currency) follows the form live.
    record: model.value,
    // Files uploaded from this document are linked to it for audit/listing.
    uploadContext: {
      module: module.value.collection,
      recordNo: String(model.value.id || ''),
    },
  })
  if (module.value.collection === 'roles' && model.value.isSystemRole === true) {
    return compiled.map(tab => ({
      ...tab,
      sections: tab.sections.map(section => ({
        ...section,
        fields: section.fields.map(field =>
          field.key === 'permissionRows' ? { ...field, readOnly: true } : field,
        ),
      })),
    }))
  }
  if (module.value.collection !== 'users') return compiled
  // Source the role field from existing roles so users pick one instead of typing.
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

/**
 * The Posting Rule History tab.
 *
 * A posting rule is configuration, not a workflow document, so the question an
 * administrator has after a posting goes somewhere unexpected is "what changed
 * about this rule, and what did it post?" — which is a tab beside the form, not
 * a second screen. The tab carries no fields; its content is rendered through
 * the document page's `tab-extra` slot.
 *
 * Only on an existing rule: a create form has nothing to look back on.
 */
const tabs = computed(() => formTabs.value)

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

/** Print one fee line of the open charge; the print page narrows the snapshot. */
function printServiceChargeLine(index: number, lineId: unknown) {
  if (!model.value.id) return
  void navigateTo(buildPrintRoute({
    collection: 'jobCharges',
    recordId: String(model.value.id),
    template: 'tax-invoice',
    returnTo: route.fullPath,
    modulePath: '/service-charges',
    lineIndex: index,
    lineId: lineId ? String(lineId) : undefined,
  }))
}

provide(freightDocumentLineTableHeaderKey, (tableKey) => {
  if (module.value?.collection !== 'jobCharges' || tableKey !== 'feeLines' || isCreate.value) return []
  const feeLines = Array.isArray(model.value.feeLines) ? model.value.feeLines : []
  return [{
    label: t('freight.ui.printAll'),
    icon: 'i-lucide-printer',
    disabled: feeLines.length === 0,
    onClick: printServiceChargeInvoice,
  }]
})

provide(freightDocumentLineTableRowMenuKey, (tableKey) => {
  if (module.value?.collection !== 'jobCharges' || tableKey !== 'feeLines' || isCreate.value) return undefined
  return (row: Record<string, unknown>) => {
    const index = Number(row._rowIndex ?? -1)
    if (index < 0) return []
    return [{
      label: t('freight.ui.printInvoice'),
      icon: 'i-lucide-printer',
      onSelect: () => printServiceChargeLine(index, row.id),
    }]
  }
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
  if (module.value?.collection === 'quotations' && tableKey === 'revisionHistory') {
    if (revisionHistory.value.length) return revisionHistory.value
    return [{
      id: model.value.id,
      revisionNo: model.value.revisionNo,
      status: model.value.status,
      quotationDate: model.value.date,
      validUntil: model.value.validUntil,
      currency: model.value.currency,
      total: model.value.total,
      isCurrent: true,
    }]
  }
  return Array.isArray(model.value[tableKey])
    ? model.value[tableKey] as Array<Record<string, unknown>>
    : []
}

/** Revision history is authoritative from the backend (all revisions, not just the latest). */
async function loadRevisionHistory() {
  if (module.value?.collection !== 'quotations' || isCreate.value || !model.value.id) {
    revisionHistory.value = []
    return
  }
  try {
    revisionHistory.value = await lcs.quotations.listRevisions(String(model.value.quotationId || model.value.id))
  }
  catch {
    revisionHistory.value = []
  }
}

const revisionTable = computed<FreightTable | null>(() =>
  module.value?.tables?.find(table => table.key === 'revisionHistory') || null,
)

const revisionGrid = computed(() => revisionGridRows(revisionHistory.value))

/** The trailing actions column: open a revision; edit/delete are deliberately absent. */
function revisionMenuItems(row: Record<string, unknown>) {
  return [{
    label: t('lcs.actions.view'),
    icon: 'i-lucide-eye',
    onSelect: () => { void onLineRowAction('view', row) },
  }]
}

watch(
  [() => module.value?.collection, () => model.value.id, () => model.value.revisionId, isCreate],
  () => { void loadRevisionHistory() },
  { immediate: true },
)

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
  const jobs = store.list('jobs')
  const linkedId = String(model.value.serviceOrderId || '').trim()
  if (linkedId) {
    const byId = jobs.find(row => String(row.id) === linkedId)
    if (byId) return byId
  }
  const linkedNo = String(model.value.serviceOrderNo || '').trim()
  if (linkedNo) {
    const byNo = jobs.find(row => String(row.jobNo || '') === linkedNo)
    if (byNo) return byNo
  }
  return jobForQuotation(jobs, model.value)
}

async function openRelatedServiceOrder() {
  const job = relatedServiceOrder()
  if (!job?.id) {
    toast.add({ title: t('lcs.states.notFound'), color: 'warning' })
    return
  }
  await navigateTo(`/service-orders/${String(job.id)}`)
}

/** Quotation delete: guarded by status/permission and the backend link rule. */
async function deleteQuotation() {
  if (!quotationAvailability.value.delete || !model.value.id) return
  const ok = await confirm({ kind: 'delete', count: 1 })
  if (!ok) return
  try {
    await moduleRecord.remove([String(model.value.id)])
    toast.add({ title: t('lcs.actions.deletedItems', { n: 1 }), color: 'success' })
    await navigateTo('/quotations')
  }
  catch (error) {
    // A dependency refusal ("still referenced by…") is a page-level message,
    // not a toast and not a field error: it has no single input to own it.
    validation.reset()
    validation.applyServerError(error)
  }
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
  onError: message => validation.addFormError(message),
})

const financeCommands = useFinanceCommands({
  lcs,
  model,
  store,
  toast: toast.add,
  t,
  periodClosed,
  recalculate,
  traceLink,
  openReverse: () => { reverseOpen.value = true },
  onError: message => validation.addFormError(message),
})

const moreItems = computed<DropdownMenuItem[][]>(() => {
  // Service charge pages: no overflow (⋯) actions.
  if (module.value?.collection === 'jobCharges') return []
  const items: DropdownMenuItem[] = []
  const isQuotation = module.value?.collection === 'quotations'
  if (isQuotation && !isCreate.value && model.value.id) {
    if (quotationAvailability.value.openServiceOrder) {
      const serviceOrderNo = String(model.value.serviceOrderNo || '').trim()
      items.push({
        label: serviceOrderNo
          ? `${t('freight.ui.openServiceOrder')} · ${serviceOrderNo}`
          : t('freight.ui.openServiceOrder'),
        icon: 'i-lucide-briefcase',
        onSelect: () => { void openRelatedServiceOrder() },
      })
    }
    if (quotationAvailability.value.revise) {
      items.push({
        label: t('freight.ui.requote'),
        icon: 'i-lucide-git-branch',
        onSelect: () => { void quotationCommands.createRevision() },
      })
    }
    if (quotationAvailability.value.delete) {
      items.push({
        label: t('freight.ui.delete'),
        icon: 'i-lucide-trash-2',
        color: 'error' as const,
        onSelect: () => { void deleteQuotation() },
      })
    }
  }

  for (const action of overflowHeaderActions.value) {
    items.push(headerActionMenuItem(action))
  }

  if (module.value?.collection === 'roles' && !isCreate.value && model.value.id && lcs.can('role.manage')) {
    items.push({
      label: t('lcs.document.duplicate'),
      icon: 'i-lucide-copy-plus',
      onSelect: () => { void duplicateCurrentRole() },
    })
  }

  if (canMutateRecord.value && !protectedSystemRecord.value) {
    // Change Status is policy-driven: only transitions that are legal from this
    // record's status and permitted for this caller are offered. Financial
    // documents still run the posting and reversal engines through their own
    // endpoints — the status is never written directly.
    const statusItem = statusMenuItem(model.value, {
      allowTransition: transition => module.value?.collection !== 'quotations'
        || transitionsAvailableForQuotation(transition),
    })
    if (statusItem) items.push(statusItem)
    // Active records must be deactivated first; only inactive records can be deleted.
    if (String(model.value.status || '').trim().toUpperCase() === 'INACTIVE') {
      items.push({
        label: t('freight.ui.delete'),
        icon: 'i-lucide-trash-2',
        color: 'error' as const,
        onSelect: () => { void deleteRecord() },
      })
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
  if (module.value?.collection === 'quotations' && key === 'customerPartyId') {
    // Keep the denormalised company name in step with the selected party id.
    const party = store.list('businessParties').find(row => String(row.id) === String(value))
    next.customer = party ? String(party.legalName || party.name || '') : ''
  }
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
  clearFieldError(key)
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
  // Any structural edit (add / remove / reorder / cell change) invalidates the
  // row-indexed errors of that table; they are recomputed on the next submit so
  // a message can never end up pointing at the wrong row.
  validation.clearTableErrors(key)
  model.value = { ...model.value, [key]: rows }
  recalculate()
}

function recalculate() {
  if (!module.value) return
  model.value = recalculateFreightRecord(module.value, model.value)
}

/**
 * Client-side gate. Runs before every create/update so an invalid form never
 * reaches the API; business rules that need the whole record live here too,
 * so their message lands on the input that caused them.
 */
function collectValidationFailures(isNew: boolean): ValidationFailure[] {
  const current = module.value
  if (!current) return []
  const failures = validateDocumentFields({
    fields: current.fields.filter(field => field.key !== 'status'),
    model: model.value as Record<string, unknown>,
    isCreate: isNew,
    label: fieldKeyLabel,
    skipKeys: [],
    formRules: businessRuleFailures(isNew),
  })

  for (const table of current.tables || []) {
    const rows = Array.isArray(model.value[table.key])
      ? model.value[table.key] as Array<Record<string, unknown>>
      : []
    if (READ_ONLY_TABLES.has(table.key) || table.kind === 'files') continue
    failures.push(...validateTableRows({
      table,
      rows,
      label: fieldKeyLabel,
      columnLabel: column => fieldLabel({ ...column, label: column.label || column.key }),
    }))
  }
  return failures
}

/** Tables the document renders for information only; never validated. */
const READ_ONLY_TABLES = new Set(['revisionHistory', 'sourceRelationships', 'attachments'])

/**
 * Cross-field and cross-record rules that a single field rule cannot express.
 * Each returns a failure aimed at the input the user must actually change.
 */
function businessRuleFailures(isNew: boolean): Record<string, (record: Record<string, unknown>) => ValidationFailure | null> {
  const current = module.value
  if (!current) return {}
  const rules: Record<string, (record: Record<string, unknown>) => ValidationFailure | null> = {}

  if (current.collection === 'quotations') {
    rules.validUntil = () => {
      const quotationDate = String(model.value.date || '').slice(0, 10)
      const validUntil = String(model.value.validUntil || '').slice(0, 10)
      if (!quotationDate || !validUntil || validUntil >= quotationDate) return null
      return {
        key: 'validUntil',
        code: 'custom',
        message: t('validation.validUntilBeforeDate'),
        label: fieldKeyLabel('validUntil'),
      }
    }
  }

  if (current.collection === 'componentTemplates') {
    rules.maximumInstances = () => {
      const minimum = Number(model.value.minimumInstances || 0)
      const maximum = Number(model.value.maximumInstances || 0)
      if (minimum < 0 || maximum < 0 || (maximum > 0 && maximum < minimum)) {
        return {
          key: 'maximumInstances',
          code: 'custom',
          message: t('freight.ui.invalidInstanceLimits'),
          label: fieldKeyLabel('maximumInstances'),
        }
      }
      return null
    }
  }

  if (current.collection === 'journals') {
    // Debit must equal credit — a cross-field rule the backend also enforces.
    rules.lines = () => (Number(model.value.balanceDifference || 0) === 0
      ? null
      : {
          key: 'lines',
          code: 'balanced',
          label: fieldKeyLabel('lines'),
        })
  }

  if (current.collection === 'debitNotes') {
    rules.allocations = () => {
      const rows = Array.isArray(model.value.allocations) ? model.value.allocations as Array<Record<string, unknown>> : []
      if (!rows.length) return null
      const total = asNumber(model.value.total || model.value.amount)
      const allocated = rows.reduce((sum, row) => sum + asNumber(row.amount), 0)
      const exceedsTarget = rows.some(row => asNumber(row.amount) > asNumber(row.targetOutstanding || row.outstandingAmount))
      if (allocated > total || exceedsTarget) {
        return {
          key: 'allocations',
          code: 'custom',
          message: t('freight.ui.allocationExceeds'),
          label: fieldKeyLabel('allocations'),
        }
      }
      return null
    }
  }

  if (current.collection === 'transportAssets') {
    // Master-data vocabulary rules, forechecked before the save round trip; the
    // backend (`_validate_asset_record`) remains the authority.
    rules.identityType = () => {
      const name = String(model.value.identityType || '').trim()
      if (!name) return null // the required rule already reports the blank choice
      // An unchanged stored value stays valid even if the vocabulary row was
      // renamed, archived or deactivated since: the backend preserves it too.
      const stored = originalModel.value
      if (stored
        && name === String(stored.identityType || '').trim()
        && String(model.value.transportType || '').trim() === String(stored.transportType || '').trim()) {
        return null
      }
      const chosen = store.list('transportAssetIdentityTypes')
        .find(row => String(row.name || '').trim().toLowerCase() === name.toLowerCase())
      if (!chosen || String(chosen.status || 'ACTIVE').toUpperCase() === 'INACTIVE') {
        return { key: 'identityType', code: 'custom', message: t('freight.ui.identityTypeUnknown'), label: fieldKeyLabel('identityType') }
      }
      const applies = String(chosen.transportType || '').trim()
      if (applies && applies.toLowerCase() !== String(model.value.transportType || '').trim().toLowerCase()) {
        return { key: 'identityType', code: 'custom', message: t('freight.ui.identityTypeMismatch'), label: fieldKeyLabel('identityType') }
      }
      return null
    }
    rules.identity = () => {
      const chosen = identityTypeRowOf(model.value as Record<string, unknown>)
      // An unknown or empty type is what the identityType rule reports.
      if (!chosen || matchesIdentityPattern(chosen.validationPattern, String(model.value.identity || ''))) return null
      const label = String(chosen.identityLabel || chosen.name || '').trim()
      return { key: 'identity', code: 'custom', message: t('freight.ui.invalidIdentityPattern', { label }), label: fieldKeyLabel('identity') }
    }
    // Capacity is optional as a whole, but value and unit travel together — the
    // backend `_validate_asset_record` refuses the half-filled pair as well.
    rules.capacityValue = () => {
      if (!String(model.value.capacityUnit || '').trim()) return null
      const value = model.value.capacityValue
      if (value === null || value === undefined || value === '') {
        return { key: 'capacityValue', code: 'custom', message: t('freight.ui.capacityNeedsValue'), label: fieldKeyLabel('capacityValue') }
      }
      return null
    }
    rules.capacityUnit = () => {
      const value = model.value.capacityValue
      if (value === null || value === undefined || value === '') return null
      if (!String(model.value.capacityUnit || '').trim()) {
        return { key: 'capacityUnit', code: 'custom', message: t('freight.ui.capacityNeedsUnit'), label: fieldKeyLabel('capacityUnit') }
      }
      return null
    }
  }

  /**
   * A period that ends before it starts is not a valid document period, whether
   * the second date is an offer expiry or a credit due date. Both dates are
   * ISO `YYYY-MM-DD`, so a lexical comparison is also a chronological one.
   */
  const dateOrderRule = (laterKey: string, earlierKey: string) => (): ValidationFailure | null => {
    const later = String(model.value[laterKey] || '').slice(0, 10)
    const earlier = String(model.value[earlierKey] || '').slice(0, 10)
    if (!later || !earlier || later >= earlier) return null
    return {
      key: laterKey,
      code: 'custom',
      message: t('validation.dateOrder', {
        field: fieldKeyLabel(laterKey),
        other: fieldKeyLabel(earlierKey),
      }),
      label: fieldKeyLabel(laterKey),
    }
  }

  if (current.collection === 'quotations') {
    rules.validUntil = dateOrderRule('validUntil', 'date')
  }
  if (current.collection === 'debitNotes') {
    rules.dueDate = dateOrderRule('dueDate', 'date')
    rules.valueDate = dateOrderRule('valueDate', 'date')
  }

  if (current.collection === 'componentTemplates' && !isNew && originalModel.value
    && String(model.value.instanceMode) !== String(originalModel.value.instanceMode || 'SINGLE')) {
    const used = store.list('serviceComponents').some(row =>
      String(row.templateCode) === String(model.value.code)
      && String(row.templateVersion) === String(model.value.version),
    )
    if (used) {
      rules.instanceMode = () => ({
        key: 'instanceMode',
        code: 'custom',
        message: t('freight.ui.cardinalityVersionRequired'),
        label: fieldKeyLabel('instanceMode'),
      })
    }
  }

  return rules
}

async function save(status?: string) {
  if (!module.value || readOnly.value) return
  // Creating a user must not bypass the password policy through Enter or a
  // programmatic call while the Save button is disabled.
  if (!canSave.value) return
  // Guard against a double click / repeated Enter while the request is pending.
  if (saving.value) return
  saving.value = true
  validation.submitting.value = true
  validation.reset()
  try {
    recalculate()
    const payload = { ...model.value }
    if (status) payload.status = status
    if (module.value.collection === 'componentTemplates') {
      Object.assign(payload, normalizeComponentTemplateRecord(payload))
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
    if (module.value.collection === 'debitNotes') {
      // A line's account code is derived from the posting rules for display, so it
      // is stripped before saving: the rule in force at posting time decides, and a
      // form that was merely opened and saved must not pin an account of its own.
      payload.lines = (Array.isArray(payload.lines) ? payload.lines : []).map((line) => {
        const next = { ...(line as Record<string, unknown>) }
        delete next.accountCode
        return next
      })
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
    }

    const isNew = isCreate.value || !payload.id
    const failures = collectValidationFailures(isNew)
    if (failures.length) {
      validation.applyFailures(failures)
      await validation.focusFirstInvalid()
      return
    }

    if (module.value.collection === 'documentSequences') {
      const duplicate = store.list('documentSequences').find(row =>
        String(row.id) !== String(payload.id || '')
        && String(row.documentType) === String(payload.documentType)
        && Number(row.year) === Number(payload.year),
      )
      if (duplicate) {
        validation.setFieldError('year', t('validation.duplicateSequence', {
          type: documentSequenceTypeLabel(payload.documentType),
          year: payload.year,
        }))
        await validation.focusFirstInvalid()
        return
      }
      if (!isCreate.value && originalModel.value && Number(payload.lastValue) !== Number(originalModel.value.lastValue)) {
        const ok = await confirm({
          kind: 'generic',
          title: t('lcs.document.sequenceChangeTitle'),
          description: t('lcs.document.sequenceChangeDescription'),
          confirmLabel: t('lcs.document.sequenceChangeConfirm'),
          confirmColor: 'warning',
        })
        if (!ok) return
      }
    }

    if (module.value.collection === 'transportAssets') {
      // An asset code is unique across active rows. The backend refuses a
      // duplicate with a field error, but catching it here keeps the message on
      // the field without a round trip and covers a code another page owns.
      const duplicate = store.list('transportAssets').find(row =>
        String(row.id) !== String(payload.id || '')
        && String(row.assetCode || '').trim().toLowerCase() === String(payload.assetCode || '').trim().toLowerCase(),
      )
      if (duplicate) {
        validation.setFieldError('assetCode', t('validation.duplicateAssetCode', { code: String(payload.assetCode || '').trim() }))
        await validation.focusFirstInvalid()
        return
      }
    }

    if (isNew) {
      payload.createdAt ||= new Date().toISOString()
      payload.createdBy ||= String(currentUser.value?.name || 'Current User')
      payload.status ||= defaultStatusForModule(module.value)
      payload.currency ||= localization.value.currency
    }
    const saved = await documentActions.persistRecord(payload, isNew)
    if (!saved) return
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    // A newly created account's password cannot be read back afterwards — the
    // server keeps only a digest — so it is shown once, here, before leaving the
    // form. Skipping this would leave the administrator unable to tell the user
    // what to sign in with.
    if (isNew && module.value.collection === 'users' && String(payload.password || '')) {
      passwordDialog.userId = String((saved as Record<string, unknown>).id || '')
      passwordDialog.userLabel = String(payload.displayName || payload.username || '')
      passwordDialog.revealedPassword = String(payload.password)
      passwordDialog.mode = 'handover'
      passwordDialog.open = true
      return
    }
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
    await leaveAfterSave()
  }
  catch (error) {
    // Every rejected request lands on a field (or the form-level summary) and
    // navigates to the first one. Validation errors never become a toast.
    validation.applyServerError(error)
    await validation.focusFirstInvalid()
  }
  finally {
    saving.value = false
    validation.submitting.value = false
  }
}

/**
 * Return to the list once the password handover (if any) has been dismissed, so
 * the administrator cannot lose the password behind a navigation.
 */
async function leaveAfterSave() {
  if (!module.value) return
  if (passwordDialog.open && passwordDialog.mode === 'handover') {
    handoverLeaving.value = true
    return
  }
  await navigateTo(module.value.path)
}

/** The handover dialog closed: now it is safe to leave the form. */
async function onPasswordDialogClosed(opened: boolean) {
  if (opened || !handoverLeaving.value) return
  handoverLeaving.value = false
  if (module.value) await navigateTo(module.value.path)
}

/**
 * Setting another account's password. The dialog owns the form and the reveal;
 * the password is shown *after* the server accepts it, so the administrator
 * hands over one that is known to work rather than one that might have been
 * rejected for a policy reason.
 */
function openPasswordDialog() {
  if (!model.value.id) return
  passwordDialog.userId = String(model.value.id)
  passwordDialog.userLabel = String(model.value.displayName || model.value.username || '')
  passwordDialog.revealedPassword = ''
  passwordDialog.mode = 'set'
  passwordDialog.open = true
}

async function duplicateCurrentRole() {
  if (module.value?.collection !== 'roles' || !model.value.id || duplicatingRole.value) return
  duplicatingRole.value = true
  try {
    const duplicated = unwrapApiData(await api.post<ApiResponse<FreightRecord>>(
      ApiV1Endpoints.ROLE_DUPLICATE(String(model.value.id)),
      {},
    ))
    await store.reload()
    toast.add({ title: t('lcs.document.duplicate'), color: 'success' })
    await navigateTo(`${module.value.path}/${duplicated.id}`)
  }
  catch (error) {
    validation.reset()
    validation.applyServerError(error)
  }
  finally {
    duplicatingRole.value = false
  }
}

async function openPrint(templateId: PrintTemplateId) {
  await documentActions.openPrint(templateId)
}

/**
 * Workflow actions (send, accept, post, issue, reverse, delete…) fail for
 * business-rule reasons — "period is closed", "already approved". Those have
 * no input to own them, so they become a page-level message rather than a
 * toast; field-addressable refusals still land on their field.
 */
function reportCommandError(error: unknown) {
  validation.reset()
  validation.applyServerError(error)
  void validation.focusFirstInvalid()
}

/**
 * Re-quotation from a service order: a new draft offer, never an edit of the
 * order or of the quotation the order was converted from.
 */
async function createRequotation() {
  const serviceOrderId = String(model.value.id || '')
  if (!serviceOrderId) return
  const ok = await confirm({
    kind: 'submit',
    title: t('freight.ui.serviceOrderRequoteTitle'),
    description: t('freight.ui.serviceOrderRequoteDescription'),
    confirmLabel: t('freight.ui.requote'),
  })
  if (!ok) return
  const created = await lcs.quotations.createFromServiceOrder(serviceOrderId)
  store.reload()
  toast.add({ title: t('freight.ui.serviceOrderRequoteCreated'), color: 'success' })
  await navigateTo(`/quotations/${String(created.id)}`)
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
    if (key === 'createRevision' && module.value.collection === 'quotations') return quotationCommands.createRevision()
    if (key === 'convertJob') return quotationCommands.convertJob()
    if (key === 'requoteFromServiceOrder' && module.value.collection === 'serviceOrders') return createRequotation()
    if (key === 'issue' && module.value.collection === 'jobCharges') return financeCommands.issueCharge()
    if (key === 'createInvoice' && module.value.collection === 'jobCharges') return financeCommands.createInvoiceFromCharge()
    if (key === 'viewInvoice' && module.value.collection === 'jobCharges') return financeCommands.viewInvoiceFromCharge()
    if (key === 'backToServiceCharge' && module.value.collection === 'debitNotes') return financeCommands.backToServiceCharge()
    if (key === 'post' && module.value.collection === 'debitNotes') return financeCommands.postDocument()
    if (key === 'postJournal' && module.value.collection === 'journals') return financeCommands.postJournal()
    if (key === 'setPassword' && module.value.collection === 'users') return openPasswordDialog()
    if (key === 'reverse' && module.value.collection === 'debitNotes') return financeCommands.reverseDocument()
    if (key === 'delete') return documentActions.deleteRecord()
    if (key === 'recordPayment') return financeCommands.recordPayment()
  }
  catch (error) {
    reportCommandError(error)
  }
}

async function deleteRecord() {
  await documentActions.deleteRecord()
}

async function confirmReverse() {
  if (!module.value) return
  const reason = String(reverseDraft.reason || '').trim()
  if (!reason) {
    reverseErrors.value = [t('validation.required', { field: t('lcs.finance.reverseReason') })]
    await nextTick()
    await focusField('reverse.reason')
    return
  }
  reverseErrors.value = []
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
    reverseErrors.value = [apiErrorMessage(error, t('api.somethingWentWrong'))]
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
:field-errors="fieldErrors"
      :on-field-edit="clearFieldError"
      :on-field-blur="validateFieldOnBlur"
      :form-errors="validation.formErrors.value"
      :can-save="canSave"
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
      <FreightUserPasswordDialog
        :open="passwordDialog.open"
        :mode="passwordDialog.mode"
        :user-id="passwordDialog.userId"
        :user-label="passwordDialog.userLabel"
        :revealed-password="passwordDialog.revealedPassword"
        @update:open="onPasswordDialogClosed" />

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
v-if="module.collection === 'debitNotes' && periodClosed"
wide
          class="space-y-4 pt-6">
          <UAlert
color="error"
variant="subtle"
            icon="i-lucide-calendar-off"
:title="$t('lcs.finance.periodClosed')" />
        </DocumentAppDocumentContentShell>
      </template>

      <template #tab-extra="{ tabId }">
        <DocumentAppDocumentContentShell
          v-if="tabId === 'revisions' && module.collection === 'quotations' && !isCreate"
          wide>
          <div class="py-6">
            <FreightAppLineTable
              v-if="revisionTable"
              :table="revisionTable"
              :model-value="revisionGrid"
              :extra-row-menu-items="revisionMenuItems" />
          </div>
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
        <CommonAppFormErrorSummary class="mb-4" :form-errors="reverseErrors" />
        <DocumentAppFieldGrid
:fields="FINANCE_REVERSE_FORM_FIELDS"
:model="reverseDraft"
          :field-errors="{ 'reason': reverseErrors[0] || '' }"
          key-prefix="reverse."
          @update="(key, value) => {
            reverseDraft[key] = value
            if (key === 'reason' && reverseErrors.length) reverseErrors = []
          }" />
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
  <div v-else class="p-6 text-sm text-muted">{{ t('lcs.document.notFound') || 'Record not found.' }}</div>
</template>

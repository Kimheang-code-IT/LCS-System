<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { DocumentTabSchema } from '~/types/common'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import { useFreightRecordChrome } from '~/composables/freight/useFreightRecordChrome'
import { useJobRelated } from '~/composables/freight/useJobRelated'
import { useModuleRecord } from '~/composables/freight/useModuleRecord'
import { useLcs } from '~/composables/freight/useLcs'
import { useRequotation } from '~/composables/freight/useRequotation'
import {
  emptyFreightRecord,
  groupedFields,
  statusColor,
  useFreightLabel,
  useFreightRouteModule,
} from '~/composables/freight/useFreight'
import type { FreightRecord } from '~/types/record'
import {
  parseJobWorkspaceSection,
  type JobWorkspaceSection,
} from '~/utils/freight/job-workspace'
import {
  JOB_FIXED_WORKSPACE_SECTIONS,
  JOB_TRAILING_WORKSPACE_SECTIONS,
} from '~/utils/freight/job-component-tabs'
import { useComponentTabs } from '~/composables/freight/useComponentTabs'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateDocumentFields } from '~/utils/validation/record-validation'
import { validateComponentRows } from '~/utils/validation/component-rules'
import { normalizeApiError } from '~/utils/validation/api-error'
import { issueFromBackendMessage } from '~/utils/validation/field-rules'
import { jobDomainStatus, serviceOrderStatusLabel } from '~/utils/freight/states'
import { sanitizeDraftModel } from '~/composables/common/useRecordDraft'
import { useRecordFormDraft } from '~/composables/common/useRecordFormDraft'
import { serviceOrderBreadcrumbs } from '~/utils/freight/job-workspace'

const { module, isCreate, recordId, route } = useFreightRouteModule()
const moduleRecord = useModuleRecord(module)
const store = useFreightStore()
const toast = useToast()
const router = useRouter()
const { t, te } = useI18n()
const { moduleTitle, fieldLabel } = useFreightLabel()
/** Linked charges with the Service Charge tab's unsaved totals (when visited). */
const chargeSummaryRows = ref<FreightRecord[]>([])
const { setBreadcrumbs, setBadges, clear } = useAppHeader()
const { confirm, setLoading: setConfirmLoading, dismiss: dismissConfirm } = useConfirm()
const lcs = useLcs()

const saving = ref(false)
const model = ref<FreightRecord>({} as FreightRecord)
const notFound = ref(false)
/** The Service Charge tab owns its own save boundary; it reports unsaved edits
 *  only so the page can warn before a destructive action. */
const chargesDirty = ref(false)
const chargesVisited = ref(false)
/** The Finance tab has the same local inline draft; keep it alive too. */
const financeVisited = ref(false)
/** Every visited editable tab stays mounted (hidden) so its local controls —
 *  selects, dates, textareas and dynamic rows — keep their in-progress state. */
const visitedTabs = ref<Set<string>>(new Set(['overview']))
function tabVisited(id: string) {
  return visitedTabs.value.has(id)
}

const domainStatus = computed(() => jobDomainStatus(model.value))
// Finish locks operational editing: an editable page and a FINISHED record no
// longer mix (finance settlement continues on the Finance tab).
const canEdit = computed(() =>
  !isCreate.value && domainStatus.value !== 'FINISHED' && lcs.can('service_order.update'))
const canEditPayments = computed(() =>
  !isCreate.value && lcs.can('service_order.update'))

const {
  listTo,
  canNavigatePrevious,
  canNavigateNext,
  navigatePrevious,
  navigateNext,
  attachments,
  setChromeField,
} = useFreightRecordChrome({ module, isCreate, recordId, model })

const jobNo = computed(() => String(model.value.jobNo || ''))
const {
  shipments,
  documents,
  charges,
  supplierCosts,
  debitNotes,
  receivables,
  actualContainers,
  containerRequirements,
} = useJobRelated(jobNo)

/**
 * Operational tabs come from the configurable component tabs (Attribute ->
 * Group -> Tab), filtered by the Service Order's trade direction.
 */
const directionId = computed(() => {
  const name = String(model.value.direction || '').trim().toLowerCase()
  if (!name) return undefined
  const row = store.list('tradeDirections').find(item =>
    String(item.name || '').toLowerCase() === name || String(item.code || '').toLowerCase() === name,
  )
  return row ? String(row.id) : undefined
})
const componentTabsState = useComponentTabs(jobNo, directionId)
const componentSections = computed(() => componentTabsState.sections.value)
const workspaceSections = computed(() => [
  ...JOB_FIXED_WORKSPACE_SECTIONS,
  ...componentSections.value,
  ...JOB_TRAILING_WORKSPACE_SECTIONS,
])

/**
 * Dynamic tabs are addressed by the same stable keys validation uses, so an
 * error deep inside a collapsed tab group can reveal itself.
 */
function componentCellLabel(key: string) {
  const [groupId, , code] = key.split('.')
  return componentGroupLabel(groupId || '', code || key)
}

function componentTabForGroup(groupId: string) {
  return componentTabsState.tabs.value.find(tab => tab.groups.some(group => group.id === groupId))
}

function componentGroupLabel(groupId: string, code: string) {
  for (const tab of componentTabsState.tabs.value) {
    const group = tab.groups.find(item => item.id === groupId)
    const attribute = group?.attributes.find(item => item.code === code)
    if (group && attribute) return `${tab.name} › ${group.name} › ${attribute.label}`
  }
  // Unknown key: return an empty label so the shared message uses its
  // label-free wording instead of leaking a composite model key to the user.
  return ''
}

const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  label: componentCellLabel,
  order: () => workspaceSections.value.flatMap(section =>
    componentTabsState.tabs.value
      .filter(tab => tab.code === section)
      .flatMap(tab => tab.groups.flatMap(group =>
        group.attributes.map(attribute => `${group.id}.0.${attribute.code}`),
      )),
  ),
  reveal: (key) => {
    const groupId = key.split('.')[0]!
    const tab = componentTabForGroup(groupId)
    if (!tab) return false
    if (activeTab.value !== tab.code) activeTab.value = tab.code
    return true
  },
})
const { requoteFromServiceOrder } = useRequotation({
  confirm,
  setConfirmLoading,
  dismissConfirm,
  toast,
  onError: message => validation.addFormError(message),
})

function setComponentRows(groupId: string, rows: Array<Record<string, unknown>>) {
  // Row-indexed errors belong to the previous row set; recompute on next save.
  validation.clearTableErrors(groupId)
  componentTabsState.setGroupRows(groupId, rows)
}

/** Validate one job header field when the user leaves it. */
function validateJobField(key: string) {
  const field = module.value?.fields.find(item => item.key === key)
  if (!field || field.computed) return
  const failures = validateDocumentFields({
    fields: [field],
    model: model.value as Record<string, unknown>,
    isCreate: isCreate.value,
    label: item => fieldLabel({ key: item, label: item }),
  })
  validation.clearFieldError(key)
  const failure = failures.find(item => item.key === key)
  if (failure) {
    validation.setFieldError(key, validation.message(failure, fieldLabel({ key, label: key })))
  }
}

/** Validate the job header plus every visible dynamic tab group. */
function validateOrder() {
  const failures = validateDocumentFields({
    fields: module.value?.fields || [],
    model: model.value as Record<string, unknown>,
    isCreate: isCreate.value,
    label: key => fieldLabel({ key, label: key }),
  })
  for (const tab of componentTabsState.tabs.value) {
    for (const group of tab.groups) {
      failures.push(...validateComponentRows({
        group,
        rows: componentTabsState.rowsForGroup(group.id),
        label: attribute => String(attribute.label || attribute.code),
        skipBlankRows: true,
      }))
    }
  }
  return failures
}

async function saveComponentGroup(groupId: string) {
  const group = componentTabsState.tabs.value.flatMap(tab => tab.groups).find(item => item.id === groupId)
    || { id: groupId, attributes: [] }
  const failures = validateComponentRows({
    group,
    rows: componentTabsState.rowsForGroup(groupId),
    label: attribute => String(attribute.label || attribute.code),
    skipBlankRows: true,
  })
  if (failures.length) {
    validation.applyFailures(failures)
    await validation.focusFirstInvalid()
    return
  }
  validation.clearTableErrors(groupId)
  try {
    await componentTabsState.saveGroup(groupId)
    // The saved rows are the new baseline: only later edits are draft-worthy.
    componentRowsSnapshot.value = componentRowsJson()
  }
  catch (error) {
    validation.reset()
    // Component row errors arrive as `<1-based row>.<code>`; the rest of the
    // app addresses cells as `<groupId>.<0-based row>.<code>`. Remap them so a
    // rejected cell shows its message inline instead of as a page-level line.
    const normalized = normalizeApiError(error)
    const codes = new Set(group.attributes.map(attribute => attribute.code))
    const mapped: Record<string, string> = {}
    const formLevel: string[] = []
    for (const item of normalized.items) {
      const row = /^(\d+)\.(.+)$/.exec(item.key)
      if (!row || !codes.has(row[2]!)) {
        formLevel.push(item.message)
        continue
      }
      const path = `${groupId}.${Math.max(Number(row[1]) - 1, 0)}.${row[2]}`
      const issue = issueFromBackendMessage(item.message)
      mapped[path] = issue
        ? validation.message(issue, componentCellLabel(path))
        : item.message.trim().toLowerCase() === 'required'
          ? validation.message({ code: 'required' }, componentCellLabel(path))
          : item.message
    }
    if (normalized.message && !formLevel.length) formLevel.push(normalized.message)
    validation.setErrors(mapped, formLevel)
    await validation.focusFirstInvalid()
  }
}

function parseSection(value: unknown) {
  return parseJobWorkspaceSection(value, workspaceSections.value)
}

const activeTab = ref<JobWorkspaceSection>('overview')

function sectionLabel(id: string) {
  const componentTab = componentTabsState.tabByCode(id)
  if (componentTab) return componentTab.name
  const key = `freight.jobSections.${id}`
  if (te(key)) return t(key)
  return id
}

const tabs = computed<DocumentTabSchema[]>(() =>
  workspaceSections.value.map(id => ({
    id,
    labelKey: `freight.jobSections.${id}`,
    label: sectionLabel(id),
    sections: [{ id, title: sectionLabel(id), fields: [] }],
  })),
)

/** Snapshot of the last loaded/saved record; a differing model means unsaved edits. */
const savedSnapshot = ref('')
const auth = useAuthStore()

/** Unsaved admin-configured component-tab rows, kept with the page draft. */
const componentDraftPending = ref<Record<string, Array<Record<string, unknown>>> | null>(null)
const componentRowsSnapshot = ref('')
/** Order the component baseline belongs to; a same-order refresh keeps it. */
let componentSnapshotOrder = ''

function componentRowsJson() {
  return JSON.stringify(sanitizeDraftModel(componentTabsState.rowsByGroup.value))
}

const componentRowsDirty = computed(() => Boolean(componentRowsSnapshot.value)
  && componentRowsJson() !== componentRowsSnapshot.value)

const jobDirty = computed(() => chargesDirty.value
  || componentRowsDirty.value
  || (Boolean(savedSnapshot.value)
    && JSON.stringify(sanitizeDraftModel(model.value)) !== savedSnapshot.value))

/**
 * One versioned local draft for the order: header/route/container/files state
 * plus the dynamic component-tab rows that are not part of `model`. A draft
 * written against an older server copy is never applied silently.
 */
const formDraft = useRecordFormDraft<FreightRecord>({
  collection: () => 'serviceOrders',
  scope: () => String(auth.user?.id || 'anon'),
  recordId: () => isCreate.value ? '' : recordId.value,
  baseUpdatedAt: () => String(model.value.updatedAt || ''),
  model: () => model.value,
  apply: (stored) => {
    const { componentRows, ...rest } = stored
    model.value = { ...model.value, ...rest } as FreightRecord
    componentDraftPending.value = componentRows && typeof componentRows === 'object'
      ? componentRows as Record<string, Array<Record<string, unknown>>>
      : null
  },
  isDirty: () => jobDirty.value,
  canDraft: () => isCreate.value || canEdit.value,
  sanitize: (record) => {
    const next = sanitizeDraftModel(record)
    // Server-owned/volatile collections are not editable draft state.
    delete next.attachments
    delete next.activity
    delete next.comments
    next.componentRows = sanitizeDraftModel(componentTabsState.rowsByGroup.value)
    return next
  },
  suspend: () => saving.value,
  warnOnUnload: true,
})

/** Point the draft at the order now in `model` and offer any stored copy. */
function restorePageDraft() {
  formDraft.bind()
  formDraft.restore()
}

/** Keep the component-row baseline in step with a fresh load or a group save. */
function captureComponentBaseline() {
  const serverRows = componentRowsJson()
  if (componentDraftPending.value) {
    for (const [groupId, rows] of Object.entries(componentDraftPending.value)) {
      if (Array.isArray(rows)) componentTabsState.setGroupRows(groupId, rows)
    }
    componentDraftPending.value = null
  }
  componentRowsSnapshot.value = serverRows
}

watch(() => componentTabsState.tabs.value, captureComponentBaseline, { immediate: true })

watch(
  [() => sanitizeDraftModel(model.value), componentRowsDirty],
  () => {
    if (jobDirty.value) formDraft.schedule()
    // A reverted edit must not leave a stale local copy behind.
    else formDraft.flush()
  },
  { deep: true },
)

function load() {
  if (!module.value) return
  // The preview belongs to the previous order; the Service Charge tab emits a
  // fresh projection once the new order is available.
  if (String(model.value.id || '') !== recordId.value) chargeSummaryRows.value = []
  // The route may already address a new record while `model` still holds the
  // previous one: keep that copy under its own key before replacing it.
  formDraft.flush()
  const targetOrder = isCreate.value ? '' : recordId.value
  if (componentSnapshotOrder !== targetOrder) {
    // No component baseline belongs to the record being replaced; the tabs
    // reload for the new order and the watcher below captures its baseline.
    componentDraftPending.value = null
    componentRowsSnapshot.value = ''
    componentSnapshotOrder = targetOrder
  }
  if (isCreate.value) {
    model.value = emptyFreightRecord(module.value) as FreightRecord
    // Method A (Quotations → Convert to Service Order) lands here with the
    // source quotation in the query; selecting it prefills the form below.
    const fromQuery = String(route.query.quotationId || '').trim()
    if (fromQuery) model.value = { ...model.value, quotationId: fromQuery }
    notFound.value = false
    savedSnapshot.value = JSON.stringify(sanitizeDraftModel(model.value))
    restorePageDraft()
    return
  }
  const found = store.get('jobs', recordId.value)
  notFound.value = !found
  model.value = found ? { ...found } as FreightRecord : {} as FreightRecord
  savedSnapshot.value = JSON.stringify(sanitizeDraftModel(model.value))
  restorePageDraft()
}

watch(
  [recordId, isCreate, () => Boolean(recordId.value && store.get('jobs', recordId.value))],
  load,
  { immediate: true },
)

watch(
  [() => route.query.section, workspaceSections],
  () => {
    const section = parseSection(route.query.section)
    if (activeTab.value !== section) activeTab.value = section
  },
  { immediate: true },
)

watch(activeTab, (section) => {
  const current = parseSection(route.query.section)
  if (current === section) return
  const query = { ...route.query }
  if (section === 'overview') delete query.section
  else query.section = section
  void router.replace({ query })
})

/** Deep link from the list row action: /service-orders/:id?section=containers&new=1 */
watch(() => route.query.new, (value) => {
  if (value !== '1') return
  activeTab.value = 'containers'
  const query = { ...route.query }
  delete query.new
  void router.replace({ query })
}, { immediate: true })

const jobSections = computed(() => module.value ? groupedFields(module.value) : [])

const headerSubtitle = computed(() =>
  [String(model.value.customer || ''), String(model.value.direction || '')]
    .filter(Boolean).join(' · '),
)

watch([jobNo, () => model.value.serviceOrderNo, () => model.value.status, () => notFound.value, headerSubtitle], () => {
  if (!module.value) return
  setBreadcrumbs(serviceOrderBreadcrumbs(
    moduleTitle(module.value),
    module.value.path,
    model.value as Record<string, unknown>,
    { loading: !notFound.value && !isCreate.value, notFound: notFound.value },
  ))
  const statusLabel = serviceOrderStatusLabel(model.value.status)
  setBadges([
    ...(model.value.direction ? [{ label: String(model.value.direction), color: 'info' as const }] : []),
    ...(statusLabel ? [{ label: statusLabel, color: statusColor(statusLabel) }] : []),
  ])
}, { immediate: true })

onBeforeUnmount(clear)
usePageSeo({ title: () => String(model.value.jobNo || 'Job') })

function setField(key: string, value: unknown) {
  model.value = { ...model.value, [key]: value }
}

function patchJob(patch: Record<string, unknown>) {
  model.value = { ...model.value, ...patch }
}

/**
 * Unsaved edits are never silently lost: Finish and Re-Quotation warn first,
 * and proceeding is an explicit "discard" decision.
 */
async function confirmUnsaved(): Promise<boolean> {
  if (!jobDirty.value) return true
  return await confirm({
    kind: 'generic',
    title: t('lcs.common.confirmTitle'),
    description: t('lcs.document.unsavedConfirm'),
    confirmLabel: t('lcs.common.confirm'),
    confirmColor: 'warning',
  })
}

/**
 * Selecting a quotation populates the reusable commercial data: business party,
 * trade direction, currency, dates, description. Route, containers and pricing
 * lines are copied server-side on save, so the order stays its own record.
 * The watch also re-runs once the quotations list finishes loading, so a
 * preselected quotation (deep link) prefills even when the list arrives late.
 */
watch([() => model.value.quotationId, () => store.list('quotations').length], ([id]) => {
  if (!isCreate.value || !id) return
  const quotation = store.list('quotations').find(row => String(row.id) === String(id))
  if (!quotation) return
  patchJob({
    customer: quotation.customer,
    customerPartyId: quotation.customerPartyId,
    direction: quotation.direction,
    currency: quotation.currency,
    date: quotation.date,
    validUntil: quotation.validUntil,
    description: quotation.description || model.value.description,
  })
})

function fieldValue(key: string) {
  return model.value[key]
}

function setFieldValue(key: string, value: unknown) {
  if (key === 'tags' || key === 'assignee' || key === 'attachments' || key === 'favorite') {
    setChromeField(key, value)
    return
  }
  setField(key, value)
}

async function save() {
  if (!module.value) return
  if (saving.value) return
  saving.value = true
  validation.submitting.value = true
  validation.reset()
  try {
    const failures = validateOrder()
    // A quotation is optional: a Service Order can be created directly, and a
    // selected quotation only prefills editable fields (the backend re-checks
    // that a supplied quotation exists and is accessible).
    if (failures.length) {
      validation.applyFailures(failures)
      await validation.focusFirstInvalid()
      return
    }
    const payload = { ...model.value }
    // Snapshot of what this request writes. Anything typed while it is in flight
    // must survive in the draft instead of being cleared by the response.
    const submitted = JSON.stringify(sanitizeDraftModel(model.value))
    // Service Charges have their own save boundary (the Service Charge tab's own
    // button); the order save never creates or posts one.
    if (isCreate.value || !payload.id) {
      if (isCreate.value) {
        // A retried create is a replay for the backend: the idempotency key
        // answers with the already-created order instead of a duplicate copy.
        await lcs.runCommand(
          'service_order.create',
          String(payload.quotationId || 'new'),
          key => moduleRecord.create(payload, key),
        )
      }
      else {
        await moduleRecord.create(payload)
      }
    }
    else {
      await moduleRecord.update(String(payload.id), payload)
      // The request wrote `submitted`, not whatever is in the model now. Keep
      // later keystrokes untouched; the baseline is what the server accepted.
      savedSnapshot.value = submitted
    }
    // Clear only when nothing newer was typed while the request was open.
    if (JSON.stringify(sanitizeDraftModel(model.value)) === submitted) formDraft.clear()
    else formDraft.flush()
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    // Return to the service-order list after saving.
    await navigateTo(module.value.path)
  }
  catch (error) {
    validation.applyServerError(error)
    await validation.focusFirstInvalid()
  }
  finally {
    saving.value = false
    validation.submitting.value = false
  }
}

/**
 * View Quotation opens the order's own linked quotation (the real id from the
 * API; the number is only a fallback for legacy rows). An order without a
 * linked quotation explains that instead of navigating anywhere.
 */
function viewQuotation() {
  const id = String(model.value.quotationId || '').trim()
  if (id) {
    void navigateTo(`/quotations/${id}`)
    return
  }
  const quotation = store.list('quotations').find(row => String(row.quotationNo || '') === String(model.value.quotationNo || ''))
  if (quotation?.id) {
    void navigateTo(`/quotations/${String(quotation.id)}`)
    return
  }
  toast.add({ title: t('freight.ui.noLinkedQuotation'), color: 'warning' })
}

const jobSaveLabel = computed(() =>
  isCreate.value ? 'Save' : t('freight.ui.saveChanges'),
)

const finishing = ref(false)

async function finishJob() {
  if (!model.value.id) return
  const ok = await confirm({
    kind: 'submit',
    title: t('freight.ui.finishConfirmTitle'),
    description: t('freight.ui.finishConfirmDescription'),
    confirmLabel: t('freight.ui.finish'),
    confirmColor: 'primary',
  })
  if (!ok) return
  finishing.value = true
  try {
    const saved = await lcs.runCommand('service_order.finish', String(model.value.id), key =>
      lcs.jobs.finish(String(model.value.id), key),
    )
    model.value = { ...model.value, ...saved } as FreightRecord
    savedSnapshot.value = JSON.stringify(sanitizeDraftModel(model.value))
    formDraft.clear()
    store.reload()
    const generated = (saved as Record<string, unknown>).financialDocuments as
      | { warnings?: string[] }
      | undefined
    const warnings = [
      ...(generated?.warnings || []),
      ...(((saved as Record<string, unknown>).financialDocumentWarnings as string[] | undefined) || []),
    ]
    if (warnings.length) {
      validation.setErrors({}, warnings)
    }
    toast.add({ title: t('freight.ui.finished'), color: 'success' })
  }
  catch (error) {
    validation.reset()
    validation.applyServerError(error)
  }
  finally {
    finishing.value = false
  }
}

/** The header menu's Finish: unsaved edits are confirmed away first. */
async function finishFromMenu() {
  if (!await confirmUnsaved()) return
  await finishJob()
}

async function requoteFromMenu() {
  if (!await confirmUnsaved()) return
  await requoteFromServiceOrder(String(model.value.id || ''), String(model.value.jobNo || ''))
}

const moreItems = computed<DropdownMenuItem[][]>(() => {
  if (isCreate.value || !model.value.id) return []
  const items: DropdownMenuItem[] = []
  items.push({ label: t('freight.ui.viewSourceQuotation'), icon: 'i-lucide-file-search', onSelect: viewQuotation })
  // Finish is the record's own workflow (same confirmation, endpoint and
  // validations as before); it is disabled once the order is finished.
  items.push({
    label: t('freight.ui.finish'),
    icon: 'i-lucide-flag',
    color: 'primary',
    disabled: !canEdit.value,
    onSelect: () => { void finishFromMenu() },
  })
  if (lcs.can('quotation.revise')) {
    items.push({ label: t('freight.ui.requote'), icon: 'i-lucide-git-branch', onSelect: () => { void requoteFromMenu() } })
  }
  return [items]
})

function onTabChange(value: string) {
  activeTab.value = parseSection(value)
}

/** Every tab with local controls stays mounted (hidden) after its first visit,
 *  so switching tabs can never discard what the user typed. */
watch(activeTab, (tab) => {
  visitedTabs.value = new Set([...visitedTabs.value, tab])
  if (tab === 'charges') chargesVisited.value = true
  if (tab === 'finance') financeVisited.value = true
}, { immediate: true })
</script>

<template>
  <DocumentAppDocumentPage
    v-if="module"
    :tabs="tabs"
    :active-tab="activeTab"
    :field-value="fieldValue"
    :set-field-value="setFieldValue"
    :saving="saving"
    :not-found="notFound"
    :save-label="jobSaveLabel"
    :field-errors="validation.fieldErrors.value"
    :form-errors="validation.formErrors.value"
    :on-field-edit="validation.clearFieldError"
    :confirm-save="false"
    :show-save="canEdit || isCreate"
    :show-cancel="false"
    show-list-nav
    content-wide
    :can-navigate-previous="canNavigatePrevious"
    :can-navigate-next="canNavigateNext"
    :list-to="listTo"
    :is-create="isCreate"
    :attachments="attachments"
    :more-items="moreItems"
    :can-export="false"
    @update:active-tab="onTabChange"
    @update:attachments="setChromeField('attachments', $event)"
    @save="save"
    @refresh="load"
    @navigate-previous="navigatePrevious"
    @navigate-next="navigateNext"
  >
    <template #form>
      <DocumentAppDocumentContentShell wide>
        <div class="space-y-6 py-5">
          <!-- Every visited tab stays mounted; `v-show` swaps the visible one
               without destroying input state. -->
          <div v-if="tabVisited('overview')" v-show="activeTab === 'overview'">
            <FreightJobOverview
              :model="model"
              :sections="jobSections"
              @update:field="setField"
              @blur-field="validateJobField"
            />
          </div>
          <div v-if="tabVisited('route')" v-show="activeTab === 'route'">
            <FreightJobRoute
              :job="model"
              :is-create="isCreate"
              :editable="canEdit"
              @update:job="patchJob"
            />
          </div>
          <div v-if="tabVisited('containers')" v-show="activeTab === 'containers'">
            <FreightJobContainers
              :job="model"
              :shipments="shipments"
              :charges="charges"
              :container-requirements="containerRequirements"
              :actual-containers="actualContainers"
              :is-create="isCreate"
              :editable="canEdit"
              :editable-payments="canEditPayments"
              @update:job="patchJob"
            />
          </div>
          <template v-for="componentTab in componentTabsState.tabs.value" :key="componentTab.code">
            <div v-if="tabVisited(componentTab.code)" v-show="activeTab === componentTab.code">
              <DocumentAppComponentTabs
                :tab="componentTab"
                :references="componentTabsState.references.value"
                :rows-by-group="componentTabsState.rowsByGroup.value"
                :editable="canEdit"
                :saving="componentTabsState.saving.value"
                :loading="componentTabsState.loading.value"
                :error="componentTabsState.error.value"
                :field-errors="validation.fieldErrors.value"
                :on-field-edit="validation.clearFieldError"
                @update:rows="setComponentRows"
                @save-group="saveComponentGroup"
              />
            </div>
          </template>
          <div v-if="tabVisited('files')" v-show="activeTab === 'files'">
            <FreightJobFiles
              :job="model"
              :documents="documents"
              :is-create="isCreate"
              :editable="canEdit"
              @update:job="patchJob"
            />
          </div>
          <!-- Mounted on first visit and then kept alive (hidden) so its pending
               inline draft survives tab switches. -->
          <div v-if="financeVisited" v-show="activeTab === 'finance'">
            <FreightJobFinance
              :job="model"
              :job-no="jobNo"
              :customer="String(model.customer || '')"
              :documents="debitNotes"
              :supplier-costs="supplierCosts"
              :receivables="receivables"
              :charges="chargeSummaryRows.length ? chargeSummaryRows : charges"
              :summary-loading="!model.id"
              :editable="canEdit"
            />
          </div>
          <!-- Mounted on first visit and then kept alive (hidden). Its save is
               its own (the shared Service Charge form), never the page save. -->
          <div v-if="chargesVisited" v-show="activeTab === 'charges'">
            <FreightJobCharges
              :job="model"
              :job-no="jobNo"
              :editable="canEdit"
              @update:dirty="chargesDirty = $event"
              @update:charges="chargeSummaryRows = $event"
              @saved="patchJob({ chargesTotal: $event.total })"
            />
          </div>
        </div>
      </DocumentAppDocumentContentShell>
    </template>
  </DocumentAppDocumentPage>
</template>

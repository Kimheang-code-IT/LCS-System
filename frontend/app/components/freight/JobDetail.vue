<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { DocumentTabSchema } from '~/types/docetra/common'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import { useFreightRecordChrome } from '~/composables/freight/useFreightRecordChrome'
import { useDynamicServiceOrderTabs } from '~/composables/freight/useDynamicServiceOrderTabs'
import { useJobRelated } from '~/composables/freight/useJobRelated'
import { useLcs } from '~/composables/lcs/useLcs'
import {
  emptyFreightRecord,
  groupedFields,
  statusColor,
  useFreightLabel,
  useFreightRouteModule,
} from '~/composables/freight/useFreight'
import type { FreightRecord } from '~/types/freight/record'
import type { ServiceOrderStatus } from '~/types/lcs/domain'
import {
  parseJobWorkspaceSection,
  type JobWorkspaceSection,
} from '~/utils/freight/job-workspace'
import {
  jobContainerCount,
  jobContainerPaymentRows,
  jobContainerPaymentTotals,
} from '~/utils/freight/job-containers'
import {
  JOB_FIXED_WORKSPACE_SECTIONS,
  JOB_TRAILING_WORKSPACE_SECTIONS,
  firstJobDocumentSection,
  isFixedJobWorkspaceSection,
  jobComponentSectionsFromGroups,
} from '~/utils/freight/job-component-tabs'
import { jobDomainStatus } from '~/utils/lcs/states'

const { module, isCreate, recordId, route } = useFreightRouteModule()
const store = useFreightStore()
const toast = useToast()
const router = useRouter()
const { t, te } = useI18n()
const { moduleTitle, moduleSingular } = useFreightLabel()
const { setBreadcrumbs, setBadges, clear } = useAppHeader()
const { confirm } = useConfirm()
const lcs = useLcs()

const saving = ref(false)
const editingOverview = ref(false)
const model = ref<FreightRecord>({} as FreightRecord)
const notFound = ref(false)

const EDITABLE_STATUSES: ServiceOrderStatus[] = ['DRAFT', 'OPEN', 'IN_PROGRESS']

const domainStatus = computed(() => jobDomainStatus(model.value))
const canEdit = computed(() =>
  !isCreate.value && lcs.can('service_order.update') && EDITABLE_STATUSES.includes(domainStatus.value))
const canEditPayments = computed(() =>
  !isCreate.value
  && lcs.can('service_order.update')
  && !['CLOSED', 'CANCELLED'].includes(domainStatus.value))
const canComplete = computed(() =>
  lcs.can('service_order.complete') && domainStatus.value === 'IN_PROGRESS')

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
  activity: chromeActivity,
  metaOwner,
  metaAssignee,
  setChromeField,
  submitComment,
  updateComment,
  deleteComment,
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

const quotation = computed(() => {
  const no = String(model.value.quotationNo || '').trim()
  if (!no) return null
  return store.list('quotations').find(row => String(row.quotationNo || '') === no) || null
})

/** Task progress comes straight from the scoped collection — no extra request. */
const taskRows = computed<FreightRecord[]>(() =>
  jobNo.value
    ? store.list('serviceComponents').filter(row => String(row.jobNo || '') === jobNo.value)
    : [])
const tasksDone = computed(() => taskRows.value.filter(row => row.status === 'COMPLETED').length)
const paymentRows = computed(() => jobContainerPaymentRows(model.value, {
  shipments: shipments.value,
  charges: charges.value,
  quotation: quotation.value,
}))
const chargesTotals = computed(() => {
  const totals = jobContainerPaymentTotals(paymentRows.value, model.value.vatRate)
  const invoiced = charges.value
    .filter(row => String(row.financialDocumentId || '').trim())
    .reduce((sum, row) => sum + Number(row.total || row.amount || 0), 0)
  return { total: totals.total, invoiced }
})
const containersCount = computed(() =>
  jobContainerCount(model.value, paymentRows.value, actualContainers.value)
  || actualContainers.value.length)

const tabOptions = computed(() => ({
  direction: String(model.value.direction || ''),
  assignments: store.list('tradeDirectionComponents'),
}))

/**
 * Operational tabs come from the configurable dynamic tables. Component groups
 * remain a fallback for installations without tab configuration.
 */
const dynamicTabsState = useDynamicServiceOrderTabs(jobNo)
const configuredSections = computed(() => dynamicTabsState.sections.value)
const groupSections = computed(() =>
  jobComponentSectionsFromGroups(store.list('componentGroups'), tabOptions.value),
)
const workspaceSections = computed(() => {
  const configured = configuredSections.value
  const operational = configured.length
    ? [...configured, ...groupSections.value.filter(id => !configured.includes(id))]
    : groupSections.value
  return [
    ...JOB_FIXED_WORKSPACE_SECTIONS,
    ...operational,
    ...JOB_TRAILING_WORKSPACE_SECTIONS,
  ]
})
const documentSection = computed(() =>
  configuredSections.value[0] || firstJobDocumentSection(store.list('componentGroups'), tabOptions.value),
)
const isDynamicTab = computed(() =>
  Boolean(activeTab.value) && dynamicTabsState.tabs.value.some(tab => tab.code === activeTab.value),
)
const activeDynamicTab = computed(() => dynamicTabsState.tabByCode(activeTab.value))
const activeDynamicRows = computed<Array<Record<string, unknown>>>(() =>
  isDynamicTab.value ? dynamicTabsState.rowsFor(activeTab.value) : [],
)
const isComponentTab = computed(() =>
  Boolean(activeTab.value) && !isFixedJobWorkspaceSection(activeTab.value) && !isDynamicTab.value,
)

function setDynamicRows(rows: Array<Record<string, unknown>>) {
  dynamicTabsState.setRows(activeTab.value, rows)
}

async function saveDynamicTab() {
  try {
    await dynamicTabsState.saveTab(activeTab.value)
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

function parseSection(value: unknown) {
  return parseJobWorkspaceSection(value, workspaceSections.value)
}

const activeTab = ref<JobWorkspaceSection>('overview')

function sectionLabel(id: string) {
  const dynamicTab = dynamicTabsState.tabByCode(id)
  if (dynamicTab) return dynamicTab.name
  const key = `freight.jobSections.${id}`
  if (te(key)) return t(key)
  const group = store.list('componentGroups').find(row =>
    String(row.code || '').toLowerCase().replace(/_/g, '-') === id,
  )
  return String(group?.name || id)
}

const tabs = computed<DocumentTabSchema[]>(() =>
  workspaceSections.value.map(id => ({
    id,
    labelKey: `freight.jobSections.${id}`,
    label: sectionLabel(id),
    sections: [{ id, title: sectionLabel(id), fields: [] }],
  })),
)

function load() {
  if (!module.value) return
  editingOverview.value = isCreate.value
  if (isCreate.value) {
    model.value = emptyFreightRecord(module.value) as FreightRecord
    notFound.value = false
    return
  }
  const found = store.get('jobs', recordId.value)
  notFound.value = !found
  model.value = found ? { ...found } as FreightRecord : {} as FreightRecord
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

watch([jobNo, () => model.value.workflowStatus, () => model.value.status, headerSubtitle], () => {
  if (!module.value) return
  setBreadcrumbs([
    { label: moduleTitle(module.value), to: module.value.path },
    { label: String(model.value.jobNo || moduleTitle(module.value)) },
  ])
  setBadges([
    ...(model.value.direction ? [{ label: String(model.value.direction), color: 'info' as const }] : []),
    ...(model.value.workflowStatus
      ? [{ label: String(model.value.workflowStatus), color: statusColor(String(model.value.status || model.value.workflowStatus)) }]
      : []),
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
  saving.value = true
  try {
    const payload = { ...model.value }
    const saved = isCreate.value || !payload.id
      ? await store.create('jobs', payload, 'job')
      : store.save('jobs', model.value)
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    editingOverview.value = false
    if (isCreate.value) await navigateTo(`/service-orders/${saved.id}`)
    else model.value = saved
  }
  finally {
    saving.value = false
  }
}

async function startEdit() {
  activeTab.value = 'overview'
  editingOverview.value = true
}

function discardEdit() {
  editingOverview.value = false
  load()
}

function applyWorkflow(next: ServiceOrderStatus, displayStatus: string) {
  if (!model.value.id) return
  const saved = store.save('jobs', {
    ...model.value,
    status: displayStatus,
    workflowStatus: next,
    updatedAt: new Date().toISOString(),
  })
  model.value = saved
}

async function transition(next: ServiceOrderStatus, displayStatus: string, messageKey: string) {
  const ok = await confirm({
    kind: 'generic',
    title: t(messageKey),
    description: `${String(model.value.jobNo || '')} · ${headerSubtitle.value}`,
    confirmLabel: t(messageKey),
    confirmColor: next === 'CANCELLED' ? 'warning' : 'primary',
  })
  if (!ok) return
  applyWorkflow(next, displayStatus)
  toast.add({ title: t(messageKey), color: next === 'CANCELLED' ? 'warning' : 'success' })
}

function openQuotation() {
  const quotation = store.list('quotations').find(row => String(row.quotationNo || '') === String(model.value.quotationNo || ''))
  if (!quotation) {
    toast.add({ title: t('docetra.states.notFound'), color: 'warning' })
    return
  }
  void navigateTo(`/quotations/${quotation.id}`)
}

const moreItems = computed<DropdownMenuItem[][]>(() => {
  if (isCreate.value || !model.value.id) return []
  const items: DropdownMenuItem[] = []
  if (lcs.can('service_order.update') && ['OPEN', 'IN_PROGRESS'].includes(domainStatus.value)) {
    items.push({ label: t('freight.ui.putOnHold'), icon: 'i-lucide-pause', onSelect: () => { void transition('ON_HOLD', 'On Hold', 'freight.ui.putOnHold') } })
  }
  if (lcs.can('service_order.update') && domainStatus.value === 'ON_HOLD') {
    items.push({ label: t('freight.ui.resume'), icon: 'i-lucide-play', onSelect: () => { void transition('IN_PROGRESS', 'In Progress', 'freight.ui.resume') } })
  }
  if (domainStatus.value === 'COMPLETED' && lcs.can('service_order.update')) {
    items.push({ label: t('freight.ui.close'), icon: 'i-lucide-lock', onSelect: () => { void transition('CLOSED', 'Closed', 'freight.ui.closeJob') } })
  }
  if (String(model.value.quotationNo || '').trim()) {
    items.push({ label: t('freight.ui.viewSourceQuotation'), icon: 'i-lucide-file-search', onSelect: openQuotation })
  }
  if (!['CLOSED', 'CANCELLED'].includes(domainStatus.value) && lcs.can('service_order.update')) {
    items.push({
      label: t('freight.ui.cancel'),
      icon: 'i-lucide-ban',
      color: 'error',
      onSelect: () => { void transition('CANCELLED', 'Cancelled', 'freight.ui.jobCancelled') },
    })
  }
  return [items]
})

function onTabChange(value: string) {
  activeTab.value = parseSection(value)
}
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
    :save-label="t('docetra.common.save')"
    :confirm-save="false"
    :show-save="editingOverview || isCreate"
    :show-cancel="!editingOverview && !isCreate"
    :show-comments="activeTab === 'overview'"
    :show-meta-rail="!isCreate"
    show-list-nav
    content-wide
    :can-navigate-previous="canNavigatePrevious"
    :can-navigate-next="canNavigateNext"
    :list-to="listTo"
    :is-create="isCreate"
    :can-comment="!isCreate"
    :comments="comments"
    :activity="chromeActivity"
    :attachments="attachments"
    :comment-body="commentBody"
    :submitting-comment="submittingComment"
    :current-user="currentUser"
    :meta-title="String(model.jobNo || moduleSingular(module))"
    :meta-subtitle="headerSubtitle || String(model.customer || moduleSingular(module))"
    :meta-icon="module.icon"
    :meta-status="String(model.status || '')"
    :meta-stage="String(model.direction || '')"
    :meta-owner="metaOwner"
    :meta-assignee="metaAssignee"
    :meta-tags="tags"
    :meta-created-at="String(model.createdAt || '')"
    :meta-updated-at="String(model.updatedAt || '')"
    :more-items="moreItems"
    :can-export="false"
    @update:active-tab="onTabChange"
    @update:comment-body="commentBody = $event"
    @update:attachments="setChromeField('attachments', $event)"
    @save="save"
    @refresh="load"
    @submit-comment="submitComment"
    @update-comment="updateComment"
    @delete-comment="deleteComment"
    @navigate-previous="navigatePrevious"
    @navigate-next="navigateNext"
  >
    <template #actions>
      <CommonAppDocumentActionButton
        v-if="canEdit"
        icon="i-lucide-pencil"
        :label="t('freight.ui.edit')"
        @click="startEdit"
      />
      <CommonAppDocumentActionButton
        v-if="canComplete"
        icon="i-lucide-check-circle-2"
        :label="t('freight.ui.complete')"
        color="success"
        @click="transition('COMPLETED', 'Financial Completed', 'freight.ui.jobCompleted')"
      />
      <CommonAppDocumentActionButton
        v-if="domainStatus === 'ON_HOLD' && lcs.can('service_order.update')"
        icon="i-lucide-play"
        :label="t('freight.ui.resume')"
        @click="transition('IN_PROGRESS', 'In Progress', 'freight.ui.resume')"
      />
    </template>

    <template #form>
      <DocumentAppDocumentContentShell wide>
        <div class="space-y-6 py-5">
          <FreightJobOverview
            v-if="activeTab === 'overview'"
            :model="model"
            :is-create="isCreate"
            :editing="editingOverview"
            :sections="jobSections"
            :containers-count="containersCount"
            :tasks-done="tasksDone"
            :tasks-total="taskRows.length"
            :document-tab="documentSection"
            :charges-total="chargesTotals.total"
            :invoiced-total="chargesTotals.invoiced"
            @update:field="setField"
            @edit="startEdit"
            @cancel-edit="discardEdit"
          />
          <FreightJobRoute
            v-else-if="activeTab === 'route'"
            :job="model"
            :is-create="isCreate"
            :editable="canEdit"
            @update:job="patchJob"
          />
          <FreightJobContainers
            v-else-if="activeTab === 'containers'"
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
          <FreightDynamicServiceOrderTabs
            v-else-if="isDynamicTab && activeDynamicTab"
            :tab="activeDynamicTab"
            :references="dynamicTabsState.references.value"
            :model-value="activeDynamicRows"
            :editable="canEdit"
            :saving="dynamicTabsState.saving.value"
            @update:model-value="setDynamicRows"
            @save="saveDynamicTab"
          />
          <FreightJobTasks
            v-else-if="isComponentTab"
            :job-no="jobNo"
            :job-id="String(model.id || '')"
            :direction="String(model.direction || '')"
            :is-create="isCreate"
            :section="activeTab"
          />
          <FreightJobFinance
            v-else-if="activeTab === 'finance'"
            :job-no="jobNo"
            :customer="String(model.customer || '')"
            :documents="debitNotes"
            :supplier-costs="supplierCosts"
            :receivables="receivables"
          />
          <FreightJobFiles
            v-else-if="activeTab === 'files'"
            :job="model"
            :documents="documents"
            :is-create="isCreate"
            :editable="canEdit"
            @update:job="patchJob"
          />
        </div>
      </DocumentAppDocumentContentShell>
    </template>
  </DocumentAppDocumentPage>
</template>

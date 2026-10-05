<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { DocumentTabSchema } from '~/types/lcs/common'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import { useFreightRecordChrome } from '~/composables/freight/useFreightRecordChrome'
import { useJobRelated } from '~/composables/freight/useJobRelated'
import { useModuleRecord } from '~/composables/freight/useModuleRecord'
import { useLcs } from '~/composables/lcs/useLcs'
import {
  emptyFreightRecord,
  groupedFields,
  statusColor,
  useFreightLabel,
  useFreightRouteModule,
} from '~/composables/freight/useFreight'
import type { FreightRecord } from '~/types/freight/record'
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
} from '~/utils/freight/job-component-tabs'
import { useComponentTabs } from '~/composables/freight/useComponentTabs'
import { jobDomainStatus } from '~/utils/lcs/states'

const { module, isCreate, recordId, route } = useFreightRouteModule()
const moduleRecord = useModuleRecord(module)
const store = useFreightStore()
const toast = useToast()
const router = useRouter()
const { t, te } = useI18n()
const { moduleTitle } = useFreightLabel()
const { setBreadcrumbs, setBadges, clear } = useAppHeader()
const { confirm } = useConfirm()
const lcs = useLcs()

const saving = ref(false)
const editingOverview = ref(false)
const model = ref<FreightRecord>({} as FreightRecord)
const notFound = ref(false)

const domainStatus = computed(() => jobDomainStatus(model.value))
const canEdit = computed(() =>
  !isCreate.value && lcs.can('service_order.update'))
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
  commentBody,
  submittingComment,
  currentUser,
  comments,
  activity,
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
const documentSection = computed(() => componentSections.value[0] || 'overview')
const isComponentTab = computed(() =>
  Boolean(activeTab.value) && componentTabsState.tabs.value.some(tab => tab.code === activeTab.value),
)
const activeComponentTab = computed(() => componentTabsState.tabByCode(activeTab.value))

function setComponentRows(groupId: string, rows: Array<Record<string, unknown>>) {
  componentTabsState.setGroupRows(groupId, rows)
}

async function saveComponentGroup(groupId: string) {
  try {
    await componentTabsState.saveGroup(groupId)
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

watch([jobNo, () => model.value.status, headerSubtitle], () => {
  if (!module.value) return
  setBreadcrumbs([
    { label: moduleTitle(module.value), to: module.value.path },
    { label: String(model.value.jobNo || moduleTitle(module.value)) },
  ])
  setBadges([
    ...(model.value.direction ? [{ label: String(model.value.direction), color: 'info' as const }] : []),
    ...(model.value.status ? [{ label: String(model.value.status), color: statusColor(String(model.value.status)) }] : []),
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
    if (isCreate.value || !payload.id) await moduleRecord.create(payload)
    else await moduleRecord.update(String(payload.id), payload)
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    editingOverview.value = false
    // Return to the service-order list after saving.
    await navigateTo(module.value.path)
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

async function setJobStatus(next: 'ACTIVE' | 'INACTIVE') {
  if (!model.value.id) return
  model.value = store.save('jobs', { ...model.value, status: next === 'ACTIVE' ? 'Active' : 'Inactive' })
  toast.add({ title: t(next === 'ACTIVE' ? 'lcs.common.activated' : 'lcs.common.deactivated'), color: 'success' })
}

async function deleteJob() {
  if (!model.value.id) return
  const ok = await confirm({ kind: 'delete', count: 1 })
  if (!ok) return
  store.remove('jobs', [String(model.value.id)])
  toast.add({ title: t('lcs.actions.deletedItems', { n: 1 }), color: 'success' })
  await navigateTo('/service-orders')
}

function openQuotation() {
  const quotation = store.list('quotations').find(row => String(row.quotationNo || '') === String(model.value.quotationNo || ''))
  if (!quotation) {
    toast.add({ title: t('lcs.states.notFound'), color: 'warning' })
    return
  }
  void navigateTo(`/quotations/${quotation.id}`)
}

const jobSaveLabel = computed(() =>
  isCreate.value ? t('freight.ui.submit') : t('freight.ui.saveChanges'),
)

const finishing = ref(false)

async function finishJob() {
  if (!model.value.id) return
  finishing.value = true
  try {
    const saved = await lcs.runCommand('service_order.finish', String(model.value.id), key =>
      lcs.jobs.finish(String(model.value.id), key),
    )
    model.value = { ...model.value, ...saved } as FreightRecord
    toast.add({ title: t('freight.ui.finished'), color: 'success' })
  }
  catch (error) {
    lcs.reportError(error)
  }
  finally {
    finishing.value = false
  }
}

const moreItems = computed<DropdownMenuItem[][]>(() => {
  if (isCreate.value || !model.value.id) return []
  const items: DropdownMenuItem[] = []
  if (String(model.value.quotationNo || '').trim()) {
    items.push({ label: t('freight.ui.viewSourceQuotation'), icon: 'i-lucide-file-search', onSelect: openQuotation })
  }
  if (lcs.can('service_order.update')) {
    const active = domainStatus.value === 'ACTIVE'
    items.push({
      label: t(active ? 'freight.ui.deactivate' : 'freight.ui.activate'),
      icon: active ? 'i-lucide-circle-off' : 'i-lucide-circle-check',
      color: active ? 'warning' : 'success',
      onSelect: () => { void setJobStatus(active ? 'INACTIVE' : 'ACTIVE') },
    })
    if (!active) {
      items.push({
        label: t('freight.ui.delete'),
        icon: 'i-lucide-trash-2',
        color: 'error',
        onSelect: () => { void deleteJob() },
      })
    }
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
    :save-label="jobSaveLabel"
    :confirm-save="false"
    :show-save="editingOverview || isCreate"
    :show-cancel="false"
    show-list-nav
    content-wide
    :can-navigate-previous="canNavigatePrevious"
    :can-navigate-next="canNavigateNext"
    :list-to="listTo"
    :is-create="isCreate"
    :attachments="attachments"
    show-comments
    :can-comment="!isCreate"
    :comments="comments"
    :activity="activity"
    :comment-body="commentBody"
    :submitting-comment="submittingComment"
    :current-user="currentUser"
    :more-items="moreItems"
    :can-export="false"
    @update:active-tab="onTabChange"
    @update:attachments="setChromeField('attachments', $event)"
    @save="save"
    @refresh="load"
    @update:comment-body="commentBody = $event"
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
        v-if="canEdit && domainStatus === 'ACTIVE'"
        icon="i-lucide-check-circle"
        :label="t('freight.ui.finish')"
        :loading="finishing"
        @click="finishJob"
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
          <DocumentAppComponentTabs
            v-else-if="isComponentTab && activeComponentTab"
            :tab="activeComponentTab"
            :references="componentTabsState.references.value"
            :rows-by-group="componentTabsState.rowsByGroup.value"
            :editable="canEdit"
            :saving="componentTabsState.saving.value"
            @update:rows="setComponentRows"
            @save-group="saveComponentGroup"
          />
          <FreightJobCharges
            v-else-if="activeTab === 'charges'"
            :job="model"
            :job-no="jobNo"
            :editable="canEdit"
          />
          <FreightJobFinance
            v-else-if="activeTab === 'finance'"
            :job="model"
            :job-no="jobNo"
            :customer="String(model.customer || '')"
            :documents="debitNotes"
            :supplier-costs="supplierCosts"
            :receivables="receivables"
            :editable="canEdit"
            @update:job="patchJob"
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

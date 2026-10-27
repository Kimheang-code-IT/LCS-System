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
import { useRecordStatus } from '~/composables/freight/useRecordStatus'
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
import { jobDomainStatus } from '~/utils/freight/states'

const { module, isCreate, recordId, route } = useFreightRouteModule()
const moduleRecord = useModuleRecord(module)
const store = useFreightStore()
const toast = useToast()
const router = useRouter()
const { t, te } = useI18n()
const { moduleTitle, fieldLabel } = useFreightLabel()
const { setBreadcrumbs, setBadges, clear } = useAppHeader()
const { confirm } = useConfirm()
const lcs = useLcs()

const saving = ref(false)
const model = ref<FreightRecord>({} as FreightRecord)
const notFound = ref(false)

const domainStatus = computed(() => jobDomainStatus(model.value))
const canEdit = computed(() =>
  !isCreate.value && lcs.can('service_order.update'))
const canEditPayments = computed(() =>
  !isCreate.value && lcs.can('service_order.update'))

/**
 * Status changes (activate / deactivate / finish / reopen) run through the
 * shared status manager, so the job page and the list offer the same legal
 * transitions and every change is validated and audited.
 */
const { menuItem: statusMenuItem } = useRecordStatus(module, {
  onError: (message) => {
    validation.reset()
    validation.addFormError(message)
  },
  onChanged: async () => {
    const refreshed = await lcs.jobs.get(String(model.value.id))
    model.value = { ...model.value, ...refreshed }
  },
})

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
const isComponentTab = computed(() =>
  Boolean(activeTab.value) && componentTabsState.tabs.value.some(tab => tab.code === activeTab.value),
)
const activeComponentTab = computed(() => componentTabsState.tabByCode(activeTab.value))

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

function load() {
  if (!module.value) return
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
  if (saving.value) return
  saving.value = true
  validation.submitting.value = true
  validation.reset()
  try {
    const failures = validateOrder()
    if (failures.length) {
      validation.applyFailures(failures)
      await validation.focusFirstInvalid()
      return
    }
    const payload = { ...model.value }
    if (isCreate.value || !payload.id) await moduleRecord.create(payload)
    else await moduleRecord.update(String(payload.id), payload)
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
    validation.reset()
    validation.applyServerError(error)
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
  // Change Status (activate / deactivate / finish / reopen) comes from the
  // shared policy, so the same legal transitions are offered here as in the list.
  const statusItem = statusMenuItem(model.value)
  if (statusItem) items.push(statusItem)
  if (lcs.can('service_order.update') && domainStatus.value === 'INACTIVE') {
    // Only an inactive order can be deleted.
    items.push({
      label: t('freight.ui.delete'),
      icon: 'i-lucide-trash-2',
      color: 'error',
      onSelect: () => { void deleteJob() },
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
            :sections="jobSections"
            @update:field="setField"
            @blur-field="validateJobField"
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
            :loading="componentTabsState.loading.value"
            :error="componentTabsState.error.value"
            :field-errors="validation.fieldErrors.value"
            :on-field-edit="validation.clearFieldError"
            @update:rows="setComponentRows"
            @save-group="saveComponentGroup"
          />
          <FreightJobCharges
            v-else-if="activeTab === 'charges'"
            :job="model"
            :job-no="jobNo"
            :editable="canEdit"
            @update:job="patchJob"
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

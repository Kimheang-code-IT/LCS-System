<script setup lang="ts">
import type { FreightRecord } from '~/types/freight/record'
import type { FreightTable } from '~/config/freight-modules'
import { useLcs } from '~/composables/lcs/useLcs'
import { useConfirm } from '~/composables/common/useConfirm'
import {
  assignmentForGroup,
  groupCodeForSection,
  groupForSection,
  isConfigFlagYes,
  resolveGroupTemplate,
} from '~/utils/freight/job-component-tabs'
import {
  componentInstanceLimits,
  resolveComponentInstanceMode,
} from '~/utils/freight/component-instance-mode'
import {
  componentAttributesToLineTable,
  componentRecordsToLineRows,
  lineRowToComponentValues,
} from '~/utils/freight/job-component-line-table'
import { missingRequiredValues } from '~/utils/freight/job-task-fields'

const props = defineProps<{
  jobNo: string
  jobId?: string
  direction?: string
  isCreate: boolean
  section: string
}>()

const { t, te } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const lcs = useLcs()
const store = useFreightStore()
const lineTableRows = ref<Array<Record<string, unknown>>>([])
const saving = ref(false)
const jobComponents = computed(() =>
  store.list('serviceComponents').filter(row => String(row.jobNo || '') === props.jobNo),
)

const groups = computed(() => store.list('componentGroups'))
const templates = computed(() => store.list('componentTemplates'))
const assignments = computed(() => store.list('tradeDirectionComponents'))
const groupCode = computed(() => groupCodeForSection(props.section, groups.value))
const group = computed(() => groupForSection(props.section, groups.value))
const assignment = computed(() => assignmentForGroup({
  group: group.value,
  assignments: assignments.value,
  direction: props.direction,
}))
const template = computed(() => resolveGroupTemplate({
  group: group.value,
  templates: templates.value,
  assignments: assignments.value,
  direction: props.direction,
}))
const effectiveMode = computed(() => resolveComponentInstanceMode(assignment.value, template.value))
const repeatable = computed(() => effectiveMode.value === 'REPEATABLE')
const limits = computed(() => componentInstanceLimits(assignment.value, template.value))
const templateAttributes = computed(() =>
  Array.isArray(template.value?.attributes) ? template.value!.attributes as Array<Record<string, unknown>> : [],
)
const sectionTitle = computed(() => {
  const key = `freight.jobSections.${props.section}`
  if (te(key)) return t(key)
  return String(group.value?.name || props.section)
})
const sectionRows = computed(() =>
  jobComponents.value
    .filter(row => String(row.groupCode || '').toUpperCase() === groupCode.value)
    .sort((a, b) => Number(a.sequenceNo || 0) - Number(b.sequenceNo || 0)),
)
const atMaximum = computed(() => Boolean(limits.value.maximum && sectionRows.value.length >= limits.value.maximum))
const cardinalityConflict = computed(() => effectiveMode.value === 'SINGLE' && sectionRows.value.length > 1)
const canMutate = computed(() =>
  !props.isCreate && Boolean(props.jobNo) && lcs.can('service_order.update'),
)
const tableDisabled = computed(() => !canMutate.value || saving.value)
const lineTable = computed<FreightTable | null>(() => {
  if (!templateAttributes.value.length) return null
  return componentAttributesToLineTable(
    templateAttributes.value,
    `component-${groupCode.value}`,
    sectionTitle.value,
  )
})

function syncLineRowsFromRecords() {
  lineTableRows.value = componentRecordsToLineRows(sectionRows.value, templateAttributes.value)
}

watch(
  () => [props.jobNo, props.section, templateAttributes.value, sectionRows.value] as const,
  () => {
    if (saving.value) return
    syncLineRowsFromRecords()
  },
  { immediate: true, deep: true },
)

function recordLabel(row: FreightRecord) {
  const sequence = Number(row.sequenceNo || 0) || sectionRows.value.indexOf(row) + 1
  return `${String(template.value?.name || sectionTitle.value)} #${sequence}`
}

async function removeComponent(componentId: string) {
  const record = sectionRows.value.find(row => String(row.id) === componentId)
  if (!record || String(record.status || '').toUpperCase() === 'COMPLETED') return
  const accepted = await confirm({
    kind: 'delete',
    descriptionKey: 'freight.ui.deleteComponentConfirm',
    descriptionParams: { name: recordLabel(record) },
  })
  if (!accepted) return
  await lcs.runCommand('component.remove', componentId, key => lcs.components.remove(componentId, key))
}

async function persistLineRows(nextRows: Array<Record<string, unknown>>) {
  if (!canMutate.value || !template.value) return
  if (!repeatable.value && nextRows.length > 1) {
    toast.add({ title: t('freight.ui.cardinalityConflict'), color: 'warning' })
    syncLineRowsFromRecords()
    return
  }
  if (limits.value.maximum && nextRows.length > limits.value.maximum) {
    toast.add({ title: t('freight.ui.componentLimitReached', { count: limits.value.maximum }), color: 'warning' })
    syncLineRowsFromRecords()
    return
  }

  const previousIds = new Set(sectionRows.value.map(row => String(row.id || '')).filter(Boolean))
  const nextIds = new Set(
    nextRows.map(row => String(row._componentId || '')).filter(Boolean),
  )

  saving.value = true
  try {
    for (const removedId of previousIds) {
      if (!nextIds.has(removedId)) await removeComponent(removedId)
    }

    for (const row of nextRows) {
      const componentId = String(row._componentId || '')
      const existing = componentId
        ? sectionRows.value.find(record => String(record.id) === componentId)
        : null
      if (existing && String(existing.status || '').toUpperCase() === 'COMPLETED') continue

      const captured = existing && Array.isArray(existing.values)
        ? existing.values as Array<Record<string, unknown>>
        : []
      const values = lineRowToComponentValues(row, templateAttributes.value, captured)
      const missing = missingRequiredValues(values)
      if (missing.length) continue

      if (!componentId) {
        const created = await lcs.components.ensureForJob(props.jobNo, {
          jobNo: props.jobNo,
          serviceOrderId: props.jobId,
          groupCode: groupCode.value,
          templateCode: String(template.value?.code || assignment.value?.componentTemplate || groupCode.value),
          templateVersion: String(template.value?.version || assignment.value?.templateVersion || ''),
          latestTemplateVersion: String(template.value?.version || ''),
          required: isConfigFlagYes(assignment.value?.required) || isConfigFlagYes(template.value?.required),
          repeatable: repeatable.value,
          instanceMode: effectiveMode.value,
          maximumInstances: limits.value.maximum,
          values,
          forceNew: repeatable.value,
        })
        row._componentId = String(created.id)
        row._status = String(created.status || 'PENDING')
      }
      else {
        await lcs.components.saveValues(componentId, values)
      }
    }

    store.reload()
    syncLineRowsFromRecords()
  }
  catch (error) {
    lcs.reportError(error)
    syncLineRowsFromRecords()
  }
  finally {
    saving.value = false
  }
}

const persistLineRowsDebounced = useDebounceFn(persistLineRows, 400)

function onLineRowsChange(nextRows: Array<Record<string, unknown>>) {
  lineTableRows.value = nextRows
  void persistLineRowsDebounced([...nextRows])
}
</script>

<template>
  <section class="space-y-2">
    <UAlert
      v-if="cardinalityConflict"
      color="warning"
      variant="subtle"
      icon="i-lucide-triangle-alert"
      :title="t('freight.ui.cardinalityConflict')"
      :description="t('freight.ui.cardinalityConflictHint')" />
    <UAlert
      v-if="repeatable && atMaximum"
      color="neutral"
      variant="subtle"
      icon="i-lucide-info"
      :title="t('freight.ui.componentLimitReached', { count: limits.maximum })" />

    <FreightJobLineTable
      v-if="lineTable"
      :table="lineTable"
      :model-value="lineTableRows"
      :disabled="tableDisabled"
      @update:model-value="onLineRowsChange" />
    <FreightJobEmptyState
      v-else
      :title="t('freight.ui.noTasks')"
      :description="t('freight.ui.noTasksHint')"
      icon="i-lucide-file-text" />
  </section>
</template>

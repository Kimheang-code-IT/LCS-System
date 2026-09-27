<script setup lang="ts">
import type { FreightField } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import { formatMoney, shortDay, useFreightLabel } from '~/composables/freight/useFreight'
import { JOB_OVERVIEW_SECTIONS, jobWorkspacePath } from '~/utils/freight/job-workspace'

const props = defineProps<{
  model: FreightRecord
  isCreate: boolean
  editing: boolean
  sections: Array<{ title: string, titleKm?: string, fields: FreightField[] }>
  containersCount?: number
  tasksDone?: number
  tasksTotal?: number
  documentTab?: string
  chargesTotal?: number
  invoicedTotal?: number
}>()

const emit = defineEmits<{
  'update:field': [key: string, value: unknown]
  edit: []
  'cancel-edit': []
}>()

const { t } = useI18n()
const { groupTitle } = useFreightLabel()

const overviewFields = computed(() =>
  props.sections.filter(section => JOB_OVERVIEW_SECTIONS.has(section.title)),
)

function tabTo(section: Parameters<typeof jobWorkspacePath>[1]) {
  return props.isCreate ? undefined : jobWorkspacePath(String(props.model.id || ''), section)
}

function displayDate(value: unknown) {
  return shortDay(value, '')
}

const jobCurrency = computed(() => String(props.model.currency || '').trim() || undefined)

const summaryItems = computed(() => [
  {
    label: t('freight.ui.containers'),
    value: String(props.containersCount ?? 0),
    to: tabTo('containers'),
  },
  {
    label: t('freight.jobSections.documents'),
    value: t('freight.ui.tasksProgress', { done: props.tasksDone ?? 0, total: props.tasksTotal ?? 0 }),
    to: props.documentTab ? tabTo(props.documentTab) : undefined,
  },
  {
    label: t('freight.ui.totalCharges'),
    value: formatMoney(props.chargesTotal ?? 0, jobCurrency.value),
    to: tabTo('containers'),
  },
  {
    label: t('freight.ui.invoicedAmount'),
    value: formatMoney(props.invoicedTotal ?? 0, jobCurrency.value),
    to: tabTo('finance'),
  },
])

const detailItems = computed(() => [
  { label: t('freight.ui.cols.customer'), value: props.model.customer },
  { label: t('freight.ui.cols.direction'), value: props.model.direction },
  { label: t('freight.ui.cols.currency'), value: props.model.currency },
  { label: t('freight.ui.cols.sourceQuotationLabel'), value: props.model.quotationNo },
  { label: t('freight.ui.cols.workflow'), value: props.model.workflowStatus || props.model.status },
  { label: t('freight.ui.cols.createdAt'), value: displayDate(props.model.createdAt) },
  { label: t('freight.ui.cols.createdBy'), value: props.model.createdBy },
  { label: t('freight.ui.cols.assignedStaff'), value: props.model.assignedStaff },
  { label: t('freight.ui.descriptionLabel'), value: props.model.description, span: 2 as const },
])
</script>

<template>
  <div class="space-y-4">
    <FreightJobSectionHeader :title="t('freight.ui.overview')">
      <template #actions>
        <UButton
          v-if="!isCreate && editing"
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          :label="t('actions.cancel')"
          @click="emit('cancel-edit')"
        />
        <UButton
          v-if="!isCreate && !editing"
          size="xs"
          color="neutral"
          variant="soft"
          icon="i-lucide-pencil"
          :label="t('freight.ui.edit')"
          @click="emit('edit')"
        />
      </template>
    </FreightJobSectionHeader>

    <FreightJobSummaryStrip v-if="!editing" :items="summaryItems" />

    <FreightJobDefinitionList v-if="!isCreate && !editing" :items="detailItems" />

    <div v-if="editing || isCreate" class="space-y-5">
      <section v-for="section in overviewFields" :key="section.title" class="space-y-3">
        <h4 class="text-xs font-semibold uppercase tracking-wide text-muted">
          {{ groupTitle(section.title) }}
        </h4>
        <div class="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
          <FreightFieldInput
            v-for="field in section.fields"
            :key="field.key"
            :field="field"
            :model-value="model[field.key]"
            :class="field.colSpan === 2 || field.type === 'textarea' ? 'sm:col-span-2' : ''"
            @update:model-value="emit('update:field', field.key, $event)"
          />
        </div>
      </section>
    </div>

    <p
      v-if="!isCreate && !editing && String(model.operationalRemark || '').trim()"
      class="text-xs text-muted"
    >
      {{ model.operationalRemark }}
    </p>
  </div>
</template>

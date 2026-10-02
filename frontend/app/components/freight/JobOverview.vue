<script setup lang="ts">
import type { FreightField } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/record'
import { useFreightLabel } from '~/composables/freight/useFreight'
import { JOB_OVERVIEW_LEAD_SECTION, JOB_OVERVIEW_SECTIONS } from '~/utils/freight/job-workspace'

const props = defineProps<{
  model: FreightRecord
  sections: Array<{ title: string, titleKm?: string, fields: FreightField[] }>
}>()

const emit = defineEmits<{
  'update:field': [key: string, value: unknown]
}>()

const { t } = useI18n()
const { groupTitle } = useFreightLabel()

const overviewFields = computed(() =>
  props.sections.filter(section => JOB_OVERVIEW_SECTIONS.has(section.title)),
)
</script>

<template>
  <div class="space-y-4">
    <FreightJobSectionHeader :title="t('freight.ui.overview')" />

    <div class="space-y-5">
      <section v-for="section in overviewFields" :key="section.title" class="space-y-3">
        <h4
          v-if="section.title !== JOB_OVERVIEW_LEAD_SECTION"
          class="text-xs font-semibold uppercase tracking-wide text-muted"
        >
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
  </div>
</template>

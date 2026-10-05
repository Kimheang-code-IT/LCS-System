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
        <DocumentAppFieldGrid
          :fields="section.fields"
          :model="model"
          @update="(key, value) => emit('update:field', key, value)"
        />
      </section>
    </div>
  </div>
</template>

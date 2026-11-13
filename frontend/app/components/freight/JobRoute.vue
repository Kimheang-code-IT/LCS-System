<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import { JOB_ROUTE_TABLE } from '~/config/job-workspace-forms'
import { jobFieldsFromPlaces, jobRoutePlaces } from '~/utils/freight/job-workspace'

const props = withDefaults(defineProps<{
  job: FreightRecord
  isCreate?: boolean
  editable?: boolean
}>(), {
  isCreate: false,
  editable: false,
})

const emit = defineEmits<{
  'update:job': [patch: Record<string, unknown>]
}>()

const table = JOB_ROUTE_TABLE
const rows = ref<Array<Record<string, unknown>>>([])
const canEdit = computed(() => props.editable || props.isCreate)

function loadRows() {
  rows.value = jobRoutePlaces(props.job)
}

/**
 * Route edits stay in the page model (and therefore in the page draft) and are
 * written by the order's own Save. A per-keystroke whole-order PUT used to race
 * the draft's server stamp and the user's typing.
 */
function persist(nextRows: Array<Record<string, unknown>>) {
  emit('update:job', jobFieldsFromPlaces(nextRows))
}

function setRows(value: Array<Record<string, unknown>>) {
  rows.value = value
  persist(value)
}

watch(() => jobRoutePlaces(props.job), () => {
  // The parent normalizes values for persistence. Do not feed that trimming
  // back into an active input (e.g. the space between two words).
  const local = jobRoutePlaces({ id: props.job.id, ...jobFieldsFromPlaces(rows.value) })
  if (JSON.stringify(local) !== JSON.stringify(jobRoutePlaces(props.job))) loadRows()
}, { immediate: true, deep: true })
</script>

<template>
  <FreightAppLineTable
    :table="table"
    :model-value="rows"
    :disabled="!canEdit"
    @update:model-value="setRows"
  />
</template>

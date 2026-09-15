<script setup lang="ts">
import type { FreightRecord } from '~/types/freight/record'
import { JOB_FILE_TABLE } from '~/config/job-workspace-forms'
import { jobFileAttachments } from '~/utils/freight/attachments'

const props = withDefaults(defineProps<{
  job: FreightRecord
  documents?: FreightRecord[]
  isCreate?: boolean
  editable?: boolean
}>(), {
  documents: () => [],
  isCreate: false,
  editable: false,
})

const emit = defineEmits<{
  'update:job': [patch: Record<string, unknown>]
}>()

const store = useFreightStore()
const table = JOB_FILE_TABLE
const rows = ref<Array<Record<string, unknown>>>([])
const canEdit = computed(() => props.editable || props.isCreate)

function loadRows() {
  rows.value = jobFileAttachments(props.job, props.documents)
}

function persist(nextRows: Array<Record<string, unknown>>) {
  const patch = { attachments: nextRows }
  emit('update:job', patch)
  if (!props.isCreate && props.job.id) {
    store.save('jobs', {
      ...props.job,
      ...patch,
      updatedAt: new Date().toISOString(),
    })
  }
}

function setRows(value: Array<Record<string, unknown>>) {
  rows.value = value
  persist(value)
}

watch(
  () => [props.job.id, props.documents.length] as const,
  loadRows,
  { immediate: true },
)
</script>

<template>
  <FreightJobLineTable
    :table="table"
    :model-value="rows"
    :disabled="!canEdit"
    @update:model-value="setRows"
  />
</template>

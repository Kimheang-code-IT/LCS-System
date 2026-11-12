<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import { JOB_FILE_TABLE } from '~/config/job-workspace-forms'
import { freightDocumentAttachmentKey } from '~/utils/freight/document-tabs'
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

const table = JOB_FILE_TABLE
const rows = ref<Array<Record<string, unknown>>>([])
const canEdit = computed(() => props.editable || props.isCreate)

/**
 * File uploads go straight into the attachment API and link to the open order
 * (its numeric id); the metadata row still round-trips through the order save.
 * An unsaved order keeps the legacy local-preview row only.
 */
provide(freightDocumentAttachmentKey, () => ({
  module: 'jobs',
  recordNo: props.isCreate ? '' : String(props.job.id || ''),
}))

function loadRows() {
  rows.value = jobFileAttachments(props.job, props.documents)
}

/**
 * Upload/remove/note writes already go through the attachment API; the order
 * only carries the metadata rows and saves them with its own Save (and draft).
 */
function persist(nextRows: Array<Record<string, unknown>>) {
  emit('update:job', { attachments: nextRows })
}

function setRows(value: Array<Record<string, unknown>>) {
  rows.value = value
  persist(value)
}

watch(
  () => [props.job.id, props.documents.length, Array.isArray(props.job.attachments) ? props.job.attachments.length : -1] as const,
  loadRows,
  { immediate: true },
)
</script>

<template>
  <FreightAppLineTable
    :table="table"
    :model-value="rows"
    :disabled="!canEdit"
    @update:model-value="setRows"
  />
</template>

<script setup lang="ts">
import { useExcelIo, type ExcelPreviewRow } from '~/composables/useExcelIo'
import { useLcs } from '~/composables/freight/useLcs'
import { useConfirm } from '~/composables/common/useConfirm'

const props = defineProps<{
  /** The Freight collection the open list page belongs to (e.g. feeTypes). */
  collection: string
}>()

const emit = defineEmits<{ imported: [] }>()

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const api = useExcelIo()
const lcs = useLcs()

/** The page's ⋯ menu opens the dialog; it owns no trigger button of its own. */
const open = defineModel<boolean>('open', { default: false })
const step = ref<'upload' | 'preview' | 'result'>('upload')
/** Import mode is fixed to the safe backend default: never overwrite existing rows. */
const importMode = 'CREATE_ONLY' as const
/** UFileUpload single-file model (multiple=false): the File, or null when removed. */
const file = ref<File | null>(null)
const token = ref('')
const summary = ref({ total: 0, create: 0, update: 0, skip: 0, error: 0 })
const rows = ref<ExcelPreviewRow[]>([])
const error = ref('')
const busy = ref(false)
const resultStatus = ref('')
const history = ref<Awaited<ReturnType<ReturnType<typeof useExcelIo>['history']>>['items']>([])

// Opening from the header menu resets the workflow and loads the import history.
watch(open, (isOpen) => {
  if (!isOpen) return
  error.value = ''
  step.value = 'upload'
  file.value = null
  void api.history(props.collection)
    .then((items) => { history.value = items.items })
    .catch(() => { /* history is informational; the form still works */ })
}, { immediate: true })


async function validate() {
  if (!file.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await api.validate(props.collection, file.value, importMode)
    token.value = result.token
    summary.value = result.summary
    rows.value = result.rows
    step.value = 'preview'
  }
  catch (caught) {
    error.value = lcs.errorMessage(caught)
  }
  finally {
    busy.value = false
  }
}

async function confirmImport() {
  busy.value = true
  error.value = ''
  try {
    const result = await api.commit(token.value)
    resultStatus.value = result.status
    summary.value = { total: result.total, create: result.create, update: result.update, skip: result.skip, error: result.error }
    step.value = 'result'
    toast.add({ title: t('freight.excel.importDone'), color: 'success' })
    emit('imported')
  }
  catch (caught) {
    error.value = lcs.errorMessage(caught)
    step.value = 'result'
    resultStatus.value = 'FAILED'
  }
  finally {
    busy.value = false
  }
}

async function closePreview() {
  const ok = await confirm({ kind: 'generic', descriptionKey: 'freight.excel.cancelNotice' })
  if (!ok) return
  if (token.value) {
    try { await api.cancel(token.value) }
    catch { /* session already gone */ }
  }
  open.value = false
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="t('freight.excel.import')"
    :close="{ color: 'primary', variant: 'outline', class: 'rounded-full' }"
    :ui="{ content: 'w-[calc(100%-2rem)] max-w-2xl sm:max-w-2xl' }"
  >
    <template #body>
      <div class="space-y-5">
        <CommonAppFormErrorSummary :form-errors="error ? [error] : []" />

        <template v-if="step === 'upload'">
          <div class="flex flex-wrap gap-2">
            <UButton
              icon="i-lucide-download"
              variant="outline"
              size="sm"
              @click="api.template(props.collection)"
            >
              {{ t('freight.excel.downloadTemplate') }}
            </UButton>
          </div>
          <UFormField :label="t('freight.excel.uploadFile')" name="import-file">
            <!-- Client-side type filtering is a hint only: the backend still rejects
                 non-.xlsx workbooks and bodies over MAX_FILE_BYTES at validate time. -->
            <UFileUpload
              v-model="file"
              accept=".xlsx"
              layout="grid"
              :interactive="false"
              data-field-key="import.file"
            />
          </UFormField>
        </template>

        <template v-else-if="step === 'preview'">
          <div class="flex gap-4 text-sm">
            <span>{{ t('freight.excel.total') }}: <strong>{{ summary.total }}</strong></span>
            <span class="text-success">{{ t('freight.excel.create') }}: {{ summary.create }}</span>
            <span class="text-info">{{ t('freight.excel.update') }}: {{ summary.update }}</span>
            <span class="text-muted">{{ t('freight.excel.skip') }}: {{ summary.skip }}</span>
            <span class="text-error">{{ t('freight.excel.errors') }}: {{ summary.error }}</span>
          </div>
          <div class="max-h-80 overflow-auto border rounded">
            <table class="w-full text-sm">
              <thead class="bg-muted/40 sticky top-0">
                <tr>
                  <th class="p-2 text-left">{{ t('freight.excel.excelRow') }}</th>
                  <th class="p-2 text-left">{{ t('freight.excel.identifier') }}</th>
                  <th class="p-2 text-left">{{ t('freight.excel.action') }}</th>
                  <th class="p-2 text-left">{{ t('freight.excel.status') }}</th>
                  <th class="p-2 text-left">{{ t('freight.excel.errorDetails') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.excelRow" class="border-t">
                  <td class="p-2">{{ row.excelRow }}</td>
                  <td class="p-2 font-mono">{{ row.identifier || '—' }}</td>
                  <td class="p-2">
                    <UBadge
                      :color="row.action === 'ERROR' ? 'error' : row.action === 'UPDATE' ? 'info' : row.action === 'SKIP' ? 'neutral' : 'success'"
                      variant="soft"
                    >
                      {{ row.action }}
                    </UBadge>
                  </td>
                  <td class="p-2">{{ row.status }}</td>
                  <td class="p-2 text-error">{{ row.errors.join(' • ') }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-else>
          <p
            class="text-sm font-medium"
            :class="resultStatus === 'COMPLETED' ? 'text-success' : 'text-error'"
          >
            {{ resultStatus === 'COMPLETED' ? t('freight.excel.importDone') : t('freight.excel.importFailed') }}
          </p>
          <div class="flex gap-4 text-sm">
            <span class="text-success">{{ t('freight.excel.create') }}: {{ summary.create }}</span>
            <span class="text-info">{{ t('freight.excel.update') }}: {{ summary.update }}</span>
            <span class="text-muted">{{ t('freight.excel.skip') }}: {{ summary.skip }}</span>
            <span class="text-error">{{ t('freight.excel.errors') }}: {{ summary.error }}</span>
          </div>
          <UButton variant="outline" icon="i-lucide-download" @click="api.errorReport(token)">
            {{ t('freight.excel.errorReport') }}
          </UButton>
          <div v-if="history.length" class="text-sm">
            <h3 class="font-semibold mb-1">{{ t('freight.excel.history') }}</h3>
            <ul class="space-y-1">
              <li v-for="job in history.slice(0, 5)" :key="job.id" class="flex gap-2">
                <span class="text-muted">{{ job.startedAt?.slice(0, 16).replace('T', ' ') }}</span>
                <span>{{ job.fileName }}</span>
                <UBadge :color="job.status === 'COMPLETED' ? 'success' : 'error'" variant="soft" size="sm">
                  {{ job.status }}
                </UBadge>
                <span>{{ job.created }}/{{ job.updated }}/{{ job.skipped }}/{{ job.failed }}</span>
              </li>
            </ul>
          </div>
        </template>
      </div>
    </template>

    <template #footer>
      <template v-if="step === 'upload'">
        <div class="flex justify-end gap-2">
          <UButton
color="neutral"
variant="ghost"
:disabled="busy"
@click="open = false">
            {{ t('freight.excel.cancel') }}
          </UButton>
          <UButton
            :loading="busy"
            :disabled="!file"
            icon="i-lucide-shield-check"
            @click="validate"
          >
            {{ t('freight.excel.validate') }}
          </UButton>
        </div>
      </template>

      <template v-else-if="step === 'preview'">
        <div class="flex w-full items-center justify-between gap-2">
          <UButton
            variant="outline"
            icon="i-lucide-file-x-2"
            :disabled="summary.error === 0 && summary.total === 0"
            @click="api.errorReport(token)"
          >
            {{ t('freight.excel.errorReport') }}
          </UButton>
          <div class="flex gap-2">
            <UButton
color="neutral"
variant="ghost"
:disabled="busy"
@click="closePreview">
              {{ t('freight.excel.cancel') }}
            </UButton>
            <UButton
              :loading="busy"
              :disabled="summary.error > 0 || (summary.create === 0 && summary.update === 0)"
              icon="i-lucide-check-circle-2"
              color="success"
              @click="confirmImport"
            >
              {{ t('freight.excel.confirm') }}
            </UButton>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="flex justify-end">
          <UButton @click="open = false">{{ t('lcs.common.close') }}</UButton>
        </div>
      </template>
    </template>
  </UModal>
</template>

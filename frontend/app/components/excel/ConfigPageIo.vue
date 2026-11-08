<script setup lang="ts">
import type { ExcelModuleInfo } from '~/composables/useExcelIo'
import { useLcs } from '~/composables/freight/useLcs'
import type { ExportFilters, ExportRequest } from '~/types/export'

/**
 * Import + Export buttons and dialogs for the Configuration pages. The backend
 * excel catalog decides availability and permissions; the shared dialogs own
 * every field. Scope stays "all matching": configuration pages have no row
 * selection and the catalog rows are not paginated like list pages.
 */
const props = defineProps<{
  /** The Import/Export module key, e.g. "componentAttributes" or "configurationVersions". */
  collection: string
  /** Status filter options for the export dialog (versions list only). */
  statuses?: Array<{ label: string, value: string }>
}>()

const emit = defineEmits<{ imported: [] }>()

const { t } = useI18n()
const toast = useToast()
const auth = useAuthStore()
const lcs = useLcs()
const excelIo = useExcelIo()

const module_ = ref<ExcelModuleInfo | null>(null)
const exportOpen = ref(false)
const importOpen = ref(false)
const exporting = ref(false)
const exportError = ref('')
const matchingCount = ref<number | null>(null)
const counting = ref(false)
let countToken = 0

async function loadModule() {
  if (!auth.user) return
  try {
    const modules = await excelIo.modules()
    module_.value = modules.find(item => item.key === props.collection) ?? null
  }
  catch { /* the buttons stay hidden; the page itself still works */ }
}

void loadModule()
watch(() => auth.user?.id, id => { if (id) void loadModule() })
watch(() => props.collection, () => void loadModule())

const canImport = computed(() => Boolean(
  module_.value?.importEnabled && lcs.can(module_.value.managePermission as never),
))
const canExport = computed(() => Boolean(
  module_.value?.exportEnabled && lcs.can(module_.value.viewPermission as never),
))

/** Debounced matching-record count shown inside the export dialog. */
function onFiltersChange(filters: ExportFilters) {
  matchingCount.value = null
  counting.value = true
  const token = ++countToken
  void excelIo.exportCount(props.collection, exportFilterParams(filters))
    .then((data) => {
      if (token === countToken) {
        matchingCount.value = data.count
        counting.value = false
      }
    })
    .catch(() => {
      if (token === countToken) {
        counting.value = false
        matchingCount.value = null
      }
    })
}

function exportFilterParams(filters: ExportFilters): Record<string, string> {
  const map: Record<string, string> = {
    dateFrom: 'date_from',
    dateTo: 'date_to',
    status: 'status',
  }
  return Object.fromEntries(
    Object.entries(filters)
      .map(([key, value]) => [map[key], String(value)])
      .filter(([key]) => Boolean(key)),
  )
}

async function runExport(request: ExportRequest) {
  exporting.value = true
  exportError.value = ''
  try {
    // Scope is all-matching on configuration pages: ids stay empty on purpose.
    await excelIo.exportRows(props.collection, [], {
      format: request.format,
      filters: request.filters ? exportFilterParams(request.filters) : {},
    })
    exportOpen.value = false
    toast.add({ title: t('lcs.exportDialog.completed'), color: 'success' })
  }
  catch (error) {
    // Inline failure message: toasts are reserved for transport failures.
    exportError.value = lcs.errorMessage(error)
  }
  finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="flex items-center gap-2">
    <p
      v-if="exportError"
      role="alert"
      class="max-w-72 truncate text-xs text-error"
      :title="exportError"
    >
      {{ exportError }}
    </p>
    <CommonAppDocumentActionButton
      v-if="canExport"
      icon="i-lucide-download"
      :label="t('actions.exportData')"
      @click="exportOpen = true"
    />
    <CommonAppDocumentActionButton
      v-if="canImport"
      icon="i-lucide-upload"
      :label="t('actions.importData')"
      @click="importOpen = true"
    />

    <ExcelImportExportDialog
      v-model:open="importOpen"
      :collection="collection"
      @imported="emit('imported')"
    />

    <CommonAppExportDialog
      v-model:open="exportOpen"
      :loading="exporting"
      :matching-count="matchingCount"
      :counting="counting"
      :statuses="statuses ?? []"
      scopes="all_matching"
      @filters-change="onFiltersChange"
      @submit="runExport"
    />
  </div>
</template>

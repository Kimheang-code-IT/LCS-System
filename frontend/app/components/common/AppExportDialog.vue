<script setup lang="ts">
import type { ExportFieldOption, ExportFilters, ExportFormat, ExportRequest, ExportScope } from '~/types/export'

const open = defineModel<boolean>('open', { default: false })

const props = withDefaults(defineProps<{
  fields?: ExportFieldOption[]
  selectedCount?: number
  loading?: boolean
  /** Searchable user options for the Created/Updated By filters (list pages only). */
  users?: Array<{ label: string, value: string }>
  statuses?: Array<{ label: string, value: string }>
  updatedBySupported?: boolean
  /** Rows matching the current filters, when the host can count them. */
  matchingCount?: number | null
  counting?: boolean
}>(), {
  fields: () => [],
  selectedCount: 0,
  loading: false,
  users: () => [],
  statuses: () => [],
  updatedBySupported: false,
  matchingCount: null,
  counting: false,
})

const emit = defineEmits<{
  submit: [request: ExportRequest]
  'filters-change': [filters: ExportFilters]
}>()

const { t } = useI18n()
const searchConfig = computed(() => getFilterSearchInputConfig(t))
const startDate = ref('')
const endDate = ref('')
const updatedBy = ref('')
const status = ref('')
const format = ref<ExportFormat>('xlsx')
const scope = ref<ExportScope>('all_matching')
const selectedFields = ref<string[]>([])

const scopeItems = computed(() => [
  { label: t('lcs.exportDialog.allMatching'), value: 'all_matching' },
  { label: t('lcs.exportDialog.currentPage'), value: 'current_page' },
  {
    label: t('lcs.exportDialog.selectedRows', { n: props.selectedCount }),
    value: 'selected',
    disabled: props.selectedCount < 1,
  },
])

const formatItems = computed(() => [
  { label: 'Excel (.xlsx)', value: 'xlsx' },
  { label: 'CSV (.csv)', value: 'csv' },
])

const hasUserFilters = computed(() => props.users.length > 0)
const userItems = computed(() => [{ label: t('lcs.exportDialog.allUsers'), value: '' }, ...props.users])
const statusItems = computed(() => [{ label: t('lcs.exportDialog.allStatuses'), value: '' }, ...props.statuses])

const filters = computed<ExportFilters>(() => ({
  ...(startDate.value ? { dateFrom: startDate.value } : {}),
  ...(endDate.value ? { dateTo: endDate.value } : {}),
  ...(updatedBy.value ? { updatedBy: updatedBy.value } : {}),
  ...(status.value ? { status: status.value } : {}),
}))

/** Any filter change is published so the host can refresh the matching count. */
watch([startDate, endDate, updatedBy, status], () => {
  emit('filters-change', filters.value)
})

const invalidRange = computed(() => Boolean(
  startDate.value && endDate.value && startDate.value > endDate.value,
))
const noFields = computed(() => props.fields.length > 0 && selectedFields.value.length === 0)
const noMatches = computed(() => props.matchingCount === 0)
const canSubmit = computed(() => !invalidRange.value && !noFields.value && !noMatches.value && !props.loading)

function resetFilters() {
  startDate.value = ''
  endDate.value = ''
  updatedBy.value = ''
  status.value = ''
}

watch(open, (isOpen) => {
  if (!isOpen) return
  resetFilters()
  format.value = 'xlsx'
  scope.value = 'all_matching'
  selectedFields.value = props.fields.map(field => field.value)
})

watch(() => props.selectedCount, (count) => {
  if (count < 1 && scope.value === 'selected') scope.value = 'all_matching'
})

function toggleField(value: string, checked: boolean | 'indeterminate') {
  selectedFields.value = checked === true
    ? [...new Set([...selectedFields.value, value])]
    : selectedFields.value.filter(field => field !== value)
}

function submit() {
  if (!canSubmit.value) return
  emit('submit', {
    startDate: startDate.value || undefined,
    endDate: endDate.value || undefined,
    scope: scope.value,
    format: format.value,
    filters: Object.keys(filters.value).length ? filters.value : undefined,
    fieldCodes: [...selectedFields.value],
  })
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="$t('lcs.exportDialog.title')"
    :description="$t('lcs.exportDialog.description')"
    :dismissible="false"
    :close="{ color: 'primary', variant: 'outline', class: 'rounded-full' }"
    :ui="{ content: 'w-[calc(100%-2rem)] max-w-2xl sm:max-w-2xl' }"
  >
    <template #body>
      <div class="space-y-5">
        <fieldset class="rounded-lg border border-default p-3">
          <legend class="px-1 text-sm font-medium text-highlighted">
            {{ $t('lcs.exportDialog.filters') }}
          </legend>
          <div class="space-y-4">
            <div>
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField :label="$t('lcs.exportDialog.startDate')">
                  <CommonAppInputDate
                    v-model="startDate"
                    class="w-full"
                  />
                </UFormField>
                <UFormField :label="$t('lcs.exportDialog.endDate')">
                  <CommonAppInputDate
                    v-model="endDate"
                    class="w-full"
                  />
                </UFormField>
              </div>
              <p v-if="invalidRange" class="mt-1 text-xs text-error">
                {{ $t('lcs.exportDialog.invalidRange') }}
              </p>
              <p v-else class="mt-1 text-xs text-muted">
                {{ $t('lcs.exportDialog.dateRangeHelp') }}
              </p>
            </div>

            <UFormField v-if="hasUserFilters && updatedBySupported" :label="$t('lcs.exportDialog.updatedBy')">
              <USelectMenu
                v-model="updatedBy"
                :items="userItems"
                value-key="value"
                :search-input="searchConfig"
                clear
                class="w-full"
              />
            </UFormField>

            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField v-if="statuses.length" :label="$t('lcs.exportDialog.status')">
                <USelect
                  v-model="status"
                  :items="statusItems"
                  value-key="value"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="$t('lcs.exportDialog.format')">
                <USelect
                  v-model="format"
                  :items="formatItems"
                  value-key="value"
                  class="w-full"
                />
              </UFormField>
            </div>

            <p v-if="counting" class="text-xs text-muted">
              {{ $t('lcs.exportDialog.counting') }}
            </p>
            <p v-else-if="matchingCount !== null" class="text-xs" :class="noMatches ? 'text-error' : 'text-muted'">
              {{ $t('lcs.exportDialog.matchingCount', { n: matchingCount }) }}
            </p>
          </div>
        </fieldset>

        <UFormField :label="$t('lcs.exportDialog.scope')" :help="$t('lcs.exportDialog.scopeHelp')">
          <USelect
            v-model="scope"
            :items="scopeItems"
            value-key="value"
            class="w-full"
          />
        </UFormField>

        <fieldset v-if="fields.length" class="rounded-lg border border-default p-3">
          <legend class="px-1 text-sm font-medium text-highlighted">
            {{ $t('lcs.exportDialog.fields') }}
          </legend>
          <p class="mb-3 text-xs text-muted">{{ $t('lcs.exportDialog.fieldsHint') }}</p>
          <div class="grid gap-2 sm:grid-cols-2">
            <UCheckbox
              v-for="field in fields"
              :key="field.value"
              :model-value="selectedFields.includes(field.value)"
              :label="field.label"
              @update:model-value="toggleField(field.value, $event)"
            />
          </div>
          <p v-if="noFields" class="mt-2 text-xs text-error">
            {{ $t('lcs.exportDialog.fieldRequired') }}
          </p>
        </fieldset>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full items-center justify-between gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :disabled="loading"
          @click="resetFilters"
        >
          {{ $t('lcs.exportDialog.resetFilters') }}
        </UButton>
        <div class="flex gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :disabled="loading"
            @click="open = false"
          >
            {{ $t('actions.cancel') }}
          </UButton>
          <UButton
            icon="i-lucide-download"
            :loading="loading"
            :disabled="!canSubmit"
            @click="submit"
          >
            {{ $t('actions.export') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

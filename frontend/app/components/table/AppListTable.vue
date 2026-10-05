<script setup lang="ts" generic="T extends Record<string, unknown>">
import type { DropdownMenuItem, TableColumn, TableRow } from '@nuxt/ui'
import type { PaginationState, SortingState } from '@tanstack/vue-table'
import { getPaginationRowModel } from '@tanstack/vue-table'
import type { DatePickerGranularity } from '~/utils/date-picker'
import { parsePageLimit, TABLE_PAGE_SIZES } from '~/utils/pagination'
import { listTableSelectedIds, listTableVirtualize } from '~/utils/table/list-table'
import {
  listSortActive,
  listSortColumns,
  listSortDirectionLabel,
  listSortFromSelection,
  type ListSortOption,
  type ListSortSelection,
  listSortSelectionOf,
  listSortSummary,
  listSortToState,
} from '~/utils/table/list-sort'
import { freightTableFillUi } from '~/utils/table/theme'

export type ListTableEmptyAction = {
  icon?: string
  label: string
  onClick: () => void
}

/** Icons live here because `app/utils` is outside the icon client-bundle scan. */
const LIST_SORT_ICONS = {
  idle: 'i-lucide-arrow-up-down',
  asc: 'i-lucide-arrow-up-narrow-wide',
  desc: 'i-lucide-arrow-down-narrow-wide',
} as const

const search = defineModel<string>('search', { default: '' })
const dateStart = defineModel<string>('dateStart', { default: '' })
const dateEnd = defineModel<string>('dateEnd', { default: '' })
const rowSelection = defineModel<Record<string, boolean>>('rowSelection', { default: () => ({}) })
const pagination = defineModel<PaginationState>('pagination', {
  default: () => ({ pageIndex: 0, pageSize: 20 }),
})
/** Optional parent-owned sort, so a page can seed, clear or restore the selection. */
const sortModel = defineModel<ListSortSelection | null>('sort', { default: null })

const props = withDefaults(defineProps<{
  data: T[]
  columns: TableColumn<T>[]
  loading?: boolean
  getRowId?: (row: T) => string
  searchPlaceholder?: string
  showDateRange?: boolean
  dateLabel?: string
  dateGranularity?: DatePickerGranularity
  /** Lights the mobile filter button when any toolbar filter or date range is set. */
  filtersActive?: boolean
  emptyIcon?: string
  emptyTitle?: string
  emptyDescription?: string
  emptyActions?: ListTableEmptyAction[]
  /** Total row count supplied by a server-paginated endpoint. */
  serverTotal?: number
  serverSide?: boolean
}>(), {
  loading: false,
  getRowId: (row: T) => String(row.id || ''),
  searchPlaceholder: '',
  showDateRange: false,
  dateLabel: '',
  dateGranularity: 'day',
  filtersActive: false,
  emptyIcon: 'i-lucide-inbox',
  emptyTitle: '',
  emptyDescription: '',
  emptyActions: () => [],
  serverTotal: 0,
  serverSide: false,
})

const emit = defineEmits<{
  select: [event: Event, row: TableRow<T>]
  /** Fired when the toolbar sort menu changes (null clears the sort). */
  sort: [sort: ListSortSelection]
}>()

const { t } = useI18n()

const sorting = ref<SortingState>([])
const sortColumns = computed(() => listSortColumns(props.columns))
const sortOptions = computed(() => sortColumns.value.flatMap(column => column.options))
const activeSort = computed(() => listSortActive(sortOptions.value, sorting.value))
const sortLabel = computed(() => t('freight.ui.sort'))
const sortSummary = computed(() => listSortSummary(activeSort.value, t))
const sortIcon = computed(() => {
  if (activeSort.value?.dir === 'asc') return LIST_SORT_ICONS.asc
  if (activeSort.value?.dir === 'desc') return LIST_SORT_ICONS.desc
  return LIST_SORT_ICONS.idle
})
/** Wide tables get a type-to-narrow field so every column is not listed at once. */
const sortFilter = computed(() => (sortColumns.value.length > 6
  ? { placeholder: t('freight.ui.sortFilter') }
  : false))

function applySort(option: ListSortOption | null) {
  sorting.value = listSortToState(option)
  const next = listSortSelectionOf(option)
  sortModel.value = next
  emit('sort', next)
}

// Keep the TanStack state, the parent model and the columns in sync. A sort whose
// column disappeared (e.g. the workspace switched module) is dropped everywhere.
watch([sortModel, sortOptions], ([selection, options]) => {
  const resolved = selection ? listSortFromSelection(options, selection) : null
  const active = listSortActive(options, sorting.value)
  if ((resolved?.id ?? null) === (active?.id ?? null)) return
  sorting.value = listSortToState(resolved)
  if (selection && !resolved) {
    sortModel.value = null
    emit('sort', null)
  }
})

/**
 * Column-first menu: the top level lists one entry per sortable column and each
 * entry opens a submenu with just its two directions, so the user never has to
 * scroll a flat list of every column × direction. The active column shows its
 * current direction as a description and is tinted.
 */
const sortMenuItems = computed<DropdownMenuItem[][]>(() => {
  if (!sortColumns.value.length) return []
  const columns: DropdownMenuItem[] = sortColumns.value.map((column) => {
    const activeOption = column.options.find(option => option.id === activeSort.value?.id)
    return {
      label: column.header,
      description: activeOption ? listSortDirectionLabel(column.kind, activeOption.dir, t) : undefined,
      color: activeOption ? 'primary' : undefined,
      children: column.options.map((option): DropdownMenuItem => ({
        type: 'checkbox',
        label: listSortDirectionLabel(option.kind, option.dir, t),
        checked: activeSort.value?.id === option.id,
        onSelect: () => applySort(activeSort.value?.id === option.id ? null : option),
      })),
    }
  })
  return [
    columns,
    [{
      label: t('freight.ui.sortDefault'),
      icon: LIST_SORT_ICONS.idle,
      onSelect: () => applySort(null),
    }],
  ]
})

const paginationOptions = computed(() => props.serverSide
  ? { manualPagination: true, manualSorting: true, rowCount: props.serverTotal ?? props.data.length }
  : { getPaginationRowModel: getPaginationRowModel() })
const selectedIds = computed(() => listTableSelectedIds(rowSelection.value))
const total = computed(() => props.serverSide ? (props.serverTotal ?? props.data.length) : props.data.length)
const visibleTotal = computed(() => props.data.length)
const virtualize = computed(() => listTableVirtualize(visibleTotal.value, pagination.value.pageSize))
const searchPlaceholderText = computed(() => props.searchPlaceholder || t('freight.ui.search'))
const dateLabelText = computed(() => props.dateLabel || t('freight.ui.date'))
const emptyTitleText = computed(() => props.emptyTitle || t('freight.ui.noRecords'))
const emptyDescriptionText = computed(() => props.emptyDescription || t('freight.ui.noRecordsHint'))
const pageSizeItems = TABLE_PAGE_SIZES.map(value => ({ label: String(value), value: String(value) }))

function rowId(row: T) {
  return props.getRowId(row)
}

function setPageSize(value: unknown) {
  pagination.value = { pageIndex: 0, pageSize: parsePageLimit(value, 20) }
}

function setPage(page: number) {
  pagination.value = { ...pagination.value, pageIndex: Math.max(0, page - 1) }
}

function onSelect(event: Event, row: TableRow<T>) {
  emit('select', event, row)
}
</script>

<template>
  <div class="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden px-1.5 pt-1.5 pb-0">
    <div class="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden rounded-sm border border-default bg-default shadow-xs">
      <div class="flex items-center gap-3 border-b border-default px-2 py-2">
        <CommonAppLiveSearch
          v-model="search"
          class="w-56 shrink-0 sm:w-64"
          :placeholder="searchPlaceholderText"
        />

        <div class="flex min-w-0 flex-1 items-center justify-end gap-2 overflow-x-auto">
          <CommonAppFilterMenu :active="filtersActive" class="min-w-0">
            <template #default="{ compact }">
              <slot name="filters" :compact="compact" />
              <CommonAppDateRangeFilter
                v-if="showDateRange"
                v-model:start="dateStart"
                v-model:end="dateEnd"
                :granularity="dateGranularity"
                :inline="compact"
                :label="dateLabelText"
              />
            </template>
          </CommonAppFilterMenu>

          <UDropdownMenu
            v-if="sortMenuItems.length"
            :items="sortMenuItems"
            :filter="sortFilter"
            :content="{ align: 'end' }"
            :aria-label="sortLabel"
          >
            <UButton
              :color="activeSort ? 'primary' : 'neutral'"
              :variant="activeSort ? 'soft' : 'outline'"
              :icon="sortIcon"
              size="sm"
              square
              class="shrink-0"
              :aria-label="`${sortLabel} · ${sortSummary}`"
              :title="`${sortLabel} · ${sortSummary}`"
            />
          </UDropdownMenu>

          <slot name="actions" :selected-ids="selectedIds" />
        </div>
      </div>

      <div class="min-h-0 flex-1 overflow-hidden">
        <UTable
          v-if="visibleTotal"
          v-model:row-selection="rowSelection"
          v-model:pagination="pagination"
          v-model:sorting="sorting"
          :data="data"
          :columns="columns"
          :loading="loading"
          :get-row-id="rowId"
          :pagination-options="paginationOptions"
          :virtualize="virtualize"
          sticky="header"
          class="freight-table h-full min-h-0"
          :ui="freightTableFillUi"
          @select="onSelect"
        />
        <UEmpty
          v-else
          variant="naked"
          :icon="emptyIcon"
          :title="emptyTitleText"
          :description="emptyDescriptionText"
          :actions="emptyActions.length ? emptyActions : undefined"
          class="py-16"
        />
      </div>

      <div class="flex items-center justify-between gap-2 border-t border-default px-2 py-1.5">
        <div class="flex items-center gap-1.5">
          <span class="text-[11px] leading-none text-muted">{{ t('common.rowsPerPage') }}</span>
          <USelect
            :model-value="String(pagination.pageSize)"
            :items="pageSizeItems"
            size="xs"
            class="w-16"
            @update:model-value="setPageSize"
          />
        </div>
        <UPagination
          :page="pagination.pageIndex + 1"
          :items-per-page="pagination.pageSize"
          :total="total"
          size="xs"
          :sibling-count="1"
          @update:page="setPage"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { PaginationState } from '@tanstack/vue-table'
import { h } from 'vue'
import { UBadge, UButton } from '#components'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { useArchiveRepository } from '~/repositories'
import type { ArchiveOptions, ArchiveRecord } from '~/repositories/contracts/archive'
import { confirmsArchiveHardDelete, hasArchivePermission } from '~/utils/archive/access'
import type { ListSortSelection } from '~/utils/table/list-sort'

definePageMeta({ titleKey: 'freight.pages.archive', permission: 'archive.view' })

const { t } = useI18n()
const auth = useAuthStore()
const repository = useArchiveRepository()
const toast = useToast()
const { confirm } = useConfirm()
const { setTitle, setBreadcrumbs, clear } = useAppHeader()

const rows = ref<ArchiveRecord[]>([])
const total = ref(0)
const loading = ref(false)
const q = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const entityTypes = ref<string[]>([])
const deletedByUsers = ref<string[]>([])
const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 20 })
const sort = ref<ListSortSelection>(null)
const options = ref<ArchiveOptions>({ entityTypes: [], deletedByUsers: [] })
const detailOpen = ref(false)
const detailLoading = ref(false)
const selected = ref<ArchiveRecord | null>(null)
const hardDeleteOpen = ref(false)
const hardDeleteInput = ref('')
const hardDeleteLoading = ref(false)

const sourcePermissions = computed<readonly string[]>(() => auth.user?.sourcePermissions || [])
const canRestore = computed(() => hasArchivePermission(sourcePermissions.value, 'archive.restore'))
const canHardDelete = computed(() => hasArchivePermission(sourcePermissions.value, 'archive.hard_delete'))
const filtersActive = computed(() => Boolean(entityTypes.value.length || deletedByUsers.value.length || dateFrom.value || dateTo.value))

function formatDate(value: string) {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

async function refresh() {
  loading.value = true
  try {
    const result = await repository.list({
      q: q.value || undefined,
      page: pagination.value.pageIndex + 1,
      page_size: pagination.value.pageSize,
      entity_type: entityTypes.value[0] || undefined,
      deleted_by: deletedByUsers.value[0] ? Number(deletedByUsers.value[0]) : undefined,
      dateFrom: dateFrom.value || undefined,
      dateTo: dateTo.value || undefined,
      sortKey: sort.value?.key,
      sortDir: sort.value?.dir,
    })
    rows.value = result.items
    total.value = result.meta.total
  }
  finally {
    loading.value = false
  }
}

async function refreshOptions() {
  options.value = await repository.options()
}

watch([q, entityTypes, deletedByUsers, dateFrom, dateTo, sort], () => {
  if (pagination.value.pageIndex !== 0) pagination.value = { ...pagination.value, pageIndex: 0 }
  else void refresh()
}, { deep: true })
watch(pagination, () => { void refresh() }, { deep: true })

async function showDetails(record: ArchiveRecord) {
  detailOpen.value = true
  detailLoading.value = true
  selected.value = record
  try {
    selected.value = await repository.get(record.entityType, record.entityId)
  }
  finally {
    detailLoading.value = false
  }
}

async function restore(record: ArchiveRecord) {
  if (!canRestore.value) return
  const ok = await confirm({
    kind: 'generic',
    title: `Restore ${record.reference}?`,
    description: 'The record will return to its original module after dependency and uniqueness checks pass.',
    confirmLabel: 'Restore',
  })
  if (!ok) return
  await repository.restore(record.entityType, record.entityId)
  toast.add({ title: `${record.reference} restored`, color: 'success' })
  detailOpen.value = false
  await Promise.all([refresh(), refreshOptions()])
}

function requestHardDelete(record: ArchiveRecord) {
  selected.value = record
  hardDeleteInput.value = ''
  hardDeleteOpen.value = true
}

async function hardDelete() {
  if (!selected.value || !confirmsArchiveHardDelete(hardDeleteInput.value) || !canHardDelete.value) return
  hardDeleteLoading.value = true
  try {
    await repository.hardDelete(selected.value.entityType, selected.value.entityId)
    toast.add({ title: `${selected.value.reference} permanently deleted`, color: 'success' })
    hardDeleteOpen.value = false
    detailOpen.value = false
    await Promise.all([refresh(), refreshOptions()])
  }
  finally {
    hardDeleteLoading.value = false
  }
}

const columns: TableColumn<ArchiveRecord>[] = [
  { accessorKey: 'module', header: 'Module / Entity', meta: { sortKind: 'text' } },
  { accessorKey: 'reference', header: 'Record / Reference', meta: { sortKind: 'text' } },
  { accessorKey: 'deletedBy', header: 'Deleted By', meta: { sortKind: 'text' } },
  {
    accessorKey: 'deletedAt',
    header: 'Deleted At',
    meta: { sortKind: 'date' },
    cell: ({ row }) => h('span', { class: 'whitespace-nowrap text-sm' }, formatDate(row.original.deletedAt)),
  },
  { accessorKey: 'originalOwner', header: 'Original Owner / Creator', meta: { sortKind: 'text' } },
  {
    accessorKey: 'status',
    header: 'Status',
    meta: { sortKind: 'text' },
    cell: ({ row }) => h(UBadge, { color: 'warning', variant: 'subtle', size: 'sm' }, () => row.original.status),
  },
  {
    id: 'actions',
    header: 'Actions',
    enableSorting: false,
    cell: ({ row }) => h('div', { class: 'flex items-center justify-end gap-1' }, [
      h(UButton, {
        icon: 'i-lucide-eye', color: 'neutral', variant: 'ghost', size: 'xs', 'aria-label': 'View deleted data',
        onClick: (event: Event) => { event.stopPropagation(); void showDetails(row.original) },
      }),
      canRestore.value
        ? h(UButton, {
            icon: 'i-lucide-rotate-ccw', color: 'primary', variant: 'ghost', size: 'xs', 'aria-label': 'Restore',
            onClick: (event: Event) => { event.stopPropagation(); void restore(row.original) },
          })
        : null,
      canHardDelete.value
        ? h(UButton, {
            icon: 'i-lucide-trash-2', color: 'error', variant: 'ghost', size: 'xs', 'aria-label': 'Permanently delete',
            onClick: (event: Event) => { event.stopPropagation(); requestHardDelete(row.original) },
          })
        : null,
    ]),
  },
]

function onRowSelect(_event: Event, row: TableRow<ArchiveRecord>) {
  void showDetails(row.original)
}

onMounted(() => {
  setTitle(t('freight.pages.archive'))
  setBreadcrumbs([{ label: t('freight.nav.administration') }, { label: t('freight.pages.archive') }])
  void Promise.all([refresh(), refreshOptions()])
})
onBeforeUnmount(clear)
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions :can-create="false" :refreshing="loading" @refresh="refresh" />

    <TableAppListTable
      v-model:search="q"
      v-model:date-start="dateFrom"
      v-model:date-end="dateTo"
      v-model:pagination="pagination"
      v-model:sort="sort"
      :data="rows"
      :columns="columns"
      :loading="loading"
      :server-total="total"
      server-side
      show-date-range
      date-label="Deleted date"
      :filters-active="filtersActive"
      search-placeholder="Search record or reference"
      empty-icon="i-lucide-archive-restore"
      empty-title="Archive is empty"
      empty-description="Deleted records from supported modules will appear here."
      @select="onRowSelect"
    >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-model="entityTypes"
          :items="options.entityTypes"
          placeholder="Module / Entity"
          :class="compact ? 'w-full' : 'w-48'"
        />
        <CommonAppFilterSelect
          v-model="deletedByUsers"
          :items="options.deletedByUsers"
          placeholder="Deleted By"
          :class="compact ? 'w-full' : 'w-48'"
        />
      </template>
    </TableAppListTable>

    <UModal v-model:open="detailOpen" :title="selected?.reference || 'Archived record details'">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-start justify-between gap-3">
              <div>
                <h3 class="font-semibold text-highlighted">{{ selected?.reference }}</h3>
                <p class="text-sm text-muted">{{ selected?.module }} · deleted by {{ selected?.deletedBy }}</p>
              </div>
              <UBadge color="warning" variant="subtle">ARCHIVED</UBadge>
            </div>
          </template>
          <div v-if="detailLoading" class="space-y-3">
            <USkeleton v-for="index in 5" :key="index" class="h-8 w-full" />
          </div>
          <div v-else class="space-y-4">
            <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt class="text-muted">Deleted at</dt><dd>{{ selected ? formatDate(selected.deletedAt) : '' }}</dd>
              <dt class="text-muted">Original owner</dt><dd>{{ selected?.originalOwner || 'Not available' }}</dd>
              <dt class="text-muted">Entity ID</dt><dd>{{ selected?.entityId }}</dd>
            </dl>
            <div>
              <p class="mb-2 text-sm font-medium text-highlighted">Deleted data snapshot</p>
              <pre class="max-h-96 overflow-auto rounded-md bg-muted p-3 text-xs">{{ JSON.stringify(selected?.data || {}, null, 2) }}</pre>
            </div>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton color="neutral" variant="ghost" @click="detailOpen = false">Close</UButton>
              <UButton v-if="canRestore && selected" icon="i-lucide-rotate-ccw" @click="restore(selected)">Restore</UButton>
              <UButton
                v-if="canHardDelete && selected"
                color="error"
                icon="i-lucide-trash-2"
                @click="requestHardDelete(selected)"
              >
                Permanently Delete
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <CommonAppConfirmDialog
      v-model:open="hardDeleteOpen"
      title="Permanently delete this record?"
      description="This action cannot be undone. Related records will not be silently deleted. Type DELETE to continue."
      confirm-label="Permanently Delete"
      confirm-color="error"
      :loading="hardDeleteLoading"
      :confirm-disabled="!confirmsArchiveHardDelete(hardDeleteInput)"
      @confirm="hardDelete"
      @cancel="hardDeleteOpen = false"
    >
      <UInput
        v-model="hardDeleteInput"
        class="mt-4"
        placeholder="Type DELETE"
        autocomplete="off"
      />
    </CommonAppConfirmDialog>
  </div>
</template>

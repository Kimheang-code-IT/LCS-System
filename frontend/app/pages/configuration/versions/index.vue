<script setup lang="ts">
import type { DropdownMenuItem, TableColumn, TableRow } from '@nuxt/ui'
import type { PaginationState } from '@tanstack/vue-table'
import { h } from 'vue'
import { UBadge, UButton, UDropdownMenu } from '#components'
import type { ConfigurationVersion } from '~/types/component-config'
import type { ListSortSelection } from '~/utils/table/list-sort'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import { userSourcePermissions } from '~/utils/freight/permissions'
import { apiErrorMessage } from '~/utils/validation/api-error'

definePageMeta({
  titleKey: 'freight.pages.configurationVersions',
  permission: 'configuration.manage',
})

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()
const auth = useAuthStore()

const rows = computed(() => config.versions.value)
const meta = computed(() => config.versionsMeta.value)
const active = computed(() => config.activeVersion.value)
const livePreview = computed(() => config.preview.value)

const pageErrors = ref<string[]>([])
const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 20 })
const sort = ref<ListSortSelection>(null)
const q = ref('')
const statusFilter = ref('')
const actingId = ref('')
const filtersActive = computed(() => Boolean(statusFilter.value))

type BadgeColor = 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'primary' | 'secondary'

const STATUS_COLORS: Record<ConfigurationVersion['status'], BadgeColor> = {
  DRAFT: 'warning',
  PUBLISHED: 'success',
  RETIRED: 'neutral',
}

const permissionCodes = computed(() => new Set<string>(userSourcePermissions(auth.user)))
const pageKeys = computed(() => new Set(auth.user?.pageAccess || auth.user?.permissions || []))

function granted(code: string, pageKey: string) {
  return permissionCodes.value.has(code) || pageKeys.value.has(pageKey)
}

const canManage = computed(() => granted('configuration.manage', 'configuration.edit'))
const canPublish = computed(() => granted('configuration.publish', 'configuration.edit') || canManage.value)
const canActivate = computed(() => granted('configuration.activate', 'configuration.edit') || canManage.value)
const canRollback = computed(() => granted('configuration.rollback', 'configuration.edit') || canManage.value)
const canDelete = computed(() => canManage.value)

const activeVersionId = computed(() => active.value?.id || '')
const busy = computed(() => Boolean(actingId.value) || config.saving.value)

// The live configuration has changes that are not frozen in a version yet, so
// publishing it is the context's primary action; otherwise creating a version
// from the live configuration stays the generic create action.
const showPublishLive = computed(() =>
  canPublish.value
  && Boolean(livePreview.value)
  && !livePreview.value?.unchanged
  && (livePreview.value?.tabCount || 0) > 0,
)

const statusItems = [
  { label: 'Draft', value: 'DRAFT' },
  { label: 'Published', value: 'PUBLISHED' },
  { label: 'Retired', value: 'RETIRED' },
]

function statusColor(version: ConfigurationVersion): BadgeColor {
  return STATUS_COLORS[version.status] || 'neutral'
}

function when(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString()
}

function rowNumber(index: number) {
  return (meta.value.page - 1) * meta.value.page_size + index + 1
}

function versionPath(version: ConfigurationVersion, action?: 'edit' | 'rollback') {
  const suffix = action ? `?action=${action}` : ''
  return `/configuration/versions/${version.id}${suffix}`
}

async function refreshHistory(resetPage = false) {
  if (resetPage && pagination.value.pageIndex !== 0) {
    pagination.value = { ...pagination.value, pageIndex: 0 }
    return
  }
  await config.loadConfigurationVersions({
    page: pagination.value.pageIndex + 1,
    pageSize: pagination.value.pageSize,
    q: q.value.trim() || undefined,
    status: statusFilter.value || undefined,
    sortKey: sort.value?.key,
    sortDir: sort.value?.dir,
  }).catch((error) => {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  })
}

async function refreshAll() {
  pageErrors.value = []
  try {
    await Promise.all([
      refreshHistory(),
      config.loadActiveConfigurationVersion(),
      config.loadConfigurationPreview(),
    ])
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

function openVersion(version: ConfigurationVersion, action?: 'edit' | 'rollback') {
  return navigateTo(versionPath(version, action))
}

function openNew() {
  return navigateTo('/configuration/versions/new')
}

async function publish(version: ConfigurationVersion) {
  const accepted = await confirm({
    kind: 'generic',
    title: `Publish v${version.versionNo}?`,
    description: 'New Service Orders will use this configuration. Existing Service Orders keep the version they were captured under.',
    confirmLabel: 'Publish',
  })
  if (!accepted) return
  actingId.value = version.id
  pageErrors.value = []
  try {
    await config.activateConfiguration(version.id)
    await refreshAll()
    toast.add({ title: `v${version.versionNo} is now published`, color: 'success' })
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
  finally {
    actingId.value = ''
  }
}

async function remove(version: ConfigurationVersion) {
  const accepted = await confirm({
    kind: 'delete',
    count: 1,
    title: `Delete draft v${version.versionNo}?`,
    description: 'Only an unpublished draft can be deleted. Published and retired versions always keep their history.',
    confirmLabel: t('actions.delete'),
  })
  if (!accepted) return
  actingId.value = version.id
  pageErrors.value = []
  try {
    await config.deleteConfigurationVersion(version.id)
    await refreshAll()
    toast.add({ title: t('actions.delete'), color: 'success' })
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
  finally {
    actingId.value = ''
  }
}

function actionItems(version: ConfigurationVersion): DropdownMenuItem[][] {
  const items: DropdownMenuItem[] = [
    { label: 'View', icon: 'i-lucide-eye', onSelect: () => void openVersion(version) },
  ]
  const editable = version.status === 'DRAFT'
  if (editable && canManage.value) {
    items.push({ label: 'Edit', icon: 'i-lucide-pencil', onSelect: () => void openVersion(version, 'edit') })
  }
  const notActive = version.id !== activeVersionId.value && version.status !== 'DRAFT'
  if (notActive && canActivate.value) {
    items.push({
      label: 'Publish',
      icon: 'i-lucide-check-circle-2',
      disabled: busy.value,
      onSelect: () => void publish(version),
    })
  }
  if (notActive && canRollback.value) {
    items.push({
      label: 'Rollback',
      icon: 'i-lucide-undo-2',
      disabled: busy.value,
      onSelect: () => void openVersion(version, 'rollback'),
    })
  }
  if (editable && canDelete.value) {
    items.push({
      label: t('actions.delete'),
      icon: 'i-lucide-trash-2',
      color: 'error',
      disabled: busy.value,
      onSelect: () => void remove(version),
    })
  }
  return [items]
}

const versionColumns: TableColumn<ConfigurationVersion>[] = [
  {
    id: 'rowNo',
    header: 'No.',
    enableSorting: false,
    cell: ({ row }) => h('span', { class: 'text-xs tabular-nums text-muted' }, String(rowNumber(row.index))),
  },
  {
    accessorKey: 'versionNo',
    header: 'Version',
    meta: { sortKind: 'number' },
    cell: ({ row }) => h('span', { class: 'font-medium tabular-nums' }, `v${row.original.versionNo}`),
  },
  {
    accessorKey: 'changeNote',
    header: 'Description',
    meta: { sortKind: 'text' },
    cell: ({ row }) => h('span', { class: 'block max-w-72 truncate text-sm', title: row.original.changeNote || '' }, row.original.changeNote || '—'),
  },
  {
    accessorKey: 'status',
    header: 'Status',
    meta: { sortKind: 'text' },
    cell: ({ row }) => h(UBadge, { color: statusColor(row.original), variant: 'subtle', size: 'sm' }, () => row.original.status),
  },
  {
    accessorKey: 'createdBy',
    header: 'Created By',
    meta: { sortKind: 'text' },
    cell: ({ row }) => h('span', { class: 'text-sm' }, row.original.createdBy || '—'),
  },
  {
    accessorKey: 'createdAt',
    header: 'Created At',
    meta: { sortKind: 'date' },
    cell: ({ row }) => h('span', { class: 'whitespace-nowrap text-sm' }, when(row.original.createdAt)),
  },
  {
    accessorKey: 'publishedBy',
    header: 'Published By',
    meta: { sortKind: 'text' },
    cell: ({ row }) => h('span', { class: 'text-sm' }, row.original.publishedBy || '—'),
  },
  {
    accessorKey: 'publishedAt',
    header: 'Published At',
    meta: { sortKind: 'date' },
    cell: ({ row }) => h('span', { class: 'whitespace-nowrap text-sm' }, when(row.original.publishedAt)),
  },
  {
    id: 'actions',
    header: 'Actions',
    enableSorting: false,
    cell: ({ row }) => h('div', { class: 'flex justify-end' }, [
      h(UDropdownMenu, { items: actionItems(row.original) }, {
        default: () => h(UButton, {
          icon: 'i-lucide-ellipsis',
          color: 'neutral',
          variant: 'ghost',
          size: 'xs',
          square: true,
          'aria-label': 'Actions',
          'disabled': busy.value,
        }),
      }),
    ]),
  },
]

// TableAppListTable is typed against a generic record; the column definitions
// themselves stay strongly typed as ConfigurationVersion.
const columns = versionColumns as unknown as TableColumn<Record<string, unknown>>[]
const tableRows = computed(() => rows.value as unknown as Record<string, unknown>[])

function onRowSelect(event: Event, row: TableRow<Record<string, unknown>>) {
  const target = event.target as HTMLElement | null
  if (target?.closest('a, button, input, [role="checkbox"], [role="menuitem"], [data-slot="dropdown-menu"]')) return
  void openVersion(row.original as unknown as ConfigurationVersion)
}

watch([q, statusFilter, sort], () => { void refreshHistory(true) }, { deep: true })
watch(pagination, () => { void refreshHistory() }, { deep: true })

onMounted(refreshAll)
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-create="canPublish && !showPublishLive"
      create-label="New Version"
      :refreshing="config.loading.value"
      @create="openNew()"
      @refresh="refreshAll"
    >
      <template #leading>
        <UBadge v-if="active" color="success" variant="subtle">
          {{ t('freight.configVersions.current', { no: active.versionNo }) }}
        </UBadge>
      </template>
      <template #default>
        <UButton
          v-if="showPublishLive"
          color="primary"
          size="sm"
          icon="i-lucide-upload-cloud"
          @click="openNew()"
        >
          Publish live configuration
        </UButton>
      </template>
    </LayoutAppHeaderPageActions>

    <CommonAppFormErrorSummary class="px-4 pt-3" :form-errors="pageErrors" />

    <div class="space-y-3 px-4 pt-3">
      <UAlert
        v-if="active && !livePreview?.unchanged"
        color="warning"
        variant="subtle"
        description="The live configuration has changes that are not part of the published version. Creating a new version freezes them."
      />
    </div>

    <TableAppListTable
      v-model:search="q"
      v-model:pagination="pagination"
      v-model:sort="sort"
      :data="tableRows"
      :columns="columns"
      :loading="config.loading.value"
      :server-total="meta.total"
      server-side
      :filters-active="filtersActive"
      search-placeholder="Search version or name"
      empty-icon="i-lucide-history"
      empty-title="No configuration versions yet"
      empty-description="Publish the live configuration to start the version history."
      :empty-actions="canPublish ? [{ icon: 'i-lucide-plus', label: 'New Version', onClick: openNew }] : []"
      @select="onRowSelect"
    >
      <template #filters>
        <USelect
          v-model="statusFilter"
          :items="statusItems"
          placeholder="Status"
          class="w-44"
        />
      </template>
    </TableAppListTable>
  </div>
</template>

<script setup lang="ts">
import type { DropdownMenuItem, TableColumn, TableRow } from '@nuxt/ui'
import type { PaginationState } from '@tanstack/vue-table'
import { h } from 'vue'
import { UBadge, ULink } from '#components'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import {
  formatFreightCell,
  freightStatusBadge,
  useFreightLabel,
  useFreightRouteModule,
} from '~/composables/freight/useFreight'
import { useLcs } from '~/composables/lcs/useLcs'
import type { FreightRecord } from '~/types/freight/record'
import { freightModules, type FreightSelectOption } from '~/config/freight-modules'
import { chargeDomainStatus, financeDomainStatus, jobDomainStatus, quotationDomainStatus } from '~/utils/lcs/states'
import { isMoneyKey, isNumericKey, jobForQuotation, jobWorkspacePath, workspaceSectionForPath } from '~/utils/freight/job-workspace'
import { enrichJobListRows } from '~/utils/freight/job-list'
import { limitFilterSelects, parseFilterQuery } from '~/utils/filter/values'
import { isFilterValueActive } from '~/utils/filter/select-ui'
import { listTableRowMetaColumn, listTableSelectColumn } from '~/utils/table/list-columns'
import { listTablePageSummary, listTableSelectedIds } from '~/utils/table/list-table'
import { documentSequenceTypeLabel, isDocumentSequenceType } from '~/utils/document-sequences'
import { normalizeAuditLog, resolveAuditEntityPath } from '~/utils/freight/audit-logs'
import type { ServiceOrderStatus } from '~/types/lcs/domain'
import { useModuleList } from '~/composables/freight/useModuleList'

const { module, route } = useFreightRouteModule()
const store = useFreightStore()
const auth = useAuthStore()
const lcs = useLcs()
const { t } = useI18n()
const { fieldLabel, moduleTitle, moduleSingular } = useFreightLabel()
const { setTitle, setBreadcrumbs, clear } = useAppHeader()
const { confirm } = useConfirm()
const toast = useToast()

const q = ref('')
const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 20 })
const filters = reactive<Record<string, string[]>>({})
const rowSelection = ref<Record<string, boolean>>({})
const pending = ref(false)
const busyId = ref('')
const dateFrom = ref('')
const dateTo = ref('')

const current = computed(() => module.value)
const moduleList = useModuleList(current)
const isJobList = computed(() => current.value?.collection === 'jobs')
const dateField = computed(() => {
  const fields = current.value?.fields || []
  return fields.find(field => field.type === 'date' || field.type === 'datetime' || field.key === 'date' || /date$/i.test(field.key))?.key
    || current.value?.columns.find(column => /date/i.test(column.key))?.key
})

async function refreshList() {
  if (!current.value) return
  pending.value = true
  try {
    await moduleList.refresh({
      q: q.value,
      filters,
      paginate: false,
      dateField: dateField.value,
      dateFrom: dateFrom.value,
      dateTo: dateTo.value,
    })
  }
  finally {
    pending.value = false
  }
}

watch([current, q, filters, dateFrom, dateTo, dateField], () => { void refreshList() }, { immediate: true, deep: true })

const result = computed(() => {
  if (!current.value) return { rows: [], total: 0, all: [] }
  let all = moduleList.items.value
  if (isJobList.value) {
    all = enrichJobListRows(all, {
      containers: store.list('actualContainers'),
      tasks: store.list('serviceComponents'),
      charges: store.list('jobCharges'),
      shipments: store.list('shipments'),
    })
  }
  return { rows: all, total: moduleList.total.value || all.length, all }
})
const isTableOnly = computed(() => Boolean(current.value?.tableOnly))
const canManageModule = computed(() => {
  if (!current.value) return false
  if (auth.user?.pageAccess?.includes('ALL_PAGES')) return true
  if (current.value.collection === 'chartOfAccounts' || current.value.collection === 'financialAccounts') return lcs.can('chart_of_accounts.manage')
  if (current.value.collection === 'organizations') return lcs.can('organization.update')
  if (current.value.collection === 'branches') return lcs.can('branch.manage')
  if (current.value.collection === 'users') return lcs.can('user.manage')
  if (current.value.collection === 'roles') return lcs.can('role.manage')
  if (current.value.group === 'master') return false
  if (current.value.group === 'configuration') return auth.canAccessPage('configuration.manage')
  return true
})
const canCreate = computed(() => {
  if (!current.value?.canCreate || current.value.readOnly || !canManageModule.value) return false
  if (isJobList.value) return lcs.can('service_order.create')
  return true
})
const canMutate = computed(() => Boolean(current.value) && !current.value?.readOnly && canManageModule.value)
const deactivationOnly = computed(() => current.value?.group === 'master' || current.value?.collection === 'documentSequences')

const selectedIds = computed(() => listTableSelectedIds(rowSelection.value))

/** Lights the collapsed filter-menu button when any toolbar filter is set. */
const hasActiveFilters = computed(() => Boolean(
  Object.values(filters).some(value => isFilterValueActive(value))
  || isFilterValueActive(dateFrom.value)
  || isFilterValueActive(dateTo.value),
))

/** Toolbar shows at most 3 selects beside the date range, 4 without it. */
const visibleFilters = computed(() => limitFilterSelects(
  current.value?.filters || [],
  Boolean(dateField.value),
  filter => filter.key === 'status' || filter.key === 'workflowStatus',
))

watch(current, (value) => {
  if (!value) return
  setTitle(moduleTitle(value))
  setBreadcrumbs([{ label: moduleTitle(value) }])
  rowSelection.value = {}
  for (const key of Object.keys(filters)) delete filters[key]
  for (const filter of value.filters || []) {
    filters[filter.key] = parseFilterQuery(route.query[filter.key])
  }
}, { immediate: true })

onBeforeUnmount(clear)

usePageSeo({
  title: () => current.value ? moduleTitle(current.value) : t('freight.pages.dashboard'),
})

watch([q, filters, dateFrom, dateTo], () => {
  rowSelection.value = {}
  pagination.value = { ...pagination.value, pageIndex: 0 }
}, { deep: true })

const jobsByNo = computed(() => {
  const map = new Map<string, string>()
  for (const job of store.list('jobs')) {
    map.set(String(job.jobNo || ''), String(job.id))
  }
  return map
})

function jobLinkFor(jobNo: unknown) {
  if (!auth.canAccessPage('operations.service_orders.view')) return ''
  const id = jobsByNo.value.get(String(jobNo || ''))
  if (!id || !current.value) return ''
  return jobWorkspacePath(id, workspaceSectionForPath(current.value.path))
}

function recordPath(id: unknown) {
  if (!current.value) return '/'
  return `${current.value.path}/${id}`
}

function cellText(row: Record<string, unknown>, key: string) {
  const source = current.value?.collection === 'auditLogs' ? normalizeAuditLog(row as FreightRecord) : row
  return formatFreightCell(source[key], key)
}

function auditEntityLinkFor(row: Record<string, unknown>) {
  if (current.value?.collection !== 'auditLogs') return ''
  return resolveAuditEntityPath(
    normalizeAuditLog(row as FreightRecord),
    freightModules,
    collection => store.list(collection),
    permission => auth.canAccessPage(permission),
  )
}

const pageSummary = computed(() =>
  listTablePageSummary(t, result.value.total, pagination.value),
)

function rowMenuItems(row: Record<string, unknown>): DropdownMenuItem[][] {
  const items: DropdownMenuItem[] = [
    {
      label: t('freight.ui.open'),
      icon: 'i-lucide-eye',
      onSelect: () => openRow(row),
    },
  ]
  const collection = current.value?.collection
  if (collection === 'documentSequences') {
    items[0] = {
      label: t('docetra.rowActions.detail'),
      icon: 'i-lucide-eye',
      onSelect: () => openRow(row),
    }
    if (canMutate.value) {
      items.push({
        label: 'Edit',
        icon: 'i-lucide-pencil',
        onSelect: () => openRow(row),
      })
      const active = String(row.status || '').toUpperCase() === 'ACTIVE'
      items.push({
        label: t(active ? 'docetra.rowActions.deactivate' : 'docetra.rowActions.activate'),
        icon: active ? 'i-lucide-circle-off' : 'i-lucide-circle-check',
        color: active ? 'warning' : 'success',
        onSelect: () => setDocumentSequenceStatus(row, active ? 'INACTIVE' : 'ACTIVE'),
      })
    }
    return [items]
  }
  if (collection === 'quotations') {
    const status = quotationDomainStatus(row.status)
    if (status === 'DRAFT' && lcs.can('quotation.update_draft')) {
      items.push({ label: t('freight.ui.editDraft'), icon: 'i-lucide-pencil', onSelect: () => openRow(row) })
      items.push({ label: t('freight.ui.send'), icon: 'i-lucide-send', onSelect: () => { void runRowAction('send', row) } })
    }
    if (status === 'SENT' && lcs.can('quotation.create')) items.push({ label: t('freight.ui.createRevision'), icon: 'i-lucide-git-branch', onSelect: () => { void runRowAction('createRevision', row) } })
    if (status === 'SENT' && lcs.can('quotation.accept')) {
      items.push({ label: t('freight.ui.accept'), icon: 'i-lucide-check', onSelect: () => { void runRowAction('accept', row) } })
      items.push({ label: t('freight.ui.reject'), icon: 'i-lucide-x', color: 'error', onSelect: () => { void runRowAction('reject', row) } })
    }
    if (status === 'ACCEPTED' && lcs.can('quotation.convert')) items.push({ label: t('freight.ui.convertServiceOrder'), icon: 'i-lucide-arrow-right', onSelect: () => { void runRowAction('convert', row) } })
    const relatedJob = jobForQuotation(store.list('jobs'), row)
    if (relatedJob) items.push({ label: t('freight.ui.openServiceOrder'), icon: 'i-lucide-briefcase', onSelect: () => { void navigateTo(`/service-orders/${relatedJob.id}`) } })
    if (['DRAFT', 'SENT', 'ACCEPTED'].includes(status) && (lcs.can('quotation.update_draft') || lcs.can('quotation.accept'))) items.push({ label: t('freight.ui.cancel'), icon: 'i-lucide-ban', color: 'warning', onSelect: () => { void runRowAction('cancel', row) } })
  }
  else if (collection === 'jobs') {
    const status = jobDomainStatus(row)
    if (lcs.can('service_order.update') && !['COMPLETED', 'CLOSED', 'CANCELLED'].includes(status)) {
      if (status === 'DRAFT') {
        items.push({ label: t('freight.ui.openJob'), icon: 'i-lucide-folder-open', onSelect: () => { void applyJobWorkflow(row, 'OPEN', 'Opened') } })
      }
      if (status === 'OPEN') {
        items.push({ label: t('freight.ui.start'), icon: 'i-lucide-play', onSelect: () => { void applyJobWorkflow(row, 'IN_PROGRESS', 'Started') } })
      }
      if (status === 'IN_PROGRESS' && lcs.can('service_order.complete')) {
        items.push({ label: t('freight.ui.complete'), icon: 'i-lucide-check-circle-2', onSelect: () => { void applyJobWorkflow(row, 'COMPLETED', 'Completed') } })
      }
      items.push({ label: t('freight.ui.putOnHold'), icon: 'i-lucide-pause', onSelect: () => { void applyJobWorkflow(row, 'ON_HOLD', 'On Hold') } })
    }
    if (lcs.can('service_order.update') && status === 'ON_HOLD') {
      items.push({ label: t('freight.ui.resume'), icon: 'i-lucide-play', onSelect: () => { void applyJobWorkflow(row, 'IN_PROGRESS', 'Resumed') } })
    }
    if (lcs.can('service_charge.create') && ['IN_PROGRESS', 'COMPLETED'].includes(status)) {
      items.push({
        label: t('freight.ui.addPayment'),
        icon: 'i-lucide-receipt',
        onSelect: () => { void navigateTo({ path: `/service-orders/${row.id}`, query: { section: 'containers', new: '1' } }) },
      })
    }
    if (lcs.can('service_order.update') && status === 'COMPLETED') {
      items.push({ label: t('freight.ui.close'), icon: 'i-lucide-lock', onSelect: () => { void applyJobWorkflow(row, 'CLOSED', 'Closed') } })
    }
    if (lcs.can('service_order.update') && !['COMPLETED', 'CLOSED', 'CANCELLED'].includes(status)) {
      items.push({
        label: t('freight.ui.cancel'),
        icon: 'i-lucide-ban',
        color: 'warning',
        onSelect: () => { void applyJobWorkflow(row, 'CANCELLED', 'Cancelled') },
      })
    }
  }
  else if (collection === 'jobCharges') {
    const status = chargeDomainStatus(row.status)
    if (status === 'DRAFT' && lcs.can('service_charge.create')) items.push({ label: t('freight.ui.editDraft'), icon: 'i-lucide-pencil', onSelect: () => openRow(row) })
    if (status === 'DRAFT' && lcs.can('service_charge.issue')) items.push({ label: t('freight.ui.issue'), icon: 'i-lucide-send', onSelect: () => { void runRowAction('issueCharge', row) } })
    if (status === 'ISSUED' && !row.financialDocumentId && lcs.can('service_charge.convert_to_invoice')) items.push({ label: t('freight.ui.createFinanceInvoice'), icon: 'i-lucide-file-plus-2', onSelect: () => { void runRowAction('createInvoice', row) } })
  }
  else if (collection === 'debitNotes') {
    const status = financeDomainStatus(row.status)
    if (status === 'DRAFT' && lcs.can('financial_document.update_draft')) items.push({ label: t('freight.ui.editDraft'), icon: 'i-lucide-pencil', onSelect: () => openRow(row) })
    if (status === 'DRAFT' && lcs.can('financial_document.post')) items.push({ label: t('freight.ui.post'), icon: 'i-lucide-check-circle-2', onSelect: () => { void runRowAction('postDocument', row) } })
    if (status === 'POSTED' && lcs.can('financial_document.allocate')) items.push({ label: t('freight.ui.allocate'), icon: 'i-lucide-split', onSelect: () => openRow(row) })
    if (status === 'POSTED' && lcs.can('financial_document.reverse')) items.push({ label: t('freight.ui.reverse'), icon: 'i-lucide-undo-2', color: 'warning', onSelect: () => openRow(row) })
  }
  else if (collection === 'accountingPeriods' && lcs.can('accounting_period.close')) {
    const status = String(row.status || '').toUpperCase()
    if (status === 'OPEN' || status === 'REOPENED') items.push({ label: t('freight.ui.closePeriod'), icon: 'i-lucide-lock', color: 'warning', onSelect: () => { void runRowAction('closePeriod', row) } })
    if (status === 'CLOSED') items.push({ label: t('freight.ui.reopenPeriod'), icon: 'i-lucide-lock-open', onSelect: () => { void runRowAction('reopenPeriod', row) } })
  }
  if (canMutate.value && collection !== 'jobs') {
    items.push({
      label: deactivationOnly.value ? t('freight.ui.deactivate') : t('freight.ui.delete'),
      icon: deactivationOnly.value ? 'i-lucide-circle-off' : 'i-lucide-trash-2',
      color: deactivationOnly.value ? 'warning' : 'error',
      onSelect: () => { void (deactivationOnly.value ? deactivateIds([String(row.id)]) : deleteIds([String(row.id)])) },
    })
  }
  return [items]
}

async function applyJobWorkflow(row: Record<string, unknown>, next: ServiceOrderStatus, displayStatus: string) {
  const id = String(row.id || '')
  const saved = store.get('jobs', id) || row
  busyId.value = id
  try {
    store.save('jobs', {
      ...saved,
      id,
      status: displayStatus,
      workflowStatus: next,
      updatedAt: new Date().toISOString(),
    } as FreightRecord)
    store.addAudit(`${displayStatus} service order`, 'Service Orders', String(row.jobNo || id))
    toast.add({ title: t('freight.ui.actionCompleted'), color: 'success' })
  }
  finally {
    busyId.value = ''
  }
}

async function runRowAction(action: string, row: Record<string, unknown>) {
  try {
    const id = String(row.id || '')
    if (action === 'send') await lcs.runCommand('quotation.send', id, key => lcs.quotations.send(id, key))
    else if (action === 'accept') await lcs.runCommand('quotation.accept', id, key => lcs.quotations.accept(id, key))
    else if (action === 'createRevision') {
      const created = await lcs.quotations.createRevision(id)
      store.reload()
      await navigateTo(`/quotations/${created.id}`)
      return
    }
    else if (action === 'convert') {
      const job = await lcs.runCommand('quotation.convert', id, key => lcs.quotations.convert(id, key))
      await navigateTo(`/service-orders/${job.id}`)
      return
    }
    else if (action === 'reject' || action === 'cancel') {
      store.save('quotations', { ...row, id, status: action === 'reject' ? 'Rejected' : 'Cancelled' } as FreightRecord)
      store.addAudit(action === 'reject' ? 'Rejected quotation' : 'Cancelled quotation', 'Quotations', String(row.quotationNo || id))
    }
    else if (action === 'issueCharge') await lcs.runCommand('charge.issue', id, key => lcs.charges.issue(id, key))
    else if (action === 'createInvoice') {
      const invoice = await lcs.runCommand('charge.create-invoice', id, key => lcs.charges.createFinanceInvoice(id, key))
      await navigateTo(`/finance/documents/${invoice.id}`)
      return
    }
    else if (action === 'postDocument') await lcs.runCommand('finance.post', id, key => lcs.finance.post(id, key))
    else if (action === 'closePeriod') {
      const draftDocuments = store.list('debitNotes').filter(item => String(item.status).toUpperCase() === 'DRAFT' && String(item.date || '').slice(0, 10) >= String(row.startDate || '') && String(item.date || '').slice(0, 10) <= String(row.endDate || '')).length
      const unallocated = store.list('customerPayments').filter(item => Number(item.unallocatedAmount || 0) > 0).length
      const unbalanced = store.list('journals').filter(item => String(item.status).toUpperCase() === 'DRAFT' && Number(item.balanceDifference || 0) !== 0).length
      const ok = await confirm({ kind: 'generic', title: `Close ${String(row.name || row.code || 'accounting period')}?`, description: `${draftDocuments} unposted documents · ${unallocated} unallocated payments · ${unbalanced} journal issues. Closed periods reject new postings.`, confirmLabel: 'Close Period', confirmColor: 'warning' })
      if (!ok) return
      await lcs.runCommand('period.close', id, key => lcs.finance.closePeriod(id, key))
    }
    else if (action === 'reopenPeriod') {
      store.save('accountingPeriods', { ...row, id, status: 'REOPENED', closedBy: '', closedAt: '', updatedAt: new Date().toISOString() } as FreightRecord)
      store.addAudit('Reopened accounting period', 'Accounting Periods', String(row.code || id))
    }
    store.reload()
    toast.add({ title: t('freight.ui.actionCompleted'), color: 'success' })
  }
  catch (error) {
    lcs.reportError(error)
  }
}

const columns = computed<TableColumn<Record<string, unknown>>[]>(() => {
  if (!current.value) return []
  const titleKey = current.value.titleField
  const dataColumns = current.value.columns.map((column, index) => ({
    accessorKey: column.key,
    enableSorting: false,
    header: fieldLabel(column),
    meta: isNumericKey(column.key) || isMoneyKey(column.key) || column.key === 'tasksProgress' || column.key === 'containersCount'
      ? { class: { td: 'text-end tabular-nums whitespace-nowrap', th: 'text-end' } }
      : undefined,
    cell: ({ row }: { row: { original: Record<string, unknown> } }) => {
      const text = cellText(row.original, column.key)
      const isTitle = column.key === titleKey || (index === 0 && !current.value!.columns.some(item => item.key === titleKey))
      const jobTo = column.key === 'jobNo' && current.value!.collection !== 'jobs'
        ? jobLinkFor(row.original.jobNo)
        : ''
      const entityTo = column.key === 'entity' ? auditEntityLinkFor(row.original) : ''
      if (entityTo) {
        return h(ULink, {
          to: entityTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (jobTo) {
        return h(ULink, {
          to: jobTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (isTitle && !isTableOnly.value) {
        return h(ULink, {
          to: recordPath(row.original.id),
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (column.key === 'status' || column.key.toLowerCase().includes('status')) {
        return freightStatusBadge(
          row.original[column.key] || row.original.workflowStatus || row.original.status,
          column.key,
          text,
        )
      }
      if (column.key === 'direction' || column.key === 'stage') {
        return h(UBadge, { color: 'info', variant: 'subtle', size: 'sm' }, () => text)
      }
      if (column.key === 'customer') {
        return h('span', { class: 'block max-w-48 truncate text-default', title: text }, text)
      }
      return h('span', { class: 'text-sm text-default' }, text)
    },
  }))

  return [
    ...(!isTableOnly.value ? [listTableSelectColumn<Record<string, unknown>>(t)] : []),
    ...dataColumns,
    ...(!isTableOnly.value
      ? [listTableRowMetaColumn<Record<string, unknown>>({
          summary: pageSummary.value,
          items: rowMenuItems,
          loadingId: busyId.value,
        })]
      : []),
  ]
})

function openCreate() {
  if (!current.value) return
  navigateTo(`${current.value.path}/new`)
}

function openRow(row: Record<string, unknown>) {
  if (!current.value || !row.id) return
  navigateTo(recordPath(row.id))
}

function onRowSelect(event: Event, row: TableRow<Record<string, unknown>>) {
  if (isTableOnly.value) return
  const target = event.target as HTMLElement | null
  if (target?.closest('a, button, input, [role="checkbox"], [role="menuitem"], [data-slot="dropdown-menu"]')) return
  openRow(row.original)
}

async function deleteIds(ids: string[]) {
  if (!current.value || !canMutate.value || !ids.length) return
  const ok = await confirm({ kind: 'delete', count: ids.length })
  if (!ok) return
  store.remove(current.value.collection, ids)
  store.addAudit('Deleted', current.value.title, ids.join(', '))
  rowSelection.value = {}
  toast.add({ title: t('docetra.actions.deletedItems', { n: ids.length }), color: 'success' })
}

async function deactivateIds(ids: string[]) {
  if (!current.value || !canMutate.value || !ids.length) return
  for (const id of ids) {
    const record = store.get(current.value.collection, id)
    if (record) store.save(current.value.collection, { ...record, status: current.value.collection === 'documentSequences' ? 'INACTIVE' : 'Inactive' })
  }
  store.addAudit('Deactivated', current.value.title, ids.join(', '))
  rowSelection.value = {}
  toast.add({ title: t('freight.ui.deactivated'), color: 'success' })
}

function setDocumentSequenceStatus(row: Record<string, unknown>, status: 'ACTIVE' | 'INACTIVE') {
  if (!current.value || !canMutate.value) return
  store.save(current.value.collection, { ...row, id: String(row.id || ''), status } as FreightRecord)
  store.addAudit(status === 'ACTIVE' ? 'Activated' : 'Deactivated', current.value.title, String(row.documentType || row.id || ''))
  toast.add({ title: t(status === 'ACTIVE' ? 'docetra.common.activated' : 'docetra.common.deactivated'), color: 'success' })
}

function refresh() {
  store.reload()
}

function optionValue(option: FreightSelectOption) {
  return typeof option === 'string' ? option : option.value
}

function filterItems(filter: { options?: readonly FreightSelectOption[] | FreightSelectOption[], key: string }) {
  const fromOptions = (filter.options || []).map(optionValue)
  const sourceRows = current.value
    ? store.list(current.value.collection).map(row => current.value?.collection === 'auditLogs' ? normalizeAuditLog(row) : row)
    : []
  const fromData = [...new Set(sourceRows.map(row => String(row[filter.key] ?? '').trim()).filter(Boolean))]
  const fromBranches = filter.key === 'branchName'
    ? store.list('branches').map(row => String(row.name || ''))
    : []
  return [...new Set([...fromOptions, ...fromData, ...fromBranches])]
    .map(value => String(value).trim())
    .filter(Boolean)
    .map((value) => {
      const label = filter.key === 'documentType' && isDocumentSequenceType(value)
        ? documentSequenceTypeLabel(value)
        : filter.key === 'workflowStatus'
          ? value.replaceAll('_', ' ')
          : value
      return { label, value }
    })
}
</script>

<template>
  <div v-if="current" class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-create="canCreate"
      :create-label="t('freight.ui.newEntity', { entity: moduleSingular(current) })"
      :refreshing="pending"
      @create="openCreate"
      @refresh="refresh"
    />

    <TableAppListTable
      v-model:search="q"
      v-model:date-start="dateFrom"
      v-model:date-end="dateTo"
      v-model:row-selection="rowSelection"
      v-model:pagination="pagination"
      :data="result.all"
      :columns="columns"
      :loading="pending"
      :show-date-range="Boolean(dateField)"
      :filters-active="hasActiveFilters"
      :empty-actions="canCreate ? [{ icon: 'i-lucide-plus', label: t('freight.ui.newEntity', { entity: moduleSingular(current) }), onClick: openCreate }] : []"
      @select="onRowSelect"
    >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-for="filter in visibleFilters"
          :key="filter.key"
          :model-value="filters[filter.key] ?? []"
          :items="filterItems(filter)"
          :placeholder="fieldLabel(filter)"
          :class="compact ? 'w-full' : 'w-40'"
          @update:model-value="filters[filter.key] = parseFilterQuery($event)"
        />
      </template>
      <template #actions>
        <template v-if="selectedIds.length && canMutate && !isJobList">
          <UButton
            :color="deactivationOnly ? 'warning' : 'error'"
            variant="soft"
            size="sm"
            :icon="deactivationOnly ? 'i-lucide-circle-off' : 'i-lucide-trash-2'"
            class="shrink-0"
            :label="`${deactivationOnly ? t('freight.ui.deactivate') : t('freight.ui.delete')} (${selectedIds.length})`"
            @click="deactivationOnly ? deactivateIds(selectedIds) : deleteIds(selectedIds)"
          />
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            class="shrink-0"
            :label="t('freight.ui.clear')"
            @click="rowSelection = {}"
          />
        </template>
      </template>
    </TableAppListTable>
  </div>
  <div v-else class="grid h-full min-h-0 flex-1 place-items-center p-8">
    <UEmpty
      variant="naked"
      icon="i-lucide-unplug"
      :title="t('freight.ui.pageNotWired')"
      :description="t('freight.ui.pageNotWiredHint')"
    />
  </div>
</template>

<script setup lang="ts">
import type { DropdownMenuItem, TableColumn } from '@nuxt/ui'
import type { PaginationState } from '@tanstack/vue-table'
import { h } from 'vue'
import { ULink } from '#components'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { formatFreightCell, formatMoney, freightStatusBadge, labeledStatusOptions } from '~/composables/freight/useFreight'
import type { FreightRecord } from '~/types/freight/record'
import { CONTAINER_STATUSES, JOB_WORKFLOW_STATUS } from '~/config/freight-options'
import { downloadCsv } from '~/utils/export/csv'
import { buildStatementGroups, postedJournalLines, reportRowDate, statementDifference as statementDifferenceOf } from '~/utils/freight/report'
import { buildReportRows } from '~/utils/freight/report-queries'
import { isFilterValueActive } from '~/utils/filter/select-ui'
import { limitFilterSelects, matchesFilter } from '~/utils/filter/values'
import { listTableRowMetaColumn, listTableSelectColumn } from '~/utils/table/list-columns'
import { listTablePageSummary } from '~/utils/table/list-table'
import { getFreightReport, type FreightReportDefinition } from '~/config/freight-reports'

const store = useFreightStore()
const auth = useAuthStore()
const route = useRoute()
const { t, te } = useI18n()
const { setTitle, clear } = useAppHeader()
const slug = computed(() => String(route.params.slug || 'service-orders'))
const report = computed(() => getFreightReport(slug.value))

function reportLabel(definition: FreightReportDefinition) {
  return te(definition.titleKey) ? t(definition.titleKey) : definition.title
}

function columnLabel(column: FreightReportDefinition['columns'][number]) {
  return column.labelKey && te(column.labelKey) ? t(column.labelKey) : column.label
}

watchEffect(() => setTitle(reportLabel(report.value)))
onBeforeUnmount(clear)
usePageSeo({ title: () => reportLabel(report.value) })

const q = ref('')
const branch = ref<string[]>([])
const party = ref<string[]>([])
const status = ref<string[]>([])
const currency = ref<string[]>([])
const dateFrom = ref('')
const dateTo = ref('')
const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 20 })
const rowSelection = ref<Record<string, boolean>>({})
const postedLines = computed<FreightRecord[]>(() => postedJournalLines(store.list('journals'), store.list('chartOfAccounts')))
function jobByNo(value: unknown) { return store.list('jobs').find(row => String(row.jobNo) === String(value)) }
const rows = computed<FreightRecord[]>(() => buildReportRows(slug.value, store, t, te))
const filtered = computed(() => rows.value.filter((row) => {
  const text = Object.values(row).join(' ').toLowerCase()
  const day = reportRowDate(row)
  const rowParty = String(row.customer || row.supplier || row.party || '')
  return (!q.value || text.includes(q.value.toLowerCase()))
    && matchesFilter(row.branchName, branch.value)
    && matchesFilter(rowParty, party.value)
    && matchesFilter(row.status || row.workflowStatus, status.value)
    && matchesFilter(row.currency, currency.value)
    && (!dateFrom.value || day >= dateFrom.value)
    && (!dateTo.value || day <= dateTo.value)
}))
watch([q, branch, party, status, currency, dateFrom, dateTo, slug], () => {
  rowSelection.value = {}
  pagination.value = { ...pagination.value, pageIndex: 0 }
})
const choices = (getter:(r:FreightRecord)=>unknown) => computed(() => [...new Set(rows.value.map(r=>String(getter(r)||'')).filter(Boolean))].sort().map(value=>({label:value,value})))
const branchItems=choices(r=>r.branchName), partyItems=choices(r=>r.customer||r.supplier||r.party), currencyItems=choices(r=>r.currency)
const statusItems=computed(()=>{
  if (['service-orders','service-order-status'].includes(slug.value)) return labeledStatusOptions(JOB_WORKFLOW_STATUS, t, te)
  if (slug.value==='containers') return labeledStatusOptions(CONTAINER_STATUSES, t, te)
  return [...new Set(rows.value.map(r=>String(r.status||r.workflowStatus||'')).filter(Boolean))].sort().map(value=>({label:value,value}))
})
type ReportFilterKey = 'branch' | 'party' | 'status' | 'currency'
const filterSelects = computed<Array<{ key: ReportFilterKey, items: Array<{ label: string, value: string }>, placeholder: string, width: string }>>(() => {
  const selects: Array<{ key: ReportFilterKey, items: Array<{ label: string, value: string }>, placeholder: string, width: string }> = []
  if (report.value.filters.includes('branch')) selects.push({ key: 'branch', items: branchItems.value, placeholder: t('freight.ui.branchCol'), width: 'w-36' })
  if (report.value.filters.includes('party')) selects.push({ key: 'party', items: partyItems.value, placeholder: t('freight.fields.party'), width: 'w-44' })
  if (report.value.filters.includes('status')) selects.push({ key: 'status', items: statusItems.value, placeholder: t('freight.ui.status'), width: 'w-36' })
  if (report.value.filters.includes('currency')) selects.push({ key: 'currency', items: currencyItems.value, placeholder: t('freight.ui.cols.currency'), width: 'w-28' })
  return limitFilterSelects(selects, report.value.filters.includes('date'), select => select.key === 'status')
})
const filterValues = computed<Record<ReportFilterKey, string[]>>(() => ({
  branch: branch.value,
  party: party.value,
  status: status.value,
  currency: currency.value,
}))

function setFilterValue(key: ReportFilterKey, value: string[] | string | undefined) {
  const next = Array.isArray(value) ? value : value ? [value] : []
  if (key === 'branch') branch.value = next
  else if (key === 'party') party.value = next
  else if (key === 'status') status.value = next
  else currency.value = next
}

const statementGroups=computed(()=>buildStatementGroups(postedLines.value, slug.value==='profit-loss'?['Revenue','Expense']:['Asset','Liability','Equity']))
const statementDifference=computed(()=>statementDifferenceOf(statementGroups.value, slug.value==='balance-sheet'))
function actions(row: FreightRecord): DropdownMenuItem[][] {
  const job = jobByNo(row.jobNo)
  if (!job) return []
  const items: DropdownMenuItem[] = []
  if (auth.canAccessPage('operations.service_orders.view')) {
    items.push({
      label: t('freight.ui.open'),
      icon: 'i-lucide-eye',
      onSelect: () => navigateTo(`/service-orders/${job.id}`),
    })
  }
  if (auth.canAccessPage('finance.service_charges.view')) {
    items.push({
      label: t('freight.jobSections.charges'),
      icon: 'i-lucide-receipt-text',
      onSelect: () => navigateTo(`/service-charges?jobNo=${encodeURIComponent(String(row.jobNo))}`),
    })
  }
  if (auth.canAccessPage('finance.financial_documents.view')) {
    items.push({
      label: t('freight.jobSections.finance'),
      icon: 'i-lucide-banknote',
      onSelect: () => navigateTo(`/finance/documents?jobNo=${encodeURIComponent(String(row.jobNo))}`),
    })
  }
  return items.length ? [items] : []
}
const columns=computed<TableColumn<FreightRecord>[]>(()=>{
  const list=report.value.columns.map(column=>{
    const label = columnLabel(column)
    return {accessorKey:column.key,header:column.numeric?()=>h('span',{class:'block text-right'},label):label,enableSorting:false,meta:column.numeric?{class:{th:'text-right',td:'text-right tabular-nums whitespace-nowrap'}}:undefined,cell:({row}:{row:{original:FreightRecord}})=>{if(column.status)return freightStatusBadge(row.original[column.key],column.key);if(column.key==='jobNo'&&report.value.group==='operations'){const job=jobByNo(row.original.jobNo);if(job)return h(ULink,{to:`/service-orders/${job.id}`,class:'font-medium text-highlighted hover:text-primary hover:underline'},()=>String(row.original.jobNo||'—'))}return formatFreightCell(row.original[column.key],column.key)}}
  })
  return [
    listTableSelectColumn<FreightRecord>(t),
    ...list,
    listTableRowMetaColumn<FreightRecord>({
      summary: listTablePageSummary(t, filtered.value.length, pagination.value),
      items: actions,
    }),
  ]
})
const hasActiveFilters = computed(() => Boolean(
  q.value
  || isFilterValueActive(branch.value)
  || isFilterValueActive(party.value)
  || isFilterValueActive(status.value)
  || isFilterValueActive(currency.value)
  || dateFrom.value
  || dateTo.value,
))
function clearFilters() {
  q.value = ''
  branch.value = []
  party.value = []
  status.value = []
  currency.value = []
  dateFrom.value = ''
  dateTo.value = ''
}
const exportFields=computed(()=>report.value.statement?[{label:'Section',value:'section'},{label:'Account',value:'account'},{label:'Amount',value:'amount'}]:report.value.columns.map(column=>({label:columnLabel(column),value:column.key})))
function exportCsv(request:{fieldCodes:string[]}){const statementRows=statementGroups.value.flatMap(group=>group.rows.map(row=>({section:group.type,account:row.name,amount:row.amount}))),source=(report.value.statement?statementRows:filtered.value) as Array<Record<string,unknown>>,codes=request.fieldCodes.length?request.fieldCodes:exportFields.value.map(field=>field.value);downloadCsv({filename:`${report.value.slug}-${new Date().toISOString().slice(0,10)}.csv`,fields:codes.map(key=>({label:exportFields.value.find(field=>field.value===key)?.label||key,value:key})),rows:source})}
</script>

<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-create="false"
      :export-fields="exportFields"
      @refresh="store.reload()"
      @export="exportCsv"
    />
    <template v-if="!report.statement">
      <TableAppListTable
        v-model:search="q"
        v-model:date-start="dateFrom"
        v-model:date-end="dateTo"
        v-model:row-selection="rowSelection"
        v-model:pagination="pagination"
        :data="filtered"
        :columns="columns"
        :show-date-range="report.filters.includes('date')"
        :filters-active="hasActiveFilters"
      >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-for="select in filterSelects"
          :key="select.key"
          :model-value="filterValues[select.key]"
          :items="select.items"
          :placeholder="select.placeholder"
          :class="compact ? 'w-full' : select.width"
          @update:model-value="setFilterValue(select.key, $event)"
        />
      </template>
        <template #actions>
          <UButton
            v-if="hasActiveFilters"
            :label="t('freight.ui.clear')"
            color="neutral"
            variant="ghost"
            size="sm"
            @click="clearFilters"
          />
        </template>
      </TableAppListTable>
    </template>
    <template v-else>
      <div class="flex min-h-0 flex-1 flex-col overflow-hidden px-1.5 pt-1.5 pb-0">
        <div class="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden rounded-sm border border-default bg-default shadow-xs">
          <div class="flex items-center gap-3 border-b border-default px-2 py-2">
            <CommonAppLiveSearch v-model="q" class="w-40 shrink-0 sm:w-56 lg:w-64" :placeholder="t('freight.ui.search')" />
            <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
              <CommonAppFilterMenu :active="hasActiveFilters">
                <template #default="{ compact }">
                  <CommonAppFilterSelect
                    v-if="report.filters.includes('branch')"
                    v-model="branch"
                    :items="branchItems"
                    :placeholder="t('freight.ui.branchCol')"
                    class="w-36"
                  />
                  <CommonAppFilterSelect
                    v-if="report.filters.includes('currency')"
                    v-model="currency"
                    :items="currencyItems"
                    :placeholder="t('freight.ui.cols.currency')"
                    class="w-28"
                  />
                  <CommonAppDateRangeFilter
                    v-if="report.filters.includes('date')"
                    v-model:start="dateFrom"
                    v-model:end="dateTo"
                    granularity="day"
                    :inline="compact"
                    :label="t('freight.ui.date')"
                  />
                </template>
              </CommonAppFilterMenu>
              <UButton
                v-if="hasActiveFilters"
                :label="t('freight.ui.clear')"
                color="neutral"
                variant="ghost"
                size="sm"
                class="shrink-0"
                @click="clearFilters"
              />
            </div>
          </div>
          <section class="min-h-0 flex-1 overflow-auto p-5">
            <div class="mx-auto max-w-3xl space-y-5">
              <div v-for="group in statementGroups" :key="group.type">
                <h2 class="border-b border-default pb-1.5 text-sm font-semibold">{{ group.type }}</h2>
                <div v-for="row in group.rows" :key="row.name" class="flex justify-between px-3 py-1.5 text-sm">
                  <span>{{ row.name }}</span>
                  <span class="tabular-nums">{{ formatMoney(row.amount) }}</span>
                </div>
                <div class="flex justify-between border-t border-default px-3 pt-2 text-sm font-semibold">
                  <span>Total {{ group.type }}</span>
                  <span>{{ formatMoney(group.total) }}</span>
                </div>
              </div>
              <div class="flex justify-between border-t-2 border-default px-3 pt-3 font-semibold">
                <span>{{ report.slug === 'profit-loss' ? 'Net Profit' : 'Difference' }}</span>
                <span>{{ formatMoney(statementDifference) }}</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </template>
  </div>
</template>


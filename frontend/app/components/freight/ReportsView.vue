<script setup lang="ts">
import type { DropdownMenuItem, TableColumn } from '@nuxt/ui'
import type { PaginationState } from '@tanstack/vue-table'
import { h } from 'vue'
import { ULink } from '#components'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { formatFreightCell, formatMoney, freightStatusBadge, labeledStatusOptions } from '~/composables/freight/useFreight'
import { formatNumber } from '~/utils/format/format-service'
import type { FreightRecord } from '~/types/record'
import { ACTIVE_STATUS, CONTAINER_STATUSES } from '~/config/freight-options'
import { downloadCsv, downloadBlob } from '~/utils/export/csv'
import { buildStatementGroups, reportRowDate, statementDifference as statementDifferenceOf } from '~/utils/freight/report'
import { buildReportRows, buildRevenueExpenseReportRows } from '~/utils/freight/report-queries'
import { isFilterValueActive } from '~/utils/filter/select-ui'
import { limitFilterSelects, matchesFilter } from '~/utils/filter/values'
import { listTableRowMetaColumn, listTableSelectColumn } from '~/utils/table/list-columns'
import { listTablePageSummary } from '~/utils/table/list-table'
import { type ListSortKind, type ListSortSelection, listSortKindFor } from '~/utils/table/list-sort'
import { getFreightReport, type FreightReportDefinition } from '~/config/freight-reports'
import { isGeneratedReport, reportExportBody, reportGenerateBody, type ReportFilterValues } from '~/utils/freight/report-request'
import { useLcsRepositories } from '~/repositories'

const store = useFreightStore()
const { reports } = useLcsRepositories()
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
const party = ref<string[]>([])
const status = ref<string[]>([])
const currency = ref<string[]>([])
const dateFrom = ref('')
const dateTo = ref('')
const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 20 })
const sort = ref<ListSortSelection>(null)
const rowSelection = ref<Record<string, boolean>>({})
function jobByNo(value: unknown) { return store.list('jobs').find(row => String(row.jobNo) === String(value)) }

const ledgerSlugs = ['revenue-expense', 'general-ledger', 'trial-balance', 'profit-loss', 'balance-sheet', 'cash-flow']
const backendSlugs = ['accounts-receivable', 'accounts-payable', 'profitability', ...ledgerSlugs]
const useBackend = computed(() => backendSlugs.includes(slug.value))
/** Statement reports are not tabular; they still wait for Generate. */
const isStatement = computed(() => Boolean(report.value.statement))
const serverPaged = computed(() => isGeneratedReport(slug.value))

// --- Generate-on-demand state ---------------------------------------------
// Nothing is requested until the user presses Generate: opening a report page
// must never pull the ledger.
const generating = ref(false)
const generated = ref(false)
const stale = ref(false)
const generateError = ref('')
const generatedAt = ref('')
const reportWarnings = ref<string[]>([])
const reportTotal = ref(0)
const trialBalanceTotals = ref<Record<string, number> | null>(null)
const trialBalanceBalanced = ref(true)
const backendRows = ref<FreightRecord[]>([])
const backendLedgerLines = ref<FreightRecord[]>([])

type ExtraReportFilters = Omit<ReportFilterValues, 'dateFrom' | 'dateTo'>
const EMPTY_EXTRA_FILTERS: ExtraReportFilters = {
  fiscalYear: '',
  accountFrom: '',
  accountTo: '',
  accountCode: '',
  party: '',
  voucherType: '',
  voucherNo: '',
  currency: '',
}
const extraFilters = reactive<ExtraReportFilters>({ ...EMPTY_EXTRA_FILTERS })
const filters = computed<ReportFilterValues>(() => ({
  dateFrom: dateFrom.value,
  dateTo: dateTo.value,
  ...extraFilters,
}))

/**
 * Filters survive leaving the page and coming back, so a user comparing two
 * reports does not retype the period. Results never do: a stale page must be
 * generated again rather than shown as current.
 */
const FILTER_MEMORY = new Map<string, ReportFilterValues>()
watch([slug, filters], () => {
  FILTER_MEMORY.set(slug.value, { ...filters.value })
}, { deep: true, immediate: true })

function applyFilters(values: ReportFilterValues | undefined) {
  const next = values || { dateFrom: '', dateTo: '', ...EMPTY_EXTRA_FILTERS }
  dateFrom.value = next.dateFrom
  dateTo.value = next.dateTo
  Object.assign(extraFilters, {
    fiscalYear: next.fiscalYear,
    accountFrom: next.accountFrom,
    accountTo: next.accountTo,
    accountCode: next.accountCode,
    party: next.party,
    voucherType: next.voucherType,
    voucherNo: next.voucherNo,
    currency: next.currency,
  })
}

/** The previous report's rows and metadata must not survive a slug change. */
function resetResults() {
  generated.value = false
  stale.value = false
  generateError.value = ''
  generatedAt.value = ''
  reportWarnings.value = []
  reportTotal.value = 0
  trialBalanceTotals.value = null
  trialBalanceBalanced.value = true
  backendRows.value = []
  backendLedgerLines.value = []
}

watch(slug, (next) => {
  resetResults()
  applyFilters(FILTER_MEMORY.get(next))
}, { immediate: true })

function errorMessage(error: unknown) {
  const payload = (error as { data?: { message?: string }, message?: string })
  return payload.data?.message || payload.message || t('freight.reportCatalog.generateFailed')
}

async function loadBackendReport() {
  let data: FreightRecord[] = []
  backendLedgerLines.value = []
  if (slug.value === 'accounts-receivable') data = await reports.receivables()
  else if (slug.value === 'accounts-payable') data = await reports.payables()
  else if (slug.value === 'profitability') data = await reports.profitability()
  else {
    const lines = await reports.ledgerLines()
    backendLedgerLines.value = lines
    if (slug.value === 'revenue-expense') data = buildRevenueExpenseReportRows(lines)
    else if (slug.value === 'cash-flow') {
      let balance = 0
      data = lines.filter(row => Boolean(row.isCashAccount)).map((row) => {
        const cashIn = Number(row.debit || 0)
        const cashOut = Number(row.credit || 0)
        balance += cashIn - cashOut
        return { ...row, cashIn, cashOut, runningBalance: balance }
      })
    }
    else data = lines
  }
  backendRows.value = data
}

async function generateReport() {
  // Repeated clicks must not queue repeated report runs.
  if (generating.value) return
  generating.value = true
  generateError.value = ''
  try {
    if (serverPaged.value) {
      const body = reportGenerateBody(
        slug.value,
        filters.value,
        pagination.value.pageIndex + 1,
        pagination.value.pageSize,
      ) || {}
      if (slug.value === 'trial-balance') {
        const result = await reports.generateTrialBalance(body)
        backendRows.value = result.items
        trialBalanceTotals.value = result.totals
        trialBalanceBalanced.value = result.balanced
        reportWarnings.value = result.meta.warnings
        reportTotal.value = result.meta.total
        generatedAt.value = result.meta.generatedAt
      }
      else {
        const result = await reports.generateGeneralLedger(body)
        backendRows.value = result.items
        trialBalanceTotals.value = null
        reportWarnings.value = result.meta.warnings
        reportTotal.value = result.meta.total
        generatedAt.value = result.meta.generatedAt
      }
    }
    else if (useBackend.value) {
      await loadBackendReport()
      reportTotal.value = backendRows.value.length
      generatedAt.value = new Date().toISOString()
      reportWarnings.value = []
    }
    else {
      // Operational reports are derived from the store, whose fetch this call
      // triggers; rows appear when the store revision bumps.
      reportTotal.value = 0
      generatedAt.value = new Date().toISOString()
      reportWarnings.value = []
    }
    generated.value = true
    stale.value = false
  }
  catch (error) {
    // Keep the previous result visible but never present it as current.
    generateError.value = errorMessage(error)
    stale.value = generated.value
  }
  finally {
    generating.value = false
  }
}

async function refreshReport() {
  if (!useBackend.value) store.reload()
  await generateReport()
}

const rows = computed<FreightRecord[]>(() => {
  if (!generated.value) return []
  if (useBackend.value) return backendRows.value
  return buildReportRows(slug.value, store)
})
const filtered = computed(() => {
  // A generated report was already filtered and paged by the backend; applying
  // the toolbar filters again would drop rows the server counted. Search only
  // narrows the page that is on screen.
  if (serverPaged.value) {
    const needle = q.value.trim().toLowerCase()
    if (!needle) return backendRows.value
    return backendRows.value.filter(row => Object.values(row).join(' ').toLowerCase().includes(needle))
  }
  if (!generated.value) return []
  return rows.value.filter((row) => {
    const text = Object.values(row).join(' ').toLowerCase()
    const day = reportRowDate(row)
    const rowParty = String(row.customer || row.supplier || row.party || '')
    return (!q.value || text.includes(q.value.toLowerCase()))
      && matchesFilter(rowParty, party.value)
      && matchesFilter(row.status || row.workflowStatus, status.value)
      && matchesFilter(row.currency, currency.value)
      && (!dateFrom.value || day >= dateFrom.value)
      && (!dateTo.value || day <= dateTo.value)
  })
})
watch([q, party, status, currency, dateFrom, dateTo, extraFilters, slug, sort], () => {
  rowSelection.value = {}
  pagination.value = { ...pagination.value, pageIndex: 0 }
  if (generated.value) stale.value = true
}, { deep: true })
// Server pagination is a request, not a client slice: fetch the page the user
// actually asked for. It never fires for a report that has not been generated.
watch(() => [pagination.value.pageIndex, pagination.value.pageSize], () => {
  if (!serverPaged.value || !generated.value || stale.value) return
  void generateReport()
})
const choices = (getter:(r:FreightRecord)=>unknown) => computed(() => [...new Set(rows.value.map(r=>String(getter(r)||'')).filter(Boolean))].sort().map(value=>({label:value,value})))
const partyItems=choices(r=>r.customer||r.supplier||r.party), currencyItems=choices(r=>r.currency)
const statusItems=computed(()=>{
  if (['service-orders','service-order-status'].includes(slug.value)) return labeledStatusOptions(ACTIVE_STATUS, t, te)
  if (slug.value==='containers') return labeledStatusOptions(CONTAINER_STATUSES, t, te)
  return [...new Set(rows.value.map(r=>String(r.status||r.workflowStatus||'')).filter(Boolean))].sort().map(value=>({label:value,value}))
})
type ReportFilterKey = 'party' | 'status' | 'currency'
const filterSelects = computed<Array<{ key: ReportFilterKey, items: Array<{ label: string, value: string }>, placeholder: string, width: string }>>(() => {
  // Generated ledger reports take their filters as text/number inputs, because
  // the choices depend on data the page has not loaded yet.
  if (serverPaged.value) return []
  const selects: Array<{ key: ReportFilterKey, items: Array<{ label: string, value: string }>, placeholder: string, width: string }> = []
  if (report.value.filters.includes('party')) selects.push({ key: 'party', items: partyItems.value, placeholder: t('freight.fields.party'), width: 'w-44' })
  if (report.value.filters.includes('status')) selects.push({ key: 'status', items: statusItems.value, placeholder: t('freight.ui.status'), width: 'w-36' })
  if (report.value.filters.includes('currency')) selects.push({ key: 'currency', items: currencyItems.value, placeholder: t('freight.ui.cols.currency'), width: 'w-28' })
  return limitFilterSelects(selects, report.value.filters.includes('date'), select => select.key === 'status')
})
const filterValues = computed<Record<ReportFilterKey, string[]>>(() => ({
  party: party.value,
  status: status.value,
  currency: currency.value,
}))

function setFilterValue(key: ReportFilterKey, value: string[] | string | undefined) {
  const next = Array.isArray(value) ? value : value ? [value] : []
  if (key === 'party') party.value = next
  else if (key === 'status') status.value = next
  else currency.value = next
}

const statementTypes=computed(()=>report.value.statementTypes||(slug.value==='profit-loss'?['Revenue','Expense']:['Asset','Liability','Equity']))
const statementLines = computed(() => backendLedgerLines.value)
const filteredPostedLines=computed(()=>statementLines.value.filter((row)=>{
  const day=reportRowDate(row)
  return matchesFilter(row.currency,currency.value)
    && (!dateFrom.value||day>=dateFrom.value)
    && (!dateTo.value||day<=dateTo.value)
}))
const statementGroups=computed(()=>buildStatementGroups(filteredPostedLines.value, statementTypes.value))
const statementDifference=computed(()=>statementDifferenceOf(statementGroups.value, slug.value==='balance-sheet'))
const statementFooterLabel=computed(()=>{const key=report.value.statementFooterKey;return key&&te(key)?t(key):(slug.value==='profit-loss'?'Net Profit':'Difference')})
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
    const kind: ListSortKind = column.numeric ? 'number' : listSortKindFor(column.key)
    return {accessorKey:column.key,header:column.numeric?()=>h('span',{class:'block text-right'},label):label,enableSorting:true,meta:{sortKind:kind,...(column.numeric?{class:{th:'text-right',td:'text-right tabular-nums whitespace-nowrap'}}:{})},cell:({row}:{row:{original:FreightRecord}})=>{
      if(column.status)return freightStatusBadge(row.original[column.key],column.key)
      if(column.key==='jobNo'&&report.value.group==='operations'){const job=jobByNo(row.original.jobNo);if(job)return h(ULink,{to:`/service-orders/${job.id}`,class:'font-medium text-highlighted hover:text-primary hover:underline'},()=>String(row.original.jobNo||'—'))}
      if(column.key==='quotationNo'){
        const quotationId=String(row.original.quotationId||'').trim()
        const text=String(row.original.quotationNo||'').trim()||'—'
        if(quotationId&&auth.canAccessPage('sales.quotations.view'))return h(ULink,{to:`/quotations/${quotationId}`,class:'font-medium text-highlighted hover:text-primary hover:underline'},()=>text)
        return h('span',{class:'text-default'},text)
      }
      const linkTargets:Record<string,{id:unknown,permission:string,prefix:string}> = {
        invoiceNo:{id:row.original.id,permission:'finance.financial_documents.view',prefix:'/finance/documents/'},
        journalNo:{id:row.original.journalId,permission:'finance.journal_entries.view',prefix:'/finance/journals/'},
        sourceDocument:{id:row.original.sourceDocumentId,permission:'finance.financial_documents.view',prefix:'/finance/documents/'},
        accountCode:{id:row.original.accountId,permission:'finance.chart_of_accounts.view',prefix:'/finance/chart-of-accounts/'},
      }
      const target=linkTargets[column.key]
      if(target){
        const id=String(target.id||'').trim()
        const text=String(row.original[column.key]||'').trim()||'—'
        if(id&&auth.canAccessPage(target.permission))return h(ULink,{to:`${target.prefix}${id}`,class:'font-medium text-highlighted hover:text-primary hover:underline'},()=>text)
        return h('span',{class:'text-default'},text)
      }
      if(column.integer)return formatNumber(row.original[column.key],{maximumFractionDigits:0,minimumFractionDigits:0})
      return formatFreightCell(row.original[column.key],column.key,String(row.original.currency||'').trim()||undefined)
    }}
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
  || isFilterValueActive(party.value)
  || isFilterValueActive(status.value)
  || isFilterValueActive(currency.value)
  || dateFrom.value
  || dateTo.value
  || Object.values(extraFilters).some(value => String(value || '').trim() !== ''),
))
function clearFilters() {
  q.value = ''
  party.value = []
  status.value = []
  currency.value = []
  dateFrom.value = ''
  dateTo.value = ''
  Object.assign(extraFilters, EMPTY_EXTRA_FILTERS)
}
const emptyTitle = computed(() => {
  if (generating.value) return t('freight.reportCatalog.generating')
  return generated.value ? t('freight.reportCatalog.emptyResultTitle') : t('freight.reportCatalog.emptyTitle')
})
const emptyDescription = computed(() => generated.value
  ? t('freight.reportCatalog.emptyResultDescription')
  : t('freight.reportCatalog.emptyDescription'))
const emptyActions = computed(() => (generated.value
  ? []
  : [{
      icon: 'i-lucide-play',
      label: t('freight.reportCatalog.generate'),
      onClick: () => { void generateReport() },
    }]))
const generatedAtLabel = computed(() => generatedAt.value
  ? t('freight.reportCatalog.generatedAt', { at: new Date(generatedAt.value).toLocaleString() })
  : '')
const exportFields=computed(()=>report.value.statement?[{label:'Section',value:'section'},{label:'Account',value:'account'},{label:'Amount',value:'amount'}]:report.value.columns.map(column=>({label:columnLabel(column),value:column.key})))
/**
 * Trial Balance and General Ledger export the whole filtered result from the
 * backend (the table only holds one page). Every other report still exports the
 * rows already loaded, because its endpoint is not paginated.
 */
async function exportCsv(request:{fieldCodes:string[]}){
  if (isGeneratedReport(slug.value)) {
    const body = reportExportBody(slug.value, filters.value, request.fieldCodes)
    if (!body) return
    const blob = slug.value === 'trial-balance'
      ? await reports.exportTrialBalance(body)
      : await reports.exportGeneralLedger(body)
    downloadBlob(blob, `${report.value.slug}-${new Date().toISOString().slice(0,10)}.csv`)
    return
  }
  const statementRows=statementGroups.value.flatMap(group=>group.rows.map(row=>({section:group.type,account:row.name,amount:row.amount}))),source=(report.value.statement?statementRows:filtered.value) as Array<Record<string,unknown>>,codes=request.fieldCodes.length?request.fieldCodes:exportFields.value.map(field=>field.value);downloadCsv({filename:`${report.value.slug}-${new Date().toISOString().slice(0,10)}.csv`,fields:codes.map(key=>({label:exportFields.value.find(field=>field.value===key)?.label||key,value:key})),rows:source})}
</script>

<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-create="false"
      :refreshing="generating"
      :export-fields="exportFields"
      @refresh="refreshReport"
      @export="exportCsv"
    >
      <UButton
        :label="t('freight.reportCatalog.generate')"
        icon="i-lucide-play"
        size="sm"
        :loading="generating"
        :disabled="generating"
        @click="generateReport"
      />
    </LayoutAppHeaderPageActions>

    <div v-if="generateError || reportWarnings.length || stale || trialBalanceTotals" class="space-y-1.5 px-1.5 pt-1.5">
      <UAlert
        v-if="generateError"
        color="error"
        :title="t('freight.reportCatalog.generateFailedTitle')"
        :description="generateError"
      />
      <UAlert
        v-for="warning in reportWarnings"
        :key="warning"
        color="warning"
        :description="warning"
      />
      <UAlert v-if="stale" color="neutral" :description="t('freight.reportCatalog.stale')" />
      <div
        v-if="trialBalanceTotals"
        class="flex flex-wrap items-center gap-x-5 gap-y-1 rounded-sm border border-default bg-default px-3 py-2 text-xs shadow-xs"
      >
        <span class="font-semibold">{{ t('freight.reportCatalog.totals') }}</span>
        <span>{{ t('freight.reportCatalog.periodDebit') }}: <b class="tabular-nums">{{ formatMoney(trialBalanceTotals.periodDebit) }}</b></span>
        <span>{{ t('freight.reportCatalog.periodCredit') }}: <b class="tabular-nums">{{ formatMoney(trialBalanceTotals.periodCredit) }}</b></span>
        <span>{{ t('freight.reportCatalog.closingDebit') }}: <b class="tabular-nums">{{ formatMoney(trialBalanceTotals.closingDebit) }}</b></span>
        <span>{{ t('freight.reportCatalog.closingCredit') }}: <b class="tabular-nums">{{ formatMoney(trialBalanceTotals.closingCredit) }}</b></span>
        <UBadge
          v-if="!trialBalanceBalanced"
          color="error"
          variant="subtle"
          :label="t('freight.reportCatalog.unbalanced')"
        />
        <span v-if="generatedAtLabel" class="ms-auto text-muted">{{ generatedAtLabel }}</span>
      </div>
    </div>

    <template v-if="!isStatement">
      <TableAppListTable
        v-model:search="q"
        v-model:date-start="dateFrom"
        v-model:date-end="dateTo"
        v-model:row-selection="rowSelection"
        v-model:pagination="pagination"
        v-model:sort="sort"
        :data="filtered"
        :columns="columns"
        :loading="generating"
        :show-date-range="report.filters.includes('date')"
        :filters-active="hasActiveFilters"
        :server-side="serverPaged"
        :server-total="reportTotal"
        :empty-title="emptyTitle"
        :empty-description="emptyDescription"
        :empty-actions="emptyActions"
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
        <template v-if="slug === 'trial-balance'">
          <UInput
            v-model="extraFilters.accountFrom"
            :placeholder="t('freight.reportCatalog.accountFrom')"
            size="sm"
            class="w-32"
          />
          <UInput
            v-model="extraFilters.accountTo"
            :placeholder="t('freight.reportCatalog.accountTo')"
            size="sm"
            class="w-32"
          />
          <UInput
            v-model="extraFilters.fiscalYear"
            type="number"
            :placeholder="t('freight.reportCatalog.fiscalYear')"
            size="sm"
            class="w-28"
          />
        </template>
        <template v-else-if="slug === 'general-ledger'">
          <UInput
            v-model="extraFilters.accountCode"
            :placeholder="t('freight.reportCatalog.accountCode')"
            size="sm"
            class="w-32"
          />
          <UInput
            v-model="extraFilters.party"
            :placeholder="t('freight.fields.party')"
            size="sm"
            class="w-40"
          />
          <UInput
            v-model="extraFilters.voucherType"
            :placeholder="t('freight.reportCatalog.columns.voucherType')"
            size="sm"
            class="w-36"
          />
          <UInput
            v-model="extraFilters.voucherNo"
            :placeholder="t('freight.reportCatalog.columns.voucherNo')"
            size="sm"
            class="w-32"
          />
        </template>
      </template>
        <template #actions>
          <UButton
            v-if="hasActiveFilters"
            :label="t('freight.reportCatalog.resetFilters')"
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
                :label="t('freight.reportCatalog.resetFilters')"
                color="neutral"
                variant="ghost"
                size="sm"
                class="shrink-0"
                @click="clearFilters"
              />
            </div>
          </div>
          <section v-if="!generated" class="flex min-h-0 flex-1 items-center justify-center p-5">
            <UEmpty
              variant="naked"
              icon="i-lucide-file-text"
              :title="emptyTitle"
              :description="emptyDescription"
              :actions="emptyActions"
              class="py-16"
            />
          </section>
          <section v-else-if="!statementGroups.length" class="flex min-h-0 flex-1 items-center justify-center p-5">
            <UEmpty
              variant="naked"
              icon="i-lucide-inbox"
              :title="emptyTitle"
              :description="emptyDescription"
              class="py-16"
            />
          </section>
          <section v-else class="min-h-0 flex-1 overflow-auto p-5">
            <div class="mx-auto max-w-3xl space-y-5">
              <div v-for="group in statementGroups" :key="group.type">
                <h2 class="border-b border-default pb-1.5 text-sm font-semibold">{{ group.type }}</h2>
                <div v-for="row in group.rows" :key="row.name" class="flex justify-between px-3 py-1.5 text-sm">
                  <span>{{ row.name }}</span>
                  <span class="tabular-nums">{{ formatMoney(row.amount, currency.length === 1 ? currency[0] : undefined) }}</span>
                </div>
                <div class="flex justify-between border-t border-default px-3 pt-2 text-sm font-semibold">
                  <span>Total {{ group.type }}</span>
                  <span>{{ formatMoney(group.total, currency.length === 1 ? currency[0] : undefined) }}</span>
                </div>
              </div>
              <div class="flex justify-between border-t-2 border-default px-3 pt-3 font-semibold">
                <span>{{ statementFooterLabel }}</span>
                <span>{{ formatMoney(statementDifference, currency.length === 1 ? currency[0] : undefined) }}</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsCoreOption } from 'echarts/core'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import {
  bucketDashboardRevenueExpense,
  dashboardChartYearRange,
  type DashboardChartPeriodFilter,
  type DashboardChartYearFilter,
  type DashboardSummary,
} from '~/utils/lcs/dashboard'
import { freightReportPath, getFreightReport } from '~/config/freight-reports'

/**
 * Compact ERP dashboard: KPI summary cards + line chart + bar chart.
 * No page-level filter bar — org/branch scope comes from the signed-in session.
 * Each chart has its own year/period filters and download menu.
 * Accounting figures are POSTED documents and journals only.
 */

const store = useFreightStore()
const tenant = useTenantStore()
const auth = useAuthStore()
const { t } = useI18n()
const { formatMoney, formatCompact, formatDatePart } = useAppLocalization()
const { setTitle, clear } = useAppHeader()

setTitle(t('freight.pages.dashboard'))
watch(() => t('freight.pages.dashboard'), title => setTitle(title))
onBeforeUnmount(clear)
usePageSeo({ title: () => t('freight.pages.dashboard') })

const pending = ref(true)
const error = ref('')
const summary = ref<DashboardSummary | null>(null)
const revenueSummary = ref<DashboardSummary | null>(null)
const ordersSummary = ref<DashboardSummary | null>(null)

const revenueYear = ref<DashboardChartYearFilter>('thisYear')
const revenuePeriod = ref<DashboardChartPeriodFilter>('monthly')
const ordersYear = ref<DashboardChartYearFilter>('thisYear')
const ordersPeriod = ref<DashboardChartPeriodFilter>('monthly')

function loadChart(year: DashboardChartYearFilter) {
  const { dateFrom, dateTo } = dashboardChartYearRange(year)
  return store.dashboardSummary({ dateFrom, dateTo })
}

const canSeeServiceOrders = computed(() => auth.canAccessPage('operations.service_orders.view'))

async function load() {
  pending.value = true
  error.value = ''
  await nextTick()
  try {
    summary.value = store.dashboardSummary()
    revenueSummary.value = loadChart(revenueYear.value)
    if (canSeeServiceOrders.value) {
      ordersSummary.value = loadChart(ordersYear.value)
    }
    else {
      ordersSummary.value = null
    }
  }
  catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  }
  finally {
    pending.value = false
  }
}

watch(() => [tenant.organizationId, tenant.branchId], load)
watch(revenueYear, year => { revenueSummary.value = loadChart(year) })
watch(ordersYear, year => {
  if (canSeeServiceOrders.value) ordersSummary.value = loadChart(year)
})
onMounted(load)

const money = (value: number) => formatMoney(value)

interface KpiCard {
  key: string
  title: string
  value: string | number
  to?: string
  hint?: string
}

const operationsCards = computed<KpiCard[]>(() => {
  const data = summary.value?.summary
  return [
    { key: 'openOrders', title: t('freight.dashboard.kpis.openOrders'), value: data?.openOrders ?? 0, to: '/service-orders?workflowStatus=OPEN' },
    { key: 'inProgress', title: t('freight.dashboard.kpis.inProgress'), value: data?.inProgressOrders ?? 0, to: '/service-orders?workflowStatus=IN_PROGRESS' },
    { key: 'onHold', title: t('freight.dashboard.kpis.onHold'), value: data?.onHoldOrders ?? 0, to: '/service-orders?workflowStatus=ON_HOLD' },
    { key: 'awaitingClosure', title: t('freight.dashboard.kpis.awaitingClosure'), value: data?.awaitingClosure ?? 0, to: '/service-orders?workflowStatus=COMPLETED' },
  ]
})

const financeCards = computed<KpiCard[]>(() => {
  const data = summary.value?.summary
  const cards: KpiCard[] = [
    { key: 'receivables', title: t('freight.dashboard.kpis.receivables'), value: money(data?.receivables ?? 0), to: freightReportPath(getFreightReport('accounts-receivable')) },
    { key: 'payables', title: t('freight.dashboard.kpis.payables'), value: money(data?.payables ?? 0), to: freightReportPath(getFreightReport('accounts-payable')) },
    { key: 'cashBank', title: t('freight.dashboard.kpis.cashBank'), value: money(data?.cashBankBalance ?? 0), to: '/finance/financial-accounts' },
    { key: 'revenue', title: t('freight.dashboard.kpis.revenue'), value: money(data?.revenue ?? 0), to: freightReportPath(getFreightReport('revenue-expense')) },
  ]
  if (data?.overdueReceivableCount) cards[0]!.hint = t('freight.dashboard.overdueInvoices', { n: data.overdueReceivableCount })
  return cards
})

const colorMode = useColorMode()
const dark = computed(() => colorMode.value === 'dark')
const axisColor = computed(() => (dark.value ? '#3f3f46' : '#e4e4e7'))
const labelColor = computed(() => (dark.value ? '#a1a1aa' : '#71717a'))
const splitColor = computed(() => (dark.value ? 'rgba(255,255,255,0.08)' : 'rgba(24,24,27,0.07)'))
const BRAND = '#e8472a'
const NAVY = '#3a539f'

function compactNumber(value: number) {
  return formatCompact(value)
}

function monthLabel(month: string) {
  const [year, m] = month.split('-')
  if (!year || !m) return month
  const date = new Date(Date.UTC(Number(year), Number(m) - 1, 1))
  const name = formatDatePart(date, { month: 'short', timeZone: 'UTC' })
  return `${name} ${year.slice(2)}`
}

function bucketLabel(key: string) {
  if (/^\d{4}-Q[1-4]$/.test(key)) {
    const [year, quarter] = key.split('-')
    return t('freight.dashboard.chartFilters.quarter', { n: Number(quarter?.slice(1)), year })
  }
  if (/^\d{4}$/.test(key)) return key
  return monthLabel(key)
}

const revenueYearNumber = computed(() => dashboardChartYearRange(revenueYear.value).year)

const revenueExpenseSeries = computed(() => bucketDashboardRevenueExpense(
  revenueSummary.value?.charts.revenueExpense || [],
  revenuePeriod.value,
  revenueYearNumber.value,
))

const sharedAxis = computed(() => ({
  axisLine: { lineStyle: { color: axisColor.value } },
  axisTick: { show: false },
  axisLabel: { color: labelColor.value, fontSize: 11, hideOverlap: true },
}))

const sharedValueAxis = computed(() => ({
  type: 'value' as const,
  splitLine: { lineStyle: { color: splitColor.value, type: 'solid' as const } },
  axisLabel: { color: labelColor.value, fontSize: 11, formatter: (value: number) => compactNumber(value) },
}))

const revenueExpenseOption = computed<EChartsCoreOption>(() => {
  const points = revenueExpenseSeries.value
  return {
    grid: { left: 8, right: 12, top: 28, bottom: 4, containLabel: true },
    legend: { top: 0, right: 0, itemWidth: 14, itemHeight: 2, icon: 'rect', textStyle: { color: labelColor.value, fontSize: 11 } },
    tooltip: { trigger: 'axis', valueFormatter: (value: string | number) => money(Number(value || 0)) },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map(point => bucketLabel(point.key)),
      ...sharedAxis.value,
    },
    yAxis: sharedValueAxis.value,
    series: [
      {
        name: t('freight.dashboard.kpis.revenue'),
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 6,
        data: points.map(point => point.revenue),
        lineStyle: { width: 2.5, color: BRAND },
        itemStyle: { color: BRAND },
        areaStyle: { color: `${BRAND}14` },
      },
      {
        name: t('freight.dashboard.expense'),
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 6,
        data: points.map(point => point.expense),
        lineStyle: { width: 2.5, color: NAVY },
        itemStyle: { color: NAVY },
      },
    ],
  }
})

const ordersByStatusOption = computed<EChartsCoreOption>(() => {
  const rows = ordersSummary.value?.charts.ordersByStatus || []
  return {
    grid: { left: 8, right: 8, top: 12, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'category',
      data: rows.map(row => t(`freight.dashboard.status.${row.status}`)),
      ...sharedAxis.value,
      axisLabel: {
        ...sharedAxis.value.axisLabel,
        interval: 0,
        rotate: rows.length > 5 ? 20 : 0,
      },
    },
    yAxis: {
      ...sharedValueAxis.value,
      minInterval: 1,
      axisLabel: { color: labelColor.value, fontSize: 11 },
    },
    series: [{
      name: t('freight.dashboard.charts.ordersByStatus'),
      type: 'bar',
      barMaxWidth: 36,
      barCategoryGap: '42%',
      itemStyle: { color: BRAND, borderRadius: 0 },
      data: rows.map(row => row.count),
    }],
  }
})

const revenueEmpty = computed(() => !revenueExpenseSeries.value.some(point => point.revenue || point.expense))
const ordersEmpty = computed(() => !ordersSummary.value?.charts.ordersByStatus.some(row => row.count))
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions :can-create="false" :refreshing="pending" @refresh="load" />

    <div class="flex w-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-auto px-1.5 pt-1.5 pb-3 xl:overflow-hidden">
      <div
        v-if="error"
        class="flex shrink-0 items-center justify-between gap-2 rounded-md border border-error/30 bg-error/5 px-3 py-2"
      >
        <p class="truncate text-xs text-error">{{ t('freight.dashboard.errorTitle') }} · {{ error }}</p>
        <UButton
          size="xs"
          variant="soft"
          color="error"
          icon="i-lucide-refresh-cw"
          :label="t('docetra.actions.retry')"
          @click="load"
        />
      </div>

      <DashboardAppKpiSection
        v-if="canSeeServiceOrders"
        :title="t('freight.dashboard.operations')"
        :cards="operationsCards"
        :loading="pending"
        @refresh="load"
      />

      <DashboardAppKpiSection
        :title="t('freight.dashboard.finance')"
        :cards="financeCards"
        :loading="pending"
        @refresh="load"
      />

      <DashboardAppChartGrid>
        <DashboardAppChartPanel
          v-model:year="revenueYear"
          v-model:period="revenuePeriod"
          :title="t('freight.dashboard.charts.revenueExpense')"
          :option="revenueExpenseOption"
          :pending="pending"
          :empty="revenueEmpty"
          download-name="revenue-expense"
        />
        <DashboardAppChartPanel
          v-if="canSeeServiceOrders"
          v-model:year="ordersYear"
          v-model:period="ordersPeriod"
          :title="t('freight.dashboard.charts.ordersByStatus')"
          :option="ordersByStatusOption"
          :pending="pending"
          :empty="ordersEmpty"
          download-name="orders-by-status"
        />
      </DashboardAppChartGrid>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsCoreOption } from 'echarts/core'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import {
  buildDashboardBuckets,
  granularityForPeriod,
  type DashboardChartPeriod,
} from '~/utils/freight/dashboard'
import type { DashboardSummary } from '~/repositories/contracts/lcs'
import { freightReportPath, getFreightReport } from '~/config/freight-reports'
import { useLcsRepositories } from '~/repositories'

definePageMeta({
  titleKey: 'freight.pages.dashboard',
  permission: 'dashboard.view',
})

/**
 * Compact ERP dashboard: KPI summary cards + line chart + bar chart.
 * Each chart has its own period select (Today / Monthly / Yearly) that drives
 * the backend granularity for that chart only.
 * Accounting figures are POSTED documents and journals only.
 */

const auth = useAuthStore()
const { reports } = useLcsRepositories()
const { t } = useI18n()
const { formatMoney, formatCompact, formatDatePart } = useAppLocalization()
const { setTitle, clear } = useAppHeader()

setTitle(t('freight.pages.dashboard'))
watch(() => t('freight.pages.dashboard'), title => setTitle(title))
onBeforeUnmount(clear)
usePageSeo({ title: () => t('freight.pages.dashboard') })

const pending = computed(() => revenuePending.value || ordersPending.value)
const error = ref('')
const revenueSummary = ref<DashboardSummary | null>(null)
const ordersSummary = ref<DashboardSummary | null>(null)
const revenuePending = ref(true)
const ordersPending = ref(true)
const periods = ref<Record<string, DashboardChartPeriod>>({ revenue: 'monthly', orders: 'monthly' })

const canSeeServiceOrders = computed(() => auth.canAccessPage('operations.service_orders.view'))

function revenueGranularity() {
  return granularityForPeriod(periods.value.revenue ?? 'monthly')
}

function ordersGranularity() {
  return granularityForPeriod(periods.value.orders ?? 'monthly')
}

async function loadRevenue() {
  revenuePending.value = true
  try {
    revenueSummary.value = await reports.dashboard(revenueGranularity())
  }
  catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  }
  finally {
    revenuePending.value = false
  }
}

async function loadOrders() {
  if (ordersGranularity() === revenueGranularity() && revenueSummary.value) {
    ordersSummary.value = revenueSummary.value
    ordersPending.value = false
    return
  }
  ordersPending.value = true
  try {
    ordersSummary.value = await reports.dashboard(ordersGranularity())
  }
  catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  }
  finally {
    ordersPending.value = false
  }
}

async function load() {
  error.value = ''
  await nextTick()
  await loadRevenue()
  await loadOrders()
}

function onPeriodChange(key: string, period: DashboardChartPeriod) {
  periods.value = { ...periods.value, [key]: period }
  if (key === 'orders') void loadOrders()
  else void loadRevenue()
}

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
  const data = revenueSummary.value?.summary
  return [
    { key: 'openOrders', title: t('freight.dashboard.kpis.openOrders'), value: data?.openOrders ?? 0, to: '/service-orders?workflowStatus=OPEN' },
    { key: 'inProgress', title: t('freight.dashboard.kpis.inProgress'), value: data?.inProgressOrders ?? 0, to: '/service-orders?workflowStatus=IN_PROGRESS' },
    { key: 'onHold', title: t('freight.dashboard.kpis.onHold'), value: data?.onHoldOrders ?? 0, to: '/service-orders?workflowStatus=ON_HOLD' },
    { key: 'awaitingClosure', title: t('freight.dashboard.kpis.awaitingClosure'), value: data?.awaitingClosure ?? 0, to: '/service-orders?workflowStatus=COMPLETED' },
  ]
})

const financeCards = computed<KpiCard[]>(() => {
  const data = revenueSummary.value?.summary
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
  if (periods.value.revenue === 'yearly') return key
  if (periods.value.revenue === 'today') {
    const day = key.split('-')[2]
    return day ? String(Number(day)) : key
  }
  return monthLabel(key)
}

const revenueExpenseSeries = computed(() => buildDashboardBuckets(
  revenueSummary.value?.charts.revenueExpense || [],
  periods.value.revenue ?? 'monthly',
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

const chartPanels = computed(() => [
  {
    key: 'revenue',
    title: t('freight.dashboard.charts.revenueExpense'),
    option: revenueExpenseOption.value,
    pending: revenuePending.value,
    empty: revenueEmpty.value,
    downloadName: 'revenue-expense',
  },
  {
    key: 'orders',
    title: t('freight.dashboard.charts.ordersByStatus'),
    option: ordersByStatusOption.value,
    pending: ordersPending.value,
    empty: ordersEmpty.value,
    downloadName: 'orders-by-status',
    visible: canSeeServiceOrders.value,
  },
])
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
          :label="t('lcs.actions.retry')"
          @click="load"
        />
      </div>

      <div
        v-if="canSeeServiceOrders"
        class="grid shrink-0 grid-cols-2 gap-2 lg:grid-cols-4"
      >
        <DashboardAppSummaryCard
          v-for="card in operationsCards"
          :key="card.key"
          :title="card.title"
          :value="card.value"
          :to="card.to"
          :loading="pending"
          @refresh="load"
        >
          <p v-if="card.hint && !pending" class="mt-1 text-xs text-muted">
            {{ card.hint }}
          </p>
        </DashboardAppSummaryCard>
      </div>

      <div class="grid shrink-0 grid-cols-2 gap-2 lg:grid-cols-4">
        <DashboardAppSummaryCard
          v-for="card in financeCards"
          :key="card.key"
          :title="card.title"
          :value="card.value"
          :to="card.to"
          :loading="pending"
          @refresh="load"
        >
          <p v-if="card.hint && !pending" class="mt-1 text-xs text-muted">
            {{ card.hint }}
          </p>
        </DashboardAppSummaryCard>
      </div>

      <DashboardAppChartGrid
        :panels="chartPanels"
        :periods="periods"
        @period-change="onPeriodChange"
      />
    </div>
  </div>
</template>

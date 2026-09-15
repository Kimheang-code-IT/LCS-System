<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { EChartsCoreOption } from 'echarts/core'
import { getFilterSelectUi } from '~/utils/filter/select-ui'
import type { DashboardChartPeriodFilter, DashboardChartYearFilter } from '~/utils/lcs/dashboard'

const props = withDefaults(defineProps<{
  title: string
  option: EChartsCoreOption
  pending?: boolean
  empty?: boolean
  downloadName?: string
}>(), {
  pending: false,
  empty: false,
  downloadName: 'chart',
})

const year = defineModel<DashboardChartYearFilter>('year', { default: 'thisYear' })
const period = defineModel<DashboardChartPeriodFilter>('period', { default: 'monthly' })

const { t } = useI18n()
const toast = useToast()
const chartRef = useTemplateRef<{ toPng: () => string }>('chartRef')

const yearItems = computed(() => [
  { label: t('freight.dashboard.chartFilters.thisYear'), value: 'thisYear' },
  { label: t('freight.dashboard.chartFilters.lastYear'), value: 'lastYear' },
])

const periodItems = computed(() => [
  { label: t('freight.dashboard.chartFilters.monthly'), value: 'monthly' },
  { label: t('freight.dashboard.chartFilters.quarterly'), value: 'quarterly' },
  { label: t('freight.dashboard.chartFilters.yearly'), value: 'yearly' },
])

function fileSlug() {
  return String(props.downloadName || props.title || 'chart')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'chart'
}

function downloadFile(href: string, filename: string) {
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  link.click()
}

function downloadPng() {
  const url = chartRef.value?.toPng()
  if (!url) {
    toast.add({ title: t('freight.dashboard.chartDownloadFailed'), color: 'error' })
    return
  }
  downloadFile(url, `${fileSlug()}.png`)
}

function csvCell(value: unknown) {
  const text = String(value ?? '')
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function axisCategories(option: EChartsCoreOption): unknown[] {
  const axis = option.xAxis as { data?: unknown[] } | Array<{ data?: unknown[] }> | undefined
  const first = Array.isArray(axis) ? axis[0] : axis
  return Array.isArray(first?.data) ? first.data : []
}

function seriesRows(option: EChartsCoreOption): Array<{ name: string, data: unknown[] }> {
  const series = option.series
  const list = Array.isArray(series) ? series : series ? [series] : []
  return list.map((item) => {
    const row = item as { name?: string, data?: unknown[] }
    return {
      name: String(row.name || ''),
      data: Array.isArray(row.data) ? row.data : [],
    }
  })
}

function downloadCsv() {
  const categories = axisCategories(props.option)
  const series = seriesRows(props.option)
  const headers = [t('freight.dashboard.chartFilters.period'), ...series.map(item => item.name)]
  const rows = categories.map((category, index) => [
    category,
    ...series.map(item => item.data[index] ?? 0),
  ])
  const csv = [headers, ...rows].map(row => row.map(csvCell).join(',')).join('\n')
  downloadFile(`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`, `${fileSlug()}.csv`)
}

const menuItems = computed<DropdownMenuItem[][]>(() => [[
  {
    label: t('docetra.actions.downloadPng'),
    icon: 'i-lucide-image',
    disabled: props.empty || props.pending,
    onSelect: downloadPng,
  },
  {
    label: t('freight.dashboard.downloadCsv'),
    icon: 'i-lucide-file-spreadsheet',
    disabled: props.empty || props.pending,
    onSelect: downloadCsv,
  },
]])
</script>

<template>
  <section class="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-md border border-default bg-default">
    <div class="flex shrink-0 items-center gap-2 border-b border-default px-3 py-2">
      <h2 class="min-w-0 flex-1 truncate text-sm font-semibold text-highlighted">{{ title }}</h2>
      <USelect
        v-model="year"
        :items="yearItems"
        value-key="value"
        size="sm"
        class="w-32 shrink-0"
        :ui="getFilterSelectUi(true)"
        :aria-label="t('freight.dashboard.chartFilters.pickYear')"
      />
      <USelect
        v-model="period"
        :items="periodItems"
        value-key="value"
        size="sm"
        class="w-28 shrink-0"
        :ui="getFilterSelectUi(true)"
        :aria-label="t('freight.dashboard.chartFilters.pickPeriod')"
      />
      <UDropdownMenu :items="menuItems" :content="{ align: 'end' }">
        <UButton
          icon="i-lucide-ellipsis"
          color="neutral"
          variant="outline"
          size="xs"
          class="shrink-0"
          :aria-label="t('docetra.actions.more')"
        />
      </UDropdownMenu>
    </div>

    <div class="flex min-h-0 min-w-0 flex-1 flex-col p-2">
      <div v-if="pending" class="h-full w-full flex-1 animate-pulse rounded bg-elevated" />
      <UEmpty
        v-else-if="empty"
        variant="naked"
        size="sm"
        icon="i-lucide-chart-no-axes-column"
        :title="t('freight.dashboard.empty')"
        class="flex h-full flex-1 items-center justify-center py-6"
      />
      <DashboardAppEChart
        v-else
        ref="chartRef"
        class="min-h-0 flex-1"
        :option="option"
        :aria-label="title"
        height="100%"
      />
    </div>
  </section>
</template>

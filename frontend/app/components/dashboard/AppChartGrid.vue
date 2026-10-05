<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { EChartsCoreOption } from 'echarts/core'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css'
import { getFilterSelectUi } from '~/utils/filter/select-ui'
import { slugify } from '~/utils/text/slug'
import type { DashboardChartPeriod } from '~/utils/lcs/dashboard'

/**
 * Combined dashboard chart grid + panel + ECharts wrapper.
 * Registers only the modules used by dashboards/reports to keep chunks small;
 * echarts/vue-echarts are split into their own chunk by nuxt.config.
 */
use([CanvasRenderer, LineChart, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

type DashboardChartPanel = {
  key: string
  title: string
  option: EChartsCoreOption
  pending?: boolean
  empty?: boolean
  downloadName?: string
  visible?: boolean
}

type ChartExport = {
  getDataURL?: (opts?: Record<string, unknown>) => string
  chart?: { getDataURL?: (opts?: Record<string, unknown>) => string }
}

const props = withDefaults(defineProps<{
  panels: DashboardChartPanel[]
  periods?: Record<string, DashboardChartPeriod>
}>(), {
  periods: () => ({}),
})

const emit = defineEmits<{
  periodChange: [key: string, period: DashboardChartPeriod]
}>()

const { t } = useI18n()
const toast = useToast()
const colorMode = useColorMode()

const visiblePanels = computed(() => props.panels.filter(panel => panel.visible !== false))

const periodItems = computed(() => [
  { label: t('freight.dashboard.chartFilters.today'), value: 'today' },
  { label: t('freight.dashboard.chartFilters.monthly'), value: 'monthly' },
  { label: t('freight.dashboard.chartFilters.yearly'), value: 'yearly' },
])

function panelPeriod(key: string): DashboardChartPeriod {
  return props.periods[key] ?? 'monthly'
}

function setPeriod(key: string, value: string) {
  emit('periodChange', key, value as DashboardChartPeriod)
}

const chartRefs = new Map<string, ChartExport>()

function setChartRef(key: string, el: unknown) {
  if (el) chartRefs.set(key, el as ChartExport)
  else chartRefs.delete(key)
}

const themedOption = (option: EChartsCoreOption): EChartsCoreOption => {
  const dark = colorMode.value === 'dark'
  return {
    textStyle: {
      fontFamily: 'Inter, "Noto Sans Khmer", ui-sans-serif, system-ui, sans-serif',
      color: dark ? '#a1a1aa' : '#52525b',
    },
    tooltip: dark
      ? { backgroundColor: '#27272a', borderColor: '#3f3f46', textStyle: { color: '#e4e4e7' } }
      : {},
    ...option,
  }
}

function toPng(panel: DashboardChartPanel) {
  const dark = colorMode.value === 'dark'
  const exporter = chartRefs.get(panel.key)
  const toUrl = exporter?.getDataURL || exporter?.chart?.getDataURL
  return toUrl?.({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: dark ? '#18181b' : '#ffffff',
  }) || ''
}

function fileSlug(panel: DashboardChartPanel) {
  return slugify(String(panel.downloadName || panel.title || 'chart'), 'chart')
}

function downloadFile(href: string, filename: string) {
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  link.click()
}

function downloadPng(panel: DashboardChartPanel) {
  const url = toPng(panel)
  if (!url) {
    toast.add({ title: t('freight.dashboard.chartDownloadFailed'), color: 'error' })
    return
  }
  downloadFile(url, `${fileSlug(panel)}.png`)
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

function downloadCsv(panel: DashboardChartPanel) {
  const categories = axisCategories(panel.option)
  const series = seriesRows(panel.option)
  const headers = [t('freight.dashboard.chartFilters.period'), ...series.map(item => item.name)]
  const rows = categories.map((category, index) => [
    category,
    ...series.map(item => item.data[index] ?? 0),
  ])
  const csv = [headers, ...rows].map(row => row.map(csvCell).join(',')).join('\n')
  downloadFile(`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`, `${fileSlug(panel)}.csv`)
}

function menuItems(panel: DashboardChartPanel): DropdownMenuItem[][] {
  return [[
    {
      label: t('lcs.actions.downloadPng'),
      icon: 'i-lucide-image',
      disabled: Boolean(panel.empty || panel.pending),
      onSelect: () => downloadPng(panel),
    },
    {
      label: t('freight.dashboard.downloadCsv'),
      icon: 'i-lucide-file-spreadsheet',
      disabled: Boolean(panel.empty || panel.pending),
      onSelect: () => downloadCsv(panel),
    },
  ]]
}
</script>

<template>
  <div class="grid min-h-72 flex-1 grid-cols-1 grid-rows-2 gap-2 xl:min-h-0 xl:grid-cols-2 xl:grid-rows-1">
    <section
      v-for="panel in visiblePanels"
      :key="panel.key"
      class="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-md border border-default bg-default"
    >
      <div class="flex shrink-0 items-center gap-2 border-b border-default px-3 py-2">
        <h2 class="min-w-0 flex-1 truncate text-sm font-semibold text-highlighted">{{ panel.title }}</h2>
        <USelect
          :model-value="panelPeriod(panel.key)"
          :items="periodItems"
          value-key="value"
          size="sm"
          class="w-32 shrink-0"
          :ui="getFilterSelectUi(true)"
          :aria-label="t('freight.dashboard.chartFilters.pickPeriod')"
          @update:model-value="setPeriod(panel.key, $event)"
        />
        <UDropdownMenu :items="menuItems(panel)" :content="{ align: 'end' }">
          <UButton
            icon="i-lucide-ellipsis"
            color="neutral"
            variant="outline"
            size="xs"
            class="shrink-0"
            :aria-label="t('lcs.actions.more')"
          />
        </UDropdownMenu>
      </div>

      <div class="flex min-h-0 min-w-0 flex-1 flex-col p-2">
        <div v-if="panel.pending" class="h-full w-full flex-1 animate-pulse rounded bg-elevated" />
        <UEmpty
          v-else-if="panel.empty"
          variant="naked"
          size="sm"
          icon="i-lucide-chart-no-axes-column"
          :title="t('freight.dashboard.empty')"
          class="flex h-full flex-1 items-center justify-center py-6"
        />
        <VChart
          v-else
          :ref="el => setChartRef(panel.key, el)"
          class="h-full w-full min-h-0 min-w-0"
          :option="themedOption(panel.option)"
          autoresize
          :aria-label="panel.title"
          role="img"
        />
      </div>
    </section>
  </div>
</template>

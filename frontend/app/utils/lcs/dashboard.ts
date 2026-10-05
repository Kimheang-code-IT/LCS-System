/**
 * Dashboard chart shaping. The dashboard summary is served by the backend
 * `GET /api/v1/reports/dashboard?granularity=day|month|year`; these helpers
 * map the selected period to a backend granularity and fill a stable chart
 * axis from the returned revenue/expense points.
 */

export type DashboardChartPeriod = 'today' | 'monthly' | 'yearly'
export type DashboardChartGranularity = 'day' | 'month' | 'year'

export interface DashboardChartPoint {
  period: string
  revenue: number
  expense: number
}

export interface DashboardChartBucket {
  key: string
  revenue: number
  expense: number
}

export function granularityForPeriod(period: DashboardChartPeriod): DashboardChartGranularity {
  if (period === 'today') return 'day'
  if (period === 'yearly') return 'year'
  return 'month'
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

/** Fill a stable chart axis for the selected period from the backend points. */
export function buildDashboardBuckets(
  points: DashboardChartPoint[],
  period: DashboardChartPeriod,
  today = new Date(),
): DashboardChartBucket[] {
  const byKey = new Map(points.map(point => [point.period, point]))
  const bucket = (key: string): DashboardChartBucket => {
    const point = byKey.get(key)
    return { key, revenue: point?.revenue || 0, expense: point?.expense || 0 }
  }

  if (period === 'today') {
    const prefix = `${today.getFullYear()}-${pad(today.getMonth() + 1)}`
    return Array.from({ length: today.getDate() }, (_, index) =>
      bucket(`${prefix}-${pad(index + 1)}`),
    )
  }

  if (period === 'yearly') {
    const years = points
      .map(point => Number(point.period))
      .filter(year => Number.isFinite(year))
    const max = Math.max(today.getFullYear(), ...years)
    const min = years.length ? Math.min(...years) : today.getFullYear()
    return Array.from({ length: max - min + 1 }, (_, index) => bucket(String(min + index)))
  }

  const year = today.getFullYear()
  return Array.from({ length: today.getMonth() + 1 }, (_, index) =>
    bucket(`${year}-${pad(index + 1)}`),
  )
}

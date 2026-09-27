/**
 * Dashboard chart shaping. The dashboard summary itself is served by the
 * backend `GET /api/v1/reports/dashboard`; these helpers only re-bucket the
 * already-fetched monthly revenue/expense points for the selected period.
 */

export type DashboardChartYearFilter = 'thisYear' | 'lastYear'
export type DashboardChartPeriodFilter = 'monthly' | 'quarterly' | 'yearly'

export interface DashboardPoint {
  month: string
  revenue: number
  expense: number
}

export interface DashboardChartBucket {
  key: string
  revenue: number
  expense: number
}

function round(value: number): number {
  return Number(value.toFixed(2))
}

export function dashboardChartYearRange(
  yearFilter: DashboardChartYearFilter,
  today = new Date(),
): { year: number, dateFrom: string, dateTo: string } {
  const year = yearFilter === 'lastYear' ? today.getFullYear() - 1 : today.getFullYear()
  return {
    year,
    dateFrom: `${year}-01-01`,
    dateTo: `${year}-12-31`,
  }
}

function monthKeyFor(year: number, month: number) {
  return `${year}-${String(month).padStart(2, '0')}`
}

/** Fill a stable chart axis for the selected year / period from monthly journal totals. */
export function bucketDashboardRevenueExpense(
  points: DashboardPoint[],
  period: DashboardChartPeriodFilter,
  year: number,
  today = new Date(),
): DashboardChartBucket[] {
  const byMonth = new Map(points.map(point => [point.month, point]))
  const lastMonth = year === today.getFullYear() ? today.getMonth() + 1 : 12

  if (period === 'yearly') {
    let revenue = 0
    let expense = 0
    for (const point of points) {
      revenue = round(revenue + point.revenue)
      expense = round(expense + point.expense)
    }
    return [{ key: String(year), revenue, expense }]
  }

  if (period === 'quarterly') {
    const lastQuarter = Math.ceil(lastMonth / 3)
    return Array.from({ length: lastQuarter }, (_, index) => {
      const quarter = index + 1
      let revenue = 0
      let expense = 0
      for (let month = (quarter - 1) * 3 + 1; month <= quarter * 3; month++) {
        if (month > lastMonth) break
        const point = byMonth.get(monthKeyFor(year, month))
        revenue = round(revenue + (point?.revenue || 0))
        expense = round(expense + (point?.expense || 0))
      }
      return { key: `${year}-Q${quarter}`, revenue, expense }
    })
  }

  return Array.from({ length: lastMonth }, (_, index) => {
    const month = monthKeyFor(year, index + 1)
    const point = byMonth.get(month)
    return { key: month, revenue: point?.revenue || 0, expense: point?.expense || 0 }
  })
}

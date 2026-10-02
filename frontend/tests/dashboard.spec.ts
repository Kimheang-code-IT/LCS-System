import { describe, expect, it } from 'vitest'
import { dashboardSummaryForYear } from '../app/utils/freight/dashboard'

describe('dashboard summary shaping', () => {
  const summary = {
    generatedAt: '2026-10-02T00:00:00Z',
    summary: { revenue: 100 },
    charts: {
      revenueExpense: [
        { month: '2025-12', revenue: 5, expense: 1 },
        { month: '2026-01', revenue: 10, expense: 2 },
        { month: '2026-02', revenue: 20, expense: 3 },
      ],
      ordersByStatus: [{ status: 'OPEN', count: 2 }],
    },
  }

  it('keeps only the selected year of revenue/expense points', () => {
    const result = dashboardSummaryForYear(summary, 2026)
    expect(result.charts.revenueExpense).toEqual([
      { month: '2026-01', revenue: 10, expense: 2 },
      { month: '2026-02', revenue: 20, expense: 3 },
    ])
  })

  it('leaves the rest of the summary untouched', () => {
    const result = dashboardSummaryForYear(summary, 2025)
    expect(result.summary).toEqual(summary.summary)
    expect(result.charts.ordersByStatus).toEqual(summary.charts.ordersByStatus)
    expect(result.generatedAt).toBe(summary.generatedAt)
  })
})

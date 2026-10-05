import { describe, expect, it } from 'vitest'
import { buildDashboardBuckets, granularityForPeriod } from '../app/utils/freight/dashboard'

describe('dashboard chart shaping', () => {
  const today = new Date(2026, 2, 15)

  it('maps the selected period to a backend granularity', () => {
    expect(granularityForPeriod('today')).toBe('day')
    expect(granularityForPeriod('monthly')).toBe('month')
    expect(granularityForPeriod('yearly')).toBe('year')
  })

  it('fills a stable monthly axis for the current year', () => {
    const buckets = buildDashboardBuckets(
      [{ period: '2026-01', revenue: 10, expense: 2 }],
      'monthly',
      today,
    )
    expect(buckets).toEqual([
      { key: '2026-01', revenue: 10, expense: 2 },
      { key: '2026-02', revenue: 0, expense: 0 },
      { key: '2026-03', revenue: 0, expense: 0 },
    ])
  })

  it('fills a daily axis for the current month', () => {
    const buckets = buildDashboardBuckets(
      [{ period: '2026-03-02', revenue: 5, expense: 1 }],
      'today',
      today,
    )
    expect(buckets).toHaveLength(15)
    expect(buckets[0]).toEqual({ key: '2026-03-01', revenue: 0, expense: 0 })
    expect(buckets[1]).toEqual({ key: '2026-03-02', revenue: 5, expense: 1 })
  })

  it('spans the years present in the data for the yearly axis', () => {
    const buckets = buildDashboardBuckets(
      [
        { period: '2024', revenue: 1, expense: 0 },
        { period: '2026', revenue: 3, expense: 0 },
      ],
      'yearly',
      today,
    )
    expect(buckets.map(bucket => bucket.key)).toEqual(['2024', '2025', '2026'])
  })
})

import { describe, expect, it } from 'vitest'
import { createLcsFreightSeed } from './fixtures/lcs-seed'
import type { FreightRecord } from '../app/types/freight/record'
import type { LcsSession } from '../app/types/lcs/session'
import { buildDashboardSummary, bucketDashboardRevenueExpense, dashboardChartYearRange } from '../app/utils/lcs/dashboard'

function adminSession(overrides: Partial<LcsSession> = {}): LcsSession {
  return {
    userId: 1,
    userName: 'System Administrator',
    organizationId: 1,
    branchId: 'all',
    assignedBranchIds: [1, 2],
    permissionScope: 'ORGANIZATION',
    sourcePermissions: [],
    ...overrides,
  }
}

function db() {
  const seed = createLcsFreightSeed()
  seed.idempotency = []
  return seed
}

describe('dashboard summary — operations KPIs', () => {
  it('counts service order workflow buckets and excludes other organizations', () => {
    const data = buildDashboardSummary(db(), adminSession())
    // Seed jobs for org 1: 1 OPEN (job-005), 3 IN_PROGRESS (job-001/002/004),
    // 1 ON_HOLD (job-007), 1 COMPLETED (job-003), 1 CLOSED (job-006).
    // job-008 belongs to the demo organization and must never appear.
    expect(data.summary.openOrders).toBe(1)
    expect(data.summary.inProgressOrders).toBe(3)
    expect(data.summary.onHoldOrders).toBe(1)
    expect(data.summary.awaitingClosure).toBe(1)
    const closed = data.charts.ordersByStatus.find(row => row.status === 'CLOSED')
    expect(closed?.count).toBe(1)
    const total = data.charts.ordersByStatus.reduce((sum, row) => sum + row.count, 0)
    expect(total).toBe(7)
  })
})

describe('dashboard summary — posted-only accounting', () => {
  it('computes receivables from POSTED invoices minus posted receipt allocations', () => {
    const data = buildDashboardSummary(db(), adminSession())
    // dn-001 Posted total 1622.5 with no allocations → outstanding.
    // dn-003 Posted 1375 fully covered by cp-003 allocation → 0.
    // dn-002 / dn-004 are Draft → excluded.
    expect(data.summary.receivables).toBe(1622.5)
  })

  it('never counts draft documents or issued charges as accounting values', () => {
    const seed = db()
    seed.debitNotes.push({
      id: 'dn-draft-test',
      debitNoteNo: 'DN-DRAFT-TEST',
      date: '2026-08-21',
      customer: 'Manhattan SEZ Co., Ltd.',
      jobNo: 'LCS-IM-260821',
      total: 99999,
      status: 'Draft',
      documentType: 'CUSTOMER_INVOICE',
      organizationId: 1,
      branchId: 1,
      currency: 'USD',
    })
    const data = buildDashboardSummary(seed, adminSession())
    expect(data.summary.receivables).toBe(1622.5)

    // Issued charge conversion stays a draft invoice — no revenue impact.
    seed.jobCharges.push({
      id: 'jc-issued-test',
      jobNo: 'LCS-IM-260821',
      chargeSide: 'Customer',
      chargeType: 'Trucking Fee',
      amount: 88888,
      status: 'Issued',
      currency: 'USD',
      organizationId: 1,
      branchId: 1,
    })
    const after = buildDashboardSummary(seed, adminSession())
    expect(after.summary.revenue).toBe(data.summary.revenue)
  })

  it('computes payables from POSTED bills minus posted supplier payments', () => {
    const data = buildDashboardSummary(db(), adminSession())
    // sc-003 Posted partial 610 minus SP-2608-020 payment 300 → 310.
    // sc-002 Posted paid in full via SP-2608-021; drafts excluded.
    expect(data.summary.payables).toBe(310)
  })

  it('derives revenue and expense from posted journal lines only', () => {
    const data = buildDashboardSummary(db(), adminSession())
    // je-001 credit 4010 Service Revenue 1475 + je-002 credit 4010 1250.
    expect(data.summary.revenue).toBe(2725)
    expect(data.charts.revenueExpense.length).toBeGreaterThan(0)
    const august = data.charts.revenueExpense.find(point => point.month === '2026-08')
    expect(august?.revenue).toBe(2725)
  })

  it('uses cash/bank account balances for the Cash/Bank KPI', () => {
    const data = buildDashboardSummary(db(), adminSession())
    expect(data.summary.cashBankBalance).toBeCloseTo(40900 + 1375 + 2700, 2)
  })
})

describe('dashboard summary — aging', () => {
  it('buckets receivables by days past due', () => {
    // dn-001 dated 2026-08-20 + 14 day terms → due 2026-09-03.
    const overdue = buildDashboardSummary(db(), adminSession(), {}, '2026-10-05')
    const bucket = overdue.charts.receivablesAging.find(item => item.key === 'd31_60')
    expect(bucket?.amount).toBe(1622.5)
    expect(overdue.summary.overdueReceivableCount).toBe(1)

    const current = buildDashboardSummary(db(), adminSession(), {}, '2026-08-25')
    const notDue = current.charts.receivablesAging.find(item => item.key === 'not_due')
    expect(notDue?.amount).toBe(1622.5)
    expect(current.summary.overdueReceivableCount).toBe(0)
  })
})

describe('dashboard summary — scope enforcement', () => {
  it('restricts branch-scoped users to their assigned branch', () => {
    const bavet = buildDashboardSummary(db(), adminSession({
      permissionScope: 'BRANCH',
      branchId: 1,
      assignedBranchIds: [1],
    }))
    // je-002 (Phnom Penh) must not contribute revenue to Bavet users.
    expect(bavet.summary.revenue).toBe(1475)
    // Phnom Penh ON_HOLD job-007 must not appear.
    expect(bavet.summary.onHoldOrders).toBe(0)
    // Phnom Penh cash account excluded.
    expect(bavet.summary.cashBankBalance).toBe(40900 + 2700)
  })

  it('isolates other organizations completely', () => {
    const demo = adminSession({
      organizationId: 2,
      branchId: 3,
      assignedBranchIds: [3],
    })
    const data = buildDashboardSummary(db(), demo)
    expect(data.summary.openOrders).toBe(1) // job-008 only
    expect(data.summary.receivables).toBe(0)
    expect(data.summary.cashBankBalance).toBe(0)
  })
})

describe('dashboard summary — filters', () => {
  it('applies customer filter to orders', () => {
    const data = buildDashboardSummary(db(), adminSession(), { customer: 'Royal Group Manufacturing' })
    const total = data.charts.ordersByStatus.reduce((sum, row) => sum + row.count, 0)
    // job-003 (COMPLETED), job-007 (ON_HOLD), job-001? no — Manhattan. Royal: job-003 + job-007.
    expect(total).toBe(2)
  })

  it('applies direction filter to orders', () => {
    const exports = buildDashboardSummary(db(), adminSession(), { direction: 'Export' })
    const total = exports.charts.ordersByStatus.reduce((sum, row) => sum + row.count, 0)
    // Export jobs: job-002 (IN_PROGRESS), job-005 (OPEN).
    expect(total).toBe(2)
  })

  it('returns zero money KPIs when currency matches nothing', () => {
    const data = buildDashboardSummary(db(), adminSession(), { currency: 'KHR' })
    expect(data.summary.receivables).toBe(0)
    expect(data.summary.payables).toBe(0)
    expect(data.summary.cashBankBalance).toBe(0)
  })

  it('narrows revenue to the selected period', () => {
    const beforeAugust = buildDashboardSummary(db(), adminSession(), { dateFrom: '2026-01-01', dateTo: '2026-07-31' })
    expect(beforeAugust.summary.revenue).toBe(0)
    const august = buildDashboardSummary(db(), adminSession(), { dateFrom: '2026-08-01', dateTo: '2026-08-31' })
    expect(august.summary.revenue).toBe(2725)
  })

  it('exposes a stable customer option list independent of filters', () => {
    const filtered = buildDashboardSummary(db(), adminSession(), { customer: 'Manhattan SEZ Co., Ltd.' })
    expect(filtered.options.customers).toContain('Tai Seng Manufacturing')
  })
})

describe('dashboard chart year and period buckets', () => {
  it('resolves this year and last year date bounds', () => {
    expect(dashboardChartYearRange('thisYear', new Date('2026-08-26'))).toEqual({
      year: 2026,
      dateFrom: '2026-01-01',
      dateTo: '2026-12-31',
    })
    expect(dashboardChartYearRange('lastYear', new Date('2026-08-26'))).toEqual({
      year: 2025,
      dateFrom: '2025-01-01',
      dateTo: '2025-12-31',
    })
  })

  it('fills monthly buckets through the current month', () => {
    const buckets = bucketDashboardRevenueExpense(
      [{ month: '2026-08', revenue: 100, expense: 40 }],
      'monthly',
      2026,
      new Date('2026-08-26'),
    )
    expect(buckets).toHaveLength(8)
    expect(buckets[0]).toEqual({ key: '2026-01', revenue: 0, expense: 0 })
    expect(buckets[7]).toEqual({ key: '2026-08', revenue: 100, expense: 40 })
  })

  it('rolls months into quarters for the current year', () => {
    const buckets = bucketDashboardRevenueExpense(
      [
        { month: '2026-01', revenue: 10, expense: 1 },
        { month: '2026-04', revenue: 20, expense: 2 },
      ],
      'quarterly',
      2026,
      new Date('2026-08-26'),
    )
    expect(buckets.map(bucket => bucket.key)).toEqual(['2026-Q1', '2026-Q2', '2026-Q3'])
    expect(buckets[0]?.revenue).toBe(10)
    expect(buckets[1]?.revenue).toBe(20)
    expect(buckets[2]?.revenue).toBe(0)
  })

  it('collapses the year into a single bucket', () => {
    const buckets = bucketDashboardRevenueExpense(
      [
        { month: '2026-01', revenue: 10, expense: 4 },
        { month: '2026-08', revenue: 5, expense: 1 },
      ],
      'yearly',
      2026,
      new Date('2026-08-26'),
    )
    expect(buckets).toEqual([{ key: '2026', revenue: 15, expense: 5 }])
  })
})

describe('dashboard summary — record shape', () => {
  it('always returns all aging buckets and status rows', () => {
    const emptyDb: Record<string, FreightRecord[]> = {}
    const data = buildDashboardSummary(emptyDb, adminSession())
    expect(data.charts.receivablesAging).toHaveLength(5)
    expect(data.charts.payablesAging).toHaveLength(5)
    expect(data.charts.ordersByStatus.map(row => row.status)).toEqual([
      'DRAFT', 'OPEN', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CLOSED', 'CANCELLED',
    ])
    expect(data.summary.revenue).toBe(0)
  })
})

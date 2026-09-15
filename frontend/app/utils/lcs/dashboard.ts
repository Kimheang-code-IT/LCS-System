import type { FreightRecord } from '~/types/freight/record'
import type { LcsSession } from '~/types/lcs/session'
import type { ServiceOrderStatus } from '~/types/lcs/domain'
import { JOB_WORKFLOW_STATUS } from '~/config/freight-options'
import { filterScopedRecords } from '~/utils/lcs/scope'
import { financeDomainStatus, jobDomainStatus } from '~/utils/lcs/states'

/**
 * Dashboard summary aggregation — the mock-data equivalent of a single
 * `GET /dashboard/summary` endpoint. All accounting figures are derived from
 * POSTED financial documents and posted journal lines only; drafts, issued
 * service charges and unposted journals never affect money KPIs.
 *
 * Scope (organization, branch, permission visibility) is enforced here before
 * any aggregation happens, mirroring what the backend must enforce.
 */

export interface DashboardFilters {
  dateFrom?: string
  dateTo?: string
  currency?: string
  direction?: string
  customer?: string
}

export interface DashboardAgingBucket {
  key: 'not_due' | 'd1_30' | 'd31_60' | 'd61_90' | 'd90_plus'
  amount: number
}

export interface DashboardPoint {
  month: string
  revenue: number
  expense: number
}

export interface DashboardStatusCount {
  status: ServiceOrderStatus
  count: number
}

export interface DashboardSummary {
  generatedAt: string
  summary: {
    openOrders: number
    inProgressOrders: number
    onHoldOrders: number
    awaitingClosure: number
    receivables: number
    overdueReceivableCount: number
    payables: number
    cashBankBalance: number
    revenue: number
    expense: number
  }
  charts: {
    revenueExpense: DashboardPoint[]
    ordersByStatus: DashboardStatusCount[]
    receivablesAging: DashboardAgingBucket[]
    payablesAging: DashboardAgingBucket[]
  }
  options: {
    customers: string[]
  }
}

export const AGING_BUCKETS: DashboardAgingBucket['key'][] = ['not_due', 'd1_30', 'd31_60', 'd61_90', 'd90_plus']

const DAY_MS = 86_400_000

function day(value: unknown): string {
  return String(value || '').slice(0, 10)
}

function num(value: unknown): number {
  const amount = Number(value || 0)
  return Number.isFinite(amount) ? amount : 0
}

function round(value: number): number {
  return Number(value.toFixed(2))
}

function inDateRange(date: string, filters: DashboardFilters): boolean {
  if (filters.dateFrom && date && date < filters.dateFrom) return false
  if (filters.dateTo && date && date > filters.dateTo) return false
  if ((filters.dateFrom || filters.dateTo) && !date) return false
  return true
}

function matchesRow(row: Record<string, unknown>, filters: DashboardFilters): boolean {
  if (filters.currency && String(row.currency || 'USD') !== filters.currency) return false
  if (filters.direction && String(row.direction || '') !== filters.direction) return false
  return true
}

function matchesParty(row: Record<string, unknown>, filters: DashboardFilters): boolean {
  if (!filters.customer) return true
  return String(row.customer || row.party || '') === filters.customer
}

/** Posted (not reversed/cancelled) customer invoices only. */
export function postedCustomerInvoices(db: Record<string, FreightRecord[]>, session: LcsSession): FreightRecord[] {
  return filterScopedRecords(db.debitNotes || [], session)
    .filter(row => String(row.documentType || 'CUSTOMER_INVOICE') === 'CUSTOMER_INVOICE')
    .filter(row => financeDomainStatus(row.status) === 'POSTED')
}

/** Posted supplier bills only. */
export function postedSupplierBills(db: Record<string, FreightRecord[]>, session: LcsSession): FreightRecord[] {
  return filterScopedRecords(db.supplierCosts || [], session)
    .filter(row => financeDomainStatus(row.postingStatus || row.status) === 'POSTED')
}

/**
 * Receipt allocations applied to each customer invoice document no.
 * Only allocations on posted receipts count; unallocated receipts stay out.
 */
export function receiptAllocationsByDocument(db: Record<string, FreightRecord[]>, session: LcsSession): Map<string, number> {
  const map = new Map<string, number>()
  const add = (targetNo: unknown, amount: unknown) => {
    const key = String(targetNo || '')
    if (!key) return
    map.set(key, round((map.get(key) || 0) + num(amount)))
  }

  for (const payment of filterScopedRecords(db.customerPayments || [], session)) {
    const allocations = Array.isArray(payment.allocations) ? payment.allocations as Array<Record<string, unknown>> : []
    for (const allocation of allocations) add(allocation.targetDocumentNo, allocation.amount)
  }
  for (const allocation of filterScopedRecords(db.allocations || [], session)) {
    const target = String(allocation.targetDocumentId || '')
    const targetNo = target
      ? String((db.debitNotes || []).find(row => row.id === target)?.debitNoteNo || target)
      : ''
    add(targetNo || allocation.targetDocumentId, allocation.amount)
  }
  return map
}

/** Supplier payments matched to bills by invoice no (or job + supplier). */
export function supplierPaidAmounts(db: Record<string, FreightRecord[]>, session: LcsSession): FreightRecord[] {
  return filterScopedRecords(db.supplierPayments || [], session)
    .filter(row => financeDomainStatus(row.status) === 'POSTED')
}export function agingBucketFor(dueDate: string, today: string): DashboardAgingBucket['key'] {
  const days = Math.floor((Date.parse(today) - Date.parse(dueDate)) / DAY_MS)
  if (Number.isNaN(days) || days <= 0) return 'not_due'
  if (days <= 30) return 'd1_30'
  if (days <= 60) return 'd31_60'
  if (days <= 90) return 'd61_90'
  return 'd90_plus'
}

function emptyBuckets(): DashboardAgingBucket[] {
  return AGING_BUCKETS.map(key => ({ key, amount: 0 }))
}

function bucketize(buckets: DashboardAgingBucket[], dueDate: string, today: string, outstanding: number) {
  const bucket = buckets.find(item => item.key === agingBucketFor(dueDate, today))
  if (bucket) bucket.amount = round(bucket.amount + Math.max(outstanding, 0))
}

/** Payment-terms days parsed from the supplier master ("15 days" → 15). */
function supplierTermDays(db: Record<string, FreightRecord[]>, session: LcsSession): number {
  const terms = filterScopedRecords(db.suppliers || [], session)
    .map(row => String(row.paymentTerms || ''))
  for (const term of terms) {
    const match = term.match(/(\d+)/)
    if (match) return Number(match[1]) || 30
  }
  return 30
}

function addDays(date: string, days: number): string {
  const time = Date.parse(`${date}T00:00:00`)
  if (Number.isNaN(time)) return date
  return new Date(time + days * DAY_MS).toISOString().slice(0, 10)
}

function accountTypeResolver(db: Record<string, FreightRecord[]>, session: LcsSession) {
  const types = new Map<string, string>()
  for (const account of filterScopedRecords(db.chartOfAccounts || [], session)) {
    types.set(String(account.accountCode || ''), String(account.accountType || ''))
  }
  return (code: string): string => {
    const known = types.get(code)
    if (known) return known
    // Fallback for ledger codes missing from the chart-of-accounts seed:
    // 4xxx = revenue, 5xxx = expense (standard CoA ranges).
    if (code.startsWith('4')) return 'Revenue'
    if (code.startsWith('5')) return 'Expense'
    return ''
  }
}

interface JournalTotals {
  byMonth: Map<string, { revenue: number, expense: number }>
  revenue: number
  expense: number
}

function journalRevenueExpense(
  db: Record<string, FreightRecord[]>,
  session: LcsSession,
  filters: DashboardFilters,
): JournalTotals {
  const resolveType = accountTypeResolver(db, session)
  const byMonth = new Map<string, { revenue: number, expense: number }>()
  let revenue = 0
  let expense = 0

  for (const journal of filterScopedRecords(db.journals || [], session)) {
    if (String(journal.status || '').toUpperCase() !== 'POSTED') continue
    const postingDate = day(journal.postingDate || journal.entryDate)
    if (!inDateRange(postingDate, filters)) continue
    const month = postingDate.slice(0, 7)
    const lines = Array.isArray(journal.lines) ? journal.lines as Array<Record<string, unknown>> : []
    for (const line of lines) {
      if (filters.currency && String(line.currency || 'USD') !== filters.currency) continue
      const code = String(line.account_code || line.accountCode || '')
      const type = resolveType(code)
      if (type !== 'Revenue' && type !== 'Expense') continue
      const debit = num(line.debit_amount ?? line.debit)
      const credit = num(line.credit_amount ?? line.credit)
      const bucket = byMonth.get(month) || { revenue: 0, expense: 0 }
      if (type === 'Revenue') {
        bucket.revenue = round(bucket.revenue + credit - debit)
        revenue = round(revenue + credit - debit)
      }
      else {
        bucket.expense = round(bucket.expense + debit - credit)
        expense = round(expense + debit - credit)
      }
      byMonth.set(month, bucket)
    }
  }
  return { byMonth, revenue, expense }
}

/**
 * Build the full dashboard summary in one pass.
 * `today` is injectable so aging is deterministic and testable.
 */
export function buildDashboardSummary(
  db: Record<string, FreightRecord[]>,
  session: LcsSession,
  filters: DashboardFilters = {},
  today = new Date().toISOString().slice(0, 10),
): DashboardSummary {
  const jobs = filterScopedRecords(db.jobs || [], session)
    .filter(row => matchesRow(row, filters) && matchesParty(row, filters))
    .filter(row => inDateRange(day(row.date), filters))

  const statusOf = (row: Record<string, unknown>) => jobDomainStatus(row)
  const ordersByStatus: DashboardStatusCount[] = JOB_WORKFLOW_STATUS.map(status => ({
    status,
    count: jobs.filter(row => statusOf(row) === status).length,
  }))

  // Stable option list: scoped parties regardless of active dashboard filters.
  const customers = new Set<string>()
  for (const row of filterScopedRecords(db.jobs || [], session)) {
    if (row.customer) customers.add(String(row.customer))
  }
  for (const row of filterScopedRecords(db.suppliers || [], session)) {
    if (row.name) customers.add(String(row.name))
  }

  const invoices = postedCustomerInvoices(db, session)
    .filter(row => matchesRow(row, filters) && matchesParty(row, filters))
    .filter(row => inDateRange(day(row.date), filters))
  const allocations = receiptAllocationsByDocument(db, session)

  let receivables = 0
  let overdueReceivableCount = 0
  const receivablesAging = emptyBuckets()
  for (const invoice of invoices) {
    const total = num(invoice.total || invoice.amount)
    const allocated = allocations.get(String(invoice.debitNoteNo || '')) || 0
    const outstanding = round(Math.max(total - allocated, 0))
    if (outstanding <= 0) continue
    receivables = round(receivables + outstanding)
    const dueDate = addDays(day(invoice.date), 14)
    if (agingBucketFor(dueDate, today) !== 'not_due') overdueReceivableCount += 1
    bucketize(receivablesAging, dueDate, today, outstanding)
  }

  // Each payment counts once per bill: matched by invoice no first,
  // falling back to job + supplier when no invoice reference exists.
  const payments = supplierPaidAmounts(db, session)
  const paidForBill = (bill: Record<string, unknown>) =>
    payments
      .filter(payment => String(payment.invoiceNo || '') === String(bill.invoiceNo || '')
        || (String(payment.jobNo || '') === String(bill.jobNo || '') && String(payment.supplier || '') === String(bill.supplier || '')))
      .reduce((sum, payment) => sum + num(payment.amount), 0)

  const termDays = supplierTermDays(db, session)
  let payables = 0
  const payablesAging = emptyBuckets()
  for (const bill of postedSupplierBills(db, session)) {
    if (!matchesParty({ customer: bill.customer, party: bill.supplier }, filters)) continue
    if (!matchesRow(bill, filters)) continue
    if (!inDateRange(day(bill.date), filters)) continue
    const amount = num(bill.amount)
    const outstanding = round(Math.max(amount - paidForBill(bill), 0))
    if (outstanding <= 0) continue
    payables = round(payables + outstanding)
    const dueDate = addDays(day(bill.date), termDays)
    bucketize(payablesAging, dueDate, today, outstanding)
  }

  let cashBankBalance = 0
  for (const account of filterScopedRecords(db.cashAccounts || [], session)) {
    if (filters.currency && String(account.currency || 'USD') !== filters.currency) continue
    cashBankBalance = round(cashBankBalance + num(account.balance))
  }

  const totals = journalRevenueExpense(db, session, filters)
  const revenueExpense = [...totals.byMonth.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([month, point]) => ({ month, revenue: point.revenue, expense: point.expense }))

  return {
    generatedAt: new Date().toISOString(),
    summary: {
      openOrders: ordersByStatus.find(item => item.status === 'OPEN')?.count || 0,
      inProgressOrders: ordersByStatus.find(item => item.status === 'IN_PROGRESS')?.count || 0,
      onHoldOrders: ordersByStatus.find(item => item.status === 'ON_HOLD')?.count || 0,
      awaitingClosure: ordersByStatus.find(item => item.status === 'COMPLETED')?.count || 0,
      receivables,
      overdueReceivableCount,
      payables,
      cashBankBalance,
      revenue: totals.revenue,
      expense: totals.expense,
    },
    charts: {
      revenueExpense,
      ordersByStatus,
      receivablesAging,
      payablesAging,
    },
    options: {
      customers: [...customers].sort(),
    },
  }
}

export type DashboardChartYearFilter = 'thisYear' | 'lastYear'
export type DashboardChartPeriodFilter = 'monthly' | 'quarterly' | 'yearly'

export interface DashboardChartBucket {
  key: string
  revenue: number
  expense: number
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

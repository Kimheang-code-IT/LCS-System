import type { FreightRecord } from '~/types/freight/record'
import { daysSince, postedJournalLines } from '~/utils/freight/report'

export function indexRowsByKey<T extends Record<string, unknown>>(
  rows: T[],
  key: keyof T | string = 'jobNo',
) {
  const map = new Map<string, T[]>()
  for (const row of rows) {
    const value = String(row[key as keyof T] || '')
    if (!value) continue
    const bucket = map.get(value) || []
    bucket.push(row)
    map.set(value, bucket)
  }
  return map
}

export function buildServiceOrderReportRows(
  jobs: FreightRecord[],
  related: {
    containers: FreightRecord[]
    components: FreightRecord[]
    charges: FreightRecord[]
    documents: FreightRecord[]
  },
) {
  const containersByJob = indexRowsByKey(related.containers)
  const componentsByJob = indexRowsByKey(related.components)
  const chargesByJob = indexRowsByKey(related.charges)
  const documentsByJob = indexRowsByKey(related.documents)

  return jobs.map((job) => {
    const jobNo = String(job.jobNo || '')
    const relatedComponents = componentsByJob.get(jobNo) || []
    const relatedCharges = chargesByJob.get(jobNo) || []
    const relatedDocuments = documentsByJob.get(jobNo) || []
    return {
      ...job,
      workflowStatus: job.workflowStatus || job.status,
      containers: (containersByJob.get(jobNo) || []).length,
      components: relatedComponents.length,
      chargeTotal: relatedCharges.reduce((sum, row) => sum + Number(row.total || 0), 0),
      invoiceTotal: relatedDocuments
        .filter(row => String(row.status).toUpperCase() === 'POSTED')
        .reduce((sum, row) => sum + Number(row.total || 0), 0),
      daysOpen: daysSince(job.createdAt || job.date),
      pendingComponents: relatedComponents.filter(row => String(row.status).toUpperCase() !== 'COMPLETED').length,
      lastActivity: job.updatedAt || job.createdAt || job.date,
    }
  })
}

export function buildContainerReportRows(
  containers: FreightRecord[],
  jobsByNo: Map<string, FreightRecord>,
) {
  return containers.map((row) => {
    const job = jobsByNo.get(String(row.jobNo || ''))
    return {
      ...row,
      customer: job?.customer,
      currentMilestone: job?.stage || job?.workflowStatus || job?.status,
    }
  })
}

export function buildRevenueExpenseReportRows(postedLines: FreightRecord[]) {
  return postedLines
    .filter(row => ['Revenue', 'Expense'].includes(String(row.accountType)))
    .map(row => ({
      ...row,
      category: row.accountType,
      revenue: row.accountType === 'Revenue' ? Number(row.credit) - Number(row.debit) : 0,
      expense: row.accountType === 'Expense' ? Number(row.debit) - Number(row.credit) : 0,
    }))
}

export function buildTrialBalanceReportRows(postedLines: FreightRecord[]) {
  const map = new Map<string, FreightRecord>()
  for (const line of postedLines) {
    const key = String(line.accountCode)
    const row = map.get(key) || {
      id: key,
      accountCode: key,
      accountName: line.accountName,
      openingDebit: 0,
      openingCredit: 0,
      periodDebit: 0,
      periodCredit: 0,
      closingDebit: 0,
      closingCredit: 0,
    }
    row.periodDebit = Number(row.periodDebit) + Number(line.debit)
    row.periodCredit = Number(row.periodCredit) + Number(line.credit)
    const balance = Number(row.periodDebit) - Number(row.periodCredit)
    row.closingDebit = Math.max(balance, 0)
    row.closingCredit = Math.max(-balance, 0)
    map.set(key, row)
  }
  return [...map.values()]
}

export function buildCashFlowReportRows(
  postedLines: FreightRecord[],
  financialAccounts: FreightRecord[],
) {
  let balance = 0
  const codes = new Set(financialAccounts.map(row => String(row.ledgerCode)))
  return postedLines
    .filter(row => codes.has(String(row.accountCode)))
    .map((row) => {
      const cashIn = Number(row.debit)
      const cashOut = Number(row.credit)
      balance += cashIn - cashOut
      return { ...row, cashIn, cashOut, runningBalance: balance }
    })
}

export function buildReportRows(
  slug: string,
  store: {
    list: (collection: string) => FreightRecord[]
  },
) {
  const jobs = store.list('jobs')
  const jobsByNo = new Map(jobs.map(job => [String(job.jobNo || ''), job]))
  const charges = store.list('jobCharges')
  const documents = store.list('debitNotes')
  const components = store.list('serviceComponents')
  const postedLines = postedJournalLines(store.list('journals'), store.list('chartOfAccounts'))

  if (['service-orders', 'service-order-status'].includes(slug)) {
    return buildServiceOrderReportRows(jobs, {
      containers: store.list('actualContainers'),
      components,
      charges,
      documents,
    })
  }
  if (slug === 'containers') {
    return buildContainerReportRows(store.list('actualContainers'), jobsByNo)
  }
  if (slug === 'revenue-expense') {
    return buildRevenueExpenseReportRows(postedLines)
  }
  if (slug === 'trial-balance') {
    return buildTrialBalanceReportRows(postedLines)
  }
  if (slug === 'cash-flow') {
    return buildCashFlowReportRows(postedLines, store.list('financialAccounts'))
  }
  return postedLines
}

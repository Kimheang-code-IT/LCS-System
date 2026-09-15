import type { FreightRecord } from '~/types/freight/record'
import {
  jobContainerCount,
  jobContainerPaymentRows,
  jobContainerPaymentTotals,
} from '~/utils/freight/job-containers'

function countBy(rows: FreightRecord[], keyOf: (row: FreightRecord) => string) {
  const map = new Map<string, number>()
  for (const row of rows) {
    const key = keyOf(row)
    if (!key) continue
    map.set(key, (map.get(key) || 0) + 1)
  }
  return map
}

function groupByJob(rows: FreightRecord[]) {
  const map = new Map<string, FreightRecord[]>()
  for (const row of rows) {
    const key = String(row.jobNo || '')
    if (!key) continue
    const list = map.get(key) || []
    list.push(row)
    map.set(key, list)
  }
  return map
}

/** List metrics for service-order / job rows — containers, tasks, payment totals. */
export function enrichJobListRows(
  rows: FreightRecord[],
  related: {
    containers: FreightRecord[]
    tasks: FreightRecord[]
    charges: FreightRecord[]
    shipments?: FreightRecord[]
  },
): FreightRecord[] {
  const containerCounts = countBy(related.containers, row => String(row.jobNo || ''))
  const taskTotals = new Map<string, number>()
  const taskDone = new Map<string, number>()
  for (const row of related.tasks) {
    const key = String(row.jobNo || '')
    if (!key) continue
    taskTotals.set(key, (taskTotals.get(key) || 0) + 1)
    if (row.status === 'COMPLETED') taskDone.set(key, (taskDone.get(key) || 0) + 1)
  }
  const chargesByJob = groupByJob(related.charges)
  const shipmentsByJob = groupByJob(related.shipments || [])

  return rows.map((row) => {
    const key = String(row.jobNo || '')
    const taskTotal = taskTotals.get(key) || 0
    const payments = jobContainerPaymentRows(row, {
      shipments: shipmentsByJob.get(key) || [],
      charges: chargesByJob.get(key) || [],
    })
    const nested = Array.isArray(row.actualContainers) ? row.actualContainers as FreightRecord[] : []
    const relatedActuals = nested.length ? nested : (related.containers.filter(item => String(item.jobNo || '') === key))
    const chargeTotal = jobContainerPaymentTotals(payments, row.vatRate).total
    return {
      ...row,
      containersCount: jobContainerCount(row, payments, relatedActuals) || containerCounts.get(key) || 0,
      tasksProgress: taskTotal ? `${taskDone.get(key) || 0} / ${taskTotal}` : '',
      chargesTotal: chargeTotal || '',
    }
  })
}

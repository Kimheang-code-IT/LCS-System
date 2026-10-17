import type { FreightRecord } from '~/types/record'

/** Outstanding amount of one document: total − allocated, floored at 0. */
export function outstandingOf(row: FreightRecord) {
  const total = Number(row.total || row.amount || 0)
  const allocated = Number(row.allocatedAmount || 0)
  return Math.max(total - allocated, 0)
}

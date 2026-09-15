import type { FreightRecord } from '~/types/freight/record'
import { financeDomainStatus } from '~/utils/lcs/states'

/** Sum of posted customer-invoice totals. Posted documents only — never drafts or other doc types. */
export function postedDocumentTotal(rows: FreightRecord[]) {
  return rows
    .filter(row => String(row.documentType || 'CUSTOMER_INVOICE') === 'CUSTOMER_INVOICE')
    .filter(row => financeDomainStatus(row.status) === 'POSTED')
    .reduce((sum, row) => sum + Number(row.total || row.amount || 0), 0)
}

/** Outstanding amount of one document: total − allocated, floored at 0. */
export function outstandingOf(row: FreightRecord) {
  const total = Number(row.total || row.amount || 0)
  const allocated = Number(row.allocatedAmount || 0)
  return Math.max(total - allocated, 0)
}

/** Amount already allocated/paid on one document (total − outstanding). */
export function paidAmountOf(row: FreightRecord) {
  if (row.outstanding != null) return Math.max(Number(row.total || row.amount || 0) - Number(row.outstanding || 0), 0)
  return Number(row.allocatedAmount || 0)
}

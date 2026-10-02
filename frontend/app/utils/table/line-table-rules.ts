/**
 * Per-line-table row arithmetic, as pure functions.
 *
 * Each function is attached to its table definition (`computeRow` / `rowDefaults`
 * on `FreightTable`), so `AppLineTable.vue` never branches on a table key. Keep
 * this module a leaf: it must not import components or module configs.
 *
 * Rounding and tax fallbacks differ per table and are reproduced exactly as the
 * renderer computed them before — changing them would silently move money.
 */

import { containerPaymentAmounts } from '~/utils/freight/job-containers'

type Row = Record<string, unknown>

function num(value: unknown) {
  return Number(value || 0)
}

function money(value: number) {
  return Number(value.toFixed(2))
}

/** Quotation `pricingLines`: qty × unit price − discount, plus tax, 2dp. */
export function computePricingLine({ row }: { row: Row }) {
  const subtotal = num(row.quantity) * num(row.unitPrice)
  const taxable = Math.max(0, subtotal - num(row.discountAmount))
  return { lineTotal: money(taxable + num(row.taxAmount)) }
}

/**
 * Service charge `feeLines`: qty × unit amount − discount, plus tax. The result
 * is intentionally not rounded — this matches the stored charge line totals.
 */
export function computeFeeLine({ row }: { row: Row }) {
  const base = Math.max(0, num(row.quantity) * num(row.unitAmount) - num(row.discount))
  return { amount: base + num(row.taxAmount) }
}

/**
 * Finance document `lines`: same shape as fee lines, but `taxAmount` falls back
 * to `tax` when the row carries a tax rate instead of a tax amount.
 */
export function computeDocumentLine({ row }: { row: Row }) {
  const base = Math.max(0, num(row.quantity) * num(row.unitAmount) - num(row.discount))
  return { amount: Number((base + num(row.taxAmount || row.tax)).toFixed(2)) }
}

/**
 * Row kinds inside the unified job finance table. Only `expense` rows are
 * editable; charge and document rows are projected from other collections and
 * are locked, so their arithmetic is never derived here.
 */
export const JOB_FINANCE_LINE_KIND = {
  charge: 'CHARGE',
  expense: 'EXPENSE',
  document: 'DOCUMENT',
} as const

export type JobFinanceLineKind = (typeof JOB_FINANCE_LINE_KIND)[keyof typeof JOB_FINANCE_LINE_KIND]

export function jobFinanceLineKind(row: Row): JobFinanceLineKind | '' {
  const kind = String(row._kind || '')
  return (Object.values(JOB_FINANCE_LINE_KIND) as string[]).includes(kind) ? kind as JobFinanceLineKind : ''
}

/** Unified job finance lines: price the expense rows, leave locked rows untouched. */
export function computeJobFinanceLine({ row }: { row: Row }) {
  if (jobFinanceLineKind(row) !== JOB_FINANCE_LINE_KIND.expense) return {}
  return { amount: money(num(row.quantity) * num(row.unitPrice)) }
}

/** "Add expense" always appends an expense row, never a charge or a document. */
export function jobFinanceLineRowDefaults() {
  return { _kind: JOB_FINANCE_LINE_KIND.expense, quantity: 1, amount: 0, reference: '', date: '', status: '' }
}

/** Quotation `otherCharges`: selling side, not rounded. */
export function computeOtherChargeLine({ row }: { row: Row }) {
  return { amount: num(row.quantity) * num(row.sellingRate) }
}

/** Container payments reuse the shared charge-line shape. */
export function computeContainerPaymentLine({ row }: { row: Row }) {
  return containerPaymentAmounts(row)
}

const CONTAINER_PAYMENT_DEFAULTS: Row = {
  unitPrice: 0,
  discountAmount: 0,
  taxAmount: 0,
  description: '',
  lineTotal: 0,
}

/** New container payment inherits the container and quantity of the row above. */
export function containerPaymentRowDefaults({ rows, blank }: { rows: Row[], blank: Row }) {
  const last = rows[rows.length - 1]
  return {
    ...CONTAINER_PAYMENT_DEFAULTS,
    quantity: Number(last?.quantity || 1) || 1,
    containerNo: String(last?.containerNo || ''),
    feeType: String(last?.feeType || blank.feeType || ''),
  }
}

export function containerRequirementRowDefaults() {
  return { quantity: 1, actualQuantity: 0, remaining: 1 }
}

export function actualContainerRowDefaults() {
  return { status: 'Expected', netWeightKg: 0, grossWeightKg: 0, containerNo: '' }
}

export function routePlaceRowDefaults({ rows }: { rows: Row[] }) {
  return { place: '', planned: '', actual: '', notes: '', sequence: rows.length + 1 }
}
import { roundMoney } from '~/utils/freight/fx'
import { toFiniteNumber } from '~/utils/format/number'

export type LineAdjustmentValues = { discount: number, taxRate: number }

type Row = Record<string, unknown>

/** Quantity x unit price, the base a discount and tax apply to. */
export function lineSubtotal(row: Row): number {
  const quantity = toFiniteNumber(row.quantity)
  const unitPrice = toFiniteNumber(row.unitPrice ?? row.unitAmount)
  return Math.max(0, quantity * unitPrice)
}

/**
 * Merge the dialog values onto a line and derive its tax amount. The dialog
 * validates first; the clamp keeps a malformed caller from writing negative or
 * over-subtotal money. The server remains the authority for saved totals.
 */
export function applyLineAdjustments(row: Row, values: LineAdjustmentValues): Row {
  const subtotal = lineSubtotal(row)
  const discount = Math.min(Math.max(0, Number(values.discount) || 0), subtotal)
  const taxRate = Math.min(Math.max(0, Number(values.taxRate) || 0), 100)
  const taxAmount = roundMoney((subtotal - discount) * taxRate / 100, 2)
  return {
    ...row,
    // Both spellings are written because the grids share keys with legacy rows.
    discountAmount: discount,
    discount,
    taxRate,
    taxAmount,
    tax: taxAmount,
  }
}

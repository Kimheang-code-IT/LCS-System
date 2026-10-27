import type { FreightLineColumn } from '~/config/freight-modules'

const moneyKeys = new Set([
  'unitPrice',
  'discountPercent',
  'taxPercent',
  'discountAmount',
  'discount',
  'taxAmount',
  'lineTotal',
  'total',
  'amount',
  'invoice_amount',
  'customs_fee',
])

/** True for a key whose values are money and should be right-aligned + currency formatted. */
export function isMoneyColumnKey(key: string) {
  return moneyKeys.has(key)
}

/**
 * How wide a line-table field is and how its value is aligned.
 *
 * `width` is the width of the *field* in CSS pixels. `AppLineTable` adds the
 * cell padding and borders on top of it and puts the total on the column, so the
 * field always fills the column it belongs to instead of floating inside it.
 * One resolver for the whole grid keeps the cell width, the field and the header
 * from disagreeing.
 */
export type LineTableColumnMetrics = {
  /** Field width in CSS pixels. */
  width: number
  /** Money/quantity values are right-aligned in the field and the header. */
  numeric: boolean
  /** Icon-only cells (delete, note, row actions) are as narrow as the icon. */
  iconOnly: boolean
}

/** Text, places and textareas: the historical `min-w-40` field. */
const TEXT_FIELD_WIDTH = 160
/** Wide enough for the icon button, no more. */
const ICON_FIELD_WIDTH = 32

function metrics(width: number, numeric = false, iconOnly = false): LineTableColumnMetrics {
  return { width, numeric, iconOnly }
}

/** Resolve a column's field width and alignment from its key, then its type. */
export function lineTableColumnMetrics(column: FreightLineColumn): LineTableColumnMetrics {
  // An explicit pixel width wins; a class string (admin-supplied) is applied to
  // the field by `lineTableColumnCellClass` and leaves this default in place.
  if (typeof column.width === 'number' && column.width > 0) {
    return metrics(column.width, numericColumn(column))
  }

  if (column.type === 'delete' || column.type === 'action' || column.type === 'reorder') {
    return metrics(ICON_FIELD_WIDTH, false, true)
  }
  if (column.key === 'blNo' || column.key === 'truckNo' || column.key === 'containerNo') return metrics(144)
  if (column.key === 'quantity' || column.key === 'actualQuantity' || column.key === 'remaining') return metrics(80, true)
  if (column.key === 'unit') return metrics(96)
  if (column.key === 'discountPercent' || column.key === 'taxPercent' || column.key === 'taxRate') return metrics(96, true)
  if (column.key === 'netWeightKg' || column.key === 'grossWeightKg' || column.key === 'weightKg') {
    return metrics(column.inlineFields?.length ? 144 : 112, true)
  }
  if (moneyKeys.has(column.key)) {
    return metrics(column.inlineFields?.length ? 176 : 128, true)
  }
  if (column.key === 'containerRequirement' || column.key === 'containerRequirementId' || column.key === 'containerType' || column.key === 'feeType') return metrics(144)
  if (column.key === 'sealNo' || column.key === 'status' || column.key === '_status') return metrics(112)
  if (column.key === 'placeRole' || column.key === 'placeRoleId') return metrics(176)
  if (column.key === 'place' || column.key === 'notes') return metrics(TEXT_FIELD_WIDTH)

  if (column.type === 'date' || column.type === 'datetime') return metrics(TEXT_FIELD_WIDTH)
  if (column.type === 'number') return metrics(112, true)
  if (column.type === 'select') return metrics(144)
  if (column.type === 'checkbox') return metrics(64)
  if (column.type === 'textarea') return metrics(TEXT_FIELD_WIDTH)
  if (column.computed) return metrics(112)

  return metrics(TEXT_FIELD_WIDTH)
}

function numericColumn(column: FreightLineColumn) {
  return moneyKeys.has(column.key)
    || column.key === 'quantity'
    || column.key === 'actualQuantity'
    || column.key === 'remaining'
    || column.key === 'netWeightKg'
    || column.key === 'grossWeightKg'
    || column.key === 'weightKg'
    || column.key === 'discountPercent'
    || column.key === 'taxPercent'
    || column.key === 'taxRate'
    || column.type === 'number'
}

/** Field width in CSS pixels — what the table turns into a column width. */
export function lineTableColumnWidth(column: FreightLineColumn) {
  return lineTableColumnMetrics(column).width
}

/**
 * Classes for the field itself: alignment, plus a class-shaped width override an
 * admin may have stored on a configurable column. The column width comes from
 * `lineTableColumnWidth`, so nothing here sets a width of its own.
 */
export function lineTableColumnCellClass(column: FreightLineColumn) {
  const align = lineTableColumnMetrics(column).numeric ? 'text-right tabular-nums' : ''
  if (typeof column.width === 'string' && column.width) return [column.width, align].filter(Boolean).join(' ')
  return align
}

export function lineTableNumericColumnKeys(extra: string[] = []) {
  return new Set([
    'quantity',
    'actualQuantity',
    'remaining',
    'netWeightKg',
    'grossWeightKg',
    'weightKg',
    'taxRate',
    ...moneyKeys,
    ...extra,
  ])
}

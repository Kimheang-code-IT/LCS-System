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

/** Shared cell width classes for AppLineTable / job workspace line tables. */
export function lineTableColumnCellClass(column: FreightLineColumn) {
  if (column.width) return column.width

  if (column.key === 'blNo' || column.key === 'truckNo' || column.key === 'containerNo') return 'w-36 min-w-28'
  if (column.key === 'quantity' || column.key === 'actualQuantity' || column.key === 'remaining') return 'w-20 min-w-20 text-right tabular-nums'
  if (column.key === 'unit') return 'w-24 min-w-24'
  if (column.key === 'discountPercent' || column.key === 'taxPercent' || column.key === 'taxRate') return 'w-24 min-w-24 text-right tabular-nums'
  if (column.key === 'netWeightKg' || column.key === 'grossWeightKg' || column.key === 'weightKg') {
    return column.inlineFields?.length ? 'w-36 min-w-32 text-right tabular-nums' : 'w-28 min-w-24 text-right tabular-nums'
  }
  if (moneyKeys.has(column.key)) {
    return column.inlineFields?.length ? 'w-44 min-w-40 text-right tabular-nums' : 'w-32 min-w-28 text-right tabular-nums'
  }
  if (column.key === 'containerRequirement' || column.key === 'containerRequirementId' || column.key === 'containerType' || column.key === 'feeType') return 'w-36 min-w-28'
  if (column.key === 'sealNo' || column.key === 'status' || column.key === '_status') return 'w-28 min-w-24'
  if (column.key === 'placeRole') return 'w-44 min-w-40'
  if (column.key === 'place' || column.key === 'notes') return 'min-w-40'
  if (column.key === 'plannedActual') return 'w-40 min-w-36'

  if (column.type === 'date' || column.type === 'datetime') return 'w-40 min-w-36'
  if (column.type === 'number') return 'w-28 min-w-24 text-right tabular-nums'
  if (column.type === 'select') return 'w-36 min-w-28'
  if (column.type === 'textarea') return 'min-w-40'
  if (column.computed) return 'w-28 min-w-24'

  return 'min-w-40'
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

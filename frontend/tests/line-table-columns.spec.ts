import { describe, expect, it } from 'vitest'
import { lineTableColumnCellClass } from '../app/utils/table/line-table-columns'

describe('line table column sizing', () => {
  it('sizes dynamic attribute columns by field type', () => {
    expect(lineTableColumnCellClass({ key: 'invoice_no', label: 'Invoice No.', type: 'text' })).toBe('min-w-40')
    expect(lineTableColumnCellClass({ key: 'invoice_date', label: 'Invoice Date', type: 'date' })).toBe('w-40 min-w-36')
    expect(lineTableColumnCellClass({ key: 'invoice_amount', label: 'Amount', type: 'number' })).toContain('text-right')
    expect(lineTableColumnCellClass({ key: '_status', label: 'Status', type: 'text', computed: true })).toBe('w-28 min-w-24')
  })

  it('keeps route column sizing', () => {
    expect(lineTableColumnCellClass({ key: 'placeRole', label: 'Role', type: 'select' })).toBe('w-44 min-w-40')
    expect(lineTableColumnCellClass({ key: 'place', label: 'Place', type: 'text' })).toBe('min-w-40')
    expect(lineTableColumnCellClass({ key: 'plannedActual', label: 'Date', type: 'date' })).toBe('w-40 min-w-36')
  })

  it('honours explicit column width from schema', () => {
    expect(lineTableColumnCellClass({ key: 'custom', label: 'Custom', type: 'text', width: 'w-52 min-w-48' })).toBe('w-52 min-w-48')
  })
})

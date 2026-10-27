import { describe, expect, it } from 'vitest'
import { lineTableColumnCellClass, lineTableColumnMetrics, lineTableColumnWidth } from '../app/utils/table/line-table-columns'

describe('line table column sizing', () => {
  it('sizes dynamic attribute columns by field type', () => {
    expect(lineTableColumnWidth({ key: 'invoice_no', label: 'Invoice No.', type: 'text' })).toBe(160)
    expect(lineTableColumnWidth({ key: 'invoice_date', label: 'Invoice Date', type: 'date' })).toBe(160)
    expect(lineTableColumnWidth({ key: 'invoice_amount', label: 'Amount', type: 'number' })).toBe(128)
    expect(lineTableColumnWidth({ key: '_status', label: 'Status', type: 'text', computed: true })).toBe(112)
  })

  it('keeps route column sizing', () => {
    expect(lineTableColumnWidth({ key: 'placeRole', label: 'Role', type: 'select' })).toBe(176)
    expect(lineTableColumnWidth({ key: 'place', label: 'Place', type: 'text' })).toBe(160)
    expect(lineTableColumnWidth({ key: 'plannedActual', label: 'Date', type: 'date' })).toBe(160)
  })

  it('gives a money column that carries inline discount/tax a wider field', () => {
    expect(lineTableColumnWidth({ key: 'lineTotal', label: 'Line Total', type: 'number' })).toBe(128)
    expect(lineTableColumnWidth({
      key: 'lineTotal',
      label: 'Line Total',
      type: 'number',
      inlineFields: [{ key: 'taxAmount', label: 'Tax' }],
    })).toBe(176)
  })

  it('aligns only numeric fields to the right', () => {
    expect(lineTableColumnCellClass({ key: 'invoice_amount', label: 'Amount', type: 'number' })).toBe('text-right tabular-nums')
    expect(lineTableColumnCellClass({ key: 'quantity', label: 'Qty', type: 'number' })).toBe('text-right tabular-nums')
    expect(lineTableColumnCellClass({ key: 'place', label: 'Place', type: 'text' })).toBe('')
    expect(lineTableColumnCellClass({ key: 'containerType', label: 'Type', type: 'select' })).toBe('')
  })

  it('marks icon columns so they stay as narrow as their button', () => {
    expect(lineTableColumnMetrics({ key: '_delete', label: '', type: 'delete' }).iconOnly).toBe(true)
    expect(lineTableColumnMetrics({ key: '_reorder', label: '', type: 'reorder' }).iconOnly).toBe(true)
    // A note is a normal text field now, not an icon cell.
    expect(lineTableColumnMetrics({ key: 'note', label: 'Note', type: 'note' }).iconOnly).toBe(false)
    expect(lineTableColumnWidth({ key: 'note', label: 'Note', type: 'note' })).toBe(160)
    expect(lineTableColumnMetrics({ key: 'place', label: 'Place', type: 'text' }).iconOnly).toBe(false)
  })

  it('honours an explicit pixel width from the schema', () => {
    expect(lineTableColumnWidth({ key: 'custom', label: 'Custom', type: 'text', width: 320 })).toBe(320)
    // An explicit width still keeps the type's alignment.
    expect(lineTableColumnCellClass({ key: 'invoice_amount', label: 'Amount', type: 'number', width: 320 }))
      .toBe('text-right tabular-nums')
  })

  it('honours a class-shaped width from an admin column config', () => {
    expect(lineTableColumnCellClass({ key: 'custom', label: 'Custom', type: 'text', width: 'w-52 min-w-48' })).toBe('w-52 min-w-48')
    // The class is applied to the field, so the column keeps its type default.
    expect(lineTableColumnWidth({ key: 'custom', label: 'Custom', type: 'text', width: 'w-52 min-w-48' })).toBe(160)
  })
})

describe('line table row controls', () => {
  it('treats the note as a normal text field', () => {
    expect(lineTableColumnMetrics({ key: 'note', label: 'Note', type: 'note' }).iconOnly).toBe(false)
  })
})

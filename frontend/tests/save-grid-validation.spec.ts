import { describe, expect, it } from 'vitest'
import { isSaveGridNewRow, rowsBeingSaved } from '../app/types/save-grid'
import { serviceChargeTable } from '../app/utils/freight/job-charges'
import { validateTableRows } from '../app/utils/validation/record-validation'

/**
 * A save-grid change set carries every row in display order. Validation must be
 * limited to what the request will actually contain, otherwise a pre-existing
 * row this user never touched would block the save — and an error must still
 * address the row the user sees, not its place in the filtered array.
 */

const table = serviceChargeTable()

const saved = [
  { id: 'a', description: 'Sea freight', quantity: 1, unitPrice: 100 },
  { id: 'b', description: '', quantity: 1, unitPrice: 20 },
]

const savedById = new Map(saved.map(row => [row.id, row]))

/** Validate the way `JobCharges.save()` does. */
function validateChange(change: { rows: Array<Record<string, unknown>>, removedIds: string[], added: Array<Record<string, unknown>> }) {
  const pending = rowsBeingSaved(change, savedById, table.columns)
  return validateTableRows({
    table,
    rows: pending.map(entry => entry.row),
    rowIndices: pending.map(entry => entry.index),
    label: key => key,
    columnLabel: column => column.label || column.key,
  })
}

describe('isSaveGridNewRow', () => {
  it('recognises a row with no server id', () => {
    expect(isSaveGridNewRow({})).toBe(true)
    expect(isSaveGridNewRow({ id: 'new_1' })).toBe(true)
    expect(isSaveGridNewRow({ id: 'a' })).toBe(false)
  })
})

describe('rowsBeingSaved', () => {
  it('includes a new row with its grid position', () => {
    const change = { rows: [...saved, { id: 'new_1', description: 'Docs' }], removedIds: [], added: [] }
    expect(rowsBeingSaved(change, savedById, table.columns)).toEqual([
      { row: { id: 'new_1', description: 'Docs' }, index: 2 },
    ])
  })

  it('includes a saved row whose value changed, at its own grid position', () => {
    const change = {
      rows: [saved[0]!, { ...saved[1]!, description: 'Port handling' }],
      removedIds: [],
      added: [],
    }
    expect(rowsBeingSaved(change, savedById, table.columns).map(entry => entry.index)).toEqual([1])
  })

  it('omits a saved row the user never touched', () => {
    const change = { rows: saved.map(row => ({ ...row })), removedIds: [], added: [] }
    expect(rowsBeingSaved(change, savedById, table.columns)).toEqual([])
  })

  it('ignores utility columns when diffing', () => {
    const change = { rows: [{ ...saved[0]!, _delete: 'ignored' }], removedIds: [], added: [] }
    expect(rowsBeingSaved(change, savedById, table.columns)).toEqual([])
  })
})

describe('grid save gating on the service-charge table', () => {
  it('requires the description of a charge line', () => {
    expect(table.columns.some(column => column.key === 'description' && column.required)).toBe(true)
  })

  it('blocks a save that would write an incomplete new row', () => {
    const change = { rows: [...saved, { id: 'new_1', description: '' }], removedIds: [], added: [] }
    expect(validateChange(change).map(failure => failure.key)).toEqual(['serviceOrderCharges.2.description'])
  })

  it('does not block on a pre-existing incomplete row the user did not touch', () => {
    const change = { rows: saved.map(row => ({ ...row })), removedIds: [], added: [] }
    expect(validateChange(change)).toEqual([])
  })

  it('addresses the row the user sees once that row is edited', () => {
    const change = {
      rows: [saved[0]!, { ...saved[1]!, quantity: 3 }],
      removedIds: [],
      added: [],
    }
    // Row 1 in the grid, not row 0 in the filtered validation array.
    expect(validateChange(change).map(failure => failure.key)).toEqual(['serviceOrderCharges.1.description'])
  })
})
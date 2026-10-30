import { describe, expect, it } from 'vitest'
import type { FreightTable } from '../app/config/freight-modules'
import { tableColumnSignature } from '../app/utils/table/table-shape'

/** The document form rebuilds this descriptor on every keystroke. */
function descriptor(): FreightTable {
  return {
    key: 'feeLines',
    title: 'Fee lines',
    columns: [
      { key: 'description', label: 'Description', type: 'text' },
      { key: 'quantity', label: 'Quantity', type: 'number', required: true },
      {
        key: 'lineTotal',
        label: 'Line Total',
        type: 'number',
        inlineFields: [{ key: 'taxAmount', label: 'Tax' }],
      },
    ],
    computeRow: () => ({}),
  }
}

describe('table column signature', () => {
  it('treats an equal-but-new descriptor as unchanged', () => {
    expect(tableColumnSignature(descriptor())).toBe(tableColumnSignature(descriptor()))
  })

  it('ignores property order', () => {
    const reordered: FreightTable = {
      columns: descriptor().columns.map(column => ({ ...column })),
      title: 'Fee lines',
      key: 'feeLines',
      computeRow: descriptor().computeRow,
    }
    expect(tableColumnSignature(reordered)).toBe(tableColumnSignature(descriptor()))
  })

  it('notices a real change in the column shape', () => {
    const changed = descriptor()
    changed.columns = [...changed.columns, { key: 'remark', label: 'Remark', type: 'text' }]
    expect(tableColumnSignature(changed)).not.toBe(tableColumnSignature(descriptor()))
  })

  it('notices a changed label, option list or inline field', () => {
    const relabelled = descriptor()
    relabelled.columns = relabelled.columns.map(column =>
      column.key === 'quantity' ? { ...column, label: 'Qty' } : column)
    expect(tableColumnSignature(relabelled)).not.toBe(tableColumnSignature(descriptor()))

    const withOptions = descriptor()
    withOptions.columns = withOptions.columns.map(column =>
      column.key === 'description' ? { ...column, options: ['A', 'B'] } : column)
    expect(tableColumnSignature(withOptions)).not.toBe(tableColumnSignature(descriptor()))

    const inline = descriptor()
    inline.columns = inline.columns.map(column =>
      column.key === 'lineTotal' ? { ...column, inlineFields: undefined } : column)
    expect(tableColumnSignature(inline)).not.toBe(tableColumnSignature(descriptor()))
  })
})

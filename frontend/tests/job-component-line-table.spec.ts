import { describe, expect, it } from 'vitest'
import {
  componentAttributesToLineTable,
  componentRecordsToLineRows,
  lineRowToComponentValues,
} from '../app/utils/freight/job-component-line-table'

describe('job component line table', () => {
  const attributes = [
    { code: 'invoice_no', label: 'Invoice No.', dataType: 'Text', inputType: 'Text', required: 'Yes', displayOrder: 10 },
    { code: 'invoice_date', label: 'Invoice Date', dataType: 'Date', inputType: 'Date', displayOrder: 20 },
    { code: 'invoice_amount', label: 'Amount', dataType: 'Number', inputType: 'Currency', displayOrder: 30 },
    { code: 'package_lines', label: 'Lines', dataType: 'Table', inputType: 'Table', displayOrder: 40, tableColumns: [{ key: 'description', label: 'Description', type: 'text', order: 1 }] },
  ]

  it('builds scalar attribute columns and skips nested table attributes', () => {
    const table = componentAttributesToLineTable(attributes, 'component-invoice', 'Invoice')
    expect(table?.columns.map(column => column.key)).toEqual([
      'invoice_no',
      'invoice_date',
      'invoice_amount',
      '_status',
    ])
    expect(table?.columns[0]?.type).toBe('text')
    expect(table?.columns[1]?.type).toBe('date')
    expect(table?.columns[2]?.type).toBe('number')
  })

  it('maps component records to editable line rows', () => {
    const rows = componentRecordsToLineRows([
      {
        id: 'cmp-1',
        status: 'PENDING',
        values: [
          { code: 'invoice_no', dataType: 'text', valueText: 'INV-001' },
          { code: 'invoice_date', dataType: 'date', valueDate: '2026-08-30' },
          { code: 'invoice_amount', dataType: 'number', valueNumber: 1200 },
        ],
      },
    ], attributes)
    expect(rows[0]).toMatchObject({
      _componentId: 'cmp-1',
      _status: 'PENDING',
      invoice_no: 'INV-001',
      invoice_date: '2026-08-30',
      invoice_amount: 1200,
    })
  })

  it('converts line rows back to captured component values', () => {
    const values = lineRowToComponentValues({
      invoice_no: 'INV-002',
      invoice_date: '2026-08-31',
      invoice_amount: 500,
    }, attributes)
    expect(values.find(value => value.code === 'invoice_no')?.valueText).toBe('INV-002')
    expect(values.find(value => value.code === 'invoice_date')?.valueDate).toBe('2026-08-31')
    expect(values.find(value => value.code === 'invoice_amount')?.valueNumber).toBe(500)
  })
})

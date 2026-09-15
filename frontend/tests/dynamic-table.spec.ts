import { describe, expect, it } from 'vitest'
import {
  dynamicTableColumnsToFreightTable,
  parseDynamicTableColumns,
  parseDynamicTableRows,
} from '../app/utils/freight/dynamic-table'
import {
  applyTaskValue,
  missingRequiredValues,
  taskValueModel,
  taskValueStorageKey,
  taskValueToDocumentField,
} from '../app/utils/freight/job-task-fields'

describe('dynamic table helpers', () => {
  it('parses column definitions and row arrays', () => {
    const columns = parseDynamicTableColumns([
      { key: 'description', label: 'Description', type: 'text', order: 2 },
      { key: 'qty', label: 'Qty', type: 'number', order: 1 },
    ])
    expect(columns.map(column => column.key)).toEqual(['qty', 'description'])
    expect(parseDynamicTableRows([{ description: 'A', qty: 2 }])).toEqual([{ description: 'A', qty: 2 }])
  })

  it('builds a freight table for AppLineTable', () => {
    const table = dynamicTableColumnsToFreightTable(
      parseDynamicTableColumns([{ key: 'description', label: 'Description', type: 'text', order: 1 }]),
      'package_lines',
      'Package Lines',
    )
    expect(table.key).toBe('package_lines')
    expect(table.columns[0]?.type).toBe('text')
  })
})

describe('job task table fields', () => {
  it('maps table attributes to dynamic-table fields with column metadata', () => {
    const field = taskValueToDocumentField({
      code: 'package_lines',
      label: 'Package Lines',
      dataType: 'Table',
      tableColumns: [{ key: 'description', label: 'Description', type: 'text', order: 1 }],
      helpText: 'Add rows for each package.',
    })
    expect(field.type).toBe('dynamic-table')
    expect(field.colSpan).toBe(2)
    expect(field.meta?.table?.columns).toHaveLength(1)
    expect(taskValueStorageKey({ dataType: 'Table' })).toBe('valueJson')
  })

  it('reads and writes table rows on valueJson', () => {
    const value: Record<string, unknown> = {
      dataType: 'table',
      valueJson: [{ description: 'Line 1', quantity: 2 }],
    }
    expect(taskValueModel(value)).toEqual([{ description: 'Line 1', quantity: 2 }])
    applyTaskValue(value, [{ description: 'Line 2', quantity: 3 }])
    expect(value.valueJson).toEqual([{ description: 'Line 2', quantity: 3 }])
  })

  it('treats required table fields as missing when no rows exist', () => {
    const missing = missingRequiredValues([
      { code: 'lines', dataType: 'table', required: true, valueJson: [] },
      { code: 'notes', dataType: 'text', required: true, valueText: 'ok' },
    ])
    expect(missing.map(value => value.code)).toEqual(['lines'])
  })
})

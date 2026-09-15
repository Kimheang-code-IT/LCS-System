import { describe, expect, it } from 'vitest'
import {
  applyTaskValue,
  taskValueModel,
  taskValueStorageKey,
  taskValueToDocumentField,
  valuesFromTemplateAttributes,
} from '../app/utils/freight/job-task-fields'

describe('job task template fields', () => {
  it('stores values on the typed payload keys', () => {
    expect(taskValueStorageKey({ dataType: 'text' })).toBe('valueText')
    expect(taskValueStorageKey({ dataType: 'Date' })).toBe('valueDate')
    expect(taskValueStorageKey({ dataType: 'integer' })).toBe('valueNumber')
    expect(taskValueStorageKey({ dataType: 'boolean' })).toBe('valueBoolean')
    expect(taskValueStorageKey({ dataType: 'json' })).toBe('valueText')
    expect(taskValueStorageKey({ dataType: 'Table' })).toBe('valueJson')
  })

  it('maps template attributes to document field types without a per-task form', () => {
    expect(taskValueToDocumentField({ code: 'declaration_no', label: 'Declaration No.', dataType: 'text' }).type).toBe('text')
    expect(taskValueToDocumentField({ code: 'cleared_at', dataType: 'date' }).type).toBe('date')
    expect(taskValueToDocumentField({ code: 'qty', dataType: 'Number' }).type).toBe('number')
    expect(taskValueToDocumentField({ code: 'done', dataType: 'boolean' }).type).toBe('boolean')
    expect(taskValueToDocumentField({ code: 'payload', dataType: 'JSON' }).type).toBe('textarea')
    expect(taskValueToDocumentField({
      code: 'package_lines',
      dataType: 'Table',
      tableColumns: [{ key: 'description', label: 'Description', type: 'text', order: 1 }],
    }).type).toBe('dynamic-table')
    expect(taskValueToDocumentField({
      code: 'mode',
      dataType: 'select',
      options: ['Road', 'Sea'],
    }).type).toBe('select')
    expect(taskValueToDocumentField({ code: 'mode', dataType: 'select' }).type).toBe('text')
  })

  it('keeps help text and required from the captured attribute', () => {
    const field = taskValueToDocumentField({
      code: 'truck_no',
      label: 'Truck No.',
      dataType: 'text',
      required: true,
      helpText: 'Transport asset used for this booking.',
    })
    expect(field).toMatchObject({
      key: 'truck_no',
      label: 'Truck No.',
      required: true,
      help: 'Transport asset used for this booking.',
    })
  })

  it('reads and writes the matching storage key', () => {
    const value: Record<string, unknown> = { dataType: 'date', valueDate: '2026-08-20' }
    expect(taskValueModel(value)).toBe('2026-08-20')
    applyTaskValue(value, '2026-08-21')
    expect(value.valueDate).toBe('2026-08-21')
  })

  it('treats Yes/No required flags as booleans and builds values from template attributes', () => {
    expect(taskValueToDocumentField({ code: 'opt', required: 'No', dataType: 'text' }).required).toBe(false)
    expect(taskValueToDocumentField({ code: 'need', required: 'Yes', dataType: 'text' }).required).toBe(true)
    const values = valuesFromTemplateAttributes([
      { code: 'invoice_no', label: 'Invoice No.', dataType: 'Text', required: 'Yes', displayOrder: 10, helpText: 'Commercial invoice number.' },
      { code: 'amount', label: 'Amount', dataType: 'Number', required: 'No', displayOrder: 20 },
    ])
    expect(values.map(value => value.code)).toEqual(['invoice_no', 'amount'])
    expect(values[0]).toMatchObject({ required: true, helpText: 'Commercial invoice number.' })
    expect(values[1]?.required).toBe(false)
  })
})

import { describe, expect, it } from 'vitest'
import {
  blankComponentAttributeRow,
  componentAttributeColumns,
  componentAttributeDataType,
  componentAttributePayload,
  componentAttributeRows,
  componentConfigTable,
  componentGroupAttributeColumns,
  componentGroupAttributeRows,
  componentNeedsOptions,
  componentOptionsText,
  componentReferenceTypeValue,
  componentTabGroupColumns,
  componentTabGroupRows,
  parseComponentOptionsText,
} from '../app/utils/freight/component-config-tables'

describe('component config grid tables', () => {
  it('declares the shared FreightTable contract for each config grid', () => {
    expect(componentConfigTable({
      key: 'componentAttributes',
      title: 'Component Attributes',
      columns: componentAttributeColumns(),
    })).toMatchObject({ key: 'componentAttributes', title: 'Component Attributes' })

    // Config grids own add/delete outside the table, so they declare no add label.
    for (const columns of [componentAttributeColumns(), componentGroupAttributeColumns(), componentTabGroupColumns()]) {
      const table = componentConfigTable({ key: 'x', title: 'X', columns })
      expect(table.addLabel).toBeUndefined()
      expect(table.computeRow).toBeUndefined()
      expect(table.rowDefaults).toBeUndefined()
    }
  })

  it('keeps the attribute grid columns in display order', () => {
    expect(componentAttributeColumns().map(column => column.key)).toEqual([
      'label',
      'code',
      'dataType',
      'referenceType',
      'isRequired',
      'optionsText',
      '_delete',
    ])
    const column = (key: string) => componentAttributeColumns().find(item => item.key === key)
    expect(column('isRequired')?.type).toBe('checkbox')
    expect(column('label')?.required).toBe(true)
  })

  it('orders membership grids by display order and offers reorder plus delete', () => {
    for (const columns of [componentGroupAttributeColumns(), componentTabGroupColumns()]) {
      expect(columns.map(column => column.type)).toContain('reorder')
      expect(columns.map(column => column.type)).toContain('delete')
    }
    expect(componentGroupAttributeColumns().map(column => column.key)).toEqual([
      'label',
      'code',
      'dataType',
      'isRequired',
      '_reorder',
      '_delete',
    ])
    expect(componentTabGroupColumns().map(column => column.key)).toEqual([
      'name',
      'code',
      'renderMode',
      '_reorder',
      '_delete',
    ])
  })

  it('flattens a saved attribute onto the row the grid edits', () => {
    expect(componentAttributeRows([{
      id: 'ca-1',
      code: 'seal_no',
      label: 'Seal No.',
      dataType: 'select',
      referenceType: null,
      isRequired: true,
      options: ['Original', { label: 'Replaced', value: 'Replaced' }],
    } as never])).toEqual([{
      id: 'ca-1',
      label: 'Seal No.',
      code: 'seal_no',
      dataType: 'select',
      referenceType: undefined,
      isRequired: true,
      optionsText: 'Original, Replaced',
    }])
  })

  it('round-trips the options string through the API payload', () => {
    expect(componentOptionsText({ options: ['A', ' B '] } as never)).toBe('A, B')
    expect(parseComponentOptionsText(' Pending , Paid ,, ')).toEqual(['Pending', 'Paid'])
    expect(componentAttributePayload({
      label: '  Status  ',
      code: '',
      dataType: 'select',
      isRequired: false,
      optionsText: 'Pending, Paid',
    }, 'status')).toEqual({
      label: 'Status',
      code: 'status',
      dataType: 'select',
      referenceType: null,
      isRequired: false,
      options: ['Pending', 'Paid'],
    })
  })

  it('drops options and reference when the data type cannot carry them', () => {
    expect(componentNeedsOptions('select')).toBe(true)
    expect(componentNeedsOptions('multi_select')).toBe(true)
    expect(componentNeedsOptions('currency')).toBe(true)
    expect(componentNeedsOptions('text')).toBe(false)

    expect(componentAttributePayload({
      label: 'Seal No.',
      code: 'seal_no',
      dataType: 'text',
      referenceType: 'fee_type',
      optionsText: 'ignored',
    }, 'seal_no')).toMatchObject({ referenceType: null, options: [] })
  })

  it('rejects cell values outside the allowed enums', () => {
    expect(componentAttributeDataType('multi_select')).toBe('multi_select')
    expect(componentAttributeDataType('not_a_type')).toBe('text')
    expect(componentReferenceTypeValue('fee_type')).toBe('fee_type')
    expect(componentReferenceTypeValue('currencies')).toBeNull()
    expect(componentReferenceTypeValue('nonsense')).toBeNull()
  })

  it('keeps the reference type only for reference attributes', () => {
    expect(componentAttributePayload({
      label: 'Currency',
      code: 'currency',
      dataType: 'reference',
      referenceType: 'fee_type',
    }, 'currency').referenceType).toBe('fee_type')
    expect(componentAttributePayload({
      label: 'Currency',
      code: 'currency',
      dataType: 'text',
      referenceType: 'fee_type',
    }, 'currency').referenceType).toBeNull()
  })

  it('starts a new attribute row blank with a text data type', () => {
    expect(blankComponentAttributeRow()).toEqual({
      label: '',
      code: '',
      dataType: 'text',
      referenceType: undefined,
      isRequired: false,
      optionsText: '',
    })
  })

  it('projects membership rows without losing the ids the API needs', () => {
    expect(componentGroupAttributeRows([{
      id: 'cga-1',
      attributeId: 'ca-1',
      code: 'seal_no',
      label: 'Seal No.',
      dataType: 'text',
      isRequired: false,
    } as never])).toEqual([{
      id: 'cga-1',
      attributeId: 'ca-1',
      label: 'Seal No.',
      code: 'seal_no',
      dataType: 'text',
      isRequired: false,
    }])

    // The grid keys rows by group id, while removal uses the tab-group link id.
    expect(componentTabGroupRows([{
      id: 'cg-1',
      tabGroupId: 'ctg-9',
      code: 'docs',
      name: 'Documents',
      renderMode: 'table',
    } as never])).toEqual([{
      id: 'cg-1',
      tabGroupId: 'ctg-9',
      name: 'Documents',
      code: 'docs',
      renderMode: 'table',
    }])
  })
})
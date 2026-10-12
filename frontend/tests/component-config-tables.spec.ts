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
  componentTabGroupColumns,
  componentTabGroupRows,
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
      'dataType',
      'isRequired',
      'helpText',
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
      placeholder: 'Enter the seal number',
      options: ['Original', { label: 'Replaced', value: 'Replaced' }],
    } as never])).toEqual([{
      id: 'ca-1',
      label: 'Seal No.',
      dataType: 'select',
      isRequired: true,
      helpText: 'Enter the seal number',
    }])
  })

  it('maps the help text onto the API placeholder and derives the code from the label', () => {
    expect(componentAttributePayload({
      label: '  Status  ',
      dataType: 'select',
      isRequired: false,
      helpText: ' Shown to the user. ',
    }, 'status')).toEqual({
      label: 'Status',
      code: 'status',
      dataType: 'select',
      isRequired: false,
      placeholder: 'Shown to the user.',
    })
  })

  it('rejects cell values outside the allowed enums', () => {
    expect(componentAttributeDataType('multi_select')).toBe('multi_select')
    expect(componentAttributeDataType('not_a_type')).toBe('text')
  })

  it('starts a new attribute row blank with a text data type', () => {
    expect(blankComponentAttributeRow()).toEqual({
      label: '',
      dataType: 'text',
      isRequired: false,
      helpText: '',
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
import { describe, expect, it } from 'vitest'
import {
  blankComponentAttributeRow,
  componentAttributeColumns,
  componentAttributeDataType,
  componentAttributePayload,
  componentAttributeRows,
  componentConfigTable,
  componentDataTypeItems,
  componentGroupAttributeColumns,
  componentGroupAttributeRows,
  componentTabGroupColumns,
  componentTabGroupRows,
  formatAttributeOptions,
  formatAttributeRules,
  normalizeAttributeCode,
  parseAttributeOptions,
  parseAttributeRules,
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
      '_reorder',
      'label',
      'code',
      'dataType',
      'isRequired',
      'displayOrder',
      'status',
      'options',
      'referenceType',
      'validationRules',
      'helpText',
    ])
    const column = (key: string) => componentAttributeColumns().find(item => item.key === key)
    expect(column('_reorder')?.type).toBe('reorder')
    expect(column('isRequired')?.type).toBe('checkbox')
    expect(column('displayOrder')?.computed).toBe(true)
    expect(column('status')?.computed).toBe(true)
    expect(column('code')?.required).toBe(true)
    expect(column('code')?.rule).toMatchObject({ required: true, maxLength: 64 })
    expect(column('label')?.required).toBe(true)
    expect(column('label')?.rule).toMatchObject({ required: true, maxLength: 255 })
    expect(column('helpText')?.rule).toMatchObject({ maxLength: 255 })
  })

  it('offers every backend data type the dynamic form can render', () => {
    const values = componentDataTypeItems().map(item => item.value)
    for (const type of ['text', 'textarea', 'number', 'integer', 'decimal', 'money', 'currency', 'date', 'datetime', 'select', 'multi_select', 'checkbox', 'boolean', 'reference']) {
      expect(values).toContain(type)
    }
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
      validationRules: { min: 0, pattern: '^[A-Z]+$' },
      displayOrder: 4,
    } as never])).toEqual([{
      id: 'ca-1',
      code: 'seal_no',
      label: 'Seal No.',
      dataType: 'select',
      options: 'Original, Replaced',
      referenceType: '',
      validationRules: 'min=0; pattern=^[A-Z]+$',
      validationRuleExtras: {},
      isRequired: true,
      helpText: 'Enter the seal number',
      displayOrder: 4,
    }])
  })

  it('maps the help text onto the API placeholder and keeps the explicit code', () => {
    expect(componentAttributePayload({
      code: '  status  ',
      label: '  Status  ',
      dataType: 'select',
      options: ' Open, Closed|C ',
      referenceType: '',
      validationRules: 'maxLength=20',
      isRequired: false,
      helpText: ' Shown to the user. ',
    }, 'status')).toEqual({
      label: 'Status',
      code: 'status',
      dataType: 'select',
      isRequired: false,
      placeholder: 'Shown to the user.',
      options: ['Open', { label: 'Closed', value: 'C' }],
      referenceType: null,
      validationRules: { maxLength: 20 },
    })
  })

  it('derives the code from the label when the code cell is blank', () => {
    expect(componentAttributePayload({ label: 'Seal Number', dataType: 'text' }, 'seal-number')).toMatchObject({
      code: 'seal-number',
    })
  })

  it('round-trips static choices and ignores duplicates', () => {
    expect(parseAttributeOptions('Open, Closed|C, Open')).toEqual(['Open', { label: 'Closed', value: 'C' }])
    expect(formatAttributeOptions(['Open', { label: 'Closed', value: 'C' }])).toBe('Open, Closed|C')
  })

  it('preserves validation rule keys the cell does not show', () => {
    const row = componentAttributeRows([{
      id: 'ca-2',
      code: 'legacy-rules',
      label: 'Legacy Rules',
      dataType: 'text',
      isRequired: false,
      validationRules: { required: true, min: 0 },
    } as never])[0]!

    expect(row.validationRules).toBe('min=0')
    expect(row.validationRuleExtras).toEqual({ required: true })
    expect(componentAttributePayload(row, 'legacy-rules').validationRules).toEqual({ required: true, min: 0 })
  })

  it('round-trips validation rules and explains a bad one', () => {
    expect(parseAttributeRules('min=0; max=10; email=true; pattern=^[A-Z]+$')).toEqual({
      rules: { min: 0, max: 10, email: true, pattern: '^[A-Z]+$' },
      error: null,
    })
    expect(formatAttributeRules({ min: 0, max: 10, email: true })).toBe('min=0; max=10; email=true')
    expect(parseAttributeRules('max=1; min=2').error).toBe('min cannot be greater than max.')
    expect(parseAttributeRules('maxLength=2.5').error).toContain('whole number')
    expect(parseAttributeRules('unknown=1').error).toContain('Unknown rule')
    expect(parseAttributeRules('max').error).toContain('key=value')
  })

  it('normalises a code the same way the API does', () => {
    expect(normalizeAttributeCode(' Seal No. ')).toBe('seal-no.')
    expect(normalizeAttributeCode('seal_no')).toBe('seal-no')
  })

  it('rejects cell values outside the allowed enums', () => {
    expect(componentAttributeDataType('multi_select')).toBe('multi_select')
    expect(componentAttributeDataType('integer')).toBe('integer')
    expect(componentAttributeDataType('not_a_type')).toBe('text')
  })

  it('starts a new attribute row blank with a text data type', () => {
    expect(blankComponentAttributeRow()).toEqual({
      code: '',
      label: '',
      dataType: 'text',
      options: '',
      referenceType: '',
      validationRules: '',
      isRequired: false,
      helpText: '',
      displayOrder: 0,
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
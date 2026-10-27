import { describe, expect, it } from 'vitest'
import {
  componentAttributeRule,
  componentCellKey,
  validateComponentRows,
} from '../app/utils/validation/component-rules'
import type { ComponentTabAttribute } from '../app/types/component-config'

function attribute(overrides: Partial<ComponentTabAttribute>): ComponentTabAttribute {
  return {
    id: 'a1',
    code: 'declarationNo',
    label: 'Declaration Number',
    fieldType: 'text',
    isRequired: false,
    sortOrder: 0,
    ...overrides,
  }
}

const group = {
  id: 'group-1',
  attributes: [
    attribute({ code: 'declarationNo', label: 'Declaration Number', isRequired: true, sortOrder: 0 }),
    attribute({ code: 'grossWeight', label: 'Gross Weight', fieldType: 'decimal', sortOrder: 1 }),
    attribute({ code: 'contactEmail', label: 'Contact Email', sortOrder: 2 }),
  ],
}

const label = (attr: ComponentTabAttribute) => attr.label

describe('component attribute rules', () => {
  it('honours the configured required flag', () => {
    expect(componentAttributeRule(attribute({ isRequired: true })).required).toBe(true)
    expect(componentAttributeRule(attribute({ isRequired: false })).required).toBe(false)
  })

  it('reads the conventional admin rule keys', () => {
    expect(componentAttributeRule(attribute({ fieldType: 'decimal', validationRules: { min: 0 } })).min).toBe(0)
    expect(componentAttributeRule(attribute({ validationRules: { maxLength: 30 } })).maxLength).toBe(30)
    expect(componentAttributeRule(attribute({ validationRules: { regex: '^[A-Z]{2}\\d+$' } })).pattern).toBe('^[A-Z]{2}\\d+$')
    expect(componentAttributeRule(attribute({ validationRules: { allowedValues: ['A', 'B'] } })).allowed).toEqual(['A', 'B'])
  })

  it('treats a `number` attribute as a whole number', () => {
    expect(componentAttributeRule(attribute({ fieldType: 'number' })).integer).toBe(true)
    expect(componentAttributeRule(attribute({ fieldType: 'decimal' })).integer).toBe(false)
  })

  it('treats an `integer` attribute as a whole number', () => {
    expect(componentAttributeRule(attribute({ fieldType: 'integer' })).integer).toBe(true)
  })

  it('treats a date attribute as a date', () => {
    expect(componentAttributeRule(attribute({ fieldType: 'date' })).date).toBe(true)
  })

  it('requires dates to be ISO so an unparseable value is caught', () => {
    expect(validateComponentRows({
      group,
      rows: [{ declarationNo: 'x', grossWeight: 1, contactEmail: 'a@b.co', shipDate: '31/12/2026' }],
      label,
    }).filter(failure => failure.code === 'date')).toEqual([])
  })

  it('falls back to the configured options as the allowed set', () => {
    expect(componentAttributeRule(attribute({
      fieldType: 'select',
      options: ['HOLD', 'RELEASED'],
    })).allowed).toEqual(['HOLD', 'RELEASED'])
  })

  it('ignores unknown rule keys instead of rejecting the configuration', () => {
    const rule = componentAttributeRule(attribute({ validationRules: { somethingElse: 'x', minValue: 5 } }))
    expect(rule.min).toBe(5)
    expect(Object.keys(rule)).not.toContain('somethingElse')
  })
})

describe('component group validation', () => {
  it('reports a missing required dynamic field against its stable key', () => {
    const failures = validateComponentRows({
      group,
      rows: [{ declarationNo: '', grossWeight: 10, contactEmail: 'ops@example.com' }],
      label,
    })
    expect(failures).toEqual([
      { code: 'required', key: componentCellKey('group-1', 0, 'declarationNo'), row: 0, label: 'Declaration Number' },
    ])
  })

  it('targets the right row when several rows are present', () => {
    const failures = validateComponentRows({
      group,
      rows: [
        { declarationNo: 'A1', grossWeight: 10, contactEmail: 'ops@example.com' },
        { declarationNo: 'A2', grossWeight: 12, contactEmail: 'ops@example.com' },
        { declarationNo: '', grossWeight: 8, contactEmail: 'ops@example.com' },
      ],
      label,
    })
    expect(failures.map(failure => failure.key)).toEqual(['group-1.2.declarationNo'])
  })

  it('validates every row, not just the first', () => {
    const failures = validateComponentRows({
      group,
      rows: [
        { declarationNo: '', grossWeight: 1, contactEmail: 'bad-email' },
        { declarationNo: '', grossWeight: 1, contactEmail: '' },
      ],
      label,
    })
    expect(failures.map(failure => failure.key).sort())
      .toEqual(['group-1.0.contactEmail', 'group-1.0.declarationNo', 'group-1.1.declarationNo'])
  })

  it('leaves a brand-new empty row alone until it is used', () => {
    const failures = validateComponentRows({
      group,
      rows: [{ declarationNo: '', grossWeight: '', contactEmail: '' }],
      label,
      skipBlankRows: true,
    })
    expect(failures).toEqual([])
  })

  it('still validates a partially filled row', () => {
    const failures = validateComponentRows({
      group,
      rows: [{ declarationNo: 'DEC-1', grossWeight: '', contactEmail: '' }],
      label,
      skipBlankRows: true,
    })
    expect(failures.map(failure => failure.key)).toEqual([])
  })

  it('applies a configured min/max on a numeric dynamic field', () => {
    const strict = {
      id: 'group-2',
      attributes: [
        attribute({
          id: 'a2',
          code: 'netWeight',
          label: 'Net Weight',
          fieldType: 'decimal',
          validationRules: { min: 0 },
        }),
      ],
    }
    expect(validateComponentRows({ group: strict, rows: [{ netWeight: -5 }], label }))
      .toEqual([{ code: 'min', params: { min: 0 }, key: 'group-2.0.netWeight', row: 0, label: 'Net Weight' }])
    expect(validateComponentRows({ group: strict, rows: [{ netWeight: 5 }], label })).toEqual([])
  })
})
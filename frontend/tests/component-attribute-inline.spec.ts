import { describe, expect, it } from 'vitest'
import {
  attributeCellKey,
  attributeFieldIssue,
  attributeFieldPayload,
  attributeFieldValue,
  attributeServerError,
  isAttributeFieldKey,
  sameAttributeFieldValue,
} from '../app/utils/freight/component-attribute-inline'

describe('component attribute inline editing', () => {
  it('addresses a cell by table, row and column', () => {
    expect(attributeCellKey(2, 'helpText')).toBe('componentAttributes.2.helpText')
  })

  it('recognises only the grid columns as editable fields', () => {
    for (const key of ['code', 'label', 'dataType', 'options', 'referenceType', 'validationRules', 'isRequired', 'helpText']) {
      expect(isAttributeFieldKey(key)).toBe(true)
    }
    expect(isAttributeFieldKey('displayOrder')).toBe(false)
  })

  it('sends one trimmed field per PATCH', () => {
    expect(attributeFieldPayload('label', { label: '  Seal No.  ' })).toEqual({ label: 'Seal No.' })
    expect(attributeFieldPayload('helpText', { helpText: '  Enter it  ' })).toEqual({ placeholder: 'Enter it' })
    expect(attributeFieldPayload('isRequired', { isRequired: true })).toEqual({ isRequired: true })
    expect(attributeFieldPayload('dataType', { dataType: 'decimal' })).toEqual({ dataType: 'decimal' })
    expect(attributeFieldPayload('code', { code: '  seal-no  ' })).toEqual({ code: 'seal-no' })
    expect(attributeFieldPayload('options', { options: 'A, B|C' })).toEqual({ options: ['A', { label: 'B', value: 'C' }] })
    expect(attributeFieldPayload('referenceType', { referenceType: 'business_party' })).toEqual({ referenceType: 'business_party' })
    expect(attributeFieldPayload('referenceType', { referenceType: '' })).toEqual({ referenceType: null })
    expect(attributeFieldPayload('validationRules', { validationRules: 'maxLength=20' })).toEqual({ validationRules: { maxLength: 20 } })
  })

  it('falls back to text for an unsupported persisted data type', () => {
    expect(attributeFieldPayload('dataType', { dataType: 'not_a_type' })).toEqual({ dataType: 'text' })
    expect(attributeFieldValue('dataType', { dataType: 'not_a_type' })).toBe('text')
  })

  it('ignores whitespace-only changes and notices a real one', () => {
    expect(sameAttributeFieldValue('label', ' Seal ', 'Seal')).toBe(true)
    expect(sameAttributeFieldValue('label', 'Seal', 'Seal No.')).toBe(false)
    expect(sameAttributeFieldValue('isRequired', true, true)).toBe(true)
    expect(sameAttributeFieldValue('isRequired', true, false)).toBe(false)
  })

  it('requires a non-empty label and caps its length', () => {
    expect(attributeFieldIssue('label', { label: '   ' })?.code).toBe('required')
    expect(attributeFieldIssue('label', { label: 'x'.repeat(256) })?.code).toBe('maxLength')
    expect(attributeFieldIssue('label', { label: 'Seal No.' })).toBeNull()
  })

  it('requires a stable, unique, lower-case code', () => {
    expect(attributeFieldIssue('code', { code: '' })?.code).toBe('required')
    expect(attributeFieldIssue('code', { code: 'Seal No.' })?.code).toBe('pattern')
    expect(attributeFieldIssue('code', { code: 'seal-no' })).toBeNull()
    expect(attributeFieldIssue('code', { code: 'seal_no' })).toBeNull()
    expect(attributeFieldIssue('code', { code: 'seal-no' }, ['seal_no'])?.message)
      .toBe('This code is already used by another attribute.')
  })

  it('requires static choices for a select and a source for a reference', () => {
    expect(attributeFieldIssue('options', { dataType: 'select', options: '' })?.code).toBe('required')
    expect(attributeFieldIssue('options', { dataType: 'select', options: 'Open, Closed' })).toBeNull()
    expect(attributeFieldIssue('options', { dataType: 'text', options: '' })).toBeNull()
    expect(attributeFieldIssue('referenceType', { dataType: 'reference', referenceType: '' })?.code).toBe('required')
    expect(attributeFieldIssue('referenceType', { dataType: 'reference', referenceType: 'business_party' })).toBeNull()
    expect(attributeFieldIssue('referenceType', { dataType: 'text', referenceType: '' })).toBeNull()
  })

  it('explains an unparseable validation rule', () => {
    expect(attributeFieldIssue('validationRules', { validationRules: 'max=1; min=2' })).toMatchObject({
      code: 'custom',
      message: 'min cannot be greater than max.',
    })
    expect(attributeFieldIssue('validationRules', { validationRules: 'maxLength=20' })).toBeNull()
  })

  it('caps Help Text but allows it to be blank', () => {
    expect(attributeFieldIssue('helpText', { helpText: '' })).toBeNull()
    expect(attributeFieldIssue('helpText', { helpText: 'x'.repeat(256) })?.code).toBe('maxLength')
  })

  it('never marks the Required checkbox invalid', () => {
    expect(attributeFieldIssue('isRequired', { isRequired: false })).toBeNull()
    expect(attributeFieldIssue('isRequired', { isRequired: true })).toBeNull()
  })

  it('maps backend code errors onto the Code cell', () => {
    const mapped = attributeServerError({
      status: 409,
      data: {
        code: 'DUPLICATE_ATTRIBUTE_CODE',
        message: 'An attribute with this code already exists.',
        field_errors: { code: 'Already in use' },
        errors: [{ field: 'code', code: 'DUPLICATE', message: 'Already in use' }],
      },
    }, 3)

    expect(mapped.fieldErrors).toEqual({
      'componentAttributes.3.code': 'Already in use',
    })
    expect(mapped.isValidation).toBe(true)
  })

  it('maps placeholder errors onto the Help Text cell', () => {
    const mapped = attributeServerError({
      status: 422,
      data: {
        code: 'VALIDATION_ERROR',
        message: 'The submitted data is invalid.',
        field_errors: { placeholder: 'String should have at most 255 characters' },
        errors: [],
      },
    }, 0)

    expect(mapped.fieldErrors).toEqual({
      'componentAttributes.0.helpText': 'String should have at most 255 characters',
    })
  })

  it('keeps an unmappable refusal at page level', () => {
    const mapped = attributeServerError(new Error('Network down'), 0)
    expect(mapped.fieldErrors).toEqual({})
    expect(mapped.message).toBe('Network down')
    expect(mapped.isValidation).toBe(false)
  })
})

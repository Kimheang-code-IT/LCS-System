import { describe, expect, it } from 'vitest'
import { isBlank, validateFieldValue } from '../app/utils/validation/field-rules'
import {
  failuresToMap,
  inferColumnRule,
  inferFieldRule,
  validateDocumentFields,
  validateDraftFields,
  validateTableRows,
} from '../app/utils/validation/record-validation'

const label = (key: string) => key

describe('field rules', () => {
  it('treats blank values as missing but keeps 0 and false', () => {
    expect(isBlank('')).toBe(true)
    expect(isBlank('   ')).toBe(true)
    expect(isBlank(undefined)).toBe(true)
    expect(isBlank([])).toBe(true)
    expect(isBlank(0)).toBe(false)
    expect(isBlank(false)).toBe(false)
  })

  it('reports required before any other rule', () => {
    expect(validateFieldValue('', { required: true, email: true })).toEqual({ code: 'required' })
    expect(validateFieldValue('', { email: true })).toBeNull()
  })

  it('rejects a malformed email with a dedicated message', () => {
    expect(validateFieldValue('nope', { email: true })).toEqual({ code: 'email' })
    expect(validateFieldValue('ops@example.com', { email: true })).toBeNull()
  })

  it('rejects non-numeric input for numeric rules', () => {
    expect(validateFieldValue('abc', { min: 0 })).toEqual({ code: 'number' })
    expect(validateFieldValue(5, { min: 10 })).toEqual({ code: 'min', params: { min: 10 } })
    expect(validateFieldValue(15, { max: 10 })).toEqual({ code: 'max', params: { max: 10 } })
    expect(validateFieldValue(-1, { nonNegative: true })).toEqual({ code: 'min', params: { min: 0 } })
    expect(validateFieldValue(1.5, { integer: true })).toEqual({ code: 'integer' })
  })

  it('enforces string length and allowed values', () => {
    expect(validateFieldValue('ab', { minLength: 3 })).toEqual({ code: 'minLength', params: { min: 3 } })
    expect(validateFieldValue('abcd', { maxLength: 3 })).toEqual({ code: 'maxLength', params: { max: 3 } })
    expect(validateFieldValue('B', { allowed: ['A', 'C'] })).toEqual({ code: 'allowed' })
    expect(validateFieldValue('A', { allowed: ['A', 'C'] })).toBeNull()
  })

  it('never throws on an admin-supplied pattern', () => {
    expect(validateFieldValue('x', { pattern: '([' })).toBeNull()
    expect(validateFieldValue('abc', { pattern: '^[a-z]+$' })).toBeNull()
    expect(validateFieldValue('ABC', { pattern: '^[a-z]+$' })).toEqual({ code: 'pattern' })
  })

  it('rejects a date that is not ISO shaped', () => {
    expect(validateFieldValue('31/12/2026', { date: true })).toEqual({ code: 'date' })
    expect(validateFieldValue('2026-12-31', { date: true })).toBeNull()
    expect(validateFieldValue('2026-12-31T09:30', { date: true })).toBeNull()
  })

  it('enforces quantity and exchange-rate positivity', () => {
    expect(validateFieldValue(0, { positive: true })).toEqual({ code: 'positive' })
    expect(validateFieldValue(-1, { positive: true })).toEqual({ code: 'positive' })
    expect(validateFieldValue(0.25, { positive: true })).toBeNull()
  })

  it('enforces money precision at the declared scale', () => {
    expect(validateFieldValue('10.12345', { decimalPlaces: 4 })).toEqual({ code: 'decimalPlaces', params: { decimals: 4 } })
    expect(validateFieldValue('10.1200', { decimalPlaces: 4 })).toBeNull()
    expect(validateFieldValue(0.0004, { decimalPlaces: 8 })).toBeNull()
  })

  it('applies the shared password policy', () => {
    expect(validateFieldValue('short', { password: true })).toMatchObject({ code: 'minLength' })
    expect(validateFieldValue('password123', { password: true })).toEqual({ code: 'commonPassword' })
    expect(validateFieldValue('Passw0rd!', { password: true })).toBeNull()
  })
})

describe('rule inference from module metadata', () => {
  it('treats an *email field as an email even when typed as text', () => {
    expect(inferFieldRule({ key: 'email' }).email).toBe(true)
    expect(inferFieldRule({ key: 'contactEmail', required: true })).toMatchObject({ email: true, required: true })
    expect(inferFieldRule({ key: 'customer' }).email).toBeUndefined()
  })

  it('requires dates to parse', () => {
    expect(inferFieldRule({ key: 'date', type: 'date' }).date).toBe(true)
  })

  it('applies the password policy to a password input automatically', () => {
    expect(inferFieldRule({ key: 'password', type: 'password' }).password).toBe(true)
  })

  it('lets an explicit rule override the inferred one', () => {
    expect(inferFieldRule({ key: 'email', rule: { email: false } }).email).toBe(false)
  })

  it('closes the value set of a select column', () => {
    expect(inferColumnRule({ key: 'status', type: 'select', options: ['OPEN', 'CLOSED'] }).allowed).toEqual(['OPEN', 'CLOSED'])
  })
})

describe('document field validation', () => {
  const fields = [
    { key: 'customer', required: true },
    { key: 'email' },
    { key: 'total', type: 'number', computed: true },
    { key: 'password', required: true, createOnly: true },
  ]

  it('reports a missing required field against its own key', () => {
    const failures = validateDocumentFields({ fields, model: {}, isCreate: true, label })
    expect(failures).toEqual([
      { code: 'required', key: 'customer', label: 'customer' },
      { code: 'required', key: 'password', label: 'password' },
    ])
  })

  it('never validates a computed field the user cannot edit', () => {
    expect(validateDocumentFields({ fields, model: {}, isCreate: true, label })
      .some(failure => failure.key === 'total')).toBe(false)
  })

  it('skips a create-only field while editing an existing record', () => {
    const failures = validateDocumentFields({ fields, model: { customer: 'ACME' }, isCreate: false, label })
    expect(failures).toEqual([])
  })

  it('runs a cross-field rule against the whole record', () => {
    const failures = validateDocumentFields({
      fields,
      model: { customer: 'ACME' },
      isCreate: false,
      label,
      formRules: {
        lines: record => (Number(record.total || 0) === 0
          ? { code: 'balanced', key: 'lines', label: 'lines' }
          : null),
      },
    })
    expect(failures).toEqual([{ code: 'balanced', key: 'lines', label: 'lines' }])
  })
})

describe('repeatable table validation', () => {
  const table = {
    key: 'pricingLines',
    columns: [
      { key: 'description', label: 'Description', required: true },
      { key: 'quantity', label: 'Quantity', type: 'number', required: true },
      { key: 'unitPrice', label: 'Unit Price', type: 'number' },
      { key: 'lineTotal', label: 'Line Total', type: 'number', computed: true },
      { key: 'actions', label: '', type: 'action' as const },
    ],
  }

  it('identifies the exact row and column of an invalid cell', () => {
    const failures = validateTableRows({
      table,
      rows: [
        { description: 'Transportation', quantity: 2, unitPrice: 100 },
        { description: 'Handling', quantity: '', unitPrice: 5 },
      ],
      label,
    })
    // quantity is declared number + required: an empty cell is still "required".
    expect(failures).toEqual([
      { code: 'required', key: 'pricingLines.1.quantity', label: 'Quantity', row: 1 },
    ])
  })

  it('ignores utility columns and computed totals', () => {
    const failures = validateTableRows({ table, rows: [{ description: 'x' }], label })
    expect(failures.map(failure => failure.key)).toEqual(['pricingLines.0.quantity'])
  })

  it('rejects a non-numeric value in a number column', () => {
    const failures = validateTableRows({
      table,
      rows: [{ description: 'Handling', quantity: 'two', unitPrice: 5 }],
      label,
    })
    expect(failures).toEqual([{ code: 'number', key: 'pricingLines.0.quantity', label: 'Quantity', row: 0 }])
  })

  it('rejects a negative amount in a column that forbids it', () => {
    const guarded = {
      key: 'lines',
      columns: [{ key: 'amount', label: 'Amount', type: 'number' as const, rule: { nonNegative: true } }],
    }
    expect(validateTableRows({ table: guarded, rows: [{ amount: -1 }], label }))
      .toEqual([{ code: 'min', params: { min: 0 }, key: 'lines.0.amount', label: 'Amount', row: 0 }])
    expect(validateTableRows({ table: guarded, rows: [{ amount: 0 }], label })).toEqual([])
  })

  it('rejects a non-integer value only when the column asks for one', () => {
    const strict = {
      key: 'containers',
      columns: [{ key: 'quantity', label: 'Qty', type: 'number' as const, rule: { integer: true } }],
    }
    expect(validateTableRows({ table: strict, rows: [{ quantity: 1.5 }], label })[0]?.code).toBe('integer')
    expect(validateTableRows({ table: strict, rows: [{ quantity: 2 }], label })).toEqual([])
  })

  it('locates a bad inline sub-cell (discount beside a computed total)', () => {
    const withInline = {
      key: 'lines',
      columns: [{
        key: 'amount',
        label: 'Line Total',
        type: 'number' as const,
        computed: true,
        inlineFields: [{ key: 'discount', label: 'Discount', rule: { nonNegative: true, decimalPlaces: 4 } }],
      }],
    }
    expect(validateTableRows({
      table: withInline,
      rows: [{ amount: 100, discount: -1 }],
      label,
    })).toEqual([{ code: 'min', params: { min: 0 }, key: 'lines.0.discount', label: 'Discount', row: 0 }])
  })

  it('collapses failures into the field-error map used by the renderer', () => {
    const map = failuresToMap(
      validateTableRows({ table, rows: [{ description: '', quantity: 1 }], label }),
      failure => failure.code,
    )
    expect(map).toEqual({ 'pricingLines.0.description': 'required' })
  })
})

describe('draft field validation (dialog forms)', () => {
  const fields = [{ key: 'name', required: true }, { key: 'description' }]

  it('reports the missing required draft field', () => {
    expect(validateDraftFields({ description: 'x' }, fields, label))
      .toEqual([{ code: 'required', key: 'name', label: 'name' }])
  })

  it('accepts a complete draft', () => {
    expect(validateDraftFields({ name: 'Customs', description: 'x' }, fields, label)).toEqual([])
  })
})
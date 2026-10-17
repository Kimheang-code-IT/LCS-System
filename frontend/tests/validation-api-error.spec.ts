import { describe, expect, it } from 'vitest'
import {
  apiErrorMessage,
  describeMessage,
  normalizeApiError,
  sanitizeMessage,
} from '../app/utils/validation/api-error'
import { LcsDomainError } from '../app/utils/freight/errors'

/** Mirrors the envelope FastAPI returns (`backend/app/main.py`). */
function fetchError(status: number, body: unknown) {
  return Object.assign(new Error(`[${status}] request failed`), {
    name: 'FetchError',
    status,
    statusCode: status,
    data: body,
  })
}

describe('sanitizeMessage', () => {
  it('drops Pydantic’s Value error prefix', () => {
    expect(sanitizeMessage('Value error, period is closed')).toBe('period is closed')
  })

  it('keeps only the first line so a stack trace never reaches the UI', () => {
    const raw = 'boom\n  File "x.py", line 1\nKeyError: boom'
    expect(sanitizeMessage(raw)).toBe('boom')
  })

  it('never returns a traceback body', () => {
    expect(sanitizeMessage('Traceback (most recent call last):\n  File "x.py"')).toBe('')
  })

  it('truncates a runaway sentence', () => {
    expect(sanitizeMessage('x'.repeat(400))).toHaveLength(240)
  })
})

describe('describeMessage', () => {
  it('maps Pydantic sentences onto the shared validation vocabulary', () => {
    expect(describeMessage('Field required')).toEqual({ code: 'required' })
    expect(describeMessage('Input should be a valid email address')).toEqual({ code: 'email' })
    expect(describeMessage('Input should be a valid integer')).toEqual({ code: 'integer' })
    expect(describeMessage('String should have at most 40 characters')).toEqual({ code: 'maxLength', params: { max: 40 } })
    expect(describeMessage('Input should be greater than or equal to 0')).toEqual({ code: 'min', params: { min: '0' } })
  })

  it('returns null for a sentence it does not recognise', () => {
    expect(describeMessage('The period is closed')).toBeNull()
  })
})

describe('normalizeApiError — FastAPI validation envelope', () => {
  it('maps a 422 field_errors map onto camelCase model keys', () => {
    const result = normalizeApiError(fetchError(422, {
      code: 'VALIDATION_ERROR',
      message: 'The submitted data is invalid.',
      request_id: 'abc123',
      field_errors: { customer_party_id: 'Field required' },
    }))

    expect(result.status).toBe(422)
    expect(result.requestId).toBe('abc123')
    expect(result.isValidation).toBe(true)
    expect(result.fieldErrors).toEqual({ customerPartyId: 'Field required' })
  })

  it('maps a nested row error to the exact cell', () => {
    const result = normalizeApiError(fetchError(422, {
      code: 'VALIDATION_ERROR',
      message: 'The submitted data is invalid.',
      field_errors: { 'lines.1.amount': 'Input should be greater than or equal to 0' },
    }))

    expect(result.fieldErrors).toEqual({ 'lines.1.amount': 'Input should be greater than or equal to 0' })
  })

  it('understands the raw Pydantic detail array', () => {
    const result = normalizeApiError(fetchError(422, {
      detail: [
        { loc: ['body', 'customer_id'], msg: 'Field required', type: 'missing' },
        { loc: ['body', 'lines', 0, 'amount'], msg: 'Input should be a valid number', type: 'float_parsing' },
      ],
    }))

    expect(result.fieldErrors).toEqual({
      customerId: 'Field required',
      'lines.0.amount': 'Input should be a valid number',
    })
  })

  it('does not repeat the envelope message once errors are on their fields', () => {
    const result = normalizeApiError(fetchError(422, {
      code: 'VALIDATION_ERROR',
      message: 'The submitted data is invalid.',
      field_errors: { date: 'Field required' },
    }))
    expect(result.message).toBe('')
  })

  it('keeps a business-rule message that owns no field', () => {
    const result = normalizeApiError(fetchError(409, {
      code: 'PERIOD_CLOSED',
      message: 'Cannot post to a closed accounting period.',
      field_errors: {},
    }))
    expect(result.message).toBe('Cannot post to a closed accounting period.')
    expect(result.fieldErrors).toEqual({})
  })

  it('reads the LCS domain error thrown by the repository layer', () => {
    const result = normalizeApiError(new LcsDomainError({
      code: 'QUANTITY_EXCEEDED',
      message: 'Allocation cannot exceed the payment.',
      request_id: 'r1',
      field_errors: { amount: 'Allocation cannot exceed the payment.' },
    }))
    expect(result.fieldErrors).toEqual({ amount: 'Allocation cannot exceed the payment.' })
  })

  it('never throws on an unrelated error value', () => {
    expect(normalizeApiError('boom').message).toBe('boom')
    expect(normalizeApiError(new Error('offline')).message).toBe('offline')
  })
})

describe('apiErrorMessage', () => {
  it('prefers the backend sentence and falls back when it is silent', () => {
    expect(apiErrorMessage(fetchError(500, { message: 'Server error' }), 'fallback')).toBe('Server error')
    expect(apiErrorMessage(new Error(''), 'fallback')).toBe('fallback')
  })

  it('summarises a field error when there is no envelope message', () => {
    expect(apiErrorMessage(fetchError(422, { field_errors: { date: 'Field required' } }), 'fallback'))
      .toBe('Field required')
  })
})
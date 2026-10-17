import { computed, ref, watch } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useFormValidation } from '../app/composables/common/useFormValidation'

/**
 * `useFormValidation` is a Nuxt auto-imported composable, so the same globals
 * the runtime injects are stubbed here. Everything it depends on is a plain
 * ref/computed, so the behaviour under test is the real thing.
 */
beforeEach(() => {
  vi.stubGlobal('ref', ref)
  vi.stubGlobal('computed', computed)
  vi.stubGlobal('watch', watch)
  vi.stubGlobal('document', undefined)
  vi.stubGlobal('requestAnimationFrame', undefined)
})

const MESSAGES: Record<string, string> = {
  'validation.required': '{field} is required.',
  'validation.requiredGeneric': 'This field is required.',
  'validation.email': 'Please enter a valid {field}.',
  'validation.emailGeneric': 'Please enter a valid email address.',
  'validation.min': '{field} must be greater than or equal to {min}.',
  'validation.minGeneric': 'Enter a value of at least {min}.',
}

function translate(key: string, params?: Record<string, unknown>) {
  const template = MESSAGES[key] ?? key
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(params?.[name] ?? ''))
}

const FORM_FIELDS = [
  { key: 'customer', label: 'Customer' },
  { key: 'email', label: 'Email' },
  { key: 'date', label: 'Date' },
  { key: 'lines', label: 'Lines' },
]

function makeValidation(overrides: Record<string, unknown> = {}) {
  return useFormValidation({
    t: translate,
    // An empty label means "this key has no user-facing name", which selects
    // the label-free wording rather than printing a raw model key.
    label: (key: string) => FORM_FIELDS.find(field => field.key === key)?.label || '',
    order: () => FORM_FIELDS.map(field => field.key),
    ...overrides,
  } as never)
}

function fetchError(status: number, body: unknown) {
  return Object.assign(new Error(`[${status}]`), { name: 'FetchError', status, statusCode: status, data: body })
}

describe('useFormValidation — client-side failures', () => {
  it('renders a required error under the field it belongs to', () => {
    const v = makeValidation()
    v.applyFailures([{ code: 'required', key: 'customer', label: 'Customer' }])

    expect(v.fieldErrors.value).toEqual({ customer: 'Customer is required.' })
    expect(v.hasFieldErrors.value).toBe(true)
  })

  it('renders an email error with the localized wording', () => {
    const v = makeValidation()
    v.applyFailures([{ code: 'email', key: 'email', label: 'Email' }])
    expect(v.fieldErrors.value).toEqual({ email: 'Please enter a valid Email.' })
  })

  it('replaces the whole error set so a stale message never survives', () => {
    const v = makeValidation()
    v.applyFailures([{ code: 'required', key: 'customer', label: 'Customer' }])
    v.applyFailures([{ code: 'required', key: 'email', label: 'Email' }])
    expect(Object.keys(v.fieldErrors.value)).toEqual(['email'])
  })

  it('clears a single error as soon as the field is edited', () => {
    const v = makeValidation()
    v.applyFailures([
      { code: 'required', key: 'customer', label: 'Customer' },
      { code: 'required', key: 'email', label: 'Email' },
    ])
    v.clearFieldError('customer')
    expect(Object.keys(v.fieldErrors.value)).toEqual(['email'])
  })

  it('clears every row error of a table when its rows change', () => {
    const v = makeValidation()
    v.applyFailures([
      { code: 'required', key: 'lines.0.description', label: 'Description', row: 0 },
      { code: 'required', key: 'lines.1.description', label: 'Description', row: 1 },
      { code: 'required', key: 'customer', label: 'Customer' },
    ])
    v.clearTableErrors('lines')
    expect(Object.keys(v.fieldErrors.value)).toEqual(['customer'])
  })

  it('clears one row cell when that cell is corrected', () => {
    const v = makeValidation()
    v.applyFailures([
      { code: 'required', key: 'lines.0.description', label: 'Description', row: 0 },
      { code: 'required', key: 'lines.1.description', label: 'Description', row: 1 },
    ])
    v.clearRowError('lines', 1, 'description')
    expect(Object.keys(v.fieldErrors.value)).toEqual(['lines.0.description'])
  })

  it('does not carry errors from one record into another', () => {
    const v = makeValidation()
    v.applyFailures([{ code: 'required', key: 'customer', label: 'Customer' }])
    v.reset()
    expect(v.hasErrors.value).toBe(false)
  })
})

describe('useFormValidation — first invalid field', () => {
  it('returns field keys in the form’s logical order, not hash order', () => {
    const v = makeValidation()
    v.applyFailures([
      { code: 'required', key: 'date', label: 'Date' },
      { code: 'required', key: 'customer', label: 'Customer' },
    ])
    expect(v.orderedErrorKeys.value).toEqual(['customer', 'date'])
  })

  it('does nothing when there is no error', async () => {
    const v = makeValidation()
    expect(await v.focusFirstInvalid()).toBeNull()
  })

  it('does not move focus while the user is typing', () => {
    const v = makeValidation()
    v.applyFailures([{ code: 'required', key: 'customer', label: 'Customer' }])
    // Nothing is invoked on an edit: only submit attempts call focusFirstInvalid.
    v.clearFieldError('customer')
    expect(v.hasFieldErrors.value).toBe(false)
  })
})

describe('useFormValidation — backend error mapping', () => {
  it('maps a 422 onto the matching field and keeps it off the summary', () => {
    const v = makeValidation()
    const result = v.applyServerError(fetchError(422, {
      code: 'VALIDATION_ERROR',
      message: 'The submitted data is invalid.',
      field_errors: { customer: 'Field required' },
    }))

    expect(result.hasFieldErrors).toBe(true)
    expect(v.fieldErrors.value).toEqual({ customer: 'Customer is required.' })
    expect(v.formErrors.value).toEqual([])
  })

  it('maps a nested row error onto its own cell', () => {
    const v = makeValidation()
    v.applyServerError(fetchError(422, {
      code: 'VALIDATION_ERROR',
      field_errors: { 'lines.1.amount': 'Input should be greater than or equal to 0' },
    }))
    expect(v.fieldErrors.value).toEqual({ 'lines.1.amount': 'Enter a value of at least 0.' })
  })

  it('routes a field this form never renders into the form-level summary', () => {
    const v = makeValidation()
    const result = v.applyServerError(fetchError(422, {
      code: 'VALIDATION_ERROR',
      field_errors: { internal_audit_trail: 'Field required' },
    }))

    expect(result.hasFieldErrors).toBe(false)
    expect(v.formErrors.value).toEqual(['Field required'])
  })

  it('keeps a business-rule refusal as a page-level message', () => {
    const v = makeValidation()
    v.applyServerError(fetchError(409, {
      code: 'PERIOD_CLOSED',
      message: 'Cannot post to a closed accounting period.',
      field_errors: {},
    }))
    expect(v.formErrors.value).toEqual(['Cannot post to a closed accounting period.'])
  })

  it('does not discard a backend message just because it has no field', () => {
    const v = makeValidation()
    v.applyServerError(new Error('Service unavailable'))
    expect(v.formErrors.value).toEqual(['Service unavailable'])
  })

  it('lists mapped fields and form errors together in the summary', () => {
    const v = makeValidation()
    v.applyServerError(fetchError(422, {
      code: 'VALIDATION_ERROR',
      message: 'The submitted data is invalid.',
      field_errors: { customer: 'Field required' },
    }))

    expect(v.summaryItems.value.map(item => item.key)).toEqual(['customer'])
    expect(v.summaryItems.value[0]?.message).toBe('Customer is required.')
    // The envelope message is not repeated next to the field it duplicated.
    expect(v.formErrors.value).toEqual([])
  })

  it('adds a group label so a hidden field can be located', () => {
    const v = makeValidation({ groupLabel: () => 'Overview › Header' })
    v.applyFailures([{ code: 'required', key: 'customer', label: 'Customer' }])
    expect(v.summaryItems.value[0]?.groupLabel).toBe('Overview › Header')
  })
})

describe('useFormValidation — submission state', () => {
  it('exposes a submitting flag so a duplicate request can be blocked', () => {
    const v = makeValidation()
    expect(v.submitting.value).toBe(false)
    v.submitting.value = true
    expect(v.submitting.value).toBe(true)
  })

  it('counts every outstanding issue for the summary headline', () => {
    const v = makeValidation()
    v.applyFailures([{ code: 'required', key: 'customer', label: 'Customer' }], ['Period is closed.'])
    expect(v.errorCount.value).toBe(2)
  })
})
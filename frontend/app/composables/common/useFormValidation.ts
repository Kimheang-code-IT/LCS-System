import type { ValidationFailure, ValidationIssue } from '~/utils/validation/field-rules'
import { issueFromBackendMessage } from '~/utils/validation/field-rules'
import { normalizeApiError } from '~/utils/validation/api-error'
import { matchesRegisteredKey, parseRowKey } from '~/utils/validation/error-paths'
import { failuresToMap } from '~/utils/validation/record-validation'
import { failureMessage, formErrorMessage } from '~/utils/validation/messages'
import type { RevealField } from '~/utils/validation/focus'
import { focusFirstInvalidField } from '~/utils/validation/focus'

export type UseFormValidationOptions = {
  /** Translates `validation.*` copy and field labels. */
  t?: (key: string, params?: Record<string, unknown>) => string
  /** Resolves the display label for a field key (already localized). */
  label?: (key: string) => string
  /**
   * Model keys in logical (document) order. Drives "first invalid field", so it
   * must follow the tab → section → field order rather than a hash map.
   */
  order?: () => string[]
  /** Opens the tab/section/dialog that owns a key before it is focused. */
  reveal?: RevealField
}

export type ApplyServerErrorResult = {
  /** At least one message landed on a field. */
  hasFieldErrors: boolean
  /** Messages no field could take, rendered as a slim form-level line. */
  formErrors: string[]
  /** Field keys, in logical order, that now carry an error. */
  keys: string[]
  /** HTTP status, when the failure came from the network layer. */
  status?: number
}

/**
 * Shared validation state for every form in the app.
 *
 * Owns the three error buckets (field / row cell / form level), the
 * translation of issues into copy, the mapping of backend failures onto
 * fields, and first-invalid-field navigation. A form supplies only its field
 * order, its labels and a way to reveal a hidden section — it never writes
 * validation logic of its own.
 */
export function useFormValidation(options: UseFormValidationOptions = {}) {
  const t = options.t ?? ((key: string) => key)
  const label = options.label ?? ((key: string) => key)
  const order = options.order ?? (() => Object.keys(fieldErrors.value))

  /** key -> ready-to-render message. Row cells use `table.<index>.<column>`. */
  const fieldErrors = ref<Record<string, string>>({})
  /** Page/form-level messages that cannot be attached to a single input. */
  const formErrors = ref<string[]>([])
  /** True while a submit attempt is being validated or awaited. */
  const submitting = ref(false)
  /** Bumped whenever a new error set lands, so effects can react once. */
  const revision = ref(0)

  const hasFieldErrors = computed(() => Object.keys(fieldErrors.value).length > 0)
  const hasErrors = computed(() => hasFieldErrors.value || formErrors.value.length > 0)
  const errorCount = computed(() => Object.keys(fieldErrors.value).length + formErrors.value.length)

  /** Field keys in logical form order, restricted to those that failed. */
  const orderedErrorKeys = computed(() => {
    const rank = new Map<string, number>()
    order().forEach((key, index) => rank.set(key, index))
    return Object.keys(fieldErrors.value)
      .filter(key => fieldErrors.value[key])
      .sort((a, b) => (rank.get(a) ?? Number.MAX_SAFE_INTEGER) - (rank.get(b) ?? Number.MAX_SAFE_INTEGER))
  })

  function reset() {
    fieldErrors.value = {}
    formErrors.value = []
  }

  function setFieldError(key: string, message: string) {
    if (!key) return
    fieldErrors.value = { ...fieldErrors.value, [key]: message }
  }

  /** Drop a single error. Called whenever the user edits the offending field. */
  function clearFieldError(key: string) {
    if (!fieldErrors.value[key]) return
    const next: Record<string, string> = {}
    for (const [existing, message] of Object.entries(fieldErrors.value)) {
      if (existing !== key) next[existing] = message
    }
    fieldErrors.value = next
  }

  /** Clear one row cell, e.g. after the cell was corrected. */
  function clearRowError(table: string, index: number, column: string) {
    clearFieldError(`${table}.${index}.${column}`)
  }

  /** Clear every error inside one repeatable table (after add/remove/reorder). */
  function clearTableErrors(table: string) {
    const entries = Object.entries(fieldErrors.value)
    const remaining = entries.filter(([key]) => parseRowKey(key)?.table !== table && key !== table)
    if (remaining.length === entries.length) return
    fieldErrors.value = Object.fromEntries(remaining)
  }

  /** Clear every error under a key prefix (a tab, or a record switch). */
  function clearErrorsUnder(prefix: string) {
    const entries = Object.entries(fieldErrors.value)
    const remaining = entries.filter(([key]) => !key.startsWith(prefix))
    if (remaining.length === entries.length) return
    fieldErrors.value = Object.fromEntries(remaining)
  }

  function addFormError(message: string) {
    const text = String(message || '').trim()
    if (text && !formErrors.value.includes(text)) formErrors.value = [...formErrors.value, text]
  }

  /**
   * Replace the whole error set. Stale errors always disappear: a fresh
   * validation pass must not leave yesterday's message on screen.
   */
  function setErrors(errors: Record<string, string>, formLevel: string[] = []) {
    fieldErrors.value = { ...errors }
    formErrors.value = formLevel.filter(Boolean)
    revision.value += 1
  }

  /** Render client-side failures (field, row and form level) in one pass. */
  function applyFailures(failures: readonly ValidationFailure[], formLevel: string[] = []) {
    setErrors(failuresToMap(failures, failure => failureMessage(t, failure)), formLevel)
    return hasFieldErrors.value
  }

  /** True when `key` (or one of its ancestors) is a field of this form. */
  function belongsToForm(registered: readonly string[], key: string): boolean {
    const parent = key.split('.')[0]!
    return registered.includes(key)
      || registered.includes(parent)
      || registered.some(candidate => candidate === parent || candidate.startsWith(`${parent}.`) || key.startsWith(`${candidate}.`))
  }

  /**
   * Re-word a backend sentence through the shared vocabulary so a server-side
   * "Field required" reads exactly like the client-side one, naming the same
   * field. A host resolver that returns an empty label means "I could not name
   * this key", which selects the label-free wording so a raw model key is never
   * shown to a user. Unrecognised sentences are shown as the backend wrote them
   * (already sanitised, so no status code or stack trace leaks).
   */
  function describeBackend(message: string, key?: string): string {
    const issue = issueFromBackendMessage(message)
    if (!issue) return message
    return failureMessage(t, { ...issue, label: key ? label(key) : '' })
  }

  /**
   * Map a rejected request onto fields.
   *
   * Nested `lines.1.amount` paths reach the right cell, an error for a key this
   * form never renders becomes a form-level message, and nothing is discarded.
   */
  function applyServerError(error: unknown): ApplyServerErrorResult {
    const normalized = normalizeApiError(error)
    const registered = order()
    const errors: Record<string, string> = {}
    const formLevel: string[] = []

    for (const item of normalized.items) {
      const owner = item.key ? matchesRegisteredKey(item.key, registered) : null
      if (owner) {
        // A cell error stays on its own key: the owner only proves the table
        // (or field) exists, it does not widen the message.
        if (!(item.key in errors)) errors[item.key] = describeBackend(item.message, item.key)
        continue
      }
      if (!item.key || !belongsToForm(registered, item.key)) {
        formLevel.push(item.message)
        continue
      }
      if (!(item.key in errors)) errors[item.key] = describeBackend(item.message, item.key)
    }

    if (normalized.message) formLevel.push(normalized.message)
    setErrors(errors, formLevel)
    return {
      hasFieldErrors: hasFieldErrors.value,
      formErrors: formErrors.value,
      keys: orderedErrorKeys.value,
      status: normalized.status,
    }
  }

  /**
   * Scroll to and focus the first invalid field, opening the tab/section that
   * owns it. Only called on an explicit submit attempt or after the backend
   * rejected the payload — never while the user is typing.
   */
  async function focusFirstInvalid() {
    if (!hasFieldErrors.value) return null
    return focusFirstInvalidField(orderedErrorKeys.value, options.reveal)
  }

  return {
    // state
    fieldErrors,
    formErrors,
    submitting,
    revision,
    hasFieldErrors,
    hasErrors,
    errorCount,
    orderedErrorKeys,
    // actions
    reset,
    setFieldError,
    clearFieldError,
    clearRowError,
    clearTableErrors,
    clearErrorsUnder,
    addFormError,
    setErrors,
    applyFailures,
    applyServerError,
    focusFirstInvalid,
    // helpers
    label,
    message: (issue: ValidationIssue, fieldLabel?: string) =>
      failureMessage(t, { ...issue, label: fieldLabel ?? label('') }),
    formMessage: (raw?: string) => formErrorMessage(t, raw),
  }
}
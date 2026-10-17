/**
 * Turn a {@link ValidationIssue} into localized copy.
 *
 * Messages are short, actionable and never mention internal field names, so
 * `customer_id` reaches the user as "Please select a customer.". A rule that
 * already carries finished wording (a backend sentence, a bespoke business
 * rule) is returned untouched.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

import type { ValidationIssue } from './field-rules'

export type Translate = (key: string, params?: Record<string, unknown>) => string

/** Keys live under `validation.*` in every shipped locale bundle. */
export const ISSUE_KEYS: Record<string, string> = {
  required: 'validation.required',
  email: 'validation.email',
  url: 'validation.url',
  number: 'validation.number',
  integer: 'validation.integer',
  boolean: 'validation.boolean',
  date: 'validation.date',
  min: 'validation.min',
  max: 'validation.max',
  minLength: 'validation.minLength',
  maxLength: 'validation.maxLength',
  pattern: 'validation.pattern',
  allowed: 'validation.allowed',
  balanced: 'validation.balanced',
  commonPassword: 'validation.commonPassword',
}

/**
 * Compose the message for one issue.
 *
 * `label` is the already-translated field label; when it is missing the
 * label-free variant of the message is used so no raw key leaks into the UI.
 * `balanced` is the one rule whose wording states the rule itself, so it has
 * no label variant.
 */
export function issueMessage(
  t: Translate,
  issue: ValidationIssue | undefined,
  label?: string,
): string {
  if (!issue) return ''
  if (issue.message && issue.code === 'custom') return issue.message

  const key = ISSUE_KEYS[issue.code]
  if (!key) return ''
  if (issue.code === 'balanced') return t(key, { ...(issue.params || {}) })
  const params = { ...(issue.params || {}), field: label || '' }
  return label ? t(key, params) : t(`${key}Generic`, params)
}

/** Message for a field-level failure (issue + resolved label). */
export function failureMessage(
  t: Translate,
  failure: ValidationIssue & { label?: string },
): string {
  if (failure.code === 'custom' && failure.message) return failure.message
  // `balanced` states the rule itself, so it never takes a field name.
  if (failure.code === 'balanced') return t('validation.balanced')
  return issueMessage(t, failure, failure.label)
}

/**
 * Page-level wording for a request the backend refused for a non-field reason.
 * Never shows a status code or a stack trace.
 */
export function formErrorMessage(t: Translate, raw?: string): string {
  const detail = String(raw || '').trim()
  if (!detail) return t('validation.formError')
  return detail
}
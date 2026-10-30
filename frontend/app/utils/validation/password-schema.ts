/**
 * Zod rule for a new-password field, so every form applies the same policy.
 *
 * The message comes from the shared validator (`validatePasswordStrength`), not
 * from a second per-page regex: a rule can then never differ between the setup,
 * change-password and profile forms. `label` names the field in locales whose
 * message templates include `{field}`.
 */
import * as z from 'zod'
import { PASSWORD_MAX_LENGTH, validatePasswordStrength } from './field-rules'
import { issueMessage, type Translate } from './messages'

/** First password-policy problem as a ready-to-render message, or '' when strong. */
export function passwordIssueMessage(t: Translate, value: string, label?: string): string {
  return issueMessage(t, validatePasswordStrength(String(value ?? '')) ?? undefined, label)
}

/**
 * Cheap syntactic gate for a *disabled submit button*, not a validation
 * decision: the form's `z.email()` schema remains the authority on submit. It
 * matches the backend's pre-validation gate (a non-whitespace email with one
 * `@`), so a syntactically odd but deliverable address can still reach it.
 */
export function isEmailLike(value: string): boolean {
  return /^[^\s@]+@[^\s@]+$/.test(String(value ?? '').trim())
}

/**
 * What the confirmation field should say right now.
 *
 * `match` → green check-circle + confirmation copy; `mismatch` → red message;
 * `''` → stay quiet (untouched field, or the confirmation agrees with a
 * password the policy still refuses, which the checklist already marks).
 */
export function passwordConfirmationState(
  password: string,
  confirmation: string,
  touched = true,
): 'match' | 'mismatch' | '' {
  const field = String(confirmation ?? '')
  if (!field) return ''
  if (field !== String(password ?? '')) return touched ? 'mismatch' : ''
  if (validatePasswordStrength(password) || !touched) return ''
  return 'match'
}

export function strongPasswordSchema(t: Translate, label: string, maxMessage?: string) {
  const schema = z
    .string()
    .max(PASSWORD_MAX_LENGTH, { error: maxMessage || t('validation.maxLength', { field: label, maxLength: PASSWORD_MAX_LENGTH }) })
  return schema.superRefine((value, ctx) => {
    const issue = validatePasswordStrength(value)
    if (issue) ctx.addIssue({ code: 'custom', message: issueMessage(t, issue, label) })
  })
}

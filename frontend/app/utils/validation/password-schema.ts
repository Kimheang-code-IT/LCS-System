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

/** The first password-policy problem as a ready-to-render message, or '' when strong. */
export function passwordIssueMessage(t: Translate, value: string, label?: string): string {
  return issueMessage(t, validatePasswordStrength(String(value ?? '')) ?? undefined, label)
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

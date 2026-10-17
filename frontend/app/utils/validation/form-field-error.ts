/**
 * Normalises validation messages for the `UFormField.error` prop.
 *
 * `UFormField` declares `error: [Boolean, String]`, and Vue casts an **empty
 * string** to `true` when the Boolean type is declared before String. Passing
 * `''` for a field that has no error therefore marks every field invalid: the
 * control renders with the error ring/outline and `aria-invalid="true"`, while
 * no message is shown because nothing is rendered for a Boolean error.
 *
 * "No error" must always be `undefined`, never `''`.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

/** Message stored for `key`, or `undefined` when the field has none. */
export function formFieldError(
  errors: Record<string, string> | null | undefined,
  key: string,
): string | undefined {
  return errors?.[key] || undefined
}

/** Same normalisation for a message held in its own ref/computed. */
export function fieldErrorMessage(value: string | null | undefined): string | undefined {
  return value || undefined
}

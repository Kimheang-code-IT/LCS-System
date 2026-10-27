import { validateFieldValue, type ValidationFailure } from '~/utils/validation/field-rules'

/** Fragments never enter HTTP requests. Consume once and keep the token in memory. */
export function takeRecoveryToken(location: Pick<Location, 'hash' | 'pathname' | 'search'>, history: Pick<History, 'replaceState'>): string {
  const token = new URLSearchParams(location.hash.slice(1)).get('token') || ''
  history.replaceState(null, '', location.pathname + location.search)
  return /^[A-Za-z0-9_-]{40,128}$/.test(token) ? token : ''
}

export function validateRecoveryForm(values: { identifier?: string, password?: string, passwordConfirmation?: string }, label: (key: string) => string): ValidationFailure[] {
  const failures: ValidationFailure[] = []
  for (const key of ['identifier', 'password', 'passwordConfirmation'] as const) {
    if (!(key in values)) continue
    const issue = validateFieldValue(values[key], { required: true, maxLength: key === 'identifier' ? 255 : 128, password: key === 'password' })
    if (issue) failures.push({ key, label: label(key), ...issue })
  }
  if (values.password !== undefined && values.passwordConfirmation !== values.password) {
    failures.push({ key: 'passwordConfirmation', label: label('passwordConfirmation'), code: 'custom', message: label('passwordMismatch') })
  }
  return failures
}

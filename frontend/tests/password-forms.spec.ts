import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import { validateRecoveryForm } from '../app/utils/auth/recovery'
import { issueFromBackendMessage, validatePasswordStrength } from '../app/utils/validation/field-rules'
import { validateDocumentFields } from '../app/utils/validation/record-validation'
import { passwordIssueMessage } from '../app/utils/validation/password-schema'

/**
 * Every new-password form, checked where a unit test can reach it.
 *
 * The components are Vue files with no Nuxt runtime in this suite, so the parts
 * that matter are asserted statically (the checklist is rendered, submission is
 * gated) and the rules themselves are exercised through the same shared
 * validator the forms call. The users form is checked through its real module
 * metadata and the shared submit validator.
 */

const source = (relative: string) =>
  readFileSync(fileURLToPath(new URL(`../app/${relative}`, import.meta.url)), 'utf8')

const PASSWORD_FORMS = [
  'pages/auth/setup.vue',
  'pages/auth/change-password.vue',
  'pages/auth/reset-password.vue',
  'components/freight/UserPasswordDialog.vue',
  'components/layout/AppUserProfileDialog.vue',
  'components/document/AppFieldGrid.vue',
]

// The create-user form's save button lives in the document chrome, not the grid.
const SUBMIT_GATES = [
  ...PASSWORD_FORMS.filter(file => file !== 'components/document/AppFieldGrid.vue'),
  'components/freight/DocumentView.vue',
]

const WEAK_PASSWORDS = ['abc@1234', 'ABC@1234', 'Abcd@efg', 'Abcd1234', 'Ab@123']

describe('every password form', () => {
  it.each(PASSWORD_FORMS)('%s shows the live requirement checklist', (file) => {
    expect(source(file)).toContain('<CommonAppPasswordRequirements')
  })

  it.each(SUBMIT_GATES)('%s disables submission until the password passes', (file) => {
    const text = source(file)
    // The gate is the same predicate the checklist renders, so a button can
    // never look enabled for a password the list still marks unsatisfied.
    expect(text).toMatch(/!passwordsValid|!passwordValid|!validatePasswordStrength/)
    expect(text).toMatch(/(?:disabled:\s*[^,\n]*(?:passwordsValid|passwordValid)|:disabled="[^"]*(?:passwordsValid|passwordValid)|:can-save="canSave")/)
  })

  it('keeps the login form out of the policy so a legacy password still signs in', () => {
    const login = source('pages/auth/login.vue')
    expect(login).not.toContain('validatePasswordStrength')
    expect(login).not.toContain('CommonAppPasswordRequirements')
  })
})

describe('the disabled save button shows its reason under the password field', () => {
  // A disabled submit button runs no validation, so the policy message must be
  // rendered live (red text under the field) instead of waiting for a submit
  // that can never happen in that state.
  it('the shared helper turns the first policy issue into a message', () => {
    const t = (key: string) => key
    expect(passwordIssueMessage(t, 'Admin@12345', 'Password')).toBe('')
    expect(passwordIssueMessage(t, 'short', 'Password')).toContain('passwordMinLength')
  })

  it.each([
    'pages/auth/setup.vue',
    'pages/auth/change-password.vue',
    'components/freight/UserPasswordDialog.vue',
  ])('%s renders password policy errors under the field while typing', (file) => {
    const text = source(file)
    expect(text).toContain('passwordIssueMessage')
    expect(text).toMatch(/role="alert"/)
  })

  it('the mismatch message is also live on the confirmation field', () => {
    for (const file of ['pages/auth/setup.vue', 'pages/auth/change-password.vue']) {
      expect(source(file)).toContain('passwordConfirmation-help')
      expect(source(file)).toContain('passwordMismatch')
    }
  })
})

describe('the create-user form', () => {
  const users = getFreightModule('/administration/users')
  if (!users) throw new Error('users module is missing')

  const model = (password: string) => ({
    username: 'policy.user',
    displayName: 'Policy User',
    email: 'policy.user@example.com',
    status: 'Active',
    role: 'AUDITOR',
    password,
  })
  const failures = (password: string) =>
    validateDocumentFields({
      fields: users.fields,
      model: model(password),
      isCreate: true,
      label: key => key,
    }).filter(failure => failure.key === 'password')

  it('accepts a compliant password', () => {
    expect(failures('Freight#2026')).toEqual([])
  })

  it.each(WEAK_PASSWORDS)('refuses %s before the save can run', (password) => {
    expect(failures(password).length, password).toBe(1)
  })
})

describe('confirm password', () => {
  it('rejects a mismatch through the shared recovery form', () => {
    const failures = validateRecoveryForm(
      { password: 'Freight#2026', passwordConfirmation: 'Freight#2027' },
      key => key,
    )
    expect(failures.map(failure => failure.key)).toContain('passwordConfirmation')
    expect(failures.find(failure => failure.key === 'passwordConfirmation')?.message).toBe('passwordMismatch')
  })

  it('accepts a matching pair', () => {
    expect(validateRecoveryForm(
      { password: 'Freight#2026', passwordConfirmation: 'Freight#2026' },
      key => key,
    )).toEqual([])
  })
})

describe('backend refusals', () => {
  it.each([
    ['Password must contain at least 8 characters.', 'passwordMinLength'],
    ['Password must contain at least one uppercase letter.', 'passwordUppercase'],
    ['Password must contain at least one lowercase letter.', 'passwordLowercase'],
    ['Password must contain at least one number.', 'passwordNumber'],
    ['Password must contain at least one special character.', 'passwordSpecial'],
    ['Password is too common.', 'commonPassword'],
  ])('maps "%s" onto the shared %s rule', (message, code) => {
    expect(issueFromBackendMessage(message)).toMatchObject({ code })
  })

  it('still renders an unmapped server sentence as-is', () => {
    expect(issueFromBackendMessage('Current password is incorrect.')).toBeNull()
  })
})

describe('the shared rule', () => {
  it('is the one the checklist reads', () => {
    for (const password of WEAK_PASSWORDS) {
      expect(validatePasswordStrength(password), password).not.toBeNull()
    }
    expect(validatePasswordStrength('Admin@12345')).toBeNull()
  })
})

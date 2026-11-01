import { describe, expect, it } from 'vitest'
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  generateStrongPassword,
  passwordRequirements,
  validatePasswordStrength,
} from '../app/utils/validation/field-rules'
import { issueMessage, ISSUE_KEYS } from '../app/utils/validation/messages'
import { isEmailLike, passwordConfirmationState } from '../app/utils/validation/password-schema'
import { compactAuthUser } from '../app/utils/auth/session'

/**
 * The password policy is mirrored from the backend (`app/core/security.py`).
 * A mismatch is a bad experience rather than a hole — the server validates every
 * password it is given — but it means the same password passes here and is
 * refused there, so the constants and the common-password list are pinned.
 */
describe('password policy', () => {
  it('mirrors the backend minimum and maximum', () => {
    expect(PASSWORD_MIN_LENGTH).toBe(8)
    expect(PASSWORD_MAX_LENGTH).toBe(128)
  })

  it('refuses a password below the minimum', () => {
    const issue = validatePasswordStrength('short')
    expect(issue).toEqual({ code: 'passwordMinLength', params: { minLength: PASSWORD_MIN_LENGTH } })
  })

  it('refuses a password missing any required character class', () => {
    // The five approved requirements, each proved independently.
    expect(validatePasswordStrength('abc@1234')).toEqual({ code: 'passwordUppercase' })
    expect(validatePasswordStrength('ABC@1234')).toEqual({ code: 'passwordLowercase' })
    expect(validatePasswordStrength('Abcd@efg')).toEqual({ code: 'passwordNumber' })
    expect(validatePasswordStrength('Abcd1234')).toEqual({ code: 'passwordSpecial' })
    expect(validatePasswordStrength('Ab@123')).toMatchObject({ code: 'passwordMinLength' })
  })

  it('accepts the approved example passwords and longer passphrases', () => {
    for (const password of ['Abc@1234', 'Freight#2026', 'Admin@12345']) {
      expect(validatePasswordStrength(password), password).toBeNull()
    }
    // Length is a floor, not a fixed size.
    expect(validatePasswordStrength('Freight-Forwarding-2026!')).toBeNull()
    expect(validatePasswordStrength('Correct Horse Battery 2026!')).toBeNull()
  })

  it('reports one requirement at a time through the live checklist state', () => {
    expect(passwordRequirements('Ab@123')).toMatchObject({
      minLength: false,
      uppercase: true,
      lowercase: true,
      number: true,
      special: true,
    })
    const complete = passwordRequirements('Abc@1234')
    expect(Object.values(complete).every(Boolean)).toBe(true)
  })

  it('keeps a rule neutral while its class is missing, green only when met', () => {
    // 4-row matrix: each row flips exactly one requirement.
    expect(passwordRequirements('ab!123xy')).toMatchObject({ uppercase: false, lowercase: true, number: true, special: true })
    expect(passwordRequirements('AB!123XY')).toMatchObject({ lowercase: false, uppercase: true, number: true, special: true })
    expect(passwordRequirements('Ab!awxyz')).toMatchObject({ number: false, uppercase: true, lowercase: true, special: true })
    expect(passwordRequirements('Abc123xy')).toMatchObject({ special: false, uppercase: true, lowercase: true })
    expect(passwordRequirements('Abc@1234')).toMatchObject({
      minLength: true,
      uppercase: true,
      lowercase: true,
      number: true,
      special: true,
    })
  })

  it('never reports a match for an empty or unconfirmed confirmation field', () => {
    expect(passwordConfirmationState('Abc@1234', '')).toBe('')
    expect(passwordConfirmationState('Abc@1234', '')).not.toBe('match')
  })

  it('reports the confirmation as matching only with a strong password', () => {
    expect(passwordConfirmationState('Abc@1234', 'Abc@1234')).toBe('match')
    expect(passwordConfirmationState('Abc@1234', 'Abc@1234', false)).toBe('')
    // A confirmation that agrees with a weak password must stay silent - the
    // checklist, not the confirmation, owns that message.
    expect(passwordConfirmationState('weakpass', 'weakpass')).toBe('')
  })

  it('reports a mismatch only once the user edited the confirmation', () => {
    expect(passwordConfirmationState('Abc@1234', 'Abc@1235', true)).toBe('mismatch')
    expect(passwordConfirmationState('Abc@1234', 'Abc@1235', false)).toBe('')
    // Changing the original password and coming back revalidates automatically
    // because the state is pure over both fields.
    expect(passwordConfirmationState('Abc@1235', 'Abc@1235', true)).toBe('match')
  })

  it('accepts an address the backend would still validate further', () => {
    expect(isEmailLike('ops@example.test')).toBe(true)
    expect(isEmailLike('ops@example.test ')

    ).toBe(true)
    expect(isEmailLike('ops@@')).toBe(false)
    expect(isEmailLike(' 不 spaces@')).toBe(false)
    expect(isEmailLike('ops@')).toBe(false)
    expect(isEmailLike('')).toBe(false)
  })

  it('refuses a password above the maximum', () => {
    const issue = validatePasswordStrength('a'.repeat(PASSWORD_MAX_LENGTH + 1))
    expect(issue).toEqual({ code: 'maxLength', params: { maxLength: PASSWORD_MAX_LENGTH } })
  })

  it('refuses the values the backend refuses outright', () => {
    // Mirrors validate_password_strength in backend/app/core/security.py, which
    // also checks the length first. `letmein` is shorter than the minimum, so
    // the length message is the one the user sees - same as on the server.
    for (const weak of ['password', 'password123', 'changeme', 'changeme123', 'admin123', 'qwerty123']) {
      expect(validatePasswordStrength(weak), weak).toEqual({ code: 'commonPassword' })
      // Casing and padding must not slip past it.
      expect(validatePasswordStrength(` ${weak.toUpperCase()} `), weak).toEqual({ code: 'commonPassword' })
    }
    expect(validatePasswordStrength('letmein')).toEqual({
      code: 'passwordMinLength',
      params: { minLength: PASSWORD_MIN_LENGTH },
    })
  })

  it('has copy for every code it can return', () => {
    expect(ISSUE_KEYS.minLength).toBe('validation.minLength')
    expect(ISSUE_KEYS.maxLength).toBe('validation.maxLength')
    expect(ISSUE_KEYS.commonPassword).toBe('validation.commonPassword')
    expect(ISSUE_KEYS.passwordMinLength).toBe('validation.passwordMinLength')
    expect(ISSUE_KEYS.passwordUppercase).toBe('validation.passwordUppercase')
    expect(ISSUE_KEYS.passwordLowercase).toBe('validation.passwordLowercase')
    expect(ISSUE_KEYS.passwordNumber).toBe('validation.passwordNumber')
    expect(ISSUE_KEYS.passwordSpecial).toBe('validation.passwordSpecial')
  })

  it('renders a message that names the field', () => {
    const t = (key: string, params?: Record<string, unknown>) =>
      `${key}${params ? `|${JSON.stringify(params)}` : ''}`
    const issue = validatePasswordStrength('short')
    expect(issueMessage(t, issue!, 'New password')).toContain('validation.passwordMinLength')
  })
})

describe('generated passwords', () => {
  it('satisfies the policy it is generated against', () => {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      const password = generateStrongPassword()
      expect(validatePasswordStrength(password), password).toBeNull()
    }
  })

  it('always contains every required class', () => {
    for (let attempt = 0; attempt < 200; attempt += 1) {
      expect(passwordRequirements(generateStrongPassword())).toMatchObject({
        uppercase: true,
        lowercase: true,
        number: true,
        special: true,
      })
    }
  })

  it('honours the requested length', () => {
    expect(generateStrongPassword(24)).toHaveLength(24)
  })

  it('does not repeat itself', () => {
    // 200 draws from a 57-character alphabet: a constant generator would collide
    // immediately, so a small sample is enough to catch one.
    const drawn = new Set(Array.from({ length: 200 }, () => generateStrongPassword()))
    expect(drawn.size).toBeGreaterThan(190)
  })

  it('never ends with the symbol, so copying it by hand cannot pick up a space', () => {
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const password = generateStrongPassword()
      expect(/[A-Za-z0-9]$/.test(password)).toBe(true)
      expect(/[^A-Za-z0-9]/.test(password)).toBe(true)
    }
  })

  it('omits glyphs that are easily confused when read aloud', () => {
    for (let attempt = 0; attempt < 50; attempt += 1) {
      expect(generateStrongPassword()).not.toMatch(/[Il1O0]/)
    }
  })
})

describe('session snapshot', () => {
  it('carries the forced password change in the cookie-safe user', () => {
    // Dropping it here would let a page reload show a signed-in shell that the
    // API refuses on every request.
    const compact = compactAuthUser({
      id: 1,
      name: 'Temporary',
      email: 'temporary@example.com',
      mustChangePassword: true,
      permissions: ['dashboard.view'],
    })
    expect(compact.mustChangePassword).toBe(true)
  })

  it('leaves the flag off a normal session', () => {
    const compact = compactAuthUser({ name: 'Normal', email: 'normal@example.com' })
    expect(compact.mustChangePassword).toBeUndefined()
  })
})
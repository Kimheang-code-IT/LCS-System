/**
 * Declarative field rules and their evaluation.
 *
 * The config-driven forms (`freight-modules`, component attributes) describe
 * their inputs with metadata, not with schemas, so validation lives here as
 * plain data + pure functions. That keeps it testable without mounting Vue and
 * lets every form share exactly one implementation.
 *
 * Issues are returned as `{ code, params }` instead of finished copy so the
 * message can be translated in the active locale (`validation.<code>`).
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

export type ValidationCode =
  | 'required'
  | 'email'
  | 'url'
  | 'number'
  | 'integer'
  | 'boolean'
  | 'date'
  | 'min'
  | 'max'
  | 'positive'
  | 'decimalPlaces'
  | 'minLength'
  | 'maxLength'
  | 'pattern'
  | 'allowed'
  | 'balanced'
  | 'commonPassword'
  | 'passwordMinLength'
  | 'passwordUppercase'
  | 'passwordLowercase'
  | 'passwordNumber'
  | 'passwordSpecial'
  | 'custom'

export type ValidationIssue = {
  code: ValidationCode
  params?: Record<string, string | number>
  /** Ready-made copy for backends/custom rules that already know the wording. */
  message?: string
}

/** Rules attached to one input (or one cell of a repeatable table). */
export type FieldRule = {
  required?: boolean
  min?: number
  max?: number
  minLength?: number
  maxLength?: number
  pattern?: string
  email?: boolean
  url?: boolean
  /** Phone / telephone format (digits, spaces and the usual separators). */
  phone?: boolean
  /** Value must parse as a finite number (any number column). */
  number?: boolean
  integer?: boolean
  date?: boolean
  nonNegative?: boolean
  /** Strictly greater than zero (quantities, exchange rates, allocations). */
  positive?: boolean
  /** Maximum digits after the decimal separator (money precision). */
  decimalPlaces?: number
  /** Apply the shared password policy (length + common-password refusal). */
  password?: boolean
  /** Closed set of acceptable values (select columns, configured options). */
  allowed?: Array<string | number>
  /** Cross-field rules resolved by the caller (e.g. double-entry balance). */
  custom?: (value: unknown) => ValidationIssue | null | undefined
}

/** A rule plus everything needed to report and locate the failure. */
export type ValidationFailure = ValidationIssue & {
  /** Canonical model path: `customerPartyId`, `lines.1.quantity`. */
  key: string
  /** Human label resolved by the caller (already translated). */
  label: string
  /** Repeatable-row index when the failure sits inside a table cell. */
  row?: number
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
const URL_PATTERN = /^(https?:\/\/)[^\s.]+\.[^\s]{2,}$/i
/**
 * A telephone number is written by hand, so the separators a person naturally
 * types are allowed; what is refused is anything with letters or stray symbols.
 * At least 6 and at most 15 digits covers national, international (+855…) and
 * extension forms alike.
 */
const PHONE_PATTERN = /^\+?[\d(][\d\s().-]{4,20}$/
// Mirrors the backend `_DATETIME_PATTERN` in app/core/validation.py, so a stored
// tz-aware timestamp (`…T00:00:00+00:00`, fractional seconds, `Z`) round-trips
// without a false "invalid date" on save.
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$/

/**
 * Password policy, mirrored from the backend's `PASSWORD_MIN_LENGTH` /
 * `PASSWORD_MAX_LENGTH` (defaults 8 and 128) and the character classes
 * `app/core/security.py::validate_password_strength` requires. The backend is
 * authoritative and re-validates every password it is given; this exists so a
 * weak one is refused before the round trip rather than after it.
 */
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

/** One boolean per approved requirement; also drives the live checklist. */
export type PasswordRequirements = {
  minLength: boolean
  maxLength: boolean
  uppercase: boolean
  lowercase: boolean
  number: boolean
  special: boolean
}

/** The five requirements a user must satisfy, in display order. */
export function passwordRequirements(value: string): PasswordRequirements {
  const password = String(value ?? '')
  return {
    minLength: password.length >= PASSWORD_MIN_LENGTH,
    maxLength: password.length <= PASSWORD_MAX_LENGTH,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
  }
}

/**
 * Values the backend refuses outright (`validate_password_strength`). Kept in
 * step with `app/core/security.py`, so the same password cannot pass here and
 * fail there.
 */
const COMMON_PASSWORDS = new Set([
  'password',
  'password123',
  'changeme',
  'changeme123',
  'admin123',
  'letmein',
  'qwerty123',
])

/** Check a password against the shared policy; returns the first problem found. */
export function validatePasswordStrength(value: string): ValidationIssue | null {
  const password = String(value ?? '')
  const checks = passwordRequirements(password)
  if (!checks.minLength) {
    return { code: 'passwordMinLength', params: { minLength: PASSWORD_MIN_LENGTH } }
  }
  if (!checks.maxLength) {
    return { code: 'maxLength', params: { maxLength: PASSWORD_MAX_LENGTH } }
  }
  if (COMMON_PASSWORDS.has(password.trim().toLowerCase())) {
    return { code: 'commonPassword' }
  }
  if (!checks.uppercase) return { code: 'passwordUppercase' }
  if (!checks.lowercase) return { code: 'passwordLowercase' }
  if (!checks.number) return { code: 'passwordNumber' }
  if (!checks.special) return { code: 'passwordSpecial' }
  return null
}

/**
 * Generate a password that satisfies {@link validatePasswordStrength}.
 *
 * Built from `crypto.getRandomValues`, never `Math.random`: a generated
 * credential that can be predicted is worse than no generator at all. The
 * alphabet omits characters that are easily confused when a password is read
 * aloud or copied by hand (I/l/1, O/0). One uppercase, one lowercase and one
 * digit are placed explicitly, because drawing the body at random could miss a
 * class the policy requires.
 */
export function generateStrongPassword(length = 16): string {
  const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  const lower = 'abcdefghijkmnopqrstuvwxyz'
  const digits = '23456789'
  const alphabet = `${upper}${lower}${digits}`
  const symbols = '!@#$%^&*-_=+'
  const size = Math.max(length, 6)
  const bytes = new Uint8Array(size + 8)
  crypto.getRandomValues(bytes)
  const pick = (source: string, index: number) => source[bytes[index]! % source.length]!

  const body = Array.from({ length: size - 1 }, (_, index) => pick(alphabet, index))
  // The class-guaranteeing characters sit in three distinct random body slots;
  // the last body slot stays alphanumeric so the symbol is never the final
  // character.
  const span = size - 2
  const offset = bytes[size]! % span
  const slots = [offset, (offset + 1) % span, (offset + 2) % span]
  body[slots[0]!] = pick(upper, size + 1)
  body[slots[1]!] = pick(lower, size + 2)
  body[slots[2]!] = pick(digits, size + 3)
  const symbol = symbols[bytes[size + 4]! % symbols.length]!
  return `${body.slice(0, -1).join('')}${symbol}${body.at(-1)}`
}

/** Treat `undefined`, `null`, `''` and `[]` as "no value"; `0`/`false` are values. */
export function isBlank(value: unknown): boolean {
  if (value === undefined || value === null) return true
  if (typeof value === 'string') return value.trim().length === 0
  if (Array.isArray(value)) return value.length === 0
  return false
}

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return null
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

/**
 * Evaluate one value against one rule set.
 *
 * `required` short-circuits: a blank required value never produces a second,
 * less useful complaint. Non-required blanks are always valid.
 */
export function validateFieldValue(value: unknown, rule: FieldRule = {}): ValidationIssue | null {
  const blank = isBlank(value)

  if (blank) {
    return rule.required ? { code: 'required' } : null
  }

  if (rule.password && typeof value === 'string') {
    const issue = validatePasswordStrength(value)
    if (issue) return issue
  }

  if (rule.nonNegative || rule.positive) {
    const number = toFiniteNumber(value)
    if (number === null) return { code: 'number' }
    if (rule.nonNegative && number < 0) return { code: 'min', params: { min: 0 } }
    if (rule.positive && number <= 0) return { code: 'positive' }
  }

  if (rule.decimalPlaces !== undefined) {
    const text = String(value).trim()
    const fraction = text.includes('.') ? text.split('.')[1]!.replace(/0+$/, '') : ''
    if (fraction.length > rule.decimalPlaces) {
      return { code: 'decimalPlaces', params: { decimals: rule.decimalPlaces } }
    }
  }

  if (rule.email && typeof value === 'string' && !EMAIL_PATTERN.test(value.trim())) {
    return { code: 'email' }
  }

  if (rule.phone && typeof value === 'string') {
    const digits = value.replace(/\D/g, '')
    // Letters, or too few / too many digits, are the two ways a number is wrong.
    if (!PHONE_PATTERN.test(value.trim()) || digits.length < 6 || digits.length > 15) {
      return { code: 'pattern' }
    }
  }

  if (rule.url && typeof value === 'string' && !URL_PATTERN.test(value.trim())) {
    return { code: 'url' }
  }

  if (rule.date && typeof value === 'string' && !ISO_DATE_PATTERN.test(value.trim())) {
    return { code: 'date' }
  }

  const numeric = toFiniteNumber(value)
  if (rule.integer || rule.min !== undefined || rule.max !== undefined || rule.number) {
    if (numeric === null) return { code: 'number' }
    if (rule.integer && !Number.isInteger(numeric)) return { code: 'integer' }
    if (rule.min !== undefined && numeric < rule.min) return { code: 'min', params: { min: rule.min } }
    if (rule.max !== undefined && numeric > rule.max) return { code: 'max', params: { max: rule.max } }
  }

  if (typeof value === 'string') {
    const text = value.trim()
    if (rule.minLength !== undefined && text.length < rule.minLength) {
      return { code: 'minLength', params: { min: rule.minLength } }
    }
    if (rule.maxLength !== undefined && text.length > rule.maxLength) {
      return { code: 'maxLength', params: { max: rule.maxLength } }
    }
    if (rule.pattern && !safeTest(rule.pattern, text)) {
      return { code: 'pattern' }
    }
  }

  if (rule.allowed?.length) {
    const text = Array.isArray(value) ? value.map(String) : [String(value)]
    const ok = text.every(item => rule.allowed!.map(String).includes(item))
    if (!ok) return { code: 'allowed' }
  }

  const custom = rule.custom?.(value)
  return custom ?? null
}

/** An admin-supplied pattern must never be able to throw mid-save. */
function safeTest(pattern: string, text: string): boolean {
  try {
    return new RegExp(pattern).test(text)
  }
  catch {
    return true
  }
}

/**
 * Translate a backend sentence onto a shared rule where possible, so an error
 * that started server-side is worded exactly like the client-side one.
 */
export function issueFromBackendMessage(raw: string): ValidationIssue | null {
  const text = String(raw ?? '')
  if (!text) return null
  if (/field (?:is )?required/i.test(text)) return { code: 'required' }
  if (/valid email/i.test(text)) return { code: 'email' }
  if (/valid (?:url|uri)/i.test(text)) return { code: 'url' }
  if (/valid integer/i.test(text)) return { code: 'integer' }
  if (/valid (?:number|decimal|float)/i.test(text)) return { code: 'number' }
  if (/valid boolean/i.test(text)) return { code: 'boolean' }
  if (/valid date/i.test(text)) return { code: 'date' }
  // Backend password sentences are worded exactly like `validation.password*`,
  // so a server refusal reads the same as the local rule that mirrors it.
  if (/at least one uppercase letter/i.test(text)) return { code: 'passwordUppercase' }
  if (/at least one lowercase letter/i.test(text)) return { code: 'passwordLowercase' }
  if (/at least one number/i.test(text)) return { code: 'passwordNumber' }
  if (/at least one special character/i.test(text)) return { code: 'passwordSpecial' }
  if (/too common/i.test(text)) return { code: 'commonPassword' }
  const passwordMin = text.match(/contain at least (\d+) characters?/i)
  if (passwordMin) return { code: 'passwordMinLength', params: { minLength: Number(passwordMin[1]) } }
  const minLength = text.match(/at least (\d+) characters?/i)
  if (minLength) return { code: 'minLength', params: { min: Number(minLength[1]) } }
  const maxLength = text.match(/at most (\d+) characters?/i)
  if (maxLength) return { code: 'maxLength', params: { max: Number(maxLength[1]) } }
  const min = text.match(/greater than or equal to (-?[\d.]+)/i)
  if (min) return { code: 'min', params: { min: Number(min[1]) } }
  const max = text.match(/less than or equal to (-?[\d.]+)/i)
  if (max) return { code: 'max', params: { max: Number(max[1]) } }
  if (/match(?:es)? (?:the )?pattern/i.test(text)) return { code: 'pattern' }
  if (/valid (?:enumeration|choice)|not a valid enumeration member|input should be '|choose one of the available options/i.test(text)) {
    return { code: 'allowed' }
  }
  const decimals = text.match(/at most (\d+) decimal places?/i)
  if (decimals) return { code: 'decimalPlaces', params: { decimals: Number(decimals[1]) } }
  if (/greater than zero|must be positive/i.test(text)) return { code: 'positive' }
  if (/valid phone|phone number/i.test(text)) return { code: 'pattern' }
  return null
}
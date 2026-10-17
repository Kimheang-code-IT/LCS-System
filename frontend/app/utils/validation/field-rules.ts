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
  | 'minLength'
  | 'maxLength'
  | 'pattern'
  | 'allowed'
  | 'balanced'
  | 'commonPassword'
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
  /** Value must parse as a finite number (any number column). */
  number?: boolean
  integer?: boolean
  date?: boolean
  nonNegative?: boolean
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
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?$/

/**
 * Password policy, mirrored from the backend's `PASSWORD_MIN_LENGTH` /
 * `PASSWORD_MAX_LENGTH` (defaults 8 and 128). The backend is authoritative and
 * re-validates every password it is given; this exists so a weak one is refused
 * before the round trip rather than after it.
 */
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

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
  if (password.length < PASSWORD_MIN_LENGTH) {
    return { code: 'minLength', params: { minLength: PASSWORD_MIN_LENGTH } }
  }
  if (password.length > PASSWORD_MAX_LENGTH) {
    return { code: 'maxLength', params: { maxLength: PASSWORD_MAX_LENGTH } }
  }
  if (COMMON_PASSWORDS.has(password.trim().toLowerCase())) {
    return { code: 'commonPassword' }
  }
  return null
}

/**
 * Generate a password that satisfies {@link validatePasswordStrength}.
 *
 * Built from `crypto.getRandomValues`, never `Math.random`: a generated
 * credential that can be predicted is worse than no generator at all. The
 * alphabet omits characters that are easily confused when a password is read
 * aloud or copied by hand (I/l/1, O/0).
 */
export function generateStrongPassword(length = 16): string {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
  const symbols = '!@#$%^&*-_=+'
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  const last = bytes[length - 1]!
  const body = Array.from(bytes.slice(0, length - 1), byte => alphabet[byte % alphabet.length]).join('')
  // Keep the symbol away from the end, so copying by hand cannot pick up a
  // trailing space that is not part of the password.
  return `${body.slice(0, -1)}${symbols[last % symbols.length]}${body.slice(-1)}`
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

  if (rule.nonNegative) {
    const number = toFiniteNumber(value)
    if (number === null) return { code: 'number' }
    if (number < 0) return { code: 'min', params: { min: 0 } }
  }

  if (rule.email && typeof value === 'string' && !EMAIL_PATTERN.test(value.trim())) {
    return { code: 'email' }
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
  if (/field required/i.test(text)) return { code: 'required' }
  if (/valid email/i.test(text)) return { code: 'email' }
  if (/valid (?:url|uri)/i.test(text)) return { code: 'url' }
  if (/valid integer/i.test(text)) return { code: 'integer' }
  if (/valid (?:number|decimal|float)/i.test(text)) return { code: 'number' }
  if (/valid boolean/i.test(text)) return { code: 'boolean' }
  if (/valid date/i.test(text)) return { code: 'date' }
  const minLength = text.match(/at least (\d+) characters?/i)
  if (minLength) return { code: 'minLength', params: { min: Number(minLength[1]) } }
  const maxLength = text.match(/at most (\d+) characters?/i)
  if (maxLength) return { code: 'maxLength', params: { max: Number(maxLength[1]) } }
  const min = text.match(/greater than or equal to (-?[\d.]+)/i)
  if (min) return { code: 'min', params: { min: Number(min[1]) } }
  const max = text.match(/less than or equal to (-?[\d.]+)/i)
  if (max) return { code: 'max', params: { max: Number(max[1]) } }
  if (/match(?:es)? (?:the )?pattern/i.test(text)) return { code: 'pattern' }
  if (/valid (?:enumeration|choice)|not a valid enumeration member|input should be '/i.test(text)) {
    return { code: 'allowed' }
  }
  return null
}
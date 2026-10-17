/**
 * One normaliser for every backend failure the UI has to render.
 *
 * The FastAPI app always answers `{code, message, request_id, field_errors}`
 * (see `backend/app/main.py`), but the repository layer also surfaces ofetch
 * failures and, defensively, a raw Pydantic `detail` array. Forms need the
 * same shape from all three, and they need messages a person can read — never
 * a stack trace and never a Pydantic sentence fragment.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

import { isLcsDomainError } from '~/utils/freight/errors'
import { fromErrorPath, normalizeErrorKey, toErrorPath } from './error-paths'

/** A single backend complaint, already addressed to a model path. */
export type MappedFieldError = {
  /** Canonical camelCase model path, e.g. `customerPartyId` or `lines.1.amount`. */
  key: string
  /** Raw backend sentence, already humanised. */
  message: string
  /** Backend `code`, when it sent one. */
  code?: string
}

export type NormalizedApiError = {
  /** HTTP status, when the failure came from the network layer. */
  status?: number
  code?: string
  requestId?: string
  /** Page/form-level message. Safe to show; empty when errors are field-level. */
  message: string
  /** Field-level errors keyed by canonical model path. */
  fieldErrors: Record<string, string>
  /** Ordered, de-duplicated field errors (the error summary reads this). */
  items: MappedFieldError[]
  /** 400/409/422 — the request was understood but rejected. */
  isValidation: boolean
}

/** FastAPI/Pydantic sentences rewritten into copy a user can act on. */
const MESSAGE_RULES: Array<{ pattern: RegExp, code: string, params?: (match: RegExpMatchArray) => Record<string, string | number> }> = [
  { pattern: /^Field required$/i, code: 'required' },
  { pattern: /^Input should be a valid email address/i, code: 'email' },
  { pattern: /^Input should be a valid url or url after scheme/i, code: 'url' },
  { pattern: /^Input should be a valid URL/i, code: 'url' },
  { pattern: /^Input should be a valid integer/i, code: 'integer' },
  { pattern: /^Input should be a valid number/i, code: 'number' },
  { pattern: /^Input should be a valid decimal number/i, code: 'number' },
  { pattern: /^Input should be a valid date(?:, time)?/i, code: 'date' },
  { pattern: /^Input should be a valid boolean/i, code: 'boolean' },
  { pattern: /String should have at least (\d+) characters?/i, code: 'minLength', params: m => ({ min: Number(m[1]) }) },
  { pattern: /String should have at most (\d+) characters?/i, code: 'maxLength', params: m => ({ max: Number(m[1]) }) },
  { pattern: /Input should be greater than or equal to (-?[\d.]+)/i, code: 'min', params: m => ({ min: m[1]! }) },
  { pattern: /Input should be less than or equal to (-?[\d.]+)/i, code: 'max', params: m => ({ max: m[1]! }) },
  { pattern: /Input should be greater than (-?[\d.]+)/i, code: 'min', params: m => ({ min: m[1]! }) },
  { pattern: /Input should be less than (-?[\d.]+)/i, code: 'max', params: m => ({ max: m[1]! }) },
  { pattern: /Input should be '.*'|Input should be \[.*\]|value is not a valid enumeration member/i, code: 'allowed' },
  { pattern: /ensure this value has at least/i, code: 'minLength' },
  { pattern: /ensure this value has less than or equal to/i, code: 'max' },
  { pattern: /ensure this value is greater than or equal to/i, code: 'min' },
  { pattern: /ensure this value is less than or equal to/i, code: 'max' },
  { pattern: /ensure this value is less than/i, code: 'max' },
  { pattern: /string should match pattern/i, code: 'pattern' },
  { pattern: /input should be a valid dictionary|input should be a valid list|input should be a valid set/i, code: 'generic' },
]

/** `customer_party_id` -> `customerPartyId` is done in `error-paths`. */

/**
 * Strip everything a user must never read: tracebacks, Pydantic's
 * `Value error,` prefix, JSON-ish payloads and runaway sentences.
 */
export function sanitizeMessage(raw: unknown): string {
  if (raw == null) return ''
  const text = String(raw)
  const firstLine = text.split(/\r?\n/).find(line => line.trim().length) ?? ''
  const withoutTrace = firstLine.includes('Traceback (most recent call last)') ? '' : firstLine
  const withoutPrefix = withoutTrace.replace(/^Value error,\s*/i, '').replace(/^Assertion failed:\s*/i, '')
  const withoutJson = withoutPrefix.replace(/^\{[\s\S]*\}$/, '').trim()
  const collapsed = withoutJson.replace(/\s+/g, ' ').trim()
  return collapsed.length > 240 ? `${collapsed.slice(0, 237)}...` : collapsed
}

/**
 * Map a raw backend sentence onto a translation key + parameters.
 * Unknown sentences are returned as-is (already sanitised) so nothing is lost.
 */
export function describeMessage(raw: unknown): { code: string, params?: Record<string, string | number> } | null {
  const text = sanitizeMessage(raw)
  if (!text) return null
  for (const rule of MESSAGE_RULES) {
    const match = text.match(rule.pattern)
    if (match) return { code: rule.code, ...(rule.params ? { params: rule.params(match) } : {}) }
  }
  return null
}

type RawErrorBody = {
  code?: unknown
  message?: unknown
  detail?: unknown
  request_id?: unknown
  field_errors?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

/**
 * `field_errors: { "lines.1.amount": "…" }` -> canonical camelCase map.
 * Non-string values are coerced; nested objects are flattened one level.
 */
function mapFieldErrors(
  raw: unknown,
  into: Map<string, MappedFieldError>,
): void {
  if (!isRecord(raw)) return
  for (const [rawKey, rawValue] of Object.entries(raw)) {
    const key = normalizeErrorKey(rawKey)
    if (!key) continue
    const message = sanitizeMessage(
      typeof rawValue === 'object' && rawValue !== null
        ? (rawValue as RawErrorBody).message
        : rawValue,
    )
    if (!message) continue
    // First writer wins: a domain error is more specific than a generic one.
    if (!into.has(key)) into.set(key, { key, message })
  }
}

/**
 * Raw Pydantic payload (only reachable if the app-level handler is bypassed):
 * `[{ loc: ["body", "customer_id"], msg, type }]`. Nested `loc` arrays —
 * including repeat-row indices — are preserved.
 */
function mapDetailArray(detail: unknown, into: Map<string, MappedFieldError>): void {
  if (!Array.isArray(detail)) return
  for (const entry of detail) {
    if (!isRecord(entry)) continue
    const segments = Array.isArray(entry.loc) ? toErrorPath(entry.loc.join('.')) : toErrorPath(String(entry.loc ?? ''))
    const message = sanitizeMessage(entry.msg)
    if (!message) continue
    // A nested object/array error with no leaf field belongs to the container.
    const key = fromErrorPath(segments)
    const target = key || ''
    if (!into.has(target)) {
      into.set(target, { key: target, message, ...(entry.type ? { code: String(entry.type) } : {}) })
    }
  }
}

export type NormalizeApiErrorOptions = {
  /**
   * Model keys currently rendered. An error whose path has no match is kept
   * verbatim so it still reaches the form-level summary — never dropped.
   */
  registeredKeys?: () => string[]
}

/**
 * Turn any thrown value into the shape every form consumes.
 *
 * Handles `LcsDomainError`, ofetch `FetchError` (with the LCS envelope or a
 * raw FastAPI body) and plain errors.
 */
export function normalizeApiError(
  error: unknown,
  options: NormalizeApiErrorOptions = {},
): NormalizedApiError {
  const mapped = new Map<string, MappedFieldError>()

  if (isLcsDomainError(error)) {
    mapFieldErrors(error.field_errors, mapped)
  }

  const raw = isRecord(error) ? error : null
  const body = (raw && isRecord(raw.data) ? raw.data : undefined) as RawErrorBody | undefined
  const envelope = (body && isRecord(body) ? body : undefined)
  const fallbackBody = envelope ?? (raw as RawErrorBody | null)

  if (envelope) {
    mapFieldErrors(envelope.field_errors, mapped)
    if (Array.isArray(envelope.detail)) mapDetailArray(envelope.detail, mapped)
  }
  else if (fallbackBody) {
    // A bare `{ detail: "..." }` / `{ detail: [...] }` body.
    if (Array.isArray(fallbackBody.detail)) mapDetailArray(fallbackBody.detail, mapped)
    mapFieldErrors((fallbackBody as RawErrorBody).field_errors, mapped)
  }

  const items = [...mapped.values()]
  const status = typeof raw?.status === 'number'
    ? raw.status
    : typeof raw?.statusCode === 'number'
      ? raw.statusCode
      : isLcsDomainError(error)
        ? error.statusCode
        : undefined
  const code = typeof envelope?.code === 'string'
    ? envelope.code
    : typeof fallbackBody?.code === 'string'
      ? fallbackBody.code
      : isLcsDomainError(error)
        ? error.code
        : undefined

  const registered = options.registeredKeys?.() ?? []
  const hasFieldErrors = items.length > 0
  const rawMessage = sanitizeMessage(
    isLcsDomainError(error)
      ? error.message
      : envelope?.message ?? fallbackBody?.message ?? fallbackBody?.detail
      // A plain `throw '…'` or a bare Error carries the only text available.
      ?? (typeof error === 'string' ? error : (error instanceof Error ? error.message : '')),
  )

  return {
    status,
    code,
    requestId: typeof envelope?.request_id === 'string'
      ? envelope.request_id
      : typeof fallbackBody?.request_id === 'string'
        ? (fallbackBody.request_id as string)
        : undefined,
    // Field errors speak for themselves; a summary message on top would double
    // up. Only surface the envelope message when nothing landed on a field.
    message: hasFieldErrors ? '' : (registered.length || rawMessage ? rawMessage : ''),
    fieldErrors: Object.fromEntries(items.map(item => [item.key, item.message])),
    items,
    isValidation: status === 422 || status === 400 || status === 409 || code === 'VALIDATION_ERROR',
  }
}

/**
 * A message safe to show at page level. Falls back to `fallback` only when the
 * backend genuinely said nothing useful.
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const normalized = normalizeApiError(error)
  if (normalized.message) return normalized.message
  if (normalized.items.length) {
    const first = normalized.items[0]!
    return normalized.items.length === 1 ? first.message : `${first.message} (+${normalized.items.length - 1})`
  }
  return fallback
}
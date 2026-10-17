/**
 * Stable, translatable identifiers for validation errors.
 *
 * The frontend addresses every input by its camelCase model path
 * (`customerPartyId`, `lines.1.quantity`). The backend speaks snake_case and
 * Pydantic array indices (`customer_party_id`, `lines.1.amount`), so every
 * inbound error path is normalised here before it reaches a field.
 *
 * Keep this module a leaf: no Vue, no components, no i18n.
 */

/** One hop in an error path: a model key or a repeatable-row index. */
export type ErrorPathSegment = string | number

/** Envelope segments FastAPI adds to `loc`; they are never model keys. */
const ENVELOPE_SEGMENTS = new Set<string>(['body', 'query', 'path', 'cookie', 'header', 'headers'])

/** `customer_party_id` -> `customerPartyId`. Already-camel keys pass through. */
export function camelizeKey(key: string): string {
  return key
    .replace(/[_-]+([a-zA-Z0-9])/g, (_, char: string) => char.toUpperCase())
    .replace(/^[_-]+/, '')
}

/**
 * Turn a backend field-error key into model path segments.
 *
 * Handles the three shapes the FastAPI app can emit:
 *  - `customer_party_id`        (single field)
 *  - `lines.1.amount`           (nested repeatable row)
 *  - `lines.0.amount` / `body.lines`  (indexed, optionally envelope-prefixed)
 */
export function toErrorPath(raw: string): ErrorPathSegment[] {
  const trimmed = String(raw ?? '').trim()
  if (!trimmed) return []
  const segments: ErrorPathSegment[] = []
  for (const part of trimmed.split('.')) {
    const segment = part.trim()
    if (!segment) continue
    if (ENVELOPE_SEGMENTS.has(segment.toLowerCase())) continue
    if (/^\d+$/.test(segment)) segments.push(Number(segment))
    else segments.push(camelizeKey(segment))
  }
  return segments
}

/** Inverse of {@link toErrorPath}; the canonical key stored in `fieldErrors`. */
export function fromErrorPath(path: ErrorPathSegment[]): string {
  return path.map(segment => String(segment)).join('.')
}

/** Normalise a raw backend key straight to the camelCase model path. */
export function normalizeErrorKey(raw: string): string {
  return fromErrorPath(toErrorPath(raw))
}

export type RowErrorParts = {
  table: string
  index: number
  column: string
}

/**
 * `lines.1.amount` -> `{ table: 'lines', index: 1, column: 'amount' }`.
 * Returns null for plain (non row-scoped) keys.
 */
export function parseRowKey(key: string): RowErrorParts | null {
  const segments = toErrorPath(key)
  if (segments.length < 3) return null
  const index = segments[segments.length - 2]
  const column = segments[segments.length - 1]
  const table = segments.slice(0, -2).join('.')
  if (typeof index !== 'number' || typeof column !== 'string' || !table) return null
  return { table, index, column }
}

/** Build the canonical key for one cell of a repeatable table. */
export function rowCellKey(table: string, index: number, column: string): string {
  return `${table}.${index}.${column}`
}

/**
 * Registered field key that owns this error key.
 *
 * Lets `customerPartyId` keep its error while a sibling field is rendered, and
 * lets a row error (`lines.1.amount`) resolve to the `lines` table — but the
 * caller must keep the precise key: matching a table does not mean collapsing
 * the row and column, because the cell is where the message belongs.
 */
export function matchesRegisteredKey(key: string, registered: Iterable<string>): string | null {
  const registeredList = Array.isArray(registered) ? registered : [...registered]
  const own = registeredList as unknown as Set<string>
  if (typeof own.has === 'function' && own.has(key)) return key
  let best: string | null = null
  for (const candidate of registeredList) {
    if (!candidate || !key.startsWith(`${candidate}.`)) continue
    // `lines.1.amount` is a cell of the `lines` table, not the table itself.
    if (/^\d+$/.test(key.slice(candidate.length + 1).split('.')[0]!)) {
      if (best === null) best = candidate
      continue
    }
    if (!best || candidate.length > best.length) best = candidate
  }
  return best
}

/** Every distinct repeatable table referenced by a set of error keys. */
export function referencedTables(keys: Iterable<string>): string[] {
  const tables: string[] = []
  for (const key of keys) {
    const row = parseRowKey(key)
    const table = row?.table ?? (key.includes('.') ? key.split('.')[0]! : key)
    if (table && !tables.includes(table)) tables.push(table)
  }
  return tables
}
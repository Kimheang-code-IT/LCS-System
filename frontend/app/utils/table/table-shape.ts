import type { FreightTable } from '~/config/freight-modules'

/**
 * Structural signature of a line-table descriptor.
 *
 * A host may hand `AppLineTable` an equal-but-new descriptor on every render
 * (the document form recompiles its tabs from the record, and `lineTableField`
 * spreads a fresh table object each time). The column definitions carry the
 * cell renderers, so rebuilding them for an unchanged descriptor re-creates the
 * cell content — and the focused `<input>` — on every keystroke. Comparing the
 * shape lets the renderer reuse the definitions it already has.
 *
 * Functions are compared by source text: the descriptors are declarative, and
 * the few hooks they carry (`computeRow`, `rowDefaults`) are stable module-level
 * functions.
 */
function serialisable(value: unknown): unknown {
  if (typeof value === 'function') return String(value)
  if (Array.isArray(value)) return value.map(serialisable)
  if (value && typeof value === 'object') {
    const source = value as Record<string, unknown>
    return Object.keys(source)
      .sort()
      .map(key => [key, serialisable(source[key])])
  }
  return value
}

export function tableColumnSignature(table: FreightTable): string {
  return JSON.stringify(serialisable(table))
}

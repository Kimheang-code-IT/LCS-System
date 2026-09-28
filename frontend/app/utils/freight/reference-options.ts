import type { FreightRecord } from '~/types/freight/record'

export type ReferenceOptionSource = {
  /** Freight store collection (also a Master Data page). */
  collection: string
  /** Master-record field stored as the select value. Defaults to `code`. */
  valueField?: 'code' | 'name' | 'id'
  /** Master-record field shown as the select label. Defaults to `name`. */
  labelField?: 'code' | 'name'
}

/**
 * Selects that must be populated from a Master Data page instead of a static
 * list. The key is the `FreightField`/`FreightLineColumn` key, so every form and
 * line table picks these up automatically.
 */
const REFERENCE_SELECT_SOURCES: Record<string, ReferenceOptionSource> = {
  containerType: { collection: 'containerTypes', valueField: 'code', labelField: 'name' },
  feeType: { collection: 'feeTypes', valueField: 'name', labelField: 'name' },
  direction: { collection: 'tradeDirections', valueField: 'name', labelField: 'name' },
  tradeDirection: { collection: 'tradeDirections', valueField: 'name', labelField: 'name' },
  placeRole: { collection: 'places', valueField: 'name', labelField: 'name' },
  parentPlace: { collection: 'places', valueField: 'name', labelField: 'name' },
  roles: { collection: 'roles', valueField: 'name', labelField: 'name' },
  currency: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  currency20: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  currency40: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  currency45: { collection: 'currencies', valueField: 'code', labelField: 'name' },
}

export function referenceOptionSource(key: string): ReferenceOptionSource | undefined {
  return REFERENCE_SELECT_SOURCES[key]
}

export function referenceSelectItems(
  records: FreightRecord[] | undefined,
  source: ReferenceOptionSource,
): Array<{ label: string, value: string }> {
  const valueField = source.valueField || 'code'
  const labelField = source.labelField || 'name'
  const items: Array<{ label: string, value: string }> = []
  const seen = new Set<string>()
  for (const row of records || []) {
    const value = String(row[valueField] ?? row.name ?? row.code ?? row.id ?? '').trim()
    if (!value || seen.has(value)) continue
    seen.add(value)
    const label = String(row[labelField] ?? row.name ?? row.code ?? value).trim() || value
    items.push({ label, value })
  }
  return items
}

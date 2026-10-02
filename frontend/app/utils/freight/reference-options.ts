import type { FreightRecord } from '~/types/record'

export type ReferenceOptionSource = {
  /** Freight store collection (also a Master Data page). */
  collection: string
  /** Master-record field stored as the select value. */
  valueField?: 'code' | 'name' | 'id' | 'legalName' | 'displayName'
  /** Master-record field shown as the select label. */
  labelField?: 'code' | 'name' | 'legalName' | 'displayName'
  /** Only include records whose `roles` include one of these (case-insensitive). */
  roles?: string[]
}

/**
 * Selects that must be populated from a Master Data page instead of a static
 * list. The key is the `FreightField`/`FreightLineColumn` key, so every form and
 * line table picks these up automatically.
 */
const REFERENCE_SELECT_SOURCES: Record<string, ReferenceOptionSource> = {
  customer: { collection: 'businessParties', valueField: 'legalName', labelField: 'legalName', roles: ['Customer'] },
  containerType: { collection: 'containerTypes', valueField: 'code', labelField: 'name' },
  feeType: { collection: 'feeTypes', valueField: 'name', labelField: 'name' },
  direction: { collection: 'tradeDirections', valueField: 'name', labelField: 'name' },
  tradeDirection: { collection: 'tradeDirections', valueField: 'name', labelField: 'name' },
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
  const roleFilter = source.roles?.map(role => role.toLowerCase())
  const items: Array<{ label: string, value: string }> = []
  const seen = new Set<string>()
  for (const row of records || []) {
    if (roleFilter?.length) {
      const roles = Array.isArray(row.roles) ? row.roles.map(role => String(role).toLowerCase()) : []
      if (!roles.some(role => roleFilter.includes(role))) continue
    }
    const value = String(row[valueField] ?? row.name ?? row.code ?? row.id ?? '').trim()
    if (!value || seen.has(value)) continue
    seen.add(value)
    const label = String(row[labelField] ?? row.name ?? row.code ?? value).trim() || value
    items.push({ label, value })
  }
  return items
}

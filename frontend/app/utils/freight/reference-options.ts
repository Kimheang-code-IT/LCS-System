import type { FreightRecord } from '~/types/record'

export type ReferenceOptionSource = {
  /** Freight store collection (also a Master Data page). */
  collection: string
  /** Master-record field stored as the select value. */
  valueField?: 'code' | 'name' | 'id' | 'legalName' | 'displayName' | 'accountCode' | 'accountName'
  /** Master-record field shown as the select label. */
  labelField?: 'code' | 'name' | 'legalName' | 'displayName' | 'accountCode' | 'accountName'
  /** Only include records whose `roles` include one of these (case-insensitive). */
  roles?: string[]
  /** Only include records whose `status` matches one of these (case-insensitive). */
  statuses?: string[]
  /** Only include records whose boolean field is true (e.g. `postable`). */
  flag?: string
}

/**
 * Selects that must be populated from a Master Data page instead of a static
 * list. The key is the `FreightField`/`FreightLineColumn` key, so every form and
 * line table picks these up automatically.
 */
const REFERENCE_SELECT_SOURCES: Record<string, ReferenceOptionSource> = {
  customerPartyId: { collection: 'businessParties', valueField: 'id', labelField: 'legalName', roles: ['Customer'], statuses: ['ACTIVE'] },
  customer: { collection: 'businessParties', valueField: 'legalName', labelField: 'legalName', roles: ['Customer'] },
  containerType: { collection: 'containerTypes', valueField: 'code', labelField: 'name' },
  transportType: { collection: 'transportTypes', valueField: 'name', labelField: 'name' },
  feeType: { collection: 'feeTypes', valueField: 'name', labelField: 'name' },
  direction: { collection: 'tradeDirections', valueField: 'name', labelField: 'name' },
  tradeDirection: { collection: 'tradeDirections', valueField: 'name', labelField: 'name' },
  currency: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  // The rate store's two sides, both from the currency master.
  fromCurrencyCode: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  toCurrencyCode: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  currency20: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  currency40: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  currency45: { collection: 'currencies', valueField: 'code', labelField: 'name' },
  // Posting rules store an account *code*, and only a postable leaf account can
  // receive a journal line - offering header accounts would only produce a
  // validation failure at posting time.
  debitAccount: { collection: 'chartOfAccounts', valueField: 'accountCode', labelField: 'accountName', statuses: ['ACTIVE'], flag: 'postable' },
  creditAccount: { collection: 'chartOfAccounts', valueField: 'accountCode', labelField: 'accountName', statuses: ['ACTIVE'], flag: 'postable' },
  taxAccount: { collection: 'chartOfAccounts', valueField: 'accountCode', labelField: 'accountName', statuses: ['ACTIVE'], flag: 'postable' },
  // The fee type narrows a rule to one scope; the backend stores its row id.
  feeTypeId: { collection: 'feeTypes', valueField: 'id', labelField: 'name', statuses: ['ACTIVE'] },
  // The business party on a financial document: a customer on a receivable, a
  // supplier on a payable, so both roles are offered and the backend stores the id.
  partyId: { collection: 'businessParties', valueField: 'id', labelField: 'legalName', statuses: ['ACTIVE'] },
  // The bank/cash account a receipt or payment settles through; the backend stores
  // the row id, so the payload carries the name separately for printing.
  financialAccountId: { collection: 'financialAccounts', valueField: 'id', labelField: 'accountName', statuses: ['ACTIVE'] },
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
  const statusFilter = source.statuses?.map(status => status.toLowerCase())
  const items: Array<{ label: string, value: string }> = []
  const seen = new Set<string>()
  for (const row of records || []) {
    if (statusFilter?.length) {
      const status = String(row.status || 'ACTIVE').toLowerCase()
      if (!statusFilter.includes(status)) continue
    }
    if (source.flag && row[source.flag] !== true) continue
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

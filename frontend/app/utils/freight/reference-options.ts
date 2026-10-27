import type { FreightRecord } from '~/types/record'
export type ReferenceOptionSource = {
  /** Freight store collection (also a Master Data page). */
  collection: string
  /** Master-record field stored as the select value. */
  valueField?: 'code' | 'name' | 'id' | 'legalName' | 'displayName' | 'accountCode' | 'accountName'
  /** Master-record field shown as the select label. */
  labelField?: 'code' | 'name' | 'legalName' | 'displayName' | 'accountCode' | 'accountName'
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
  // The party a quotation is issued to, and the one on the service order it
  // becomes. Both forms label the field "Company"/"Business Party", and the
  // Business Parties master records a company under whatever roles apply
  // (Customer, Supplier, Company, or several at once). Restricting the picker to
  // `Customer`/`Company` hid a supplier-only party that we may still quote for,
  // so every role is offered and only `status` narrows the list — matching
  // `partyId` on a financial document. `resolve_party_by_id` on the backend
  // validates existence and ACTIVE status, never the role.
  customerPartyId: { collection: 'businessParties', valueField: 'id', labelField: 'legalName', statuses: ['ACTIVE'] },
  customer: { collection: 'businessParties', valueField: 'legalName', labelField: 'legalName' },
  // A party's roles are master data now. The form binds `roleIds` (ids, so a
  // rename never rewrites an assignment); the list and filter use the names the
  // backend serializes into `roles`.
  roleIds: { collection: 'partyRoles', valueField: 'id', labelField: 'name', statuses: ['ACTIVE'] },
  roles: { collection: 'partyRoles', valueField: 'name', labelField: 'name' },
  // The owner and the operator of a transport asset. Both are optional, and both
  // are stored by legal name: `_asset_computed` reads them back out by that same
  // name, so the select value and the stored column never drift apart. Every role
  // is offered — the party that owns a truck may well be recorded as a Supplier.
  ownerParty: { collection: 'businessParties', valueField: 'legalName', labelField: 'legalName', statuses: ['ACTIVE'] },
  operatorParty: { collection: 'businessParties', valueField: 'legalName', labelField: 'legalName', statuses: ['ACTIVE'] },
  // Route stops select their role from the administrator-managed Place Roles
  // master. The location is free text, so no separate Places collection exists.
  // Inactive roles are not offered for new selections; a saved id stays readable.
  placeRoleId: { collection: 'placeRoles', valueField: 'id', labelField: 'name', statuses: ['ACTIVE'] },
  // Central Document Types master: the value stays a stable code (the canonical
  // code, or a custom type's own code) and the label is the master's name. New
  // document types appear in every module that uses this key without a deploy.
  documentType: { collection: 'documentTypes', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
  documentTypeId: { collection: 'documentTypes', valueField: 'id', labelField: 'name', statuses: ['ACTIVE'] },
  containerType: { collection: 'containerTypes', valueField: 'code', labelField: 'name' },
  transportType: { collection: 'transportTypes', valueField: 'name', labelField: 'name' },
  // What an asset's `identity` holds. The vocabulary lives in its own Master
  // Data collection (`transportAssetIdentityTypes`), seeded by the backend
  // migration and edited by an administrator like Party/Place Roles; the asset
  // form narrows it by transport type with the field's `referenceFilter`.
  identityType: { collection: 'transportAssetIdentityTypes', valueField: 'name', labelField: 'name', statuses: ['ACTIVE'] },
  // The unit of an asset's optional capacity: a small list (`capacityUnits`).
  // Storing the code keeps the display ("24,500 KG") identical everywhere.
  capacityUnit: { collection: 'capacityUnits', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
  // Quotation pricing stores the Transport Type id, so renaming a master record
  // changes the label without rewriting history. Inactive types are hidden from
  // new lines; `referenceItemForValue` keeps a saved one readable.
  transportBy: { collection: 'transportTypes', valueField: 'id', labelField: 'name', statuses: ['ACTIVE'] },
  feeType: { collection: 'feeTypes', valueField: 'name', labelField: 'name', statuses: ['ACTIVE'] },
  direction: { collection: 'tradeDirections', valueField: 'name', labelField: 'name', statuses: ['ACTIVE'] },
  tradeDirection: { collection: 'tradeDirections', valueField: 'name', labelField: 'name', statuses: ['ACTIVE'] },
  currency: { collection: 'currencies', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
  // The rate store's two sides, both from the currency master.
  fromCurrencyCode: { collection: 'currencies', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
  toCurrencyCode: { collection: 'currencies', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
  currency20: { collection: 'currencies', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
  currency40: { collection: 'currencies', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
  currency45: { collection: 'currencies', valueField: 'code', labelField: 'name', statuses: ['ACTIVE'] },
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
  const statusFilter = source.statuses?.map(status => status.toLowerCase())
  const items: Array<{ label: string, value: string }> = []
  const seen = new Set<string>()
  for (const row of records || []) {
    if (statusFilter?.length) {
      const status = String(row.status || 'ACTIVE').toLowerCase()
      if (!statusFilter.includes(status)) continue
    }
    if (source.flag && row[source.flag] !== true) continue
    const value = String(row[valueField] ?? row.name ?? row.code ?? row.id ?? '').trim()
    if (!value || seen.has(value)) continue
    seen.add(value)
    const label = String(row[labelField] ?? row.name ?? row.code ?? value).trim() || value
    items.push({ label, value })
  }
  return items
}

/**
 * Label for a saved value that is no longer among the offered options — an
 * inactive master record, or a legacy quotation that stored the transport name
 * before the select was keyed by id. Returns null when no record matches, so
 * the caller can fall back to the raw value.
 */
export function referenceItemForValue(
  records: FreightRecord[] | undefined,
  source: ReferenceOptionSource,
  value: unknown,
): { label: string, value: string } | null {
  const current = String(value ?? '').trim()
  if (!current) return null
  const valueField = source.valueField || 'code'
  const labelField = source.labelField || 'name'
  const record = (records || []).find(item =>
    [item[valueField], item.name, item.code]
      .some(candidate => String(candidate ?? '').trim() === current),
  )
  if (!record) return null
  return {
    label: String(record[labelField] ?? record.name ?? record.code ?? current).trim() || current,
    value: current,
  }
}

// --- Transport asset identity hooks -------------------------------------------
// The asset form reads its identity vocabulary straight from the
// `transportAssetIdentityTypes` master, so these helpers (used as `FreightField`
// hooks and by the client-side rules) follow the same *name* the backend accepts.

/** The identity-type row a record selected, for label/placeholder/pattern hooks. */
export function identityTypeRowOf(record: Record<string, unknown>): FreightRecord | undefined {
  const name = String(record.identityType || '').trim()
  if (!name) return undefined
  // Called during render, so the pinia instance is active.
  return useFreightStore().list('transportAssetIdentityTypes').find(row =>
    String(row.name || '').trim().toLowerCase() === name.toLowerCase(),
  )
}

/** Offers only the identity types that apply to the asset's transport type. */
export function identityTypeOptionsFor(
  record: Record<string, unknown> | undefined,
  records: FreightRecord[],
): FreightRecord[] {
  const transportType = String(record?.transportType || '').trim().toLowerCase()
  if (!transportType) return records
  return records.filter((row) => {
    const applies = String(row.transportType || '').trim().toLowerCase()
    return !applies || applies === transportType
  })
}

/** `FreightField.labelFor` — the chosen row's field label (falls back on ''). */
export function identityLabelFor(record: Record<string, unknown>): string {
  return String(identityTypeRowOf(record)?.identityLabel || '').trim()
}

/** `FreightField.placeholderFor` — e.g. "Enter the 7-digit IMO number". */
export function identityPlaceholderFor(record: Record<string, unknown>): string {
  return String(identityTypeRowOf(record)?.identityPlaceholder || '').trim()
}

/**
 * The identity value must match the chosen row's pattern (`validation_pattern`),
 * which seeds the "is this a real IMO number" rules as admin-editable data.
 * Returns false only for a value the row refuses; a blank value or an
 * unparseable pattern leaves validation to the backend.
 */
export function matchesIdentityPattern(pattern: unknown, value: unknown): boolean {
  const source = String(pattern || '').trim()
  const target = String(value || '').trim()
  if (!source || !target) return true
  try {
    // Full-match like the backend `re.fullmatch`, even when the admin pattern
    // omits the ^…$ anchors; otherwise the browser precheck passes values the
    // server refuses.
    return new RegExp(`^(?:${source})$`).test(target)
  }
  catch {
    return true
  }
}

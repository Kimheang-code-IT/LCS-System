import type { FreightModule } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'

const CANONICAL_COLLECTION_PATHS: Record<string, string> = {
  jobs: '/service-orders',
  quotations: '/quotations',
  jobCharges: '/service-charges',
  debitNotes: '/finance/documents',
}

const REFERENCE_KEYS = [
  'id',
  'jobNo',
  'recordNo',
  'quotationNo',
  'chargeNo',
  'debitNoteNo',
  'documentNo',
  'paymentNo',
  'invoiceNo',
  'entryNo',
  'code',
]

function compact(value: unknown) {
  return String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '')
}

function eventTypeFrom(action: unknown) {
  return String(action || 'EVENT')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_|_$/g, '') || 'EVENT'
}

/** Supports both the legacy module/recordNo shape and the API entityType/entity shape. */
export function normalizeAuditLog(row: FreightRecord): FreightRecord {
  return {
    ...row,
    eventType: row.eventType || eventTypeFrom(row.action),
    entityType: row.entityType || row.module || 'Record',
    entity: row.entity || row.recordNo || '',
    result: row.result || 'SUCCESS',
    reason: row.reason || row.remark || '',
  }
}

function moduleHintScore(module: FreightModule, hint: string) {
  if (!hint) return 0
  const candidates = [module.title, module.singular, module.collection, module.path]
  return candidates.some(value => compact(value).includes(hint) || hint.includes(compact(value))) ? 10 : 0
}

/** Finds the real audited record and returns a route only when it still exists and is accessible. */
export function resolveAuditEntityPath(
  auditRow: FreightRecord,
  modules: FreightModule[],
  listRecords: (collection: string) => FreightRecord[],
  canAccess: (permission: string) => boolean = () => true,
) {
  const reference = compact(auditRow.entity || auditRow.recordNo)
  if (!reference) return ''

  const hint = compact(auditRow.entityType || auditRow.module)
  const candidates = new Map<string, FreightModule>()
  for (const module of modules) {
    if (module.collection === 'auditLogs' || !canAccess(module.permission)) continue
    const existing = candidates.get(module.collection)
    const canonicalPath = CANONICAL_COLLECTION_PATHS[module.collection]
    if (!existing || module.path === canonicalPath) candidates.set(module.collection, module)
  }

  let best: { path: string, score: number } | null = null
  for (const module of candidates.values()) {
    const match = listRecords(module.collection).find((record) => {
      const keys = new Set([module.titleField, ...REFERENCE_KEYS])
      return [...keys].some(key => compact(record[key]) === reference)
    })
    if (!match) continue

    const score = moduleHintScore(module, hint) + (module.path === CANONICAL_COLLECTION_PATHS[module.collection] ? 1 : 0)
    if (!best || score > best.score) best = { path: `${module.path}/${match.id}`, score }
  }
  return best?.path || ''
}

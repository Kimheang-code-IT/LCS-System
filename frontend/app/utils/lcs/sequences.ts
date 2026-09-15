import type { FreightRecord } from '~/types/freight/record'
import type { LcsCollections } from '~/utils/lcs/commands'
import { normalizeDocumentSequenceRecord } from '~/utils/document-sequences'

export type CollectionSequenceConfig = {
  documentType: string | ((input: Record<string, unknown>) => string)
  fallback: string
  numberField: string
}

export const COLLECTION_SEQUENCE_CONFIG: Record<string, CollectionSequenceConfig> = {
  quotations: { documentType: 'QUOTATION', fallback: 'Q', numberField: 'quotationNo' },
  jobCharges: { documentType: 'SERVICE_CHARGE', fallback: 'SC', numberField: 'chargeNo' },
  debitNotes: {
    documentType: input => String(input.documentType || 'CUSTOMER_INVOICE'),
    fallback: 'INV',
    numberField: 'debitNoteNo',
  },
  journals: { documentType: 'JOURNAL', fallback: 'JE', numberField: 'entryNo' },
}

export type AllocateOfficialNumberInput = {
  documentType: string
  year?: number
  fallbackPrefix?: string
}

export type AllocateOfficialNumberResult = {
  number: string
  sequenceId: string | null
  lastValue: number
}

export function resolveDocumentType(
  config: CollectionSequenceConfig,
  input: Record<string, unknown> = {},
): string {
  return typeof config.documentType === 'function'
    ? config.documentType(input)
    : config.documentType
}

export function formatOfficialNumber(
  sequence: FreightRecord | null,
  next: number,
  fallbackPrefix: string,
  year: number,
): string {
  const prefix = String(sequence?.prefix || fallbackPrefix).trim()
  const padding = Math.max(1, Number(sequence?.paddingLength || 6))
  return [prefix, year, String(next).padStart(padding, '0')].filter(Boolean).join('-')
}

export function allocateOfficialNumber(
  db: LcsCollections,
  input: AllocateOfficialNumberInput,
): AllocateOfficialNumberResult {
  const year = input.year ?? new Date().getFullYear()
  const sequences = (db.documentSequences || []).map(normalizeDocumentSequenceRecord)
  const sequence = sequences.find(row =>
    String(row.documentType) === input.documentType
    && Number(row.year) === year
    && String(row.status).toUpperCase() === 'ACTIVE',
  ) || null
  const next = Number(sequence?.lastValue || 0) + 1
  const number = formatOfficialNumber(sequence, next, input.fallbackPrefix || '', year)

  if (sequence) {
    const index = sequences.findIndex(row => row.id === sequence.id)
    if (index >= 0) {
      sequences[index] = { ...sequence, lastValue: next }
      db.documentSequences = sequences
    }
  }

  return {
    number,
    sequenceId: sequence ? String(sequence.id) : null,
    lastValue: next,
  }
}

export function allocateCollectionNumber(
  db: LcsCollections,
  collection: string,
  input: Record<string, unknown> = {},
): AllocateOfficialNumberResult | null {
  const config = COLLECTION_SEQUENCE_CONFIG[collection]
  if (!config) return null
  return allocateOfficialNumber(db, {
    documentType: resolveDocumentType(config, input),
    fallbackPrefix: config.fallback,
  })
}

export function stripOfficialNumberFields(
  input: Record<string, unknown>,
  collection: string,
): Record<string, unknown> {
  const config = COLLECTION_SEQUENCE_CONFIG[collection]
  if (!config) return { ...input }
  const next = { ...input }
  if (collection === 'jobCharges' && isManualServiceChargeNumber(input)) {
    delete next.id
    return next
  }
  delete next[config.numberField]
  delete next.id
  return next
}

/** Standalone service charges (no service order) keep a user-entered charge number. */
export function isManualServiceChargeNumber(input: Record<string, unknown>): boolean {
  return !String(input.jobNo || '').trim() && Boolean(String(input.chargeNo || '').trim())
}

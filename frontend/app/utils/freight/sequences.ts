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

/** Official document numbers are allocated by the backend; strip any client-supplied value. */
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
  Reflect.deleteProperty(next, config.numberField)
  delete next.id
  return next
}

/** Standalone service charges (no service order) keep a user-entered charge number. */
export function isManualServiceChargeNumber(input: Record<string, unknown>): boolean {
  return !String(input.jobNo || '').trim() && Boolean(String(input.chargeNo || '').trim())
}

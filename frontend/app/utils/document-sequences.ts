import type { FreightRecord } from '~/types/freight/record'

export const DOCUMENT_SEQUENCE_TYPES = [
  'QUOTATION',
  'SERVICE_ORDER',
  'SERVICE_CHARGE',
  'CUSTOMER_INVOICE',
  'SUPPLIER_BILL',
  'CUSTOMER_RECEIPT',
  'SUPPLIER_PAYMENT',
  'JOURNAL',
] as const

export const DOCUMENT_SEQUENCE_STATUSES = ['ACTIVE', 'INACTIVE'] as const

const TYPE_LABELS: Record<string, string> = {
  QUOTATION: 'Quotation',
  SERVICE_ORDER: 'Service Order',
  SERVICE_CHARGE: 'Service Charge',
  CUSTOMER_INVOICE: 'Customer Invoice',
  SUPPLIER_BILL: 'Supplier Bill',
  CUSTOMER_RECEIPT: 'Customer Receipt',
  SUPPLIER_PAYMENT: 'Supplier Payment',
  JOURNAL: 'Journal Entry',
}

const LEGACY_TYPES: Record<string, string> = {
  Quotation: 'QUOTATION',
  'Service Order': 'SERVICE_ORDER',
  'Service Charge': 'SERVICE_CHARGE',
  'Financial Document': 'CUSTOMER_INVOICE',
  Receipt: 'CUSTOMER_RECEIPT',
  Payment: 'SUPPLIER_PAYMENT',
  Journal: 'JOURNAL',
}

export function isDocumentSequenceType(value: string) {
  return (DOCUMENT_SEQUENCE_TYPES as readonly string[]).includes(value)
}

export function documentSequenceTypeLabel(value: unknown) {
  const type = String(value || '')
  return TYPE_LABELS[type] || type.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, letter => letter.toUpperCase())
}

export function documentSequencePreview(record: Record<string, unknown>) {
  const prefix = String(record.prefix || '').trim()
  const year = Number(record.year || record.periodYear || new Date().getFullYear())
  const next = Math.max(0, Number(record.lastValue || 0)) + 1
  const padding = Math.max(1, Number(record.paddingLength || 6))
  return [prefix, year, String(next).padStart(padding, '0')].filter(Boolean).join('-')
}

export function normalizeDocumentSequenceRecord(record: FreightRecord): FreightRecord {
  const documentType = LEGACY_TYPES[String(record.documentType || '')] || String(record.documentType || '')
  return {
    ...record,
    documentType,
    year: Number(record.year || record.periodYear || new Date().getFullYear()),
    prefix: String(record.prefix || '').trim(),
    lastValue: Math.max(0, Number(record.lastValue || 0)),
    paddingLength: Math.max(1, Number(record.paddingLength || 6)),
    status: String(record.status || 'ACTIVE').toUpperCase(),
  }
}

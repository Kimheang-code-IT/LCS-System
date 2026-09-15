import type { FreightRecord } from '~/types/freight/record'

/** Printable document templates supported by the shared print workflow. */
export type PrintTemplateId = 'tax-invoice' | 'debit-note'

export interface PrintTemplateDef {
  id: PrintTemplateId
  labelKey: string
  descriptionKey: string
  icon: string
  orientation: 'landscape' | 'portrait'
  collections: readonly string[]
}

export const PRINT_TEMPLATES: PrintTemplateDef[] = [
  {
    id: 'tax-invoice',
    labelKey: 'freight.print.templates.taxInvoice',
    descriptionKey: 'freight.print.templates.taxInvoiceDesc',
    icon: 'i-lucide-receipt-text',
    orientation: 'portrait',
    collections: ['debitNotes', 'jobCharges', 'jobs', 'quotations'],
  },
  {
    id: 'debit-note',
    labelKey: 'freight.print.templates.debitNote',
    descriptionKey: 'freight.print.templates.debitNoteDesc',
    icon: 'i-lucide-credit-card',
    orientation: 'portrait',
    collections: ['debitNotes', 'jobCharges', 'jobs', 'quotations'],
  },
]

/** Collections that can go through the shared print workflow. */
export const PRINT_SUPPORTED_COLLECTIONS = [...new Set(PRINT_TEMPLATES.flatMap(t => [...t.collections]))]

export function supportedPrintTemplates(collection: string): PrintTemplateDef[] {
  return PRINT_TEMPLATES.filter(template => template.collections.includes(collection))
}

/**
 * Derive the initially-selected template from the record's collection and
 * document type. Users can always switch in the selection modal.
 */
export function defaultPrintTemplate(collection: string, record?: FreightRecord | null): PrintTemplateId {
  if (collection === 'debitNotes') {
    const documentType = String(record?.documentType || '').toUpperCase()
    return documentType === 'CUSTOMER_INVOICE' ? 'tax-invoice' : 'debit-note'
  }
  if (collection === 'quotations') return 'tax-invoice'
  if (collection === 'jobs') return 'debit-note'
  return 'tax-invoice'
}

export function printTemplateById(id: string): PrintTemplateDef | null {
  return PRINT_TEMPLATES.find(template => template.id === id) || null
}

/**
 * Debit-note approval grid captions (i18n keys), driven by configuration and
 * rendered only when non-empty.
 */
export const DEBIT_NOTE_APPROVAL_SLOTS: readonly string[] = [
  'freight.print.fields.staff',
  'freight.print.fields.manager',
  'freight.print.fields.generalManager',
  'freight.print.fields.director',
  'freight.print.fields.president',
]

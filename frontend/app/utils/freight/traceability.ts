import type { FreightRecord } from '~/types/freight/record'

export type TraceLinkKind = 'quotation' | 'serviceOrder' | 'serviceCharge' | 'financeInvoice' | 'postedJournal'

export type TraceLink = {
  id: string
  sourceTypeKey: TraceLinkKind
  sourceNo: string
  createdAt: string
  path: string
}

export type TraceLookups = {
  jobs: FreightRecord[]
  quotations: FreightRecord[]
  charges: FreightRecord[]
  documents: FreightRecord[]
  journals: FreightRecord[]
}

export type DocumentTraceability = {
  invoiceNo: string
  journalId: string
  journalNo: string
  sourceChargeNo: string
  links: TraceLink[]
}

function text(value: unknown) {
  return String(value || '').trim()
}

function byId(rows: FreightRecord[], id: string) {
  if (!id) return undefined
  return rows.find(row => String(row.id) === id)
}

function link(
  kind: TraceLinkKind,
  record: FreightRecord | undefined,
  sourceNo: unknown,
  path: string,
  createdAt?: unknown,
): TraceLink | undefined {
  if (!record?.id) return undefined
  const no = text(sourceNo)
  if (!no) return undefined
  return {
    id: String(record.id),
    sourceTypeKey: kind,
    sourceNo: no,
    createdAt: text(createdAt || record.date || record.createdAt || record.postedAt),
    path,
  }
}

function findJob(jobNo: string, lookups: TraceLookups) {
  if (!jobNo) return undefined
  return lookups.jobs.find(row => text(row.jobNo) === jobNo)
}

function findQuotation(quotationNo: string, lookups: TraceLookups) {
  if (!quotationNo) return undefined
  return lookups.quotations.find(row => text(row.quotationNo) === quotationNo)
}

export function linkedFinanceInvoiceForCharge(charge: FreightRecord, lookups: TraceLookups) {
  const id = text(charge.financialDocumentId)
  if (id) {
    const byKey = byId(lookups.documents, id)
    if (byKey) return byKey
  }
  const chargeId = text(charge.id)
  if (chargeId) {
    const fromSource = lookups.documents.find(row => text(row.sourceChargeId) === chargeId)
    if (fromSource) return fromSource
  }
  const invoiceNo = text(charge.invoiceNo)
  if (!invoiceNo) return undefined
  return lookups.documents.find(row => text(row.debitNoteNo) === invoiceNo)
}

export function sourceChargeForFinanceDocument(document: FreightRecord, lookups: TraceLookups) {
  const sourceId = text(document.sourceChargeId)
  if (sourceId) {
    const source = byId(lookups.charges, sourceId)
    if (source) return source
  }
  const documentId = text(document.id)
  if (documentId) {
    const byDocument = lookups.charges.find(row => text(row.financialDocumentId) === documentId)
    if (byDocument) return byDocument
  }
  const documentNo = text(document.debitNoteNo)
  if (!documentNo) return undefined
  return lookups.charges.find(row => text(row.invoiceNo) === documentNo)
}

export type ServiceChargeInvoiceAction = 'create' | 'view' | null

export function serviceChargeInvoiceAction(options: {
  status: unknown
  hasInvoice: boolean
  canCreate: boolean
  canView: boolean
}): ServiceChargeInvoiceAction {
  if (String(options.status || '').trim().toUpperCase() !== 'ISSUED') return null
  if (options.hasInvoice) return options.canView ? 'view' : null
  return options.canCreate ? 'create' : null
}

function findJournal(document: FreightRecord | undefined, extraId: string, lookups: TraceLookups) {
  const journalId = text(document?.journalId || extraId)
  if (journalId) {
    const byKey = byId(lookups.journals, journalId)
    if (byKey) return byKey
  }
  const sourceId = text(document?.id)
  if (!sourceId) return undefined
  return lookups.journals.find(row => text(row.sourceDocumentId) === sourceId)
}

function push(rows: TraceLink[], item: TraceLink | undefined) {
  if (!item) return
  if (rows.some(row => row.path === item.path && row.id === item.id)) return
  rows.push(item)
}

/** Quotation → service order → service charge → finance invoice → posted journal. */
export function resolveDocumentTraceability(
  record: FreightRecord,
  kind: 'charge' | 'finance',
  lookups: TraceLookups,
): DocumentTraceability {
  const charge = kind === 'charge'
    ? record
    : sourceChargeForFinanceDocument(record, lookups)
  const invoice = kind === 'finance' ? record : linkedFinanceInvoiceForCharge(record, lookups)
  const job = findJob(text(invoice?.jobNo || charge?.jobNo || record.jobNo), lookups)
  const quotation = findQuotation(text(job?.quotationNo), lookups)
  const journal = findJournal(invoice, text(record.journalId || charge?.journalId), lookups)
  const links: TraceLink[] = []
  push(links, link('quotation', quotation, quotation?.quotationNo, '/quotations', quotation?.date))
  push(links, link('serviceOrder', job, job?.jobNo, '/service-orders', job?.date || job?.createdAt))
  if (kind !== 'charge') {
    push(links, link('serviceCharge', charge, charge?.chargeNo || charge?.id, '/service-charges', charge?.documentDate || charge?.createdAt))
  }
  if (kind !== 'finance') {
    push(links, link('financeInvoice', invoice, invoice?.debitNoteNo, '/finance/documents', invoice?.date))
  }
  push(links, link('postedJournal', journal, journal?.entryNo, '/finance/journals', journal?.postingDate || journal?.postedAt))
  return {
    invoiceNo: text(invoice?.debitNoteNo || record.invoiceNo),
    journalId: text(journal?.id || record.journalId),
    journalNo: text(journal?.entryNo),
    sourceChargeNo: text(charge?.chargeNo || record.sourceChargeId),
    links,
  }
}

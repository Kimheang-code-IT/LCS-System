import { describe, expect, it } from 'vitest'
import { createLcsFreightSeed } from './fixtures/lcs-seed'
import type { FreightRecord } from '../app/types/freight/record'
import {
  linkedFinanceInvoiceForCharge,
  resolveDocumentTraceability,
  serviceChargeInvoiceAction,
  sourceChargeForFinanceDocument,
} from '../app/utils/freight/traceability'

function lookups() {
  const seed = createLcsFreightSeed()
  return {
    jobs: seed.jobs,
    quotations: seed.quotations,
    charges: seed.jobCharges,
    documents: seed.debitNotes,
    journals: seed.journals,
  }
}

describe('resolveDocumentTraceability', () => {
  it('chains quotation, job, invoice, and posted journal for an issued service charge', () => {
    const ctx = lookups()
    const charge = ctx.charges.find(row => row.id === 'jc-001')
    expect(charge).toBeTruthy()
    const trace = resolveDocumentTraceability(charge!, 'charge', ctx)
    expect(trace.invoiceNo).toBe('DN-2608-041')
    expect(trace.journalNo).toBe('JE-2026-0041')
    expect(trace.links.map(row => row.sourceTypeKey)).toEqual([
      'quotation',
      'serviceOrder',
      'financeInvoice',
      'postedJournal',
    ])
    expect(trace.links.map(row => row.sourceNo)).toEqual([
      'QT-2026-0812',
      'LCS-IM-260821',
      'DN-2608-041',
      'JE-2026-0041',
    ])
  })

  it('does not invent links for a new service charge', () => {
    const ctx = lookups()
    const trace = resolveDocumentTraceability({ id: '' } as FreightRecord, 'charge', ctx)
    expect(trace.links).toEqual([])
    expect(trace.invoiceNo).toBe('')
    expect(trace.journalNo).toBe('')
  })

  it('points a finance invoice back to its source service charge', () => {
    const ctx = lookups()
    const invoice = ctx.documents.find(row => row.id === 'dn-001')
    expect(invoice).toBeTruthy()
    const trace = resolveDocumentTraceability(invoice!, 'finance', ctx)
    expect(trace.sourceChargeNo).toMatch(/^SC-/)
    expect(trace.links.map(row => row.sourceTypeKey)).toContain('serviceCharge')
    expect(trace.links.map(row => row.sourceTypeKey)).not.toContain('financeInvoice')
  })

  it('resolves legacy links by source id, document id, and invoice number', () => {
    const ctx = lookups()
    const invoice = ctx.documents.find(row => row.id === 'dn-001')!
    const charge = ctx.charges.find(row => row.id === 'jc-001')!

    expect(linkedFinanceInvoiceForCharge({ ...charge, financialDocumentId: '' }, ctx)?.id).toBe('dn-001')
    expect(linkedFinanceInvoiceForCharge({ ...charge, financialDocumentId: '', id: 'legacy-charge' }, ctx)?.id).toBe('dn-001')
    expect(sourceChargeForFinanceDocument({ ...invoice, sourceChargeId: '' }, ctx)?.id).toBe('jc-001')
    expect(sourceChargeForFinanceDocument({ ...invoice, sourceChargeId: '', id: 'legacy-document' }, ctx)?.id).toBe('jc-001')
  })
})

describe('service charge invoice actions', () => {
  it.each([
    ['Draft', false, true, true, null],
    ['Issued', false, true, true, 'create'],
    ['Issued', false, false, true, null],
    ['Issued', true, true, true, 'view'],
    ['Issued', true, true, false, null],
  ] as const)('resolves %s linked=%s create=%s view=%s', (status, hasInvoice, canCreate, canView, expected) => {
    expect(serviceChargeInvoiceAction({ status, hasInvoice, canCreate, canView })).toBe(expected)
  })
})

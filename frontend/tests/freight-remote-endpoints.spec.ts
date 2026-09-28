import { describe, expect, it } from 'vitest'
import {
  JOB_DERIVED_COLLECTIONS,
  endpointFor,
  normalizeItems,
  stripRecord,
} from '../app/utils/api/freight-remote'

describe('freight-remote endpoint mapping', () => {
  it('routes document collections to their canonical backend paths', () => {
    expect(endpointFor('quotations')).toMatchObject({
      path: '/api/v1/quotations',
      upsertViaPost: true,
      bulkDelete: true,
    })
    expect(endpointFor('jobs')).toMatchObject({
      path: '/api/v1/service-orders',
      bulkDelete: true,
    })
    expect(endpointFor('jobCharges')).toMatchObject({
      path: '/api/v1/service-charges',
      upsertViaPost: true,
    })
    expect(endpointFor('journals')).toMatchObject({
      path: '/api/v1/journal-entries',
    })
    expect(endpointFor('journals')?.itemPath?.('7')).toBe('/api/v1/journal-entries/7')
    expect(endpointFor('journals')?.bulkDelete).toBeFalsy()
  })

  it('filters financial documents by document type', () => {
    const expected: Record<string, string> = {
      debitNotes: 'CUSTOMER_INVOICE',
      customerPayments: 'CUSTOMER_RECEIPT',
      supplierCosts: 'SUPPLIER_BILL',
      supplierPayments: 'SUPPLIER_PAYMENT',
    }
    for (const [collection, documentType] of Object.entries(expected)) {
      expect(endpointFor(collection)).toMatchObject({
        path: '/api/v1/financial-documents',
        query: { document_type: documentType },
        upsertViaPost: true,
        bulkDelete: true,
      })
    }
  })

  it('keeps legacy aliases pointing at the canonical resources', () => {
    expect(endpointFor('chargeTypes')?.path).toBe('/api/v1/feeTypes')
    expect(endpointFor('suppliers')?.path).toBe('/api/v1/businessParties')
    expect(endpointFor('cashAccounts')).toMatchObject({
      path: '/api/v1/financial-accounts',
      readOnly: true,
    })
  })

  it('marks read-only projections so the store never writes to them', () => {
    for (const collection of ['auditLogs', 'receivables', 'payables', 'profitability']) {
      expect(endpointFor(collection)?.readOnly).toBe(true)
    }
  })

  it('reports derived job collections separately', () => {
    expect(JOB_DERIVED_COLLECTIONS).toEqual(['containerRequirements', 'actualContainers'])
    expect(endpointFor('containerRequirements')).toBeNull()
    expect(endpointFor('unknown-collection')).toBeNull()
  })

  it('builds item paths for generic reference collections', () => {
    expect(endpointFor('businessParties')?.itemPath?.('3')).toBe('/api/v1/businessParties/3')
    expect(endpointFor('businessParties')?.bulkDelete).toBe(true)
  })
})

describe('freight-remote payload helpers', () => {
  it('normalizes arrays, envelopes, and invalid payloads', () => {
    expect(normalizeItems([{ id: '1' }])).toEqual([{ id: '1' }])
    expect(normalizeItems({ items: [{ id: '2' }] })).toEqual([{ id: '2' }])
    expect(normalizeItems({ data: [] })).toEqual([])
    expect(normalizeItems(null)).toEqual([])
  })

  it('strips client-only underscore keys before sending to the API', () => {
    expect(stripRecord({ id: '1', name: 'Row', _selected: true, _dirty: false })).toEqual({
      id: '1',
      name: 'Row',
    })
  })
})

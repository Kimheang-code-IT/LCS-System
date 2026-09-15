import { describe, expect, it } from 'vitest'
import type { FreightRecord } from '../app/types/freight/record'
import { buildChargePrintViewModel } from '../app/utils/freight/charge-print'

const context = {
  organizations: [{
    id: 'org-001',
    legalName: 'LCS Freight Forwarding Co., Ltd.',
    taxIdentifier: 'K001-LCS',
  }],
  branches: [{ id: 1, name: 'Bavet' }],
  companies: [{
    id: 'co-1',
    name: 'QiLu Cambodia Co., Ltd.',
    legalName: 'QiLu Cambodia Co., Ltd.',
    taxIdentifier: 'TIN-QILU',
  }],
  jobs: [],
  financialAccounts: [],
  logoUrl: '/lcs-invoice-logo.png',
  localCurrency: 'KHR',
}

function charge(overrides: Record<string, unknown> = {}): FreightRecord {
  return {
    id: 'jc-print',
    chargeNo: 'SC-2026-0001',
    documentDate: '2026-08-20',
    customer: 'QiLu Cambodia Co., Ltd.',
    jobNo: 'LCS-IM-260821',
    currency: 'USD',
    status: 'Issued',
    feeLines: [
      {
        feeType: 'FREIGHT_SERVICE',
        description: 'Ocean freight',
        containerNo: 'MSCU 482190-7',
        quantity: 1,
        unitAmount: 1200,
        discount: 0,
        taxAmount: 120,
        amount: 1320,
      },
      {
        feeType: 'INLAND_TRANSPORT',
        description: 'Trucking',
        containerNo: 'TGHU 771923-4',
        quantity: 1,
        unitAmount: 980,
        discount: 0,
        taxAmount: 98,
        amount: 1078,
      },
    ],
    ...overrides,
  } as FreightRecord
}

describe('service charge print helpers', () => {
  it('builds a whole-charge tax invoice from all fee lines', () => {
    const model = buildChargePrintViewModel(charge(), 'tax-invoice', context)
    expect(model.document.documentType).toBe('CUSTOMER_INVOICE')
    expect(model.document.number).toBe('SC-2026-0001')
    expect(model.lines).toHaveLength(2)
    expect(model.totals.grandTotal).toBe(2398)
  })

  it('builds a per-fee-line tax invoice with auto-split document numbers', () => {
    const first = buildChargePrintViewModel(charge(), 'tax-invoice', context, { lineIndex: 0 })
    const second = buildChargePrintViewModel(charge(), 'tax-invoice', context, { lineIndex: 1 })
    expect(first.document.number).toBe('SC-2026-0001/1')
    expect(second.document.number).toBe('SC-2026-0001/2')
    expect(first.lines).toHaveLength(1)
    expect(second.lines).toHaveLength(1)
    expect(first.lines[0]?.amount).toBe(1320)
    expect(second.lines[0]?.amount).toBe(1078)
    expect(first.shipment.containerNo).toBe('MSCU 482190-7')
    expect(second.shipment.containerNo).toBe('TGHU 771923-4')
  })
})

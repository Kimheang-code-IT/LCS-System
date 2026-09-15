import { describe, expect, it } from 'vitest'
import type { FreightRecord } from '../app/types/freight/record'
import {
  buildQuotationPrintViewModel,
  expandQuotationContainerSlots,
} from '../app/utils/freight/quotation-print'

const context = {
  organizations: [{
    id: 'org-001',
    organizationId: 1,
    legalName: 'LCS Freight Forwarding Co., Ltd.',
    legalNameKh: 'អិលស៊ីអេស',
    taxIdentifier: 'K001-LCS',
    address: 'Phnom Penh',
    phone: '+855 23 000 000',
    email: 'info@lcs.com.kh',
  }],
  branches: [{ id: 1, name: 'Bavet' }],
  companies: [{
    id: 'co-1',
    name: 'QiLu Cambodia Co., Ltd.',
    legalName: 'QiLu Cambodia Co., Ltd.',
    taxIdentifier: 'TIN-QILU',
    address: 'Manhattan SEZ',
    phone: '+855 12 889 221',
    email: 'vannak@qilu.com.kh',
  }],
  jobs: [{
    id: 'job-1',
    jobNo: 'LCS-IM-260818',
    blNo: 'BL-8814',
    vessel: 'MV DEMO',
    loadingPort: 'CATLAI',
    dischargePort: 'MANHATTAN',
    containerNo: 'MSCU 482190-7',
    containerType: '40HC',
  }],
  financialAccounts: [{
    id: 'fa-1',
    accountName: 'Operating Account',
    accountType: 'Bank',
    bankName: 'ABA Bank',
    accountNumberMasked: '****5678',
    swiftCode: 'ABAAKHPP',
  }],
  logoUrl: '/lcs-invoice-logo.png',
  localCurrency: 'KHR',
}

function quotation(overrides: Record<string, unknown> = {}): FreightRecord {
  return {
    id: 'qt-print',
    quotationNo: 'QT-2026-0814',
    date: '2026-08-14',
    validUntil: '2026-09-20',
    customer: 'QiLu Cambodia Co., Ltd.',
    phone: '+855 12 889 221',
    email: 'vannak@qilu.com.kh',
    currency: 'USD',
    total: 2400,
    amount: 2400,
    status: 'Accepted',
    convertedJobNo: 'LCS-IM-260818',
    pickup: 'CATLAI',
    delivery: 'MANHATTAN',
    containerRequirements: [
      { containerType: '40HC', quantity: 2, description: 'Two high-cube containers' },
    ],
    pricingLines: [
      { feeType: 'INLAND_TRANSPORT', containerType: '40HC', description: 'Cross-border freight', quantity: 2, unit: 'Container', unitPrice: 1200, total: 2400 },
    ],
    ...overrides,
  } as FreightRecord
}

describe('quotation print helpers', () => {
  it('expands container requirements by quantity', () => {
    expect(expandQuotationContainerSlots(quotation())).toHaveLength(2)
    expect(expandQuotationContainerSlots(quotation()).map(slot => slot.containerType)).toEqual(['40HC', '40HC'])
  })

  it('builds a whole-quotation tax invoice view model', () => {
    const model = buildQuotationPrintViewModel(quotation(), 'tax-invoice', context)
    expect(model.document.number).toBe('QT-2026-0814')
    expect(model.document.documentType).toBe('CUSTOMER_INVOICE')
    expect(model.lines).toHaveLength(1)
    expect(model.lines[0]?.amount).toBe(2400)
    expect(model.shipment.workNo).toBe('LCS-IM-260818')
    expect(model.shipment.blNo).toBe('BL-8814')
  })

  it('builds per-container debit notes with split amounts', () => {
    const first = buildQuotationPrintViewModel(quotation(), 'debit-note', context, { containerIndex: 0 })
    const second = buildQuotationPrintViewModel(quotation(), 'debit-note', context, { containerIndex: 1 })
    expect(first.document.number).toBe('QT-2026-0814/1')
    expect(second.document.number).toBe('QT-2026-0814/2')
    expect(first.shipment.containerType).toBe('40HC')
    expect(first.lines[0]?.amount).toBe(1200)
    expect(second.lines[0]?.amount).toBe(1200)
  })
})

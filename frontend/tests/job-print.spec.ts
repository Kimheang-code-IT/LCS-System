import { describe, expect, it } from 'vitest'
import type { FreightRecord } from '../app/types/freight/record'
import {
  buildJobPrintViewModel,
  expandJobContainerSlots,
} from '../app/utils/freight/job-print'

const context = {
  organizations: [{
    id: 'org-001',
    organizationId: 1,
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

function job(overrides: Record<string, unknown> = {}): FreightRecord {
  return {
    id: 'job-print',
    jobNo: 'LCS-IM-260821',
    date: '2026-08-21',
    customer: 'QiLu Cambodia Co., Ltd.',
    currency: 'USD',
    vatRate: 10,
    blNo: 'BL-8814',
    actualContainers: [
      { id: 'ac-1', containerNo: 'MSCU 482190-7', containerType: '40HC', status: 'Loaded' },
      { id: 'ac-2', containerNo: 'TGHU 771923-4', containerType: '20GP', status: 'Loaded' },
    ],
    containerPayments: [
      { feeType: 'INLAND_TRANSPORT', containerNo: 'MSCU 482190-7', quantity: 1, unitPrice: 1200, lineTotal: 1200 },
      { feeType: 'INLAND_TRANSPORT', containerNo: 'TGHU 771923-4', quantity: 1, unitPrice: 980, lineTotal: 980 },
    ],
    ...overrides,
  } as FreightRecord
}

describe('job print helpers', () => {
  it('expands actual containers into printable slots', () => {
    expect(expandJobContainerSlots(job())).toHaveLength(2)
    expect(expandJobContainerSlots(job()).map(slot => slot.containerNo)).toEqual([
      'MSCU 482190-7',
      'TGHU 771923-4',
    ])
  })

  it('builds per-container tax invoice lines from container payments', () => {
    const model = buildJobPrintViewModel(job(), 'tax-invoice', context, { containerIndex: 0 })
    expect(model.document.number).toBe('LCS-IM-260821/1')
    expect(model.document.documentType).toBe('CUSTOMER_INVOICE')
    expect(model.lines).toHaveLength(1)
    expect(model.lines[0]?.amount).toBe(1200)
    expect(model.shipment.containerNo).toBe('MSCU 482190-7')
  })

  it('builds per-container debit notes with auto-split document numbers', () => {
    const first = buildJobPrintViewModel(job(), 'debit-note', context, { containerIndex: 0 })
    const second = buildJobPrintViewModel(job(), 'debit-note', context, { containerIndex: 1 })
    expect(first.document.number).toBe('LCS-IM-260821/1')
    expect(second.document.number).toBe('LCS-IM-260821/2')
    expect(first.lines[0]?.amount).toBe(1200)
    expect(second.lines[0]?.amount).toBe(980)
  })
})

import { describe, expect, it } from 'vitest'
import type { FreightRecord } from '../app/types/freight/record'
import {
  amountInWords,
  buildPrintViewModel,
  formatDebitNoteAmountInWords,
  numberToEnglishWords,
  printNum,
  printStr,
  printWatermarkFor,
  sumPrintLines,
} from '../app/utils/freight/print-model'
import {
  PRINT_SUPPORTED_COLLECTIONS,
  defaultPrintTemplate,
  supportedPrintTemplates,
} from '../app/config/print-templates'

function record(overrides: Record<string, unknown> = {}): FreightRecord {
  return { id: 'dn-900', ...overrides } as FreightRecord
}

const context = {
  organizations: [
    {
      id: 'org-001',
      organizationId: 1,
      legalName: 'Test Forwarding Co., Ltd.',
      displayName: 'Test Freight',
      legalNameKh: 'ក្រុមហ៊ុន តេស្ត',
      taxIdentifier: 'K001-TEST',
      address: 'Test Road, Test Province',
      phone: '+855 00 000 000',
      email: 'test@example.com',
      defaultCurrency: 'USD',
    },
  ],
  branches: [{ id: 1, name: 'Test Branch' }],
  companies: [
    {
      id: 'co-1',
      name: 'Acme Manufacturing',
      legalName: 'Acme Manufacturing Co., Ltd.',
      taxIdentifier: 'TIN-ACME',
      address: 'Acme Street',
      phone: '+855 11 111 111',
      email: 'acme@example.com',
    },
  ],
  suppliers: [
    {
      id: 'sup-1',
      name: 'NTL Transport',
      legalName: 'NTL Transport',
      taxIdentifier: 'TIN-NTL',
      address: 'Bavet',
      bankName: 'Test Bank',
      accountName: 'NTL Transport',
      accountNumber: '000 123 456',
    },
  ],
  jobs: [
    {
      id: 'job-1',
      jobNo: 'LCS-IM-260001',
      blNo: 'BL-0001',
      vessel: 'MV TEST',
      voyage: 'V-001',
      loadingPort: 'HO CHI MINH PORT',
      dischargePort: 'PHNOM PENH PORT',
      etd: '2026-06-24',
      eta: '2026-06-25',
    },
  ],
  financialAccounts: [
    {
      id: 'fa-1',
      accountName: 'Test Bank Operating',
      accountType: 'Bank',
      bankName: 'Test Bank',
      accountNumberMasked: '****1234',
      swiftCode: 'TESTKHPP',
    },
  ],
  logoUrl: '/lcs-invoice-logo.png',
  localCurrency: 'KHR',
}

describe('print model accessors', () => {
  it('never renders null/undefined/NaN as text', () => {
    expect(printStr(undefined)).toBe('')
    expect(printStr(null)).toBe('')
    expect(printStr(12)).toBe('12')
    expect(printNum('abc')).toBe(0)
    expect(printNum('1,234.5')).toBe(1234.5)
  })

  it('maps statuses to watermarks and leaves operational statuses clean', () => {
    expect(printWatermarkFor('Draft')).toBe('DRAFT')
    expect(printWatermarkFor('DRAFT')).toBe('DRAFT')
    expect(printWatermarkFor('Cancelled')).toBe('CANCELLED')
    expect(printWatermarkFor('REVERSED')).toBe('REVERSED')
    expect(printWatermarkFor('Posted')).toBeNull()
    expect(printWatermarkFor('')).toBeNull()
  })
})

describe('amount in words', () => {
  it('converts numbers deterministically', () => {
    expect(numberToEnglishWords(0)).toBe('zero')
    expect(numberToEnglishWords(979)).toBe('nine hundred seventy-nine')
    expect(numberToEnglishWords(1234567)).toBe('one million two hundred thirty-four thousand five hundred sixty-seven')
  })

  it('is currency-aware for supported currencies', () => {
    expect(amountInWords(979.07, 'USD')).toBe('nine hundred seventy-nine dollars and seven cents only')
    expect(amountInWords(1.01, 'USD')).toBe('one dollar and one cent only')
    expect(amountInWords(440, 'USD')).toBe('four hundred forty dollars only')
    expect(amountInWords(1000, 'KHR')).toBe('one thousand riels only')
  })

  it('formats debit-note amount in words like the DCN sample', () => {
    expect(formatDebitNoteAmountInWords(979.07, 'USD')).toBe('USD NINE HUNDRED SEVENTY NINE AND CENTS SEVEN')
  })

  it('falls back safely for unsupported currencies', () => {
    expect(amountInWords(12.5, 'XYZ')).toBe('12.50 XYZ')
    expect(amountInWords(Number.NaN, 'USD')).toBe('-')
  })
})

describe('print totals', () => {
  it('sums debit/credit and subtotal from normalized lines', () => {
    const lines = [
      { no: 1, reference: 'R', description: 'A', quantity: 1, unit: 'Service', unitPrice: 100, currency: 'USD', debit: 100, credit: 0, amount: 100 },
      { no: 2, reference: 'R', description: 'B', quantity: 1, unit: 'Service', unitPrice: 50, currency: 'USD', debit: 50, credit: 20, amount: 50 },
    ]
    expect(sumPrintLines(lines)).toEqual({ totalDebit: 150, totalCredit: 20, subtotal: 150 })
  })

  it('derives vat and grand total with fallbacks', () => {
    const model = buildPrintViewModel(record({
      currency: 'USD',
      amount: 1087,
      vatRate: 10,
      vat: 108.7,
      total: 1195.7,
    }), 'tax-invoice', context)
    expect(model.totals.subtotal).toBe(1087)
    expect(model.totals.taxAmount).toBe(108.7)
    expect(model.totals.grandTotal).toBe(1195.7)
    expect(model.amountInWords).toContain('one thousand one hundred ninety-five dollars')
  })

  it('keeps tax-inclusive line totals out of the invoice subtotal', () => {
    const model = buildPrintViewModel(record({
      currency: 'USD',
      lines: [{ quantity: 1, unitAmount: 1475, taxAmount: 147.5, amount: 1622.5 }],
      vatRate: 10,
      vat: 147.5,
      total: 1622.5,
    }), 'tax-invoice', context)
    expect(model.lines[0]?.amount).toBe(1475)
    expect(model.totals.subtotal).toBe(1475)
    expect(model.totals.taxAmount).toBe(147.5)
    expect(model.totals.grandTotal).toBe(1622.5)
  })

  it('spells the debit-note balance rather than the tax-invoice grand total', () => {
    const model = buildPrintViewModel(record({
      currency: 'USD',
      lines: [{ quantity: 1, unitAmount: 1475, taxAmount: 147.5, amount: 1622.5 }],
      vat: 147.5,
      total: 1622.5,
    }), 'debit-note', context)
    expect(model.totals.balance).toBe(1475)
    expect(model.amountInWords).toBe('USD ONE THOUSAND FOUR HUNDRED SEVENTY FIVE ONLY')
  })

  it('computes local-currency total only with a valid exchange rate', () => {
    const base = record({ amount: 100, total: 110, currency: 'USD' })
    const withoutRate = buildPrintViewModel(base, 'tax-invoice', context)
    expect(withoutRate.totals.grandTotalLocal).toBe(0)

    const withRate = buildPrintViewModel({ ...base, exchangeRate: 4050 }, 'tax-invoice', context)
    expect(withRate.totals.grandTotalLocal).toBe(110 * 4050)
  })
})

describe('view model mapping', () => {
  it('resolves issuer from organization data and logo from branding settings', () => {
    const model = buildPrintViewModel(record({ customer: 'Acme Manufacturing' }), 'tax-invoice', context)
    expect(model.issuer.legalName).toBe('Test Forwarding Co., Ltd.')
    expect(model.issuer.legalNameKh).toBe('ក្រុមហ៊ុន តេស្ត')
    expect(model.issuer.logoUrl).toBe('/lcs-invoice-logo.png')
    expect(model.party.legalName).toBe('Acme Manufacturing Co., Ltd.')
    expect(model.party.taxIdentifier).toBe('TIN-ACME')
  })

  it('uses branding logoUrl from print context when provided', () => {
    const model = buildPrintViewModel(record(), 'tax-invoice', {
      ...context,
      logoUrl: '/custom-brand-logo.png',
    })
    expect(model.issuer.logoUrl).toBe('/custom-brand-logo.png')
  })

  it('resolves shipment info from the linked service order', () => {
    const model = buildPrintViewModel(record({ jobNo: 'LCS-IM-260001' }), 'debit-note', context)
    expect(model.shipment.workNo).toBe('LCS-IM-260001')
    expect(model.shipment.blNo).toBe('BL-0001')
    expect(model.shipment.vessel).toBe('MV TEST')
    expect(model.shipment.loadingPort).toBe('HO CHI MINH PORT')
  })

  it('uses charge tables and computes balance from debit/credit lines', () => {
    const model = buildPrintViewModel(record({
      debitNoteNo: 'DN-TEST-001',
      currency: 'USD',
      charges: [
        { description: 'Trucking Charge', cambodia: 420, vietnam: 0, cash: 0 },
        { description: 'Lift Off Charge', cambodia: 0, vietnam: 68.54, cash: 0 },
      ],
    }), 'debit-note', context)
    expect(model.lines).toHaveLength(2)
    expect(model.totals.totalDebit).toBeCloseTo(488.54)
    expect(model.totals.totalCredit).toBe(0)
    expect(model.totals.balance).toBeCloseTo(488.54)
  })

  it('resolves settlement from the financial account with only masked data', () => {
    const model = buildPrintViewModel(record({ financialAccount: 'Test Bank Operating' }), 'tax-invoice', context)
    expect(model.settlement.bankName).toBe('Test Bank')
    expect(model.settlement.accountNumber).toBe('****1234')
    expect(model.settlement.swiftCode).toBe('TESTKHPP')
  })

  it('keeps internal/ledger-only fields out of the model', () => {
    const model = buildPrintViewModel(record({
      customsUsername: 'secret-user',
      credentialReference: 'CRED-TEST',
      internalNote: 'do not print',
    }), 'tax-invoice', context)
    expect(JSON.stringify(model)).not.toContain('secret-user')
    expect(JSON.stringify(model)).not.toContain('CRED-TEST')
    expect(JSON.stringify(model)).not.toContain('do not print')
  })

  it('falls back to dashes for missing optional shipment and bank fields', () => {
    const model = buildPrintViewModel(record({ customer: 'Unknown Party' }), 'debit-note', context)
    expect(model.shipment.vessel).toBe('')
    expect(model.settlement.accountName).toBe('Test Bank Operating')
    expect(model.party.address).toBe('')
  })
})

describe('default template selection', () => {
  it('defaults customer invoices to the tax invoice and other finance documents to the debit note', () => {
    expect(defaultPrintTemplate('debitNotes', record({ documentType: 'CUSTOMER_INVOICE' }))).toBe('tax-invoice')
    expect(defaultPrintTemplate('debitNotes', record({ documentType: 'SUPPLIER_BILL' }))).toBe('debit-note')
    expect(defaultPrintTemplate('debitNotes', record({}))).toBe('debit-note')
    expect(defaultPrintTemplate('jobCharges', record({}))).toBe('tax-invoice')
  })

  it('exposes both templates for supported collections only', () => {
    expect(PRINT_SUPPORTED_COLLECTIONS.sort()).toEqual(['debitNotes', 'jobCharges', 'jobs', 'quotations'].sort())
    expect(supportedPrintTemplates('debitNotes')).toHaveLength(2)
    expect(supportedPrintTemplates('quotations')).toHaveLength(2)
    expect(supportedPrintTemplates('jobs')).toHaveLength(2)
    expect(supportedPrintTemplates('journals')).toHaveLength(0)
  })

  it('defaults quotations to the tax invoice template', () => {
    expect(defaultPrintTemplate('quotations', record({}))).toBe('tax-invoice')
  })
})

describe('watermark selection in the view model', () => {
  it('marks drafts and cancelled documents, posted documents stay clean', () => {
    expect(buildPrintViewModel(record({ status: 'Draft' }), 'debit-note', context).watermark).toBe('DRAFT')
    expect(buildPrintViewModel(record({ status: 'Cancelled' }), 'debit-note', context).watermark).toBe('CANCELLED')
    expect(buildPrintViewModel(record({ status: 'Posted' }), 'debit-note', context).watermark).toBeNull()
  })
})

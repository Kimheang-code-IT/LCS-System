import { describe, expect, it } from 'vitest'
import { financialContainerOptions, financialPrintModel, type FinancialPrintData } from '../app/utils/freight/financial-print'
import { buildPrintViewModel } from '../app/utils/freight/print-model'
import { buildPrintRoute, printTemplateQuery } from '../app/utils/freight/print-navigation'

function data(): FinancialPrintData {
  const base = buildPrintViewModel({ id: '91', documentNo: 'INV-91' }, 'tax-invoice')
  return {
    containers: [{ id: '11', number: 'ABCU1234567', type: '40HC' }, { id: '12', number: 'MSCU7654321', type: '40HC' }],
    selectedContainerId: '', taxInvoiceEligible: false, warnings: [],
    model: {
      ...base, precision: 2,
      document: { ...base.document, number: 'INV-91', exchangeRate: '1.23000000', titleKey: 'freight.print.title.invoice' },
      lines: [{ no: 1, reference: 'SO-1', description: 'រក្សាទុក / Stored charge', descriptionKh: '', quantity: '1.000',
        unit: 'CONT', unitPrice: '400.0000', currency: 'EUR', amount: '400.0000', debit: '389.2500', credit: '0.0000' }],
      totals: { ...base.totals, currency: 'EUR', subtotal: '400.0000', discount: '20.0000', taxableAmount: '380.0000',
        taxRate: '0', taxAmount: '9.2500', grandTotal: '389.2500', totalDebit: '389.2500',
        totalCredit: '0', balance: '389.2500', localCurrency: 'USD', exchangeRate: '1.23000000',
        grandTotalLocal: '478.7775', outstanding: '89.2500' },
    },
  }
}

describe('stored financial print projection', () => {
  it('uses the supplied totals, discount, tax and stored base amount without repricing', () => {
    const source = data()
    const before = JSON.stringify(source)
    const model = financialPrintModel(source)
    expect(model.totals).toMatchObject({ currency: 'EUR', subtotal: 400, discount: 20, taxAmount: 9.25,
      taxRate: 0, grandTotal: 389.25, grandTotalLocal: 478.7775, outstanding: 89.25 })
    expect(model.document.number).toBe('INV-91')
    expect(model.document.titleKey).toBe('freight.print.title.invoice')
    expect(model.lines[0]?.debit).toBe(389.25)
    expect(model.lines[0]?.description).toContain('រក្សាទុក')
    expect(JSON.stringify(source)).toBe(before)
  })

  it('identifies same-type boxes by stable actual ID and number, never by type', () => {
    expect(financialContainerOptions(data()).map(row => [row.value, row.label])).toEqual([
      ['11', 'ABCU1234567'], ['12', 'MSCU7654321'],
    ])
    expect(financialContainerOptions(null)).toEqual([])
    expect(buildPrintRoute({ collection: 'debitNotes', recordId: '91', template: 'debit-note',
      containerId: '12', autoPrint: false }).query).toMatchObject({ containerId: '12', template: 'debit-note' })
  })

  it('keeps container-breakdown amounts and draft watermark supplied by the server', () => {
    const source = data()
    source.model.isContainerBreakdown = true
    source.model.watermark = 'DRAFT'
    const model = financialPrintModel(source)
    expect(model.isContainerBreakdown).toBe(true)
    expect(model.watermark).toBe('DRAFT')
    expect(model.amountInWords).toContain('EUR')
  })

  it('omits cents words for unsupported fractional precision rather than rounding them', () => {
    const source = data()
    source.model.precision = 3
    source.model.totals.grandTotal = '1.234'
    const model = financialPrintModel(source)
    expect(model.totals.grandTotal).toBe(1.234)
    expect(model.amountInWords).toBe('')
  })

  it('clears a previous container scope when switching to the consolidated invoice', () => {
    const debit = buildPrintRoute({ collection: 'debitNotes', recordId: '91', template: 'debit-note', containerId: '12', autoPrint: false })
    const invoice = printTemplateQuery(debit.query, 'tax-invoice')
    expect(invoice).not.toHaveProperty('containerId')
    expect(invoice.returnTo).toBe(debit.query.returnTo)
    expect(printTemplateQuery(debit.query, 'debit-note').containerId).toBe('12')
  })

  it('preserves distinct document and base currency precisions', () => {
    const source = data()
    source.model.precision = 0
    source.model.totals.currency = 'JPY'
    source.model.totals.localCurrency = 'USD'
    source.model.totals.localPrecision = '2'
    source.model.totals.grandTotalLocal = '12.34'
    const model = financialPrintModel(source)
    expect(model.precision).toBe(0)
    expect(model.totals.localPrecision).toBe(2)
    expect(model.totals.grandTotalLocal).toBe(12.34)
  })
})


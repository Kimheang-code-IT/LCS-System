import { describe, expect, it } from 'vitest'
import {
  buildFinanceSummary,
  financeDocumentBehavior,
  scaledDecimal,
  scaledNumber,
} from '../app/utils/freight/finance-summary'

const charges = [
  { id: 'c1', status: 'Draft', currency: 'USD', total: 100.1 },
  { id: 'c2', status: 'Issued', currency: 'USD', total: 200.2, financialDocumentId: 'd1' },
]

describe('service order finance summary', () => {
  it('adds Service Charge totals without floating-point drift', () => {
    const groups = buildFinanceSummary({
      charges: [
        { id: 'a', status: 'Draft', currency: 'USD', total: 0.1 },
        { id: 'b', status: 'Draft', currency: 'USD', total: 0.2 },
      ],
      entries: [],
      primaryCurrency: 'USD',
    })
    expect(groups[0]!.totalCharges).toBe(0.3)
    expect(scaledNumber(scaledDecimal('0.1') + scaledDecimal('0.2'))).toBe(0.3)
  })

  it('separates charged from uncharged and keeps discounts/taxes in the charge total', () => {
    const [group] = buildFinanceSummary({ charges, entries: [], primaryCurrency: 'USD' })
    expect(group).toMatchObject({
      currency: 'USD',
      totalCharges: 300.3,
      chargedAmount: 200.2,
      unchargedAmount: 100.1,
      totalExpenses: 0,
      estimated: true,
    })
  })

  it('adds the container-payment sheet to the customer charges', () => {
    const [group] = buildFinanceSummary({
      charges: [{ id: 'sc', status: 'Draft', currency: 'USD', total: 200 }],
      containerCharge: { currency: 'USD', total: 400 },
      entries: [],
      primaryCurrency: 'USD',
    })
    expect(group).toMatchObject({
      totalCharges: 600,
      chargedAmount: 0,
      unchargedAmount: 600,
      netAmount: 600,
      estimated: true,
    })
  })

  it('does not clamp a credit/overcharge to zero', () => {
    const [group] = buildFinanceSummary({
      charges: [{ id: 'credit', status: 'Draft', currency: 'USD', total: -25 }],
      entries: [],
      primaryCurrency: 'USD',
    })
    expect(group!.totalCharges).toBe(-25)
    expect(group!.unchargedAmount).toBe(-25)
  })

  it('counts qualifying expenses but not settlements or reversals', () => {
    const [group] = buildFinanceSummary({
      charges,
      entries: [
        { id: 'e1', status: 'Draft', behavior: 'SUPPLIER_BILL', currency: 'USD', total: 40 },
        { id: 'e2', status: 'Posted', behavior: 'OTHER_EXPENSE', currency: 'USD', total: 10 },
        { id: 'p1', status: 'Posted', behavior: 'SUPPLIER_PAYMENT', currency: 'USD', total: 25 },
        { id: 'e3', status: 'Reversed', behavior: 'SUPPLIER_BILL', currency: 'USD', total: 99 },
      ],
      primaryCurrency: 'USD',
    })
    expect(group!.totalExpenses).toBe(50)
    expect(group!.draftExpenses).toBe(40)
    expect(group!.netAmount).toBe(250.3)
    expect(group!.estimated).toBe(true)
  })

  it('previews internal cost until its supplier bill exists', () => {
    const preview = buildFinanceSummary({
      charges,
      entries: [],
      internalCharges: [{ currency: 'USD', costTotal: 40 }],
      primaryCurrency: 'USD',
    })[0]!
    expect(preview.totalExpenses).toBe(40)
    expect(preview.estimated).toBe(true)

    const documented = buildFinanceSummary({
      charges,
      entries: [{ id: 'bill', status: 'Draft', behavior: 'SUPPLIER_BILL', currency: 'USD', total: 40 }],
      internalCharges: [{ currency: 'USD', costTotal: 40, supplierDocumentId: '9' }],
      primaryCurrency: 'USD',
    })[0]!
    expect(documented.totalExpenses).toBe(40)
  })

  it('uses authoritative posted outstanding and ignores draft invoices', () => {
    const [group] = buildFinanceSummary({
      charges,
      entries: [
        { id: 'i1', status: 'Posted', behavior: 'CUSTOMER_INVOICE', currency: 'USD', total: 200, paidAmount: 50, outstanding: 150 },
        { id: 'i2', status: 'Draft', behavior: 'CUSTOMER_INVOICE', currency: 'USD', total: 80 },
        { id: 'i3', status: 'Reversed', behavior: 'CUSTOMER_INVOICE', currency: 'USD', total: 20, outstanding: 20 },
      ],
      primaryCurrency: 'USD',
    })
    expect(group!.outstandingBalance).toBe(150)
  })

  it('applies approved credit adjustments without clamping negative balances', () => {
    const [group] = buildFinanceSummary({
      charges,
      entries: [
        { id: 'inv', status: 'Posted', behavior: 'CUSTOMER_INVOICE', currency: 'USD', total: 100, paidAmount: 80, outstanding: 20 },
        { id: 'cn', status: 'Posted', behavior: 'CREDIT_NOTE', currency: 'USD', total: 35, outstanding: 35 },
        { id: 'scn', status: 'Posted', behavior: 'SUPPLIER_CREDIT_NOTE', currency: 'USD', total: 10 },
      ],
      primaryCurrency: 'USD',
    })
    // 20 outstanding invoice − 35 approved credit = −15 customer credit.
    expect(group!.outstandingBalance).toBe(-15)
    expect(group!.totalExpenses).toBe(-10)
  })

  it('keeps currencies separate instead of adding them', () => {
    const groups = buildFinanceSummary({
      charges: [
        { id: 'u', status: 'Issued', currency: 'USD', total: 100 },
        { id: 'e', status: 'Issued', currency: 'EUR', total: 80 },
      ],
      entries: [{ id: 'exp', status: 'Posted', behavior: 'SUPPLIER_BILL', currency: 'EUR', total: 30 }],
      primaryCurrency: 'USD',
    })
    expect(groups.map(group => group.currency).sort()).toEqual(['EUR', 'USD'])
    expect(groups.find(group => group.currency === 'USD')).toMatchObject({ totalCharges: 100, netAmount: 100 })
    expect(groups.find(group => group.currency === 'EUR')).toMatchObject({ totalCharges: 80, totalExpenses: 30, netAmount: 50 })
  })

  it('overlays an unsaved charge preview without double counting', () => {
    const [group] = buildFinanceSummary({
      charges: [{ id: 'c1', status: 'Draft', currency: 'USD', total: 100 }],
      previewCharge: { id: 'c1', status: 'Draft', currency: 'USD', total: 125 },
      entries: [],
      primaryCurrency: 'USD',
    })
    expect(group!.totalCharges).toBe(125)
  })

  it('returns zeroed metrics when the order has no data yet', () => {
    const [group] = buildFinanceSummary({ charges: [], entries: [], primaryCurrency: 'USD' })
    expect(group).toMatchObject({
      currency: 'USD',
      totalCharges: 0,
      chargedAmount: 0,
      unchargedAmount: 0,
      totalExpenses: 0,
      netAmount: 0,
      outstandingBalance: 0,
      estimated: false,
    })
  })

  it('resolves a document behaviour from the Document Types master', () => {
    expect(financeDocumentBehavior(
      { documentType: 'CUSTOM_INVOICE' },
      [{ code: 'CUSTOM_INVOICE', accountingBehavior: 'CUSTOMER_INVOICE' }],
    )).toBe('CUSTOMER_INVOICE')
    expect(financeDocumentBehavior({ documentType: 'SUPPLIER_BILL' })).toBe('SUPPLIER_BILL')
  })
})

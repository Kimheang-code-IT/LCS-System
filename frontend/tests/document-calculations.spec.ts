import { describe, expect, it } from 'vitest'
import type { FreightRecord } from '../app/types/record'
import { recalculateFreightRecord } from '../app/utils/freight/document-calculations'

describe('document calculations', () => {
  it('normalizes quotation pricing lines and totals', () => {
    const record = {
      id: 'q1',
      pickup: 'Phnom Penh',
      border: 'Bavet',
      delivery: 'HCMC',
      pricingLines: [
        { quantity: 2, unitPrice: 100, discountAmount: 10, taxAmount: 5 },
        { quantity: 1, unitPrice: 50, discountAmount: 0, taxAmount: 0 },
      ],
    } as FreightRecord

    const result = recalculateFreightRecord(
      { kind: 'quotation', collection: 'quotations', path: '/sales/quotations' },
      record,
    )

    expect(result.pricingLines).toEqual([
      { quantity: 2, unitPrice: 100, discountAmount: 10, taxAmount: 5, subtotal: 200, lineTotal: 195 },
      { quantity: 1, unitPrice: 50, discountAmount: 0, taxAmount: 0, subtotal: 50, lineTotal: 50 },
    ])
    expect(result).toMatchObject({ subtotal: 250, discount: 10, tax: 5, total: 245, amount: 245 })
    expect(result.route).toBe('Phnom Penh → Bavet → HCMC')
  })

  it('zeroes quotation totals when there are no pricing lines', () => {
    const result = recalculateFreightRecord(
      { kind: 'quotation', collection: 'quotations', path: '/sales/quotations' },
      { id: 'q1' } as FreightRecord,
    )
    expect(result).toMatchObject({ subtotal: 0, discount: 0, tax: 0, total: 0, amount: 0 })
  })

  it('derives quotation legacy pricing profit and margin', () => {
    const result = recalculateFreightRecord(
      { kind: 'quotation', collection: 'quotations', path: '/sales/quotations' },
      {
        id: 'q1',
        otherCharges: [{ quantity: 2, buyingRate: 10, sellingRate: 20 }],
      } as FreightRecord,
    )
    expect(result).toMatchObject({
      totalBuying: 20,
      totalSelling: 40,
      amount: 40,
      profit: 20,
      margin: 50,
    })
  })

  it('totals debit-note charge currencies and VAT', () => {
    const result = recalculateFreightRecord(
      { kind: 'debit-note', collection: 'debitNotes', path: '/finance/debit-notes' },
      {
        id: 'd1',
        vatRate: 10,
        charges: [{ cambodia: 100, vietnam: 50, cash: 25 }],
      } as FreightRecord,
    )
    expect(result).toMatchObject({
      cambodiaSubtotal: 100,
      vietnamSubtotal: 50,
      cashSubtotal: 25,
      amount: 175,
      vat: 17.5,
      total: 192.5,
    })
  })

  it('totals service charge fee lines', () => {
    const result = recalculateFreightRecord(
      { collection: 'jobCharges', path: '/service-charges' },
      { id: 'c1', feeLines: [{ quantity: 2, unitAmount: 100, discount: 10, taxAmount: 5 }] } as FreightRecord,
    )
    expect(result).toMatchObject({ subtotal: 200, discount: 10, tax: 5, total: 195, amount: 195 })
  })

  it('totals finance document lines excluding VAT from amount', () => {
    const result = recalculateFreightRecord(
      { collection: 'debitNotes', path: '/finance/documents' },
      { id: 'd1', lines: [{ quantity: 2, unitAmount: 100, discount: 10, taxAmount: 5 }] } as FreightRecord,
    )
    expect(result).toMatchObject({ amount: 190, vat: 5, total: 195 })
  })

  it('balances journal debit and credit totals', () => {
    const result = recalculateFreightRecord(
      { collection: 'journals', path: '/finance/journals' },
      {
        id: 'j1',
        lines: [{ debit_amount: 100, credit_amount: 0 }, { debit_amount: 0, credit_amount: 60 }],
      } as FreightRecord,
    )
    expect(result).toMatchObject({ debitTotal: 100, creditTotal: 60, balanceDifference: 40 })
  })

  it('derives customer payment allocation and status', () => {
    const module = { collection: 'customerPayments', path: '/finance/customer-payments' }
    expect(recalculateFreightRecord(module, {
      id: 'p1',
      received: 100,
      amountDue: 150,
      allocations: [{ amount: 40 }],
    } as FreightRecord)).toMatchObject({
      allocatedAmount: 40,
      unallocatedAmount: 60,
      outstanding: 50,
      status: 'Partial',
    })

    expect(recalculateFreightRecord(module, {
      id: 'p1',
      received: 150,
      amountDue: 150,
      allocations: [],
    } as FreightRecord)).toMatchObject({ outstanding: 0, status: 'Paid' })

    expect(recalculateFreightRecord(module, {
      id: 'p1',
      received: 0,
      amountDue: 150,
      allocations: [],
    } as FreightRecord)).toMatchObject({ status: 'Unpaid' })
  })

  it('refreshes the document sequence preview', () => {
    const result = recalculateFreightRecord(
      { collection: 'documentSequences', path: '/administration/document-sequences' },
      { id: 's1', prefix: '  INV', year: 2026, lastValue: 41, paddingLength: 6 } as FreightRecord,
    )
    expect(result.prefix).toBe('INV')
    expect(result.nextNumberPreview).toBe('INV2026-000042')
  })

  it('leaves modules without calculation rules untouched', () => {
    const record = { id: 'c1', code: 'USD' } as FreightRecord
    expect(recalculateFreightRecord(
      { collection: 'currencies', path: '/master-data/currencies' },
      record,
    )).toBe(record)
  })
})

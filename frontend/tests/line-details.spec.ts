import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import { JOB_CONTAINER_PAYMENT_TABLE } from '../app/config/job-workspace-forms'
import { serviceChargePayload, serviceChargeTable, serviceChargeTotals } from '../app/utils/freight/job-charges'
import { applyLineAdjustments, lineSubtotal } from '../app/utils/table/line-adjustments'
import { computePricingLine } from '../app/utils/table/line-table-rules'

describe('line additional details', () => {
  it('is offered on all four supported tables', () => {
    const quotation = getFreightModule('/quotations')!
    const pricing = quotation.tables!.find(table => table.key === 'pricingLines')!
    const charges = getFreightModule('/service-charges')!.tables!.find(table => table.key === 'feeLines')!
    expect(pricing.lineDetails).toBe(true)
    expect(charges.lineDetails).toBe(true)
    expect(JOB_CONTAINER_PAYMENT_TABLE.lineDetails).toBe(true)
    expect(serviceChargeTable().lineDetails).toBe(true)
  })

  it('shows the discount and tax lines in the quotation pricing summary', () => {
    const pricing = getFreightModule('/quotations')!.tables!.find(table => table.key === 'pricingLines')!
    // The generic totals block hides discount/tax when `hideDiscountTax` is set.
    expect(pricing.hideDiscountTax).toBeFalsy()
  })

  it('derives the tax amount from the line rate and the discounted base', () => {
    const row = { quantity: 2, unitPrice: 100 }
    expect(lineSubtotal(row)).toBe(200)
    const adjusted = applyLineAdjustments(row, { discount: 20, taxRate: 10 })
    expect(adjusted.discountAmount).toBe(20)
    expect(adjusted.taxRate).toBe(10)
    expect(adjusted.taxAmount).toBe(18)
    expect(computePricingLine({ row: adjusted })).toEqual({ lineTotal: 198 })
  })

  it('keeps zero adjustments at zero', () => {
    const adjusted = applyLineAdjustments({ quantity: 1, unitPrice: 50 }, { discount: 0, taxRate: 0 })
    expect(adjusted.taxAmount).toBe(0)
    expect(computePricingLine({ row: adjusted })).toEqual({ lineTotal: 50 })
  })

  it('never discounts below zero or above the line subtotal', () => {
    const adjusted = applyLineAdjustments({ quantity: 1, unitPrice: 50 }, { discount: 900, taxRate: 0 })
    expect(adjusted.discountAmount).toBe(50)
    expect(adjusted.taxAmount).toBe(0)
  })

  it('sends the line rate so the server derives the authoritative tax', () => {
    const payload = serviceChargePayload({
      description: 'Freight',
      quantity: 10,
      unitPrice: 2320,
      discount: 320,
      taxRate: 10,
      taxAmount: 2000,
    }, 'USD')
    expect(payload.lines[0]).toMatchObject({ discount: 320, taxRate: 10 })
  })

  it('sums line adjustments once and ignores the sheet rate when they exist', () => {
    const rows = [
      { quantity: 1, unitPrice: 100, discount: 10, taxRate: 10, taxAmount: 9 },
      { quantity: 1, unitPrice: 100, discount: 0, taxRate: 0, taxAmount: 0 },
    ]
    expect(serviceChargeTotals(rows, 10, 50)).toMatchObject({
      subtotal: 200,
      discount: 10,
      vat: 9,
      total: 199,
    })
  })
})

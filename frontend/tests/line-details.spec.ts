import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import { JOB_CONTAINER_PAYMENT_TABLE } from '../app/config/job-workspace-forms'
import { recalculateFreightRecord } from '../app/utils/freight/document-calculations'
import { serviceChargeFormPayload, serviceChargeModule } from '../app/utils/freight/service-charge-form'
import { applyLineAdjustments, lineSubtotal } from '../app/utils/table/line-adjustments'
import { computeFeeLine, computePricingLine } from '../app/utils/table/line-table-rules'

describe('line additional details', () => {
  it('is offered on every supported live table', () => {
    const quotation = getFreightModule('/quotations')!
    const pricing = quotation.tables!.find(table => table.key === 'pricingLines')!
    const charges = serviceChargeModule().tables!.find(table => table.key === 'feeLines')!
    expect(pricing.lineDetails).toBe(true)
    expect(charges.lineDetails).toBe(true)
    expect(JOB_CONTAINER_PAYMENT_TABLE.lineDetails).toBe(true)
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

  it('sends the fee line and its discount/tax through the shared charge payload', () => {
    const payload = serviceChargeFormPayload({
      id: '',
      status: 'Draft',
      feeLines: [{
        description: 'Freight',
        quantity: 10,
        unitAmount: 2320,
        discount: 320,
        taxRate: 10,
        taxAmount: 200,
      }],
    })
    expect(payload.feeLines[0]).toMatchObject({ discount: 320, taxRate: 10 })
    expect(payload.total).toBe(23080)
  })

  it('sums fee-line adjustments once through the shared record recalculation', () => {
    const next = recalculateFreightRecord(serviceChargeModule(), {
      id: '',
      feeLines: [
        { quantity: 1, unitAmount: 100, discount: 10, taxRate: 10, taxAmount: 9 },
        { quantity: 1, unitAmount: 100, discount: 0, taxRate: 0, taxAmount: 0 },
      ],
    } as never)
    expect(next.subtotal).toBe(200)
    expect(next.discount).toBe(10)
    expect(next.tax).toBe(9)
    expect(next.total).toBe(199)
  })

  it('keeps the fee-line row arithmetic in the shared table rules', () => {
    expect(computeFeeLine({ row: { quantity: 2, unitAmount: 100, discount: 20, taxAmount: 18 } }))
      .toEqual({ amount: 198 })
  })
})

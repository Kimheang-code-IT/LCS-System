import { describe, expect, it } from 'vitest'
import {
  containerPaymentAmounts,
  duplicateContainerNumber,
  invalidGrossWeight,
  jobActualContainers,
  jobContainerCount,
  jobContainerPaymentRows,
  jobContainerPaymentTotals,
  jobContainerRequirements,
  serviceOrderContainersFromQuotation,
  withRequirementProgress,
} from '../app/utils/freight/job-containers'

describe('service order containers', () => {
  const quotation = {
    quotationNo: 'QT-1',
    containerRequirements: [
      { id: 'qrc-1', containerType: '40HC', quantity: 2, description: 'Quoted boxes' },
    ],
    pricingLines: [
      { feeType: 'Trucking Fee', containerRequirement: '40HC', description: 'Inland trucking', quantity: 2, unit: 'Container', unitPrice: 1000, discountAmount: 0, taxPercent: 10 },
    ],
  }

  it('copies quotation container requirements onto the service order', () => {
    const rows = jobContainerRequirements({ quotationNo: 'QT-1' }, { quotation })
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      containerType: '40HC',
      quantity: 2,
      description: 'Quoted boxes',
      sourceQuotationContainerId: 'qrc-1',
    })
  })

  it('counts remaining actuals against each requirement', () => {
    const requirements = jobContainerRequirements({ quotationNo: 'QT-1' }, { quotation })
    const actuals = [
      { id: 'ac-1', containerRequirementId: requirements[0].id, containerNo: 'MSCU 1', containerType: '40HC' },
    ]
    const progress = withRequirementProgress(requirements, actuals)
    expect(progress[0]).toMatchObject({ actualQuantity: 1, remaining: 1 })
  })

  it('keeps an explicit tax amount in the grand total instead of a tax rate column', () => {
    expect(containerPaymentAmounts({
      quantity: 2,
      unitPrice: 1000,
      discountAmount: 100,
      taxRate: 10,
      taxAmount: 50,
    })).toMatchObject({
      discountAmount: 100,
      taxAmount: 50,
      lineTotal: 1950,
    })
  })

  it('links payments to actual containers and totals tax on the line', () => {
    const copied = serviceOrderContainersFromQuotation(quotation, { id: 'job-1', jobNo: 'SO-1' })
    expect(copied.requirements[0]).toMatchObject({ containerType: '40HC', quantity: 2, jobNo: 'SO-1' })
    expect(copied.payments[0]).toMatchObject({
      feeType: 'Trucking Fee',
      quantity: 2,
      unitPrice: 1000,
      taxAmount: 200,
      lineTotal: 2200,
    })
    expect(jobContainerPaymentTotals(copied.payments, 0)).toMatchObject({
      subtotal: 2000,
      vat: 200,
      total: 2200,
    })
  })

  it('counts unique actual container numbers', () => {
    const job = { containerNo: 'MSCU 1', actualContainers: [
      { containerNo: 'MSCU 1' },
      { containerNo: 'MSCU 1' },
      { containerNo: 'MSCU 2' },
    ] }
    expect(jobContainerCount(job)).toBe(2)
    expect(jobActualContainers(job)).toHaveLength(3)
  })

  it('rejects gross weight below net weight and duplicate numbers', () => {
    expect(invalidGrossWeight([{ netWeightKg: 10, grossWeightKg: 8 }])).toBeTruthy()
    expect(invalidGrossWeight([{ netWeightKg: 10, grossWeightKg: 12 }])).toBeNull()
    expect(duplicateContainerNumber([
      { containerNo: 'MSCU 1' },
      { containerNo: 'mscu 1' },
    ])).toBe('MSCU 1')
  })

  it('keeps legacy B/L + truck payment rows for totals', () => {
    const rows = jobContainerPaymentRows({
      vatRate: 10,
      containerPayments: [
        { blNo: 'BL-1', truckNo: '3C-1', quantity: 1, description: 'Trucking', amount: 100 },
        { blNo: 'BL-1', truckNo: '3C-1', quantity: 1, description: 'Clearance', amount: 20 },
      ],
    })
    expect(jobContainerCount({ containerPayments: rows }, rows)).toBe(1)
    expect(jobContainerPaymentTotals(rows, 10)).toMatchObject({ subtotal: 120, vat: 12, total: 132 })
  })
})

import { describe, expect, it } from 'vitest'
import { JOB_ACTUAL_CONTAINER_TABLE, JOB_CONTAINER_PAYMENT_TABLE } from '../app/config/job-workspace-forms'
import {
  containerPaymentAmounts,
  duplicateContainerNumber,
  invalidGrossWeight,
  jobActualContainers,
  jobContainerCount,
  jobContainerPaymentRows,
  jobContainerPaymentTotals,
  jobContainerRequirements,
  persistableActuals,
  persistablePayments,
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

  it('shows only the container, weight, note and delete columns', () => {
    expect(JOB_ACTUAL_CONTAINER_TABLE.columns.map(column => column.key)).toEqual([
      'containerNo',
      'containerType',
      'sealNo',
      'netWeightKg',
      'grossWeightKg',
      'note',
      'trust',
    ])
    expect(JOB_ACTUAL_CONTAINER_TABLE.columns.find(column => column.key === 'note')?.type).toBe('note')
    expect(JOB_ACTUAL_CONTAINER_TABLE.columns.find(column => column.key === 'trust')?.type).toBe('delete')
  })

  it('persists the row note through normalization', () => {
    const [row] = persistableActuals([{ containerNo: 'MSCU 1', note: '  Seal replaced  ' }])
    expect(row.note).toBe('Seal replaced')
  })

  it('keeps a prepared row without a container number', () => {
    const rows = persistableActuals([
      { id: '12', containerType: '40HC', containerNo: '', grossWeightKg: 20000 },
      { id: 'ac-1', containerType: '40HC', containerNo: 'MSCU1234567' },
    ])
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ id: '12', containerType: '40HC', containerNo: '' })
    expect(JOB_ACTUAL_CONTAINER_TABLE.columns.find(column => column.key === 'containerNo')?.required)
      .toBeFalsy()
  })

  it('generates one payment per actual container and one shipment charge', () => {
    const actuals = [
      { id: '11', containerType: '40HC', containerNo: '' },
      { id: '12', containerType: '40HC', containerNo: '' },
    ]
    const rows = jobContainerPaymentRows({}, {
      actuals,
      quotation: {
        pricingLines: [
          { feeType: 'Documentation Fee', containerType: '40HC', quantity: 1, unitPrice: 10 },
          { feeType: 'Customs Clearance', quantity: 1, unitPrice: 50 },
        ],
      },
    })
    const perContainer = rows.filter(row => row.feeType === 'Documentation Fee')
    expect(perContainer).toHaveLength(2)
    expect(perContainer.map(row => row.serviceOrderContainerId)).toEqual(['11', '12'])
    expect(rows.filter(row => row.feeType === 'Customs Clearance')).toHaveLength(1)
    expect(rows.find(row => row.feeType === 'Customs Clearance')?.containerNo).toBe('')
  })

  it('does not duplicate stored payments and refreshes their container reference', () => {
    const stored = [{
      id: 'cp-1',
      feeType: 'Documentation Fee',
      containerNo: '',
      serviceOrderContainerId: '11',
      quantity: 1,
      unitPrice: 10,
    }]
    const actuals = [{ id: '11', containerType: '40HC', containerNo: 'MSCU1234567' }]
    const rows = jobContainerPaymentRows({ containerPayments: stored }, {
      actuals,
      quotation: { pricingLines: [{ feeType: 'Documentation Fee', containerType: '40HC', quantity: 1, unitPrice: 10 }] },
    })
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ id: 'cp-1', containerNo: 'MSCU1234567', unitPrice: 10 })
  })

  it('reads persisted actual containers instead of a stale json copy', () => {
    const rows = jobActualContainers(
      { actualContainers: [{ id: 'stale', containerNo: 'OLD1' }] },
      { actuals: [{ id: '11', containerType: '40HC', containerNo: '' }] },
    )
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ id: '11', containerNo: '' })
  })

  it('shows container, fee, money, note and utility columns on container payments', () => {
    expect(JOB_CONTAINER_PAYMENT_TABLE.columns.map(column => column.key)).toEqual([
      'containerNo',
      'feeType',
      'quantity',
      'unitPrice',
      'lineTotal',
      'note',
      '_delete',
      '_invoice',
    ])
    const column = (key: string) => JOB_CONTAINER_PAYMENT_TABLE.columns.find(item => item.key === key)
    // A payment sheet carries one discount and tax for the whole sheet, so there
    // is no per-row discount column; the totals block owns those values instead.
    expect(column('discountAmount')).toBeUndefined()
    expect(JOB_CONTAINER_PAYMENT_TABLE.pricing).toBe(true)
    expect(column('lineTotal')).toMatchObject({ type: 'number', computed: true })
    expect(column('note')?.type).toBe('note')
    expect(column('_delete')?.type).toBe('delete')
    expect(column('_invoice')).toMatchObject({ type: 'action', action: 'invoice' })
  })

  it('keeps a container payment note and reprices the row', () => {
    const [row] = persistablePayments([{
      containerNo: 'MSCU 482190-7',
      feeType: 'Trucking Fee',
      quantity: 2,
      unitPrice: 1000,
      discountAmount: 100,
      taxRate: 10,
      note: '  Paid in cash by driver  ',
    }])
    expect(row.note).toBe('Paid in cash by driver')
    expect(row).toMatchObject({ lineSubtotal: 2000, taxAmount: 190, lineTotal: 2090 })
  })
})

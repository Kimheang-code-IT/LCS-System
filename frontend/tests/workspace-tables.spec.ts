import { describe, expect, it } from 'vitest'
import { JOB_FINANCE_LINES_TABLE } from '../app/config/job-workspace-forms'
import { serviceChargeColumns, serviceChargeTotals, serviceChargeToRow } from '../app/utils/freight/job-charges'

describe('service order workspace tables', () => {
  it('keeps the service-charge grid to the review columns and offers a detail action', () => {
    const keys = serviceChargeColumns().map(column => column.key)
    expect(keys).toEqual(['feeType', 'description', 'quantity', 'unitPrice', 'total'])
    // Hidden fields stay in the row: the detail page and payload still carry them.
    const row = serviceChargeToRow({
      id: '7',
      documentDate: '2026-10-20',
      documentType: 'SERVICE_NOTE',
      status: 'DRAFT',
      invoiceNo: 'INV-1',
      total: 110,
      feeLines: [{ description: 'Freight', quantity: 1, unitAmount: 100, taxRate: 10 }],
    })
    expect(row).toMatchObject({ documentDate: '2026-10-20', documentType: 'SERVICE_NOTE', status: 'DRAFT', invoiceNo: 'INV-1' })
  })

  it('keeps the finance grid read-only with type, date, description, party, amount and status', () => {
    expect(JOB_FINANCE_LINES_TABLE.columns.map(column => column.key)).toEqual([
      'type',
      'date',
      'description',
      'party',
      'amount',
      'status',
    ])
    expect(JOB_FINANCE_LINES_TABLE.columns.find(column => column.key === 'date')?.type).toBe('date')
    expect(JOB_FINANCE_LINES_TABLE.hideAddRow).toBe(true)
    expect(JOB_FINANCE_LINES_TABLE.columns.some(column => column.type === 'action')).toBe(false)
  })

  it('summarises a service charge sheet like the container payment block', () => {
    const rows = [
      { quantity: 2, unitPrice: 10 },
      { quantity: 1, unitPrice: 5 },
    ]
    expect(serviceChargeTotals(rows, 10, 5)).toMatchObject({
      subtotal: 25,
      discount: 5,
      vat: 2,
      total: 22,
    })
  })
})

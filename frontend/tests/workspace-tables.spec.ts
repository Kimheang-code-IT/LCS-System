import { describe, expect, it } from 'vitest'
import { JOB_FINANCE_LINES_TABLE } from '../app/config/job-workspace-forms'
import { isDeletableCharge, serviceChargeColumns, serviceChargeRowDisabled, serviceChargeToRow, serviceChargeTotals } from '../app/utils/freight/job-charges'

describe('service order workspace tables', () => {
  it('keeps the service-charge grid to the review columns and offers row actions', () => {
    const keys = serviceChargeColumns().map(column => column.key)
    // Exactly # (the renderer's own row-number column), Fee Type, Description,
    // Qty, Unit Price, Line Total — plus the row-menu Delete command. Invoice
    // No. left the grid: invoicing is the row's Print Invoice action, and the
    // row's `financialDocumentId` identifies the owning invoice.
    expect(keys).toEqual(['feeType', 'description', 'quantity', 'unitPrice', 'total', '_delete'])
    // Hidden fields stay in the row: the detail page and payload still carry them.
    const row = serviceChargeToRow({
      id: '7',
      documentDate: '2026-10-20',
      documentType: 'SERVICE_NOTE',
      status: 'DRAFT',
      financialDocumentId: 'doc-9',
      total: 110,
      feeLines: [{ description: 'Freight', quantity: 1, unitAmount: 100, taxRate: 10 }],
    })
    expect(row).toMatchObject({ documentDate: '2026-10-20', documentType: 'SERVICE_NOTE', status: 'DRAFT', financialDocumentId: 'doc-9' })
  })

  it('locks issued charges and leaves draft rows editable', () => {
    expect(serviceChargeRowDisabled({ id: '7', status: 'DRAFT' })).toBe(false)
    expect(serviceChargeRowDisabled({ id: '7', status: 'ISSUED' })).toBe(true)
    // An unsaved row is always editable, and invoicing is the invoice's state.
    expect(serviceChargeRowDisabled({ status: 'ISSUED' })).toBe(false)
    // The API spells the status "Draft"; only the domain value gates saving.
    expect(isDeletableCharge({ status: 'Draft' })).toBe(true)
    expect(isDeletableCharge({ status: 'Issued' })).toBe(false)
  })

  it('keeps the finance grid inline-editable with date, type, description, amount and currency', () => {
    // The Business Party is not a column: income entries default to the order
    // customer and payee entries are completed through Additional Details.
    expect(JOB_FINANCE_LINES_TABLE.columns.map(column => column.key)).toEqual([
      'date',
      'type',
      'description',
      'amount',
      'currency',
    ])
    expect(JOB_FINANCE_LINES_TABLE.columns.find(column => column.key === 'type')?.type).toBe('select')
    expect(JOB_FINANCE_LINES_TABLE.hideAddRow).toBe(true)
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

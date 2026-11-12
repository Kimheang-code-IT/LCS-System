import { describe, expect, it } from 'vitest'
import { JOB_FINANCE_LINES_TABLE } from '../app/config/job-workspace-forms'
import { isDeletableCharge } from '../app/utils/freight/job-charges'
import { serviceChargeFormPayload, serviceChargeModule } from '../app/utils/freight/service-charge-form'

describe('service order workspace tables', () => {
  it('uses the live Fee Lines table shared by both charge hosts', () => {
    const feeLines = serviceChargeModule().tables!.find(table => table.key === 'feeLines')!
    expect(feeLines.columns.map(column => column.key)).toEqual([
      'feeType',
      'description',
      'quantity',
      'unitAmount',
      'amount',
      '_delete',
    ])
    expect(feeLines.lineDetails).toBe(true)
    // Every new row gets a stable marker before it reaches the charge API.
    const defaults = feeLines.rowDefaults?.({ rows: [], blank: {} })
    expect(String(defaults?.clientRowId)).toMatch(/^feeLine_/)
  })

  it('locks issued charges and leaves draft rows editable', () => {
    // The API spells the status "Draft"; only the domain value gates saving.
    expect(isDeletableCharge({ status: 'Draft' })).toBe(true)
    expect(isDeletableCharge({ status: 'ISSUED' })).toBe(false)
    expect(isDeletableCharge({})).toBe(false)
  })

  it('drops the auto-started empty fee line and recalculates the saved totals', () => {
    const payload = serviceChargeFormPayload({
      id: '',
      status: 'Draft',
      feeLines: [
        { feeType: '', description: '', quantity: 1, unitAmount: 0 },
        { feeType: 'Freight', description: 'Ocean freight', quantity: 2, unitAmount: 100, discount: 20, taxAmount: 18 },
      ],
    })
    expect(payload.feeLines).toHaveLength(1)
    expect(payload.subtotal).toBe(200)
    expect(payload.discount).toBe(20)
    expect(payload.tax).toBe(18)
    expect(payload.total).toBe(198)
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
})

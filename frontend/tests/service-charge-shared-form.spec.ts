import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import {
  emptyLinkedServiceCharge,
  internalFeeLinesTable,
  serviceChargeDraftRecordId,
  serviceChargeFormPayload,
  serviceChargeFormTabs,
  serviceChargeModule,
} from '../app/utils/freight/service-charge-form'

const job = {
  id: '7',
  jobNo: 'SO2026-000007',
  customer: 'ACME',
  customerPartyId: '3',
  currency: 'USD',
}

describe('shared service charge form model', () => {
  it('uses the same module the standalone page uses', () => {
    expect(serviceChargeModule().collection).toBe('jobCharges')
    expect(getFreightModule('/service-charges')!.tables?.map(table => table.key))
      .toContain('feeLines')
  })

  it('builds the same tabs for standalone and embedded forms', () => {
    const module = serviceChargeModule()
    const standalone = serviceChargeFormTabs(module, { id: '1', feeLines: [] })
    const linked = serviceChargeFormTabs(module, { id: '1', feeLines: [] }, { linkedToOrder: true })
    expect(linked.map(tab => tab.id)).toEqual(standalone.map(tab => tab.id))
    expect(linked.map(tab => tab.id)).toContain('general')
    expect(linked.map(tab => tab.id)).toContain('fee-lines')
  })

  it('shows only Fee Lines when embedded in a Service Order', () => {
    const module = serviceChargeModule()
    const tabs = serviceChargeFormTabs(module, { id: '1', feeLines: [] }, { linkedToOrder: true, feeLinesOnly: true })
    expect(tabs.map(tab => tab.id)).toEqual(['fee-lines'])
    // The standalone form still carries its header fields.
    expect(serviceChargeFormTabs(module, { id: '1', feeLines: [] }).map(tab => tab.id))
      .toContain('general')
  })

  it('adds cost and margin only to the internal fee-line table', () => {
    const internal = internalFeeLinesTable(serviceChargeModule())
    const keys = internal.columns.map(column => column.key)
    expect(keys).toContain('costUnitPrice')
    expect(keys).toContain('costAmount')
    expect(keys).toContain('margin')
    const row = {
      quantity: 2,
      unitAmount: 50,
      costUnitPrice: 30,
      discount: 0,
      taxAmount: 0,
    }
    const computed = internal.computeRow?.({ row, rows: [row], index: 0 })
    expect(computed).toMatchObject({ amount: 100, costAmount: 60, margin: 40 })
  })

  it('shows Supplier and cost fields in the embedded internal tabs', () => {
    const tabs = serviceChargeFormTabs(
      serviceChargeModule(),
      { id: '', feeLines: [], chargeSide: 'INTERNAL' },
      { linkedToOrder: true, feeLinesOnly: true },
    )
    const fields = tabs[0]!.sections.flatMap(section => section.fields)
    expect(fields.some(field => field.key === 'supplierPartyId')).toBe(true)
    const table = fields.find(field => field.key === 'feeLines')
    const columns = (table?.meta?.table as { columns: Array<{ key: string }> }).columns
    expect(columns.map(column => column.key)).toContain('costUnitPrice')
  })

  it('hides traceability until the charge exists', () => {
    const module = serviceChargeModule()
    expect(serviceChargeFormTabs(module, { id: '', feeLines: [] }).map(tab => tab.id))
      .not.toContain('traceability')
    expect(serviceChargeFormTabs(module, { id: '9', feeLines: [] }).map(tab => tab.id))
      .toContain('traceability')
  })

  it('starts a linked charge in the correct Service Order context', () => {
    const charge = emptyLinkedServiceCharge(job)
    expect(charge.serviceOrderId).toBe('7')
    expect(charge.jobNo).toBe('SO2026-000007')
    expect(charge.customerPartyId).toBe('3')
    expect(charge.currency).toBe('USD')
    expect(charge.status).toBe('Draft')
    expect(charge.feeLines).toHaveLength(1)
    expect(String(charge.clientRowId)).toMatch(/^charge[-_]/)
  })

  it('computes the grand total from fee lines and drops only empty auto lines', () => {
    const charge = emptyLinkedServiceCharge(job)
    const payload = serviceChargeFormPayload({
      ...charge,
      feeLines: [
        { feeType: 'Freight', description: 'Ocean freight', quantity: 2, unitAmount: 100, discount: 20, taxAmount: 18 },
        { feeType: 'Handling', description: 'Handling', quantity: 1, unitAmount: 50 },
        { feeType: '', description: '', quantity: 1, unitAmount: 0 },
      ],
    })
    expect(payload.feeLines).toHaveLength(2)
    expect(payload.subtotal).toBe(250)
    expect(payload.discount).toBe(20)
    expect(payload.tax).toBe(18)
    expect(payload.total).toBe(248)
  })

  it('keys a saved draft by order and charge while isolating the new slot', () => {
    const charge = emptyLinkedServiceCharge(job)
    expect(serviceChargeDraftRecordId('7', { ...charge, id: '55' })).toBe('7:55')
    expect(serviceChargeDraftRecordId('7', charge)).toContain('7:new:')
  })
})

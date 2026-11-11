import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'

const charges = getFreightModule('/service-charges')!

describe('service charge list', () => {
  it('shows exactly the six business columns in order', () => {
    // Checkbox and row actions are the shared list table's own columns; the
    // description summarises each charge's fee lines, so every charge appears
    // once and SO No. / Invoice No. / Status stay off the page.
    expect(charges.columns.map(column => column.key)).toEqual([
      'chargeNo',
      'customer',
      'description',
      'total',
      'createdBy',
      'createdAt',
    ])
  })

  it('labels the charge, party and total columns and drops currency and adjustments', () => {
    expect(charges.columns[0]?.label).toBe('SC No.')
    expect(charges.columns.find(column => column.key === 'customer')?.labelKey)
      .toBe('freight.fields.customerPartyId')
    expect(charges.columns.find(column => column.key === 'description')?.labelKey)
      .toBe('freight.ui.cols.description')
    expect(charges.columns.find(column => column.key === 'total')?.labelKey)
      .toBe('freight.fields.total')
    expect(charges.columns.find(column => column.key === 'createdAt')?.type).toBe('datetime')
    for (const hidden of ['currency', 'subtotal', 'discount', 'tax', 'jobNo', 'invoiceNo', 'status']) {
      expect(charges.columns.some(column => column.key === hidden)).toBe(false)
    }
  })

  it('keeps the party and document-type filters; the list itself is standalone-only', () => {
    const filters = charges.filters || []
    expect(filters.find(filter => filter.key === 'customer')?.labelKey).toBe('freight.fields.customerPartyId')
    expect(filters.find(filter => filter.key === 'documentType')).toBeTruthy()
    expect(filters.some(filter => filter.key === 'jobNo' || filter.key === 'status')).toBe(false)
  })
})

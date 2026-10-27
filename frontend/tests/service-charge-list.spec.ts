import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import { getFreightModule } from '../app/config/freight-modules'

const charges = getFreightModule('/service-charges')!

describe('service charge list', () => {
  it('shows exactly the seven business columns in order', () => {
    expect(charges.columns.map(column => column.key)).toEqual([
      'chargeNo',
      'jobNo',
      'customer',
      'total',
      'invoiceNo',
      'status',
      'createdBy',
      'createdAt',
    ])
  })

  it('labels SC / SO / invoice columns and drops currency, discount and creator', () => {
    expect(charges.columns[0]?.label).toBe('SC No.')
    expect(charges.columns[1]?.labelKey).toBe('freight.ui.cols.jobNo')
    expect(en.freight.ui.cols.jobNo).toBe('SO No.')
    expect(charges.columns[4]?.labelKey).toBe('freight.ui.cols.invoiceNoCol')
    expect(en.freight.ui.cols.invoiceNoCol).toBe('Invoice No.')
    expect(charges.columns.find(column => column.key === 'createdAt')?.type).toBe('datetime')
    for (const hidden of ['currency', 'subtotal', 'discount', 'tax']) {
      expect(charges.columns.some(column => column.key === hidden)).toBe(false)
    }
  })

  it('renames the filters without changing their parameters', () => {
    const filters = charges.filters || []
    expect(filters.find(filter => filter.key === 'jobNo')?.labelKey).toBe('freight.ui.cols.jobNo')
    expect(filters.find(filter => filter.key === 'customer')?.labelKey).toBe('freight.fields.customerPartyId')
    expect(filters.find(filter => filter.key === 'status')).toBeTruthy()
  })
})

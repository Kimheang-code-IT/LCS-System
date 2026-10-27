import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import km from '../i18n/locales/km.json'
import zh from '../i18n/locales/zh.json'
import { getFreightModule } from '../app/config/freight-modules'

const serviceOrders = getFreightModule('/service-orders')!

describe('service order list', () => {
  it('keeps the eight business columns in order', () => {
    expect(serviceOrders.columns.map(column => column.key)).toEqual([
      'jobNo',
      'quotationNo',
      'customer',
      'direction',
      'containersCount',
      'chargesTotal',
      'status',
      'createdBy',
      'createdAt',
    ])
  })

  it('labels the number column SO No. while keeping the jobNo data key', () => {
    const column = serviceOrders.columns.find(item => item.key === 'jobNo')!
    expect(column.labelKey).toBe('freight.ui.cols.jobNo')
    expect(en.freight.ui.cols.jobNo).toBe('SO No.')
    expect(km.freight.ui.cols.jobNo).toBeTruthy()
    expect(zh.freight.ui.cols.jobNo).toBeTruthy()
    expect(en.freight.ui.cols.quotation).toBe('Quotation')
  })

  it('ends the finance document list with Created By then Created At', () => {
    const keys = getFreightModule('/finance/documents')!.columns.map(column => column.key)
    expect(keys.slice(-2)).toEqual(['createdBy', 'createdAt'])
  })
})

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { FREIGHT_REPORTS } from '../app/config/freight-reports'

const bySlug = (slug: string) => FREIGHT_REPORTS.find(item => item.slug === slug)!
const keys = (slug: string) => bySlug(slug).columns.map(column => column.key)

describe('operations reports', () => {
  it('service order register ends with creator and creation time', () => {
    expect(keys('service-orders')).toEqual([
      'jobNo',
      'quotationNo',
      'customer',
      'direction',
      'containers',
      'chargeTotal',
      'status',
      'createdBy',
      'createdAt',
    ])
    expect(bySlug('service-orders').columns.find(column => column.key === 'containers')?.integer).toBe(true)
  })

  it('service order status shows aging, pending work and creator', () => {
    expect(keys('service-order-status')).toEqual([
      'jobNo',
      'customer',
      'direction',
      'status',
      'daysOpen',
      'pendingComponents',
      'lastActivity',
      'createdBy',
    ])
    expect(bySlug('service-order-status').columns.find(column => column.key === 'pendingComponents')?.integer).toBe(true)
  })

  it('containers report uses actual container columns only', () => {
    expect(keys('containers')).toEqual([
      'containerNo',
      'containerType',
      'jobNo',
      'customer',
      'sealNo',
      'status',
      'netWeightKg',
      'grossWeightKg',
    ])
  })

  it('profitability keeps the posted financial keys', () => {
    expect(keys('profitability')).toEqual([
      'jobNo',
      'customer',
      'quoted',
      'serviceCharges',
      'postedRevenue',
      'postedCost',
      'grossProfit',
      'margin',
    ])
  })

  it('links document numbers by API id, not by formatted number', () => {
    const source = readFileSync(fileURLToPath(new URL('../app/components/freight/ReportsView.vue', import.meta.url)), 'utf8')
    expect(source).toContain('/service-orders/${job.id}')
    expect(source).toContain('/quotations/${quotationId}')
  })
})

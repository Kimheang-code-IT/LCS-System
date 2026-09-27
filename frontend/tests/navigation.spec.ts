import { describe, expect, it } from 'vitest'

describe('navigation workspace modules', () => {
  it('resolves every sidebar page path to a freight module', async () => {
    const { getFreightModule } = await import('../app/config/freight-modules')
    const paths = [
      '/quotations',
      '/service-orders',
      '/service-charges',
      '/finance/documents',
      '/finance/chart-of-accounts',
      '/finance/financial-accounts',
      '/finance/journals',
      '/finance/accounting-periods',
      '/reports',
      '/master-data/business-parties',
      '/master-data/places',
      '/master-data/trade-directions',
      '/master-data/container-types',
      '/master-data/transport-types',
      '/master-data/transport-assets',
      '/master-data/fee-types',
      '/configuration/component-templates',
      '/administration/users',
      '/administration/roles',
      '/administration/audit-logs',
    ]
    for (const path of paths) {
      expect(getFreightModule(path)?.path, path).toBe(path)
      expect(getFreightModule(`${path}/sample-id`)?.path, `${path}/id`).toBe(path)
    }
  })
})

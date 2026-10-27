import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'

const keys = (path: string) => getFreightModule(path)!.columns.map(column => column.key)

describe('master data list columns', () => {
  it('matches the required columns and ends with the audit pair', () => {
    const expected: Record<string, string[]> = {
      '/master-data/business-parties': ['partyCode', 'displayName', 'roles', 'contactPerson', 'phone', 'status', 'createdBy', 'createdAt'],
      '/master-data/party-roles': ['code', 'name', 'description', 'status', 'createdBy', 'createdAt'],
      '/master-data/place-roles': ['code', 'name', 'sortOrder', 'description', 'status', 'createdBy', 'createdAt'],
      '/master-data/trade-directions': ['code', 'name', 'description', 'status', 'createdBy', 'createdAt'],
      '/master-data/container-types': ['code', 'name', 'size', 'isoCode', 'maxGrossWeightKg', 'status', 'createdBy', 'createdAt'],
      '/master-data/transport-types': ['code', 'name', 'description', 'status', 'createdBy', 'createdAt'],
      '/master-data/transport-assets': ['assetCode', 'assetName', 'transportType', 'identity', 'capacity', 'ownerParty', 'status', 'createdBy', 'createdAt'],
      '/master-data/asset-identity-types': ['name', 'transportType', 'identityLabel', 'validationPattern', 'status', 'createdBy', 'createdAt'],
      '/master-data/capacity-units': ['code', 'name', 'status', 'createdBy', 'createdAt'],
      '/master-data/fee-types': ['code', 'name', 'description', 'status', 'createdBy', 'createdAt'],
      '/master-data/currencies': ['code', 'name', 'symbol', 'decimalPlaces', 'status', 'createdBy', 'createdAt'],
    }
    for (const [path, columns] of Object.entries(expected)) {
      expect(keys(path), path).toEqual(columns)
    }
  })

  it('marks both audit columns as read-only display columns', () => {
    for (const path of ['/master-data/fee-types', '/master-data/currencies', '/master-data/party-roles']) {
      const columns = getFreightModule(path)!.columns
      expect(columns.find(column => column.key === 'createdBy')?.labelKey).toBe('freight.fields.createdBy')
      expect(columns.find(column => column.key === 'createdAt')?.type).toBe('datetime')
    }
  })
})

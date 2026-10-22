import { describe, expect, it } from 'vitest'
import { QUOTATION_ROUTE_TABLE } from '../app/config/route-stop-table'
import { JOB_ROUTE_TABLE } from '../app/config/job-workspace-forms'
import { jobFieldsFromPlaces, jobRoutePlaces } from '../app/utils/freight/job-workspace'
import { referenceOptionSource } from '../app/utils/freight/reference-options'

describe('job route places', () => {
  it('does not invent stops when the order has no saved route', () => {
    // Route stops are now rows (service_order_places), not four hardcoded header
    // keys. An order without rows must show an empty table.
    expect(jobRoutePlaces({ id: '', shipmentDate: '2026-10-01', etaPort: '2026-10-01' })).toEqual([])
    expect(jobRoutePlaces({ id: 'job-001', pickup: 'Cat Lai' })).toEqual([])
  })

  it('normalises stored rows, keeping the role id and free-text location', () => {
    expect(jobRoutePlaces({
      id: 'job-001',
      places: [{
        id: '17',
        sequence: 2,
        placeRoleId: '4',
        placeRole: 'Pickup',
        place: 'Cai Mep',
        planned: '2026-08-16T08:30',
        actual: '2026-08-16T09:10',
        notes: 'Gate 2',
      }],
    })).toEqual([
      {
        id: '17',
        sequence: 2,
        placeRoleId: '4',
        placeRole: 'Pickup',
        place: 'Cai Mep',
        planned: '2026-08-16T08:30',
        actual: '2026-08-16T09:10',
        notes: 'Gate 2',
      },
    ])
  })

  it('keeps the legacy single planned column readable', () => {
    expect(jobRoutePlaces({
      id: 'job-001',
      places: [{ placeRole: 'Pickup', place: 'Cai Mep', plannedActual: '2026-08-16', notes: 'Gate 2' }],
    })).toEqual([
      {
        id: '',
        sequence: 1,
        placeRoleId: '',
        placeRole: 'Pickup',
        place: 'Cai Mep',
        planned: '2026-08-16',
        actual: '',
        notes: 'Gate 2',
      },
    ])
  })

  it('writes only the route collection back, without hardcoded header mirrors', () => {
    const patch = jobFieldsFromPlaces([
      { placeRoleId: '4', place: 'Cai Mep', planned: '2026-08-16', actual: '2026-08-17', notes: 'Gate 2' },
    ])
    expect(Object.keys(patch)).toEqual(['places'])
    const rows = patch.places as Array<Record<string, unknown>>
    expect(rows[0]).toMatchObject({ placeRoleId: '4', place: 'Cai Mep', notes: 'Gate 2', actual: '2026-08-17' })
  })

  it('uses the shared table definition with role, location, actual time, notes, reorder and delete', () => {
    expect(JOB_ROUTE_TABLE.columns.map(column => ({ key: column.key, type: column.type }))).toEqual([
      { key: 'placeRoleId', type: 'select' },
      { key: 'place', type: 'text' },
      { key: 'planned', type: 'datetime' },
      { key: 'actual', type: 'datetime' },
      { key: 'notes', type: 'note' },
      { key: '_order', type: 'reorder' },
      { key: 'trust', type: 'delete' },
    ])
    // The quotation and the service order share exactly these selection rules;
    // only the actual-time column differs.
    expect(QUOTATION_ROUTE_TABLE.columns.map(column => column.key)).toEqual([
      'placeRoleId',
      'place',
      'planned',
      'notes',
      '_order',
      'trust',
    ])
  })

  it('populates the role cell from the live master', () => {
    expect(referenceOptionSource('placeRoleId')).toMatchObject({
      collection: 'placeRoles',
      valueField: 'id',
      labelField: 'name',
      statuses: ['ACTIVE'],
    })
    expect(referenceOptionSource('placeId')).toBeUndefined()
    expect(referenceOptionSource('placeRole')).toBeUndefined()
  })
})

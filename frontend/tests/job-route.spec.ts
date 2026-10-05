import { describe, expect, it } from 'vitest'
import { PLACE_ROLES } from '../app/config/freight-options'
import { JOB_ROUTE_TABLE } from '../app/config/job-workspace-forms'
import { jobFieldsFromPlaces, jobRoutePlaces } from '../app/utils/freight/job-workspace'
import { referenceOptionSource } from '../app/utils/freight/reference-options'

describe('job route places', () => {
  it('starts a new order with no rows so the Route table is not pre-filled with blank stops', () => {
    // `emptyFreightRecord` pre-fills every date field with today, so an
    // unsaved order must not derive stops from them.
    expect(jobRoutePlaces({ id: '', shipmentDate: '2026-10-01', etaPort: '2026-10-01' })).toEqual([])
  })

  it('fills place and date from header fields when places are not stored', () => {
    const rows = jobRoutePlaces({
      id: 'job-001',
      pickup: 'Cat Lai',
      port: 'Cat Lai',
      border: 'Moc Bai / Bavet',
      destination: 'Manhattan SEZ',
      shipmentDate: '2026-08-19',
      etaPort: '2026-08-20',
      etaBorder: '2026-08-20',
      deliveryDate: '2026-08-21',
    })
    expect(rows).toEqual([
      { sequence: 1, placeRole: 'Pickup', place: 'Cat Lai', planned: '2026-08-19', actual: '', notes: '' },
      { sequence: 2, placeRole: 'Port of Loading', place: 'Cat Lai', planned: '2026-08-20', actual: '', notes: '' },
      { sequence: 3, placeRole: 'Transit / Border', place: 'Moc Bai / Bavet', planned: '2026-08-20', actual: '', notes: '' },
      { sequence: 4, placeRole: 'Destination', place: 'Manhattan SEZ', planned: '2026-08-21', actual: '', notes: '' },
    ])
  })

  it('keeps planned dates on orders saved before Planned and Actual were split', () => {
    expect(jobRoutePlaces({
      id: 'job-001',
      places: [{ placeRole: 'Pickup', place: 'Cai Mep', plannedActual: '2026-08-16', notes: 'Gate 2' }],
    })).toEqual([
      { sequence: 1, placeRole: 'Pickup', place: 'Cai Mep', planned: '2026-08-16', actual: '', notes: 'Gate 2' },
    ])
  })

  it('writes header pickup and dates back from the table', () => {
    const patch = jobFieldsFromPlaces([
      { placeRole: 'Pickup', place: 'Cai Mep', planned: '2026-08-16', actual: '2026-08-17', notes: 'Gate 2' },
      { placeRole: 'Destination', place: 'PPSEZ', planned: '2026-08-18', actual: '', notes: '' },
    ])
    expect(patch.pickup).toBe('Cai Mep')
    expect(patch.shipmentDate).toBe('2026-08-16')
    expect(patch.destination).toBe('PPSEZ')
    expect(patch.deliveryDate).toBe('2026-08-18')
    expect((patch.places as Array<Record<string, unknown>>)[0].notes).toBe('Gate 2')
    expect((patch.places as Array<Record<string, unknown>>)[0].actual).toBe('2026-08-17')
  })

  it('splits the stop into Role / Place / Planned / Actual / Note plus a delete icon', () => {
    expect(JOB_ROUTE_TABLE.columns.map(column => ({ key: column.key, type: column.type }))).toEqual([
      { key: 'placeRole', type: 'select' },
      { key: 'place', type: 'text' },
      { key: 'planned', type: 'date' },
      { key: 'actual', type: 'date' },
      // Icon-only cell: opens the shared row-note dialog with a textarea.
      { key: 'notes', type: 'note' },
      { key: '_delete', type: 'delete' },
    ])
  })

  it('offers every stop role as a select option so the Role cell is never blank', () => {
    const roleColumn = JOB_ROUTE_TABLE.columns.find(column => column.key === 'placeRole')
    expect(roleColumn?.type).toBe('select')
    expect([...(roleColumn?.options || [])]).toEqual([...PLACE_ROLES])

    // A master-data source would override `options` and render place names (or
    // nothing when Places is empty) instead of route roles.
    expect(referenceOptionSource('placeRole')).toBeUndefined()
  })

  it('keeps the role options aligned with the stops written back to the header', () => {
    for (const role of PLACE_ROLES) {
      expect(jobRoutePlaces({ id: 'job-001' })).toContainEqual(expect.objectContaining({ placeRole: role }))
    }
  })
})

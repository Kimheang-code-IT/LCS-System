import { describe, expect, it } from 'vitest'
import { jobFieldsFromPlaces, jobRoutePlaces } from '../app/utils/freight/job-workspace'

describe('job route places', () => {
  it('fills place and date from header fields when places are not stored', () => {
    const rows = jobRoutePlaces({
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
      { sequence: 1, placeRole: 'Pickup', place: 'Cat Lai', plannedActual: '2026-08-19', notes: '' },
      { sequence: 2, placeRole: 'Port of Loading', place: 'Cat Lai', plannedActual: '2026-08-20', notes: '' },
      { sequence: 3, placeRole: 'Transit / Border', place: 'Moc Bai / Bavet', plannedActual: '2026-08-20', notes: '' },
      { sequence: 4, placeRole: 'Destination', place: 'Manhattan SEZ', plannedActual: '2026-08-21', notes: '' },
    ])
  })

  it('writes header pickup and dates back from the table', () => {
    const patch = jobFieldsFromPlaces([
      { placeRole: 'Pickup', place: 'Cai Mep', plannedActual: '2026-08-16', notes: 'Gate 2' },
      { placeRole: 'Destination', place: 'PPSEZ', plannedActual: '2026-08-18', notes: '' },
    ])
    expect(patch.pickup).toBe('Cai Mep')
    expect(patch.shipmentDate).toBe('2026-08-16')
    expect(patch.destination).toBe('PPSEZ')
    expect(patch.deliveryDate).toBe('2026-08-18')
    expect((patch.places as Array<Record<string, unknown>>)[0].notes).toBe('Gate 2')
  })
})

import { describe, expect, it } from 'vitest'
import {
  backfillConvertedJobOperationalFields,
  quotationOperationalFields,
} from '../app/utils/freight/quotation-conversion'

describe('quotation operational conversion', () => {
  const quotation = {
    places: [
      { placeRole: 'Pickup', place: 'Cat Lai', plannedActual: '2026-08-30' },
      { placeRole: 'Transit / Border', place: 'Moc Bai', plannedActual: '2026-08-31' },
      { placeRole: 'Delivery', place: 'Bavet SEZ', plannedActual: '2026-09-01' },
    ],
    attachments: [{ fileName: 'route-plan.pdf' }],
  }

  it('maps route rows, header aliases, dates, and files', () => {
    expect(quotationOperationalFields(quotation)).toMatchObject({
      pickup: 'Cat Lai',
      border: 'Moc Bai',
      destination: 'Bavet SEZ',
      shipmentDate: '2026-08-30',
      etaBorder: '2026-08-31',
      deliveryDate: '2026-09-01',
      attachments: [{ fileName: 'route-plan.pdf' }],
    })
  })

  it('backfills old conversions without overwriting job edits', () => {
    const result = backfillConvertedJobOperationalFields({
      destination: 'Edited destination',
      places: [],
      attachments: [],
    }, quotation)
    expect(result.destination).toBe('Edited destination')
    expect(result.places).toHaveLength(3)
    expect(result.attachments).toEqual([{ fileName: 'route-plan.pdf' }])
  })
})

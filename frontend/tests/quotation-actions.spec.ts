import { describe, expect, it } from 'vitest'
import { quotationActionAvailability, serviceOrderRequotationAvailability } from '../app/utils/freight/quotation-actions'

const allAllowed = { updateDraft: true, submit: true, convert: true }
const readOnly = { updateDraft: false, submit: false, convert: false }

describe('quotationActionAvailability', () => {
  it('treats every quotation as editable: CRUD only, no submit', () => {
    for (const status of ['Draft', 'Submitted', 'Sent', 'Accepted', 'Converted']) {
      const availability = quotationActionAvailability(status, allAllowed)
      expect(availability).toMatchObject({
        edit: true,
        submit: false,
        revise: false,
      })
    }
  })

  it('offers Convert to Service Order for every convertible quotation', () => {
    // A quotation is a reusable reference: one quotation may produce many
    // service orders, so convert never gates on status or prior conversions.
    for (const status of ['Draft', 'Submitted', 'Sent', 'Accepted', 'Converted']) {
      expect(quotationActionAvailability(status, allAllowed).convert).toBe(true)
    }
    expect(quotationActionAvailability('Accepted', readOnly).convert).toBe(false)
  })

  it('offers delete only while no service order depends on the quotation', () => {
    const free = quotationActionAvailability('Draft', allAllowed)
    expect(free.delete).toBe(true)
    const linked = quotationActionAvailability('Converted', allAllowed, { hasServiceOrder: true })
    expect(linked.delete).toBe(false)
    expect(linked.openServiceOrder).toBe(true)
  })

  it('withholds every action without the source permissions', () => {
    const availability = quotationActionAvailability('Draft', readOnly)
    expect(availability).toMatchObject({
      edit: false,
      submit: false,
      convert: false,
      revise: false,
      delete: false,
    })
  })
})

describe('serviceOrderRequotationAvailability', () => {
  it('is retired: re-quotation is never offered', () => {
    expect(serviceOrderRequotationAvailability({ isCreate: false, hasRecord: true, canRevise: true })).toBe(false)
  })
})
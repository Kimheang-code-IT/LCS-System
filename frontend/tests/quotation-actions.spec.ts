import { describe, expect, it } from 'vitest'
import { quotationActionAvailability, serviceOrderRequotationAvailability } from '../app/utils/freight/quotation-actions'

const allAllowed = { updateDraft: true, submit: true, convert: true }
const readOnly = { updateDraft: false, submit: false, convert: false }

describe('quotationActionAvailability', () => {
  it('treats every quotation as editable: CRUD only, no submit or convert', () => {
    for (const status of ['Draft', 'Submitted', 'Sent', 'Accepted', 'Converted']) {
      const availability = quotationActionAvailability(status, allAllowed)
      expect(availability).toMatchObject({
        edit: true,
        submit: false,
        convert: false,
        revise: false,
      })
    }
  })

  it('keeps legacy statuses convertible-free: they were sent or accepted before', () => {
    // Legacy rows keep their status readable; the workflow vocabulary is
    // retired, so no submit/convert action is offered from any status.
    expect(quotationActionAvailability('Sent', allAllowed).submit).toBe(false)
    expect(quotationActionAvailability('Accepted', allAllowed).convert).toBe(false)
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
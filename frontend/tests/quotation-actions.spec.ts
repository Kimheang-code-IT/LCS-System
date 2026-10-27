import { describe, expect, it } from 'vitest'
import { quotationActionAvailability, serviceOrderRequotationAvailability } from '../app/utils/freight/quotation-actions'

const allAllowed = { updateDraft: true, send: true, accept: true, convert: true }
const readOnly = { updateDraft: false, send: false, accept: false, convert: false }

describe('quotationActionAvailability', () => {
  it('offers save/send/delete/requote on a draft and nothing else', () => {
    const availability = quotationActionAvailability('Draft', allAllowed)
    expect(availability.status).toBe('DRAFT')
    expect(availability).toMatchObject({
      edit: true,
      send: true,
      accept: false,
      convert: false,
      revise: true,
      delete: true,
      openServiceOrder: false,
    })
  })

  it('accepts a sent quotation; deletion stays restricted to draft/sent', () => {
    const availability = quotationActionAvailability('Sent', allAllowed)
    expect(availability).toMatchObject({
      edit: false,
      send: false,
      accept: true,
      convert: false,
      revise: true,
      delete: true,
    })
  })

  it('converts an accepted quotation and keeps re-quotation available', () => {
    const availability = quotationActionAvailability('Accepted', allAllowed)
    expect(availability).toMatchObject({
      edit: false,
      send: false,
      accept: false,
      convert: true,
      revise: true,
      delete: false,
    })
  })

  it('treats a converted quotation as linked to a service order', () => {
    const availability = quotationActionAvailability('Converted', allAllowed)
    expect(availability).toMatchObject({
      convert: false,
      revise: true,
      delete: false,
      openServiceOrder: true,
    })
  })

  it('hides delete once a service order exists even while the quotation is draft again', () => {
    const availability = quotationActionAvailability('Draft', allAllowed, { hasServiceOrder: true })
    expect(availability.openServiceOrder).toBe(true)
    expect(availability.delete).toBe(false)
    expect(availability.send).toBe(true)
  })

  it('withholds every transition without the source permission', () => {
    const availability = quotationActionAvailability('Draft', readOnly)
    expect(availability).toMatchObject({
      edit: false,
      send: false,
      accept: false,
      convert: false,
      revise: false,
      delete: false,
    })
  })
})

describe('serviceOrderRequotationAvailability', () => {
  it('offers re-quotation on a saved service order to a user who may revise', () => {
    expect(serviceOrderRequotationAvailability({ isCreate: false, hasRecord: true, canRevise: true })).toBe(true)
  })

  it('hides it without quotation.revise — the backend refuses the call anyway', () => {
    expect(serviceOrderRequotationAvailability({ isCreate: false, hasRecord: true, canRevise: false })).toBe(false)
  })

  it('hides it on an unsaved order', () => {
    expect(serviceOrderRequotationAvailability({ isCreate: true, hasRecord: false, canRevise: true })).toBe(false)
  })
})

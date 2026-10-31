import { describe, expect, it } from 'vitest'
import { quotationActionAvailability, serviceOrderRequotationAvailability } from '../app/utils/freight/quotation-actions'

const allAllowed = { updateDraft: true, submit: true, convert: true }
const readOnly = { updateDraft: false, submit: false, convert: false }

describe('quotationActionAvailability', () => {
  it('offers save/submit/delete on a draft and nothing else', () => {
    const availability = quotationActionAvailability('Draft', allAllowed)
    expect(availability.status).toBe('DRAFT')
    expect(availability).toMatchObject({
      edit: true,
      submit: true,
      convert: false,
      delete: true,
      openServiceOrder: false,
    })
  })

  it('converts a submitted quotation directly; no Sent or Accepted step', () => {
    const availability = quotationActionAvailability('Submitted', allAllowed)
    expect(availability).toMatchObject({
      edit: false,
      submit: false,
      convert: true,
      delete: false,
      revise: true,
      openServiceOrder: false,
    })
  })

  it('keeps legacy sent and accepted quotations convertible without actions of their own', () => {
    for (const legacy of ['Sent', 'Accepted']) {
      const availability = quotationActionAvailability(legacy, allAllowed)
      expect(availability).toMatchObject({
        edit: false,
        submit: false,
        convert: true,
        revise: true,
        openServiceOrder: false,
      })
    }
    // A legacy sent offer was deletable before the simplification; a submitted
    // one is not — submission is a commitment, its withdrawal is a cancel.
    expect(quotationActionAvailability('Sent', allAllowed).delete).toBe(true)
    expect(quotationActionAvailability('Accepted', allAllowed).delete).toBe(false)
  })

  it('treats a converted quotation as linked to a service order and offers re-quotation only', () => {
    const availability = quotationActionAvailability('Converted', allAllowed)
    expect(availability).toMatchObject({
      edit: false,
      submit: false,
      convert: false,
      revise: true,
      delete: false,
      openServiceOrder: true,
    })
  })

  it('hides delete once a service order exists', () => {
    const availability = quotationActionAvailability('Submitted', allAllowed, { hasServiceOrder: true })
    expect(availability.openServiceOrder).toBe(true)
    expect(availability.delete).toBe(false)
    expect(availability.convert).toBe(false)
  })

  it('withholds every action without the source permissions', () => {
    const availability = quotationActionAvailability('Submitted', readOnly)
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
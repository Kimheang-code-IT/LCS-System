/**
 * The quotation header has two distinct party fields, and they must not be
 * conflated:
 *
 * 1. `customerPartyId` — a required select that links the Business Party record.
 *    It is labelled "Business Party" (not "Company").
 * 2. `customer` — the company name that is printed. It is editable text:
 *    picking a party fills it from the party's legal name, and the operator may
 *    override it. It must therefore NOT be a computed (read-only) field.
 *
 * The backend counterpart (`save_quotation`) preserves a typed name instead of
 * overwriting it with the party's legal name; see
 * `test_quotation_keeps_a_typed_company_name` in `backend/tests/test_quotations.py`.
 */
import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import km from '../i18n/locales/km.json'
import zh from '../i18n/locales/zh.json'
import { getFreightModule } from '../app/config/freight-modules'

const quotation = getFreightModule('/quotations')!
const field = (key: string) => quotation.fields.find(item => item.key === key)!

describe('quotation party fields', () => {
  it('keeps the business party selector required and backed by the master data', () => {
    const party = field('customerPartyId')
    expect(party.type).toBe('select')
    expect(party.required).toBe(true)
  })

  it('allows the company name to be typed instead of only auto-filled', () => {
    const company = field('customer')
    expect(company.type).toBe('text')
    // Computed fields render read-only; the company name must stay editable.
    expect(company.computed).toBeFalsy()
  })

  it('labels the selector "Business Party" in every locale', () => {
    expect(en.freight.fields.customerPartyId).toBe('Business Party')
    // Both translations must exist and differ from the English copy.
    expect(km.freight.fields.customerPartyId).toBeTruthy()
    expect(km.freight.fields.customerPartyId).not.toBe('Business Party')
    expect(zh.freight.fields.customerPartyId).toBeTruthy()
    expect(zh.freight.fields.customerPartyId).not.toBe('Business Party')
  })
})

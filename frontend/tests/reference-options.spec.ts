/**
 * The quotation / service-order party selector is populated from Master Data
 * (Business Parties).
 *
 * Those forms label the field "Company" / "Business Party", but the master records
 * a company under whatever roles apply — `Customer`, `Supplier` or `Company`. The
 * picker therefore offers every role and narrows on `status` only; filtering on a
 * role made a party unselectable, and because a metadata-driven select fails
 * silently (an empty list, no error), the wiring is pinned here.
 *
 * The backend counterpart is `test_quotation_accepts_a_supplier_role_party` in
 * `backend/tests/test_quotations.py`.
 */
import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'
import { referenceItemForValue, referenceOptionSource, referenceSelectItems } from '../app/utils/freight/reference-options'

const parties = [
  { id: '1', legalName: 'Customer Only Ltd.', roles: ['Customer'], status: 'ACTIVE' },
  { id: '2', legalName: 'Company Only Ltd.', roles: ['Company'], status: 'ACTIVE' },
  { id: '3', legalName: 'Supplier Only Ltd.', roles: ['Supplier'], status: 'ACTIVE' },
  { id: '4', legalName: 'Archived Company Ltd.', roles: ['Company'], status: 'INACTIVE' },
  { id: '5', legalName: 'Customer And Company Ltd.', roles: ['Customer', 'Company'], status: 'ACTIVE' },
  { id: '6', legalName: 'Unroled Ltd.', roles: [], status: 'ACTIVE' },
]

describe('business party reference selects', () => {
  it('backs the party roles form field with the Party Roles master, keyed by id', () => {
    const module = getFreightModule('/master-data/business-parties')!
    const field = module.fields.find(item => item.key === 'roleIds')
    expect(field?.type).toBe('multiselect')
    expect(referenceOptionSource('roleIds')).toMatchObject({
      collection: 'partyRoles',
      valueField: 'id',
      labelField: 'name',
      statuses: ['ACTIVE'],
    })
  })

  it('offers only active party roles for a new assignment', () => {
    const roles = [
      { id: '10', name: 'Customer', status: 'ACTIVE' },
      { id: '11', name: 'Legacy Carrier', status: 'INACTIVE' },
    ]
    expect(referenceSelectItems(roles, referenceOptionSource('roleIds')!)).toEqual([
      { label: 'Customer', value: '10' },
    ])
    // The list filter keeps inactive roles so an assigned one stays findable.
    expect(referenceSelectItems(roles, referenceOptionSource('roles')!).map(item => item.value)).toEqual([
      'Customer',
      'Legacy Carrier',
    ])
  })

  it('backs the quotation party field with the Business Parties master, keyed by id', () => {
    const field = getFreightModule('/quotations')!.fields.find(item => item.key === 'customerPartyId')
    expect(field?.type).toBe('select')
    expect(
      referenceOptionSource('customerPartyId'),
    ).toMatchObject({ collection: 'businessParties', valueField: 'id', labelField: 'legalName' })
  })

  it('offers a party of any role, because the picker never filters on roles', () => {
    for (const role of ['Customer', 'Supplier', 'Company']) {
      const items = referenceSelectItems([{ ...parties[0], roles: [role] }], referenceOptionSource('customerPartyId')!)
      expect(items, `a party holding only the ${role} role must be selectable`).toEqual([
        { label: 'Customer Only Ltd.', value: '1' },
      ])
    }
    for (const key of ['customerPartyId', 'customer']) {
      const items = referenceSelectItems(parties, referenceOptionSource(key)!)
      expect(items.map(item => item.value), `${key} must offer a supplier-only party`).toContain(
        key === 'customer' ? 'Supplier Only Ltd.' : '3',
      )
    }
  })

  it('lists every active party regardless of role', () => {
    // Value is the business party id for `customerPartyId`.
    expect(referenceSelectItems(parties, referenceOptionSource('customerPartyId')!)).toEqual([
      { label: 'Customer Only Ltd.', value: '1' },
      { label: 'Company Only Ltd.', value: '2' },
      { label: 'Supplier Only Ltd.', value: '3' },
      { label: 'Customer And Company Ltd.', value: '5' },
      { label: 'Unroled Ltd.', value: '6' },
    ])
  })

  it('still excludes inactive parties', () => {
    const keeps = (id: string) =>
      referenceSelectItems(parties, referenceOptionSource('customerPartyId')!).some(item => item.value === id)
    expect(keeps('4'), 'inactive company must not be selectable').toBe(false)
  })

  it('resolves the plain customer field to the legal name, not the id', () => {
    const source = referenceOptionSource('customer')!
    expect(source.valueField).toBe('legalName')
    const items = referenceSelectItems(parties, source)
    expect(items).toContainEqual({ label: 'Company Only Ltd.', value: 'Company Only Ltd.' })
    expect(items).toContainEqual({ label: 'Supplier Only Ltd.', value: 'Supplier Only Ltd.' })
  })
})

describe('quotation transport reference', () => {
  const transportTypes = [
    { id: '10', code: 'TRUCK', name: 'Truck', status: 'ACTIVE' },
    { id: '11', code: 'SEA', name: 'Sea', status: 'INACTIVE' },
    { id: '12', code: 'AIR', name: 'Air', status: 'ACTIVE' },
  ]

  it('backs the pricing By column with Transport Types keyed by id', () => {
    const source = referenceOptionSource('transportBy')!
    expect(source).toMatchObject({
      collection: 'transportTypes',
      valueField: 'id',
      labelField: 'name',
      statuses: ['ACTIVE'],
    })
    expect(referenceSelectItems(transportTypes, source)).toEqual([
      { label: 'Truck', value: '10' },
      { label: 'Air', value: '12' },
    ])
  })

  it('keeps a saved inactive or legacy value readable', () => {
    const source = referenceOptionSource('transportBy')!
    expect(referenceItemForValue(transportTypes, source, '11')).toEqual({ label: 'Sea', value: '11' })
    expect(referenceItemForValue(transportTypes, source, 'Sea')).toEqual({ label: 'Sea', value: 'Sea' })
    expect(referenceItemForValue(transportTypes, source, 'Road')).toBeNull()
  })
})
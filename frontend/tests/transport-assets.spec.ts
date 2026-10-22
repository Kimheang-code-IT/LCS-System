/**
 * The Transport Assets form (`/master-data/transport-assets`).
 *
 * Three of its fields are Master Data references (`transportType`, `ownerParty`,
 * `operatorParty`) and one is a closed dropdown (`identityType`). A metadata-driven
 * select fails silently — an empty list, no error — so the wiring from field to
 * master collection is pinned here, alongside the required-field rules.
 *
 * The backend counterpart is `backend/tests/test_transport_assets.py`.
 */
import { describe, expect, it } from 'vitest'
import { IDENTITY_TYPES } from '../app/config/freight-options'
import { getFreightModule } from '../app/config/freight-modules'
import { referenceOptionSource, referenceSelectItems } from '../app/utils/freight/reference-options'
import { validateDocumentFields } from '../app/utils/validation/record-validation'
import { getFilterSearchInputConfig } from '../app/utils/filter/select-ui'

const module = getFreightModule('/master-data/transport-assets')!
const fieldByKey = (key: string) => module.fields.find(item => item.key === key)!
const label = (key: string) => key

const transportTypes = [
  { name: 'Truck', status: 'ACTIVE' },
  { name: 'Vessel', status: 'ACTIVE' },
  { name: 'Retired Barge', status: 'INACTIVE' },
]

const parties = [
  { id: '1', legalName: 'Plate Owner Ltd.', roles: ['Supplier'], status: 'ACTIVE' },
  { id: '2', legalName: 'Plate Operator Ltd.', roles: ['Supplier'], status: 'ACTIVE' },
  { id: '3', legalName: 'Dormant Hauler', roles: ['Carrier'], status: 'INACTIVE' },
]

describe('transport assets form', () => {
  it('offers the identity types as a closed dropdown, required', () => {
    const identityType = fieldByKey('identityType')
    expect(identityType.type).toBe('select')
    expect(identityType.required).toBe(true)
    expect(identityType.options).toEqual([...IDENTITY_TYPES])
  })

  it('keeps the identity type vocabulary in step with the backend', () => {
    // The stored value is the label itself; `IDENTITY_TYPES` in
    // `backend/app/modules/master_data/service.py` is the accepted closed set.
    expect(IDENTITY_TYPES).toEqual(['License Plate', 'IMO Number', 'Flight Number', 'Other'])
  })

  it('requires the fields the table declares NOT NULL', () => {
    const failures = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(failure => failure.key).sort()
    // asset_code, transport_type_id and identity are NOT NULL on transport_assets.
    expect(failures).toEqual(['assetCode', 'identity', 'identityType', 'transportType'])
  })

  it('does not require the ownership parties', () => {
    const failures = validateDocumentFields({
      fields: module.fields,
      model: { assetCode: 'TRK-1', transportType: 'Truck', identity: '3C-9088', identityType: 'License Plate' },
      isCreate: true,
      label,
    })
    expect(failures).toEqual([])
  })

  it('backs the transport type with the Transport Types master', () => {
    expect(fieldByKey('transportType').type).toBe('select')
    expect(referenceOptionSource('transportType')).toMatchObject({ collection: 'transportTypes', valueField: 'name' })
    // Unfiltered by status, as it always has been: a job or a historic asset that
    // still names a retired transport type must keep resolving it.
    expect(referenceSelectItems(transportTypes, referenceOptionSource('transportType')!)).toEqual([
      { label: 'Truck', value: 'Truck' },
      { label: 'Vessel', value: 'Vessel' },
      { label: 'Retired Barge', value: 'Retired Barge' },
    ])
  })

  it('backs the owner and operator parties with the Business Parties master', () => {
    for (const key of ['ownerParty', 'operatorParty']) {
      expect(fieldByKey(key).type, `${key} must be a select, not free text`).toBe('select')
      // Stored by legal name: `_asset_computed` reads the parties back by name.
      expect(referenceOptionSource(key), key).toMatchObject({
        collection: 'businessParties',
        valueField: 'legalName',
        labelField: 'legalName',
        statuses: ['ACTIVE'],
      })
      expect(referenceSelectItems(parties, referenceOptionSource(key)!), key).toEqual([
        { label: 'Plate Owner Ltd.', value: 'Plate Owner Ltd.' },
        { label: 'Plate Operator Ltd.', value: 'Plate Operator Ltd.' },
      ])
    }
  })

  it('offers a party of any role, because the owner is often recorded as a Supplier', () => {
    const items = referenceSelectItems(parties, referenceOptionSource('ownerParty')!)
    expect(items.map(item => item.value)).toContain('Plate Owner Ltd.')
    expect(items.map(item => item.value)).not.toContain('Dormant Hauler')
  })

  it('renders every reference field as a searchable dropdown', () => {
    // `AppFieldGrid` routes `type: 'select'` through `CommonAppReferenceSelect`,
    // which is a `USelectMenu` with a search box — that is what makes these
    // "searchable dropdown" rather than a plain list.
    const searchInput = getFilterSearchInputConfig(() => 'Search')
    expect(searchInput).toMatchObject({ type: 'text', icon: 'i-lucide-search' })
    for (const key of ['transportType', 'ownerParty', 'operatorParty']) {
      expect(referenceOptionSource(key), key).toBeTruthy()
    }
  })

  it('keeps the asset code within the column width', () => {
    expect(fieldByKey('assetCode').required).toBe(true)
    expect(fieldByKey('assetCode').rule?.maxLength).toBe(50)
    expect(fieldByKey('identity').rule?.maxLength).toBe(128)
  })
})
/**
 * The Transport Assets form (`/master-data/transport-assets`) and the identity
 * vocabulary behind it (`/master-data/asset-identity-types`).
 *
 * The Identity Type is a Master Data reference, not a closed dropdown: the form
 * narrows the vocabulary by transport type through the field's `referenceFilter`
 * hook, and ends up reporting on `identity` when a sample does not match the
 * chosen row's pattern. A metadata-driven select fails silently — an empty list,
 * no error — so the wiring from field to master collection is pinned here,
 * alongside the required-field rules.
 *
 * The backend counterpart is `backend/tests/test_transport_assets.py`.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { ASSET_STATUSES } from '../app/config/freight-options'
import { getFreightModule } from '../app/config/freight-modules'
import { referenceOptionSource, referenceSelectItems, identityTypeOptionsFor, matchesIdentityPattern } from '../app/utils/freight/reference-options'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'
import { validateDocumentFields } from '../app/utils/validation/record-validation'
import { getFilterSearchInputConfig } from '../app/utils/filter/select-ui'

const module = getFreightModule('/master-data/transport-assets')!
const vocabulary = getFreightModule('/master-data/asset-identity-types')!
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

const identityVocabulary = [
  { name: 'License Plate', transportType: 'Truck', status: 'ACTIVE', identityLabel: 'License Plate Number', identityPlaceholder: 'Enter the license plate number' },
  { name: 'IMO Number', transportType: 'Vessel', status: 'ACTIVE', identityLabel: 'IMO Number', identityPlaceholder: 'Enter the 7-digit IMO number', validationPattern: '^\\d{7}$' },
  { name: 'Other', transportType: '', status: 'ACTIVE' },
  { name: 'Retired Code', transportType: '', status: 'INACTIVE' },
]

describe('transport assets form', () => {
  it('backs the identity type with the asset identity vocabulary, required', () => {
    const identityType = fieldByKey('identityType')
    expect(identityType.type).toBe('select')
    expect(identityType.required).toBe(true)
    // The vocabulary is master data; no shipped options list.
    expect(identityType.options).toBeUndefined()
    expect(referenceOptionSource('identityType')).toMatchObject({ collection: 'transportAssetIdentityTypes', valueField: 'name', labelField: 'name', statuses: ['ACTIVE'] })
  })

  it('narrowly offers the identity types the chosen transport type applies to', () => {
    // Status is filtered later, in `referenceSelectItems`; the hook only narrows
    // by transport type, and an unlinked row suits every type.
    expect(identityTypeOptionsFor({ transportType: 'Truck' }, identityVocabulary).map(row => row.name)).toEqual(['License Plate', 'Other', 'Retired Code'])
    expect(identityTypeOptionsFor({ transportType: 'Vessel' }, identityVocabulary).map(row => row.name)).toEqual(['IMO Number', 'Other', 'Retired Code'])
    // Without a transport type yet, every row is offered.
    expect(identityTypeOptionsFor({}, identityVocabulary)).toHaveLength(4)
  })

  it('carries the record hooks through to the dynamic form renderer', () => {
    const tabs = moduleDocumentTabs(module)
    const fields = tabs.flatMap(tab => tab.sections.flatMap(section => section.fields))
    const identityType = fields.find(field => field.key === 'identityType')!
    const identity = fields.find(field => field.key === 'identity')!
    expect(identityType.meta?.referenceFilter).toBe(identityTypeOptionsFor)
    // The Identity label and placeholder follow the chosen identity type; the
    // hook itself is exercised in the browser against the loaded vocabulary.
    expect(typeof identity.meta?.labelFor).toBe('function')
    expect(typeof identity.meta?.placeholderFor).toBe('function')
  })

  it('accepts a value when it matches the chosen row pattern, and nothing else', () => {
    expect(matchesIdentityPattern('^\\d{7}$', '9991234')).toBe(true)
    expect(matchesIdentityPattern('^\\d{7}$', 'IMO-9991234')).toBe(false)
    // An unanchored pattern still behaves exactly like the backend full match.
    expect(matchesIdentityPattern('\\d{7}', '9991234')).toBe(true)
    expect(matchesIdentityPattern('\\d{7}', 'X999123')).toBe(false)
    // No pattern, blank value or unparseable pattern leave it to the backend.
    expect(matchesIdentityPattern(undefined, 'anything')).toBe(true)
    expect(matchesIdentityPattern('^\\d{7}$', '')).toBe(true)
    expect(matchesIdentityPattern('([a-z', 'anything')).toBe(true)
  })

  it('requires the fields the table declares NOT NULL', () => {
    const failures = validateDocumentFields({ fields: module.fields, model: {}, isCreate: true, label })
      .map(failure => failure.key).sort()
    // asset_code, transport_type_id and identity are NOT NULL; the identity type
    // names the value the identity column holds.
    expect(failures).toEqual(['assetCode', 'identity', 'identityType', 'transportType'])
  })

  it('does not require the optional descriptive or ownership fields', () => {
    const failures = validateDocumentFields({
      fields: module.fields,
      model: { assetCode: 'TRK-1', transportType: 'Truck', identity: '3C-9088', identityType: 'License Plate', assetName: 'Phnom Penh Hauler 01', capacityValue: 22.5, capacityUnit: 'KG' },
      isCreate: true,
      label,
    })
    expect(failures).toEqual([])
  })

  it('keeps the capacity value from going negative', () => {
    const failures = validateDocumentFields({
      fields: module.fields,
      model: { assetCode: 'TRK-2', transportType: 'Truck', identity: '3C-9089', identityType: 'License Plate', capacityValue: -1 },
      isCreate: true,
      label,
    }).map(failure => failure.key)
    expect(failures).toContain('capacityValue')
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
    // `AppDynamicFieldRenderer` routes `type: 'select'` through
    // `CommonAppReferenceSelect`, which is a `USelectMenu` with a search box.
    const searchInput = getFilterSearchInputConfig(() => 'Search')
    expect(searchInput).toMatchObject({ type: 'text', icon: 'i-lucide-search' })
    for (const key of ['transportType', 'identityType', 'ownerParty', 'operatorParty']) {
      expect(referenceOptionSource(key), key).toBeTruthy()
    }
  })

  it('keeps the asset code within the column width', () => {
    expect(fieldByKey('assetCode').required).toBe(true)
    expect(fieldByKey('assetCode').rule?.maxLength).toBe(50)
    expect(fieldByKey('identity').rule?.maxLength).toBe(128)
  })

  it('backs the capacity unit with the Capacity Units master, as a select', () => {
    const capacityUnit = fieldByKey('capacityUnit')
    expect(capacityUnit.type).toBe('select')
    // Master data — never a shipped options list.
    expect(capacityUnit.options).toBeUndefined()
    // The optional capacity must be clearable, so blank stays null — not 0.
    expect(fieldByKey('capacityValue').nullable).toBe(true)
    const fields = moduleDocumentTabs(module).flatMap(tab => tab.sections.flatMap(section => section.fields))
    expect(fields.find(field => field.key === 'capacityValue')?.meta?.nullable).toBe(true)
    expect(referenceOptionSource('capacityUnit')).toMatchObject({
      collection: 'capacityUnits',
      valueField: 'code',
      labelField: 'name',
      statuses: ['ACTIVE'],
    })
    const units = [
      { code: 'KG', name: 'Kilograms', status: 'ACTIVE' },
      { code: 'PAL', name: 'Pallets', status: 'ACTIVE' },
      { code: 'OLD', name: 'Retired Unit', status: 'INACTIVE' },
    ]
    expect(referenceSelectItems(units, referenceOptionSource('capacityUnit')!)).toEqual([
      { label: 'Kilograms', value: 'KG' },
      { label: 'Pallets', value: 'PAL' },
    ])
  })

  it('prechecks the capacity pair in the form, mirroring the backend refusal', () => {
    // The rule itself is a cross-field check in `DocumentView`'s shared
    // `businessRuleFailures` pipeline; the keys it reports must be the field
    // i18n keys all three locales ship.
    const source = readFileSync(new URL('../app/components/freight/DocumentView.vue', import.meta.url), 'utf8')
    expect(source).toContain('freight.ui.capacityNeedsValue')
    expect(source).toContain('freight.ui.capacityNeedsUnit')
  })

  it('records the three asset statuses the row menu can reach', () => {
    expect(module.statuses).toEqual([...ASSET_STATUSES])
    const statusFilter = module.filters?.find(field => field.key === 'status')
    expect(statusFilter?.options).toEqual([...ASSET_STATUSES])
  })
})

describe('asset identity types master', () => {
  it('is a Master Data page linked to the asset vocabulary', () => {
    expect(vocabulary.collection).toBe('transportAssetIdentityTypes')
    expect(vocabulary.permission).toBe('master.transport_assets.view')
    expect(vocabulary.fields.map(field => field.key)).toContain('transportType')
    expect(vocabulary.fields.map(field => field.key)).toContain('validationPattern')
  })

  it('requires the name, and nothing else', () => {
    const failures = validateDocumentFields({ fields: vocabulary.fields, model: {}, isCreate: true, label })
      .map(failure => failure.key).sort()
    expect(failures).toEqual(['name'])
  })

  it('keeps its label within the column width', () => {
    expect(fieldById(vocabulary, 'name').rule?.maxLength).toBe(100)
  })

  it('gives the pattern field the Test Pattern helper', () => {
    const tabs = moduleDocumentTabs(vocabulary)
    const pattern = tabs.flatMap(tab => tab.sections.flatMap(section => section.fields))
      .find(field => field.key === 'validationPattern')!
    expect(pattern.meta?.patternTester).toBe(true)
  })
})

describe('capacity units master', () => {
  const units = getFreightModule('/master-data/capacity-units')!

  it('is a Master Data page backed by the capacityUnits collection', () => {
    expect(units.collection).toBe('capacityUnits')
    expect(units.permission).toBe('master.transport_assets.view')
    expect(units.fields.map(field => field.key)).toEqual(['code', 'name', 'status'])
  })

  it('requires a short code and a name, and nothing else', () => {
    const failures = validateDocumentFields({ fields: units.fields, model: {}, isCreate: true, label })
      .map(failure => failure.key).sort()
    expect(failures).toEqual(['code', 'name'])
    expect(fieldById(units, 'code').rule?.maxLength).toBe(16)
    expect(fieldById(units, 'name').rule?.maxLength).toBe(64)
  })
})

function fieldById(mod: typeof module, key: string) {
  return mod.fields.find(item => item.key === key)!
}

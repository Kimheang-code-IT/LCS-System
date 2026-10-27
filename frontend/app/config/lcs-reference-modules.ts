import type { FreightField, FreightModule } from './freight-modules'
import { DOCUMENT_SEQUENCE_STATUSES, DOCUMENT_SEQUENCE_TYPES } from '~/utils/document-sequences'
import { DOCUMENT_TYPE_BEHAVIORS, DOCUMENT_TYPE_CATEGORIES, DOCUMENT_TYPE_MODULES, postingRuleDocumentTypeFilter } from '~/utils/constants/document-types'
import { identityLabelFor, identityPlaceholderFor, identityTypeOptionsFor } from '~/utils/freight/reference-options'
import {
  ACCOUNT_TYPES,
  ACTIVE_STATUS,
  ASSET_STATUSES,
  CURRENCY_RATE_STATUSES,
  FINANCIAL_DOCUMENT_STATUSES,
  FINANCIAL_DOCUMENT_TYPES,
  PERIOD_STATUS,
} from './freight-options'

const YES_NO = ['Yes', 'No'] as const

const field = (
  key: string,
  label: string,
  labelKm: string,
  section = 'General',
  sectionKm = 'ព័ត៌មានទូទៅ',
  type: FreightField['type'] = 'text',
  options?: FreightField['options'],
  required = false,
  extra: Partial<FreightField> = {},
): FreightField => ({ key, label, labelKm, section, sectionKm, type, options, required, ...extra })

const column = (key: string, label: string, labelKm: string, extra: Partial<FreightField> = {}): FreightField => ({ key, label, labelKm, ...extra })
const module = (value: FreightModule): FreightModule => value

/** Metadata-driven pages required by the approved freight-forwarding scope. */
export const lcsReferenceModules: FreightModule[] = [
  module({
    path: '/master-data/business-parties', title: 'Business Parties', titleKm: 'ដៃគូអាជីវកម្ម', singular: 'Business Party', singularKm: 'ដៃគូអាជីវកម្ម',
    description: 'One shared record for customer, supplier and company roles.', descriptionKm: 'កំណត់ត្រារួមសម្រាប់តួនាទីដៃគូអាជីវកម្ម។',
    icon: 'i-lucide-handshake', group: 'master', permission: 'master.business_parties.view', collection: 'businessParties', titleField: 'legalName', kind: 'standard', canCreate: true,
    columns: [
      column('partyCode', 'Party Code', 'លេខកូដ'), column('displayName', 'Business Party', 'ដៃគូអាជីវកម្ម'),
      column('roles', 'Roles', 'តួនាទី'), column('contactPerson', 'Contact Person', 'អ្នកទំនាក់ទំនង'),
      column('phone', 'Phone', 'ទូរស័ព្ទ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('partyCode', 'Party Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { minLength: 1, maxLength: 50, pattern: '^[A-Za-z0-9][A-Za-z0-9._/-]*$' } }), field('legalName', 'Legal Name', 'ឈ្មោះផ្លូវការ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }),
      field('displayName', 'Display Name', 'ឈ្មោះបង្ហាញ', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 255 } }), field('taxIdentifier', 'VAT / TIN', 'អាករ / TIN', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 64 } }), field('contactPerson', 'Contact Person', 'អ្នកទំនាក់ទំនង', 'Contact', 'ទំនាក់ទំនង', 'text', undefined, false, { rule: { maxLength: 255 } }),
      field('phone', 'Phone', 'ទូរស័ព្ទ', 'Contact', 'ទំនាក់ទំនង', 'text', undefined, false, { rule: { maxLength: 64 } }), field('email', 'Email', 'អ៊ីមែល', 'Contact', 'ទំនាក់ទំនង', 'text', undefined, false, { rule: { maxLength: 255 } }),
      field('address', 'Address', 'អាសយដ្ឋាន', 'Address', 'អាសយដ្ឋាន', 'textarea', undefined, false, { colSpan: 2 }),
      field('roleIds', 'Party Roles', 'តួនាទីដៃគូ', 'Contact', 'ទំនាក់ទំនង', 'multiselect', undefined, true), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('roles', 'Role', 'តួនាទី', '', '', 'select'), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/party-roles', title: 'Party Roles', titleKm: 'តួនាទីដៃគូអាជីវកម្ម', singular: 'Party Role', singularKm: 'តួនាទីដៃគូអាជីវកម្ម',
    description: 'Roles a business party can hold, such as Customer, Supplier or Company. Deactivate a role instead of deleting it once a party uses it.',
    descriptionKm: 'តួនាទីដែលដៃគូអាជីវកម្មអាចកាន់ ដូចជា អតិថិជន អ្នកផ្គត់ផ្គង់ ឬក្រុមហ៊ុន។ បិទដំណើរការតួនាទីជំនួសឱ្យការលុប នៅពេលដៃគូប្រើវា។',
    icon: 'i-lucide-users', group: 'master', permission: 'master.party_roles.view', collection: 'partyRoles', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Role Name', 'ឈ្មោះ'),
      column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('code', 'Role Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 50, pattern: '^[A-Za-z][A-Za-z0-9_-]*$' } }),
      field('name', 'Role Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }),
      field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
      field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/place-roles', title: 'Place Roles', titleKm: 'តួនាទីទីកន្លែង', singular: 'Place Role', singularKm: 'តួនាទីទីកន្លែង',
    description: 'Route-stop roles such as Pickup, Origin or Customs Clearance. Roles are configuration, not locations; deactivate one instead of deleting it once a route refers to it.',
    descriptionKm: 'តួនាទីចំណុចផ្លូវ ដូចជា ការទទួល ដើមកំណើត ឬការបោសសំអាតគយ។ តួនាទីគឺជាការកំណត់ មិនមែនទីកន្លែងទេ។',
    icon: 'i-lucide-signpost', group: 'master', permission: 'master.place_roles.view', collection: 'placeRoles', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'),
      column('sortOrder', 'Display Order', 'លំដាប់បង្ហាញ'), column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 50, pattern: '^[A-Za-z][A-Za-z0-9_-]*$' } }),
      field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }),
      field('sortOrder', 'Display Order', 'លំដាប់បង្ហាញ', undefined, undefined, 'number', undefined, true, { rule: { integer: true, nonNegative: true } }),
      field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
      field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/trade-directions', title: 'Trade Directions', titleKm: 'ទិសដៅពាណិជ្ជកម្ម', singular: 'Trade Direction', singularKm: 'ទិសដៅពាណិជ្ជកម្ម', description: 'Import, export, transit and re-export service directions.', descriptionKm: 'ទិសដៅនាំចូល នាំចេញ ឆ្លងកាត់ និងនាំចេញវិញ។',
    icon: 'i-lucide-route', group: 'master', permission: 'master.trade_directions.view', collection: 'tradeDirections', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 50 } }), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/container-types', title: 'Container Types', titleKm: 'ប្រភេទកុងតឺន័រ', singular: 'Container Type', singularKm: 'ប្រភេទកុងតឺន័រ', description: 'Physical container ISO classifications and dimensions.', descriptionKm: 'ចំណាត់ថ្នាក់ និងទំហំកុងតឺន័រ ISO។',
    icon: 'i-lucide-container', group: 'master', permission: 'master.container_types.view', collection: 'containerTypes', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('size', 'Size', 'ទំហំ'), column('isoCode', 'ISO Code', 'លេខកូដ ISO'),
      column('maxGrossWeightKg', 'Max Gross Weight', 'ទម្ងន់អតិបរមា'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 50 } }), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }), field('size', 'Container Size', 'ទំហំកុងតឺន័រ', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 32 } }), field('kind', 'Container Kind', 'ប្រភេទកុងតឺន័រ', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 32 } }), field('isoCode', 'ISO Code', 'លេខកូដ ISO', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 16 } }),
      field('lengthFeet', 'Length Feet', 'ប្រវែងហ្វីត', 'Dimensions', 'វិមាត្រ', 'number', undefined, false, { rule: { number: true, nonNegative: true } }), field('widthMeters', 'Width', 'ទទឹង', 'Dimensions', 'វិមាត្រ', 'number', undefined, false, { rule: { number: true, nonNegative: true } }), field('heightMeters', 'Height', 'កម្ពស់', 'Dimensions', 'វិមាត្រ', 'number', undefined, false, { rule: { number: true, nonNegative: true } }), field('maxGrossWeightKg', 'Max Gross Weight', 'ទម្ងន់សរុបអតិបរមា', 'Dimensions', 'វិមាត្រ', 'number', undefined, false, { rule: { number: true, nonNegative: true } }),
      field('description', 'Description', 'បរិយាយ', 'Details', 'ព័ត៌មានលម្អិត', 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/transport-types', title: 'Transport Types', titleKm: 'ប្រភេទដឹកជញ្ជូន', singular: 'Transport Type', singularKm: 'ប្រភេទដឹកជញ្ជូន', description: 'Road, sea, air, rail and multimodal transport types.', descriptionKm: 'ដឹកជញ្ជូនផ្លូវគោក សមុទ្រ អាកាស ផ្លូវដែក និងចម្រុះ។',
    icon: 'i-lucide-truck', group: 'master', permission: 'master.transport_types.view', collection: 'transportTypes', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 50 } }), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/transport-assets', title: 'Transport Assets', titleKm: 'ទ្រព្យដឹកជញ្ជូន', singular: 'Transport Asset', singularKm: 'ទ្រព្យដឹកជញ្ជូន', description: 'Vehicles, vessels and other transport identities.', descriptionKm: 'យានយន្ត នាវា និងអត្តសញ្ញាណដឹកជញ្ជូន។',
    icon: 'i-lucide-truck-front', group: 'master', permission: 'master.transport_assets.view', collection: 'transportAssets', titleField: 'identity', kind: 'standard', canCreate: true,
    columns: [
      column('assetCode', 'Asset Code', 'លេខកូដទ្រព្យ'), column('assetName', 'Asset Name', 'ឈ្មោះទ្រព្យ'), column('transportType', 'Transport Type', 'ប្រភេទដឹកជញ្ជូន'),
      column('identity', 'Identity', 'អត្តសញ្ញាណ'), column('capacity', 'Capacity', 'និទ្ធភាព'), column('ownerParty', 'Owner', 'ម្ចាស់'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('assetCode', 'Asset Code', 'លេខកូដទ្រព្យ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 50 } }),
      field('assetName', 'Asset Name', 'ឈ្មោះទ្រព្យ', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 150 } }),
      // `transportType`, `ownerParty` and `operatorParty` are Master Data
      // references: `reference-options.ts` backs them with the Transport Types and
      // Business Parties masters, so each is a searchable dropdown of real records.
      field('transportType', 'Transport Type', 'ប្រភេទដឹកជញ្ជូន', undefined, undefined, 'select', undefined, true),
      // Says what `identity` holds, so the value below is read as the plate
      // number, the IMO number or the flight identifier rather than a free note.
      // The vocabulary is Master Data; `identityTypeOptionsFor` filters out the
      // identity types the chosen transport type does not apply to.
      field('identityType', 'Identity Type', 'ប្រភេទអត្តសញ្ញាណ', undefined, undefined, 'select', undefined, true, { referenceFilter: identityTypeOptionsFor }),
      // The Identity label and placeholder follow the chosen identity type
      // ("License Plate Number", "Enter the 7-digit IMO number").
      field('identity', 'Identity', 'អត្តសញ្ញាណ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 128 }, labelFor: identityLabelFor, placeholderFor: identityPlaceholderFor }),
      // Capacity is optional and paired: a value without a unit, or the reverse,
      // still reads as one display string computed by the backend. The unit is
      // chosen from the Capacity Units master (`capacityUnits`), seeded as data.
      field('capacityValue', 'Capacity', 'និទ្ធភាព', undefined, undefined, 'number', undefined, false, { rule: { nonNegative: true }, nullable: true }),
      field('capacityUnit', 'Capacity Unit', 'ឯកតានិទ្ធភាព', undefined, undefined, 'select', undefined, false),
      field('ownerParty', 'Owner Party', 'ភាគីម្ចាស់', 'Ownership', 'កម្មសិទ្ធិ', 'select'),
      field('operatorParty', 'Operator Party', 'ភាគីប្រតិបត្តិករ', 'Ownership', 'កម្មសិទ្ធិ', 'select'),
      field('description', 'Description', 'បរិយាយ', 'Details', 'ព័ត៌មានលម្អិត', 'textarea', undefined, false, { colSpan: 2 }),
    ],
    filters: [field('transportType', 'Transport Type', 'ប្រភេទដឹកជញ្ជូន', '', '', 'select'), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ASSET_STATUSES)],
    statuses: ASSET_STATUSES,
  }),
  module({
    path: '/master-data/asset-identity-types', title: 'Asset Identity Types', titleKm: 'ប្រភេទអត្តសញ្ញាណទ្រព្យ', singular: 'Asset Identity Type', singularKm: 'ប្រភេទអត្តសញ្ញាណទ្រព្យ',
    description: 'What a transport asset\u2019s identity holds, the label and pattern that go with it. Deactivate one instead of deleting it once an asset uses it.',
    descriptionKm: 'អ្វីដែលអត្តសញ្ញាណទ្រព្យដឹកជញ្ជូននិយាយ ជាមួយស្លាក និងទម្រង់ត្រួតពិនិត្យ។ បិទដំណើរការជំនួសឱ្យការលុប នៅពេលទ្រព្យមួយប្រើវា។',
    icon: 'i-lucide-fingerprint', group: 'master', permission: 'master.transport_assets.view', collection: 'transportAssetIdentityTypes', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('name', 'Identity Type', 'ប្រភេទអត្តសញ្ញាណ'), column('transportType', 'Applies To', 'អនុវត្តលើ'),
      column('identityLabel', 'Field Label', 'ស្លាកចំណត'), column('validationPattern', 'Validation Pattern', 'ទម្រង់ត្រួតពិនិត្យ'),
      column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('name', 'Identity Type', 'ប្រភេទអត្តសញ្ញាណ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 100 } }),
      // Empty (= every transport type) or one transport type; the asset form
      // offers the vocabulary narrowed by this link.
      field('transportType', 'Applies To', 'អនុវត្តលើ', undefined, undefined, 'select'),
      field('identityLabel', 'Field Label', 'ស្លាកចំណត', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 100 } }),
      field('identityPlaceholder', 'Placeholder', 'កន្លែងសរសេរ', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 120 } }),
      field('validationPattern', 'Validation Pattern', 'ទម្រង់ត្រួតពិនិត្យ', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 200 }, patternTester: true }),
      field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/capacity-units', title: 'Capacity Units', titleKm: 'ឯកតានិទ្ធភាព', singular: 'Capacity Unit', singularKm: 'ឯកតានិទ្ធភាព',
    description: 'Units the transport asset capacity can use (KG, CBM, Pallets, ...). Deactivate one instead of deleting it once an asset uses it.',
    descriptionKm: 'ឯកតាដែលនិទ្ធភាពទ្រព្យដឹកជញ្ជូនប្រើ ដូចជាគីឡូក្រាម ទឹកការេម៉ែត្រ ឬប៉ាឡា។ បិទដំណើរការជំនួសឱ្យការលុប នៅពេលទ្រព្យមួយប្រើវា។',
    icon: 'i-lucide-scale', group: 'master', permission: 'master.transport_assets.view', collection: 'capacityUnits', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('code', 'Unit Code', 'លេខកូដឯកតា', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 16, pattern: '^[A-Za-z][A-Za-z0-9_-]*$' } }),
      field('name', 'Unit Name', 'ឈ្មោះឯកតា', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 64 } }),
      field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/fee-types', title: 'Fee Types', titleKm: 'ប្រភេទថ្លៃ', singular: 'Fee Type', singularKm: 'ប្រភេទថ្លៃ', description: 'Reusable operational and financial fee definitions.', descriptionKm: 'និយមន័យថ្លៃប្រតិបត្តិការ និងហិរញ្ញវត្ថុដែលប្រើឡើងវិញ។',
    icon: 'i-lucide-receipt-text', group: 'master', permission: 'master.fee_types.view', collection: 'feeTypes', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 50 } }), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),

  module({
    path: '/master-data/currencies', title: 'Currencies', titleKm: 'រូបិយប័ណ្ណ', singular: 'Currency', singularKm: 'រូបិយប័ណ្ណ',
    description: 'ISO currencies used for pricing, invoices and accounting.', descriptionKm: 'រូបិយប័ណ្ណ ISO សម្រាប់តម្លៃ វិក្កយបត្រ និងគណនេយ្យ។',
    icon: 'i-lucide-coins', group: 'master', permission: 'master.currencies.view', collection: 'currencies', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('symbol', 'Symbol', 'សញ្ញា'),
      column('decimalPlaces', 'Decimal Places', 'ខ្ទង់ទសភាគ'), column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { minLength: 3, maxLength: 3, pattern: '^[A-Za-z]{3}$' } }),
      field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 100 } }),
      field('symbol', 'Symbol', 'សញ្ញា', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 10 } }),
      field('numericCode', 'Numeric Code', 'លេខកូដលេខ', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 3 } }),
      field('decimalPlaces', 'Decimal Places', 'ខ្ទង់ទសភាគ', undefined, undefined, 'number', undefined, true, { rule: { integer: true, min: 0, max: 6 } }),
      field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
      field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),

  // The rate store the document form resolves from. Only an APPROVED row is ever
  // applied, and a pair is unique per effective date; the resolution rules live in
  // `backend/app/modules/master_data/currency_rates.py`.
  //
  // This collection has no sidebar page and no `app/pages/master-data/currency-rates`
  // directory: the owner asked for it to stay out of the menu, and the store is
  // maintained through the `currencyRates` master-data API (`/api/v1/currencyRates`).
  // Adding a page means adding the page directory *and* a `useMenu.ts` link back.
  module({
    path: '/master-data/currency-rates', title: 'Currency Rates', titleKm: 'អត្រាប្តូរប្រាក់', singular: 'Currency Rate', singularKm: 'អត្រាប្តូរប្រាក់',
    description: 'Approved conversion rates between currencies, effective from a date. A document in another currency resolves its rate from the newest approved row.', descriptionKm: 'អត្រាប្តូរប្រាក់ដែលបានអនុម័តរវាងរូបិយប័ណ្ណ ចាប់ផ្តើមអនុវត្តពីកាលបរិច្ឆេទមួយ។ ឯកសារជារូបិយប័ណ្ណផ្សេង យកអត្រាពីជួរដែលបានអនុម័តថ្មីបំផុត។',
    icon: 'i-lucide-repeat', group: 'master', permission: 'master.currencies.view', collection: 'currencyRates', titleField: 'fromCurrencyCode', kind: 'standard', canCreate: true,
    columns: [
      column('fromCurrencyCode', 'From', 'ពី'), column('toCurrencyCode', 'To', 'ទៅ'), column('rate', 'Rate', 'អត្រា'),
      column('effectiveDate', 'Effective Date', 'កាលបរិច្ឆេទអនុវត្ត'), column('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      field('fromCurrencyCode', 'From Currency', 'រូបិយប័ណ្ណដើម', undefined, undefined, 'select', undefined, true, { rule: { minLength: 3, maxLength: 3 } }),
      field('toCurrencyCode', 'To Currency', 'រូបិយប័ណ្ណគោលដៅ', undefined, undefined, 'select', undefined, true, { rule: { minLength: 3, maxLength: 3 } }),
      field('effectiveDate', 'Effective Date', 'កាលបរិច្ឆេទអនុវត្ត', undefined, undefined, 'date', undefined, true),
      field('rate', 'Rate', 'អត្រា', undefined, undefined, 'number', undefined, true, { rule: { positive: true, decimalPlaces: 8 } }),
      field('status', 'Status', 'ស្ថានភាព', undefined, undefined, 'select', CURRENCY_RATE_STATUSES, true),
      field('source', 'Source', 'ប្រភព', undefined, undefined, 'text', undefined, false, { rule: { maxLength: 80 } }),
      field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', CURRENCY_RATE_STATUSES)],
  }),

  module({
    path: '/master-data/document-types',
    title: 'Document Types',
    titleKm: 'ប្រភេទឯកសារ',
    singular: 'Document Type',
    singularKm: 'ប្រភេទឯកសារ',
    description: 'Central catalogue of document types with their accounting behavior.',
    descriptionKm: 'បញ្ជីកណ្តាលនៃប្រភេទឯកសារ ជាមួយសកម្មភាពគណនេយ្យរបស់វា។',
    icon: 'i-lucide-file-stack',
    group: 'master',
    permission: 'master.reference.view',
    collection: 'documentTypes',
    titleField: 'name',
    kind: 'standard',
    canCreate: true,
    columns: [
      column('code', 'Code', 'លេខកូដ'),
      column('name', 'Document Type', 'ប្រភេទឯកសារ'),
      column('category', 'Category', 'ប្រភេទក្រុម'),
      column('postingRequired', 'Posting Required', 'ត្រូវចុះបញ្ជី', { type: 'checkbox' }),
      column('status', 'Status', 'ស្ថានភាព'),
      column('createdBy', 'Created By', 'បង្កើតដោយ', { labelKey: 'freight.fields.createdBy' }),
      column('createdAt', 'Created At', 'បង្កើតនៅ', { labelKey: 'freight.fields.createdAt', type: 'datetime' }),
    ],
    fields: [
      field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true, { rule: { required: true, maxLength: 64, pattern: '^[A-Z][A-Z0-9_]*$' } }),
      field('name', 'Document Type Name', 'ឈ្មោះប្រភេទឯកសារ', undefined, undefined, 'text', undefined, true, { rule: { required: true, maxLength: 255 } }),
      field('category', 'Category', 'ប្រភេទក្រុម', undefined, undefined, 'select', [...DOCUMENT_TYPE_CATEGORIES], true),
      field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
      field('availableIn', 'Available In', 'អាចប្រើក្នុង', undefined, undefined, 'multiselect', [...DOCUMENT_TYPE_MODULES], true),
      field('accountingBehavior', 'Accounting Behavior', 'សកម្មភាពគណនេយ្យ', undefined, undefined, 'select', [...DOCUMENT_TYPE_BEHAVIORS], true),
      field('postingRequired', 'Posting Required', 'ត្រូវចុះបញ្ជី', undefined, undefined, 'checkbox', undefined, true),
      field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [
      field('category', 'Category', 'ប្រភេទក្រុម', '', '', 'select', [...DOCUMENT_TYPE_CATEGORIES]),
      field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS),
    ],
  }),

  module({
    path: '/administration/document-sequences', title: 'Document Sequences', titleKm: 'លំដាប់លេខឯកសារ', singular: 'Document Sequence', singularKm: 'លំដាប់ឯកសារ', description: 'Manage automatic document numbering by document type and year.', descriptionKm: 'គ្រប់គ្រងលេខឯកសារស្វ័យប្រវត្តិ តាមប្រភេទឯកសារ និងឆ្នាំ។',
    icon: 'i-lucide-list-ordered', group: 'admin', permission: 'admin.document_sequences.view', collection: 'documentSequences', titleField: 'documentType', kind: 'standard', canCreate: true,
    columns: [
      column('documentType', 'Document Type', 'ប្រភេទឯកសារ'), column('year', 'Year', 'ឆ្នាំ'), column('prefix', 'Prefix', 'បុព្វបទ'),
      column('lastValue', 'Last Value', 'តម្លៃចុងក្រោយ'), column('paddingLength', 'Padding', 'ប្រវែងលេខ'), column('nextNumberPreview', 'Next Number', 'លេខបន្ទាប់'), column('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      field('documentType', 'Document Type', 'ប្រភេទឯកសារ', undefined, undefined, 'select', DOCUMENT_SEQUENCE_TYPES, true),
      field('year', 'Year', 'ឆ្នាំ', undefined, undefined, 'number', undefined, true, { rule: { integer: true, min: 1000, max: 9999 } }),
      field('prefix', 'Prefix', 'បុព្វបទ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 16 } }),
      field('lastValue', 'Starting / Last Value', 'តម្លៃចាប់ផ្តើម / ចុងក្រោយ', undefined, undefined, 'number', undefined, true, { rule: { integer: true, nonNegative: true } }),
      field('paddingLength', 'Padding Length', 'ប្រវែងលេខ', undefined, undefined, 'number', undefined, true, { rule: { integer: true, min: 1, max: 12 } }),
      field('nextNumberPreview', 'Next Number Preview', 'លេខបន្ទាប់', undefined, undefined, 'text', undefined, false, { computed: true }),
    ],
    filters: [
      field('documentType', 'Document Type', 'ប្រភេទឯកសារ', '', '', 'select', DOCUMENT_SEQUENCE_TYPES),
      field('year', 'Year', 'ឆ្នាំ', '', '', 'select'),
      field('status', 'Status', 'ស្ថានភាព', '', '', 'select', DOCUMENT_SEQUENCE_STATUSES),
    ],
  }),

  module({
    path: '/finance/chart-of-accounts', title: 'Chart of Accounts', titleKm: 'បញ្ជីគណនី', singular: 'Ledger Account', singularKm: 'គណនី', description: 'Double-entry ledger accounts.', descriptionKm: 'គណនីសៀវភៅធំសម្រាប់គណនេយ្យទ្វេភាគ។',
    icon: 'i-lucide-list-tree', group: 'finance', permission: 'finance.chart_of_accounts.view', collection: 'chartOfAccounts', titleField: 'accountName', kind: 'standard', canCreate: true,
    columns: [column('accountCode', 'Account Code', 'លេខកូដគណនី'), column('accountName', 'Account Name', 'ឈ្មោះគណនី'), column('accountType', 'Account Type', 'ប្រភេទគណនី'), column('parentCode', 'Parent Account', 'គណនីមេ'), column('normalBalance', 'Normal Balance', 'សមតុល្យធម្មតា'), column('postable', 'Postable', 'អាចចុះបញ្ជី'), column('status', 'Status', 'ស្ថានភាព')],
    // The status field is the create default (`defaultStatusForModule` uses its
    // first option); `moduleDocumentTabs` keeps it off every form, so the
    // status itself is only changed from the record's "..." menu.
    fields: [field('accountCode', 'Account Code', 'លេខកូដគណនី', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 32, pattern: '^[A-Za-z0-9][A-Za-z0-9._-]*$' } }), field('accountName', 'Account Name', 'ឈ្មោះគណនី', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }), field('accountType', 'Account Type', 'ប្រភេទគណនី', undefined, undefined, 'select', ACCOUNT_TYPES, true, { rule: { required: true } }), field('parentCode', 'Parent Account', 'គណនីមេ', 'Structure', 'រចនាសម្ព័ន្ធ', 'text', undefined, false, { rule: { maxLength: 32 } }), field('normalBalance', 'Normal Balance', 'សមតុល្យធម្មតា', 'Structure', 'រចនាសម្ព័ន្ធ', 'select', ['Debit', 'Credit'], true, { rule: { required: true } }), field('postable', 'Is Postable', 'អាចចុះបញ្ជី', 'Control', 'ការគ្រប់គ្រង', 'checkbox', YES_NO), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('accountType', 'Account Type', 'ប្រភេទគណនី', '', '', 'select', ACCOUNT_TYPES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/finance/financial-accounts', title: 'Financial Accounts', titleKm: 'គណនីហិរញ្ញវត្ថុ', singular: 'Financial Account', singularKm: 'គណនីហិរញ្ញវត្ថុ', description: 'Cash, bank and settlement accounts linked to the ledger.', descriptionKm: 'គណនីសាច់ប្រាក់ ធនាគារ និងទូទាត់ភ្ជាប់សៀវភៅធំ។',
    icon: 'i-lucide-wallet-cards', group: 'finance', permission: 'finance.financial_accounts.view', collection: 'financialAccounts', titleField: 'accountName', kind: 'standard', canCreate: true,
    columns: [column('accountName', 'Account Name', 'ឈ្មោះគណនី'), column('accountType', 'Account Type', 'ប្រភេទគណនី'), column('ledgerCode', 'Ledger Account', 'គណនីសៀវភៅ'), column('currency', 'Currency', 'រូបិយប័ណ្ណ'), column('bankName', 'Bank', 'ធនាគារ'), column('accountNumberMasked', 'Account No.', 'លេខគណនី'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('ledgerCode', 'Ledger Account', 'គណនីសៀវភៅ', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 32 } }), field('accountName', 'Account Name', 'ឈ្មោះគណនី', undefined, undefined, 'text', undefined, true, { rule: { maxLength: 255 } }), field('accountType', 'Account Type', 'ប្រភេទគណនី', undefined, undefined, 'select', ['Bank', 'Cash'], true), field('currency', 'Currency', 'រូបិយប័ណ្ណ', undefined, undefined, 'select'), field('bankName', 'Bank Name', 'ឈ្មោះធនាគារ', 'Bank Details', 'ព័ត៌មានធនាគារ'), field('accountNumberMasked', 'Masked Account Number', 'លេខគណនីបិទបាំង', 'Bank Details', 'ព័ត៌មានធនាគារ'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('accountType', 'Account Type', 'ប្រភេទគណនី', '', '', 'select', ['Bank', 'Cash']), field('currency', 'Currency', 'រូបិយប័ណ្ណ', '', '', 'select'), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/finance/journals', title: 'Journal Entries', titleKm: 'បញ្ជីទិនានុប្បវត្តិ', singular: 'Journal Entry', singularKm: 'ទិនានុប្បវត្តិ', description: 'Balanced debit and credit entries with source traceability.', descriptionKm: 'ឥណពន្ធ និងឥណទានមានតុល្យភាព និងប្រភពតាមដាន។',
    icon: 'i-lucide-book-check', group: 'finance', permission: 'finance.journal_entries.view', collection: 'journals', titleField: 'entryNo', kind: 'standard', canCreate: true,
    columns: [column('entryNo', 'Journal No.', 'លេខទិនានុប្បវត្តិ'), column('postingDate', 'Posting Date', 'កាលបរិច្ឆេទចុះបញ្ជី'), column('sourceDocumentNo', 'Source Document', 'ឯកសារប្រភព'), column('jobNo', 'SO No.', 'លេខ SO'), column('description', 'Description', 'បរិយាយ'), column('debitTotal', 'Debit', 'ឥណពន្ធ'), column('creditTotal', 'Credit', 'ឥណទាន'), column('status', 'Status', 'ស្ថានភាព'), column('createdBy', 'Created By', 'បង្កើតដោយ')],
    fields: [field('entryNo', 'Entry No.', 'លេខទិនានុប្បវត្តិ', undefined, undefined, 'text', undefined, true, { computed: true }), field('entryType', 'Entry Type', 'ប្រភេទទិនានុប្បវត្តិ', undefined, undefined, 'select', ['MANUAL', 'AUTOMATIC', 'REVERSAL']), field('entryDate', 'Entry Date', 'កាលបរិច្ឆេទទិនានុប្បវត្តិ', undefined, undefined, 'date'), field('postingDate', 'Posting Date', 'កាលបរិច្ឆេទចុះបញ្ជី', undefined, undefined, 'date'), field('periodId', 'Accounting Period', 'រយៈពេលគណនេយ្យ'), field('sourceDocumentNo', 'Source Document', 'ឯកសារប្រភព'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ['DRAFT', 'POSTED', 'REVERSED', 'VOIDED']), field('description', 'Description', 'បរិយាយ', 'Details', 'ព័ត៌មានលម្អិត', 'textarea', undefined, false, { colSpan: 2 }), field('debitTotal', 'Total Debit', 'ឥណពន្ធសរុប', 'Balance', 'តុល្យភាព', 'number', undefined, false, { computed: true }), field('creditTotal', 'Total Credit', 'ឥណទានសរុប', 'Balance', 'តុល្យភាព', 'number', undefined, false, { computed: true }), field('balanceDifference', 'Balance Difference', 'ភាពខុសគ្នា', 'Balance', 'តុល្យភាព', 'number', undefined, false, { computed: true })],
    tables: [{ key: 'lines', title: 'Journal Lines', titleKm: 'ជួរទិនានុប្បវត្តិ', addLabel: 'Add journal line', columns: [
      { key: 'account_code', label: 'Account', labelKm: 'គណនី', required: true }, { key: 'party', label: 'Party', labelKm: 'ដៃគូ' }, { key: 'serviceOrder', label: 'Service Job', labelKm: 'បញ្ជាសេវាកម្ម' }, { key: 'description', label: 'Description', labelKm: 'បរិយាយ', rule: { maxLength: 1000 } }, { key: 'debit_amount', label: 'Debit', labelKm: 'ឥណពន្ធ', type: 'number', rule: { number: true, nonNegative: true, decimalPlaces: 4 } }, { key: 'credit_amount', label: 'Credit', labelKm: 'ឥណទាន', type: 'number', rule: { number: true, nonNegative: true, decimalPlaces: 4 } }, { key: 'currency', label: 'Currency', labelKm: 'រូបិយប័ណ្ណ', type: 'select' },
    ] }],
    actions: [{ key: 'postJournal', label: 'Post', labelKm: 'ចុះបញ្ជី', icon: 'i-lucide-book-check', color: 'success' }],
    filters: [field('entryType', 'Entry Type', 'ប្រភេទទិនានុប្បវត្តិ', '', '', 'select', ['MANUAL', 'AUTOMATIC', 'REVERSAL']), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ['DRAFT', 'POSTED', 'REVERSED', 'VOIDED']), field('periodId', 'Accounting Period', 'រយៈពេលគណនេយ្យ')],
  }),
  module({
    path: '/finance/accounting-periods', title: 'Accounting Periods', titleKm: 'រយៈពេលគណនេយ្យ', singular: 'Accounting Period', singularKm: 'រយៈពេលគណនេយ្យ', description: 'Posting periods and closure control.', descriptionKm: 'រយៈពេលចុះគណនី និងការគ្រប់គ្រងការបិទ។',
    icon: 'i-lucide-calendar-range', group: 'finance', permission: 'finance.accounting_periods.view', collection: 'accountingPeriods', titleField: 'name', kind: 'standard', canCreate: false, readOnly: true,
    columns: [column('name', 'Period', 'រយៈពេល'), column('startDate', 'Start Date', 'ថ្ងៃចាប់ផ្តើម'), column('endDate', 'End Date', 'ថ្ងៃបញ្ចប់'), column('status', 'Status', 'ស្ថានភាព'), column('postingCount', 'Posting Count', 'ចំនួនការចុះបញ្ជី'), column('closedBy', 'Closed By', 'បិទដោយ'), column('closedAt', 'Closed At', 'ពេលបិទ')],
    fields: [field('year', 'Year', 'ឆ្នាំ', undefined, undefined, 'number'), field('month', 'Month', 'ខែ', undefined, undefined, 'number'), field('startDate', 'Start Date', 'ថ្ងៃចាប់ផ្តើម', undefined, undefined, 'date'), field('endDate', 'End Date', 'ថ្ងៃបញ្ចប់', undefined, undefined, 'date'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', PERIOD_STATUS), field('postingCount', 'Posting Count', 'ចំនួនការចុះបញ្ជី', 'Control', 'ការគ្រប់គ្រង', 'number', undefined, false, { computed: true }), field('closedBy', 'Closed By', 'បិទដោយ', 'Closure', 'ការបិទ', 'text', undefined, false, { computed: true }), field('closedAt', 'Closed At', 'ពេលបិទ', 'Closure', 'ការបិទ', 'datetime', undefined, false, { computed: true })],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ['OPEN', 'CLOSED', 'REOPENED'])],
  }),
  module({
    path: '/finance/posting-rules', title: 'Posting Rules', titleKm: 'ច្បាប់ចុះបញ្ជី', singular: 'Posting Rule', singularKm: 'ច្បាប់ចុះបញ្ជី', description: 'Which ledger accounts a document type posts through.', descriptionKm: 'គណនីក្បត់គ្រប់អ្វីដែលប្រភេទឯកសារនីមួយៗចុះបញ្ជីតាម.',
    icon: 'i-lucide-git-branch', group: 'finance', permission: 'finance.posting_rules.view', collection: 'postingRules', titleField: 'documentTypeLabel', kind: 'standard', canCreate: true,
    // Accounts are selected by code from the live chart of accounts; the backend
    // re-validates postability on write, so a stale list can never post an entry
    // to a header account.
    columns: [column('documentTypeLabel', 'Document Type', 'ប្រភេទឯកសារ'), column('feeType', 'Fee Type', 'ប្រភេទថ្លៃ'), column('debitAccount', 'Debit Account', 'គណនីឥណពន្ធ'), column('creditAccount', 'Credit Account', 'គណនីឥណទាន'), column('taxAccount', 'Tax Account', 'គណនីពន្ធ'), column('priority', 'Priority', 'អាទិភាព'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [
      field('documentType', 'Document Type', 'ប្រភេទឯកសារ', undefined, undefined, 'select', FINANCIAL_DOCUMENT_TYPES, true, { referenceFilter: postingRuleDocumentTypeFilter }),
      field('feeTypeId', 'Fee Type (optional)', 'ប្រភេទថ្លៃ (ស្រេចចិត្ត)', undefined, undefined, 'select'),
      field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
      field('debitAccount', 'Debit Account', 'គណនីឥណពន្ធ', 'Accounts', 'គណនី', 'select', undefined, true),
      field('creditAccount', 'Credit Account', 'គណនីឥណទាន', 'Accounts', 'គណនី', 'select', undefined, true),
      field('taxAccount', 'Tax Account', 'គណនីពន្ធ', 'Accounts', 'គណនី', 'select'),
      field('priority', 'Priority', 'អាទិភាព', 'Control', 'ការគ្រប់គ្រង', 'number', undefined, false, { rule: { integer: true, min: 0 } }),
      field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', FINANCIAL_DOCUMENT_STATUSES, true),
    ],
    filters: [
      field('documentType', 'Document Type', 'ប្រភេទឯកសារ', '', '', 'select', FINANCIAL_DOCUMENT_TYPES),
      field('status', 'Status', 'ស្ថានភាព', '', '', 'select', FINANCIAL_DOCUMENT_STATUSES),
    ],
  }),
]

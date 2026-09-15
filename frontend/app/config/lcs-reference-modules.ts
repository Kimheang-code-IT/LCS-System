import type { FreightField, FreightModule } from './freight-modules'
import { DOCUMENT_SEQUENCE_STATUSES, DOCUMENT_SEQUENCE_TYPES } from '~/utils/document-sequences'
import {
  ACCOUNT_TYPES,
  ACTIVE_STATUS,
  COUNTRIES,
  COMPONENT_INSTANCE_MODES,
  COMPONENT_INSTANCE_MODE_OVERRIDES,
  CURRENCIES,
  TIMEZONES,
  DIRECTIONS,
  PARTY_ROLES,
  PERIOD_STATUS,
  PLACE_CATEGORIES,
  TRANSPORT_TYPES,
} from './freight-options'

const YES_NO = ['Yes', 'No'] as const
const FINANCE_DOCUMENT_TYPES = [
  'CUSTOMER_INVOICE', 'SUPPLIER_BILL', 'CUSTOMER_RECEIPT', 'SUPPLIER_PAYMENT',
  'OTHER_INCOME', 'OTHER_EXPENSE', 'TRANSFER', 'ADJUSTMENT',
] as const

const field = (
  key: string,
  label: string,
  labelKm: string,
  section = 'General',
  sectionKm = 'ព័ត៌មានទូទៅ',
  type: FreightField['type'] = 'text',
  options?: readonly string[],
  required = false,
  extra: Partial<FreightField> = {},
): FreightField => ({ key, label, labelKm, section, sectionKm, type, options, required, ...extra })

const column = (key: string, label: string, labelKm: string): FreightField => ({ key, label, labelKm })
const module = (value: FreightModule): FreightModule => value

/** Metadata-driven pages required by the approved freight-forwarding scope. */
export const lcsReferenceModules: FreightModule[] = [
  module({
    path: '/master-data/business-parties', title: 'Business Parties', titleKm: 'ដៃគូអាជីវកម្ម', singular: 'Business Party', singularKm: 'ដៃគូអាជីវកម្ម',
    description: 'One shared record for customer, supplier, carrier, broker and transport-operator roles.', descriptionKm: 'កំណត់ត្រារួមសម្រាប់តួនាទីដៃគូអាជីវកម្ម។',
    icon: 'i-lucide-handshake', group: 'master', permission: 'master.reference.view', collection: 'businessParties', titleField: 'legalName', kind: 'standard', canCreate: true,
    columns: [
      column('partyCode', 'Party Code', 'លេខកូដ'), column('legalName', 'Legal Name', 'ឈ្មោះផ្លូវការ'), column('displayName', 'Display Name', 'ឈ្មោះបង្ហាញ'),
      column('roles', 'Roles', 'តួនាទី'), column('taxIdentifier', 'VAT / TIN', 'អាករ / TIN'), column('contactPerson', 'Contact Person', 'អ្នកទំនាក់ទំនង'),
      column('phone', 'Phone', 'ទូរស័ព្ទ'), column('email', 'Email', 'អ៊ីមែល'), column('country', 'Country', 'ប្រទេស'), column('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      field('partyCode', 'Party Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('legalName', 'Legal Name', 'ឈ្មោះផ្លូវការ', undefined, undefined, 'text', undefined, true),
      field('displayName', 'Display Name', 'ឈ្មោះបង្ហាញ'), field('taxIdentifier', 'VAT / TIN', 'អាករ / TIN'), field('contactPerson', 'Contact Person', 'អ្នកទំនាក់ទំនង', 'Contact', 'ទំនាក់ទំនង'),
      field('phone', 'Phone', 'ទូរស័ព្ទ', 'Contact', 'ទំនាក់ទំនង'), field('email', 'Email', 'អ៊ីមែល', 'Contact', 'ទំនាក់ទំនង'),
      field('address', 'Address', 'អាសយដ្ឋាន', 'Address', 'អាសយដ្ឋាន', 'textarea', undefined, false, { colSpan: 2 }), field('country', 'Country', 'ប្រទេស', 'Address', 'អាសយដ្ឋាន', 'select', COUNTRIES),
      field('roles', 'Party Roles', 'តួនាទីដៃគូ', 'Roles', 'តួនាទី', 'multiselect', PARTY_ROLES, true), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('roles', 'Role', 'តួនាទី', '', '', 'select', PARTY_ROLES), field('country', 'Country', 'ប្រទេស', '', '', 'select', COUNTRIES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/places', title: 'Places', titleKm: 'ទីកន្លែង', singular: 'Place', singularKm: 'ទីកន្លែង', description: 'Ports, checkpoints, SEZs, warehouses, factories and destinations.', descriptionKm: 'កំពង់ផែ ច្រកព្រំដែន តំបន់សេដ្ឋកិច្ច ឃ្លាំង និងគោលដៅ។',
    icon: 'i-lucide-map-pin', group: 'master', permission: 'master.reference.view', collection: 'places', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('category', 'Category', 'ប្រភេទ'), column('parentPlace', 'Parent Place', 'ទីកន្លែងមេ'), column('country', 'Country', 'ប្រទេស'), column('address', 'Address', 'អាសយដ្ឋាន'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [
      field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
      field('category', 'Place Category', 'ប្រភេទទីកន្លែង', 'Classification', 'ចំណាត់ថ្នាក់', 'select', PLACE_CATEGORIES), field('parentPlace', 'Parent Place', 'ទីកន្លែងមេ', 'Classification', 'ចំណាត់ថ្នាក់'),
      field('address', 'Address', 'អាសយដ្ឋាន', 'Location', 'ទីតាំង', 'textarea', undefined, false, { colSpan: 2 }), field('country', 'Country', 'ប្រទេស', 'Location', 'ទីតាំង', 'select', COUNTRIES),
      field('latitude', 'Latitude', 'រយៈទទឹង', 'Coordinates', 'កូអរដោនេ', 'number'), field('longitude', 'Longitude', 'រយៈបណ្តោយ', 'Coordinates', 'កូអរដោនេ', 'number'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('category', 'Category', 'ប្រភេទ', '', '', 'select', PLACE_CATEGORIES), field('country', 'Country', 'ប្រទេស', '', '', 'select', COUNTRIES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/trade-directions', title: 'Trade Directions', titleKm: 'ទិសដៅពាណិជ្ជកម្ម', singular: 'Trade Direction', singularKm: 'ទិសដៅពាណិជ្ជកម្ម', description: 'Import, export, transit and re-export service directions.', descriptionKm: 'ទិសដៅនាំចូល នាំចេញ ឆ្លងកាត់ និងនាំចេញវិញ។',
    icon: 'i-lucide-route', group: 'master', permission: 'master.reference.view', collection: 'tradeDirections', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'select', DIRECTIONS, true), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/container-types', title: 'Container Types', titleKm: 'ប្រភេទកុងតឺន័រ', singular: 'Container Type', singularKm: 'ប្រភេទកុងតឺន័រ', description: 'Physical container ISO classifications and dimensions.', descriptionKm: 'ចំណាត់ថ្នាក់ និងទំហំកុងតឺន័រ ISO។',
    icon: 'i-lucide-container', group: 'master', permission: 'master.reference.view', collection: 'containerTypes', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('size', 'Size', 'ទំហំ'), column('kind', 'Kind', 'ប្រភេទ'), column('isoCode', 'ISO Code', 'លេខកូដ ISO'), column('lengthFeet', 'Length', 'ប្រវែង'), column('maxGrossWeightKg', 'Max Gross Weight', 'ទម្ងន់អតិបរមា'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [
      field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true), field('size', 'Container Size', 'ទំហំកុងតឺន័រ'), field('kind', 'Container Kind', 'ប្រភេទកុងតឺន័រ'), field('isoCode', 'ISO Code', 'លេខកូដ ISO'),
      field('lengthFeet', 'Length Feet', 'ប្រវែងហ្វីត', 'Dimensions', 'វិមាត្រ', 'number'), field('widthMeters', 'Width', 'ទទឹង', 'Dimensions', 'វិមាត្រ', 'number'), field('heightMeters', 'Height', 'កម្ពស់', 'Dimensions', 'វិមាត្រ', 'number'), field('maxGrossWeightKg', 'Max Gross Weight', 'ទម្ងន់សរុបអតិបរមា', 'Dimensions', 'វិមាត្រ', 'number'),
      field('description', 'Description', 'បរិយាយ', 'Details', 'ព័ត៌មានលម្អិត', 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/transport-types', title: 'Transport Types', titleKm: 'ប្រភេទដឹកជញ្ជូន', singular: 'Transport Type', singularKm: 'ប្រភេទដឹកជញ្ជូន', description: 'Road, sea, air, rail and multimodal transport types.', descriptionKm: 'ដឹកជញ្ជូនផ្លូវគោក សមុទ្រ អាកាស ផ្លូវដែក និងចម្រុះ។',
    icon: 'i-lucide-truck', group: 'master', permission: 'master.reference.view', collection: 'transportTypes', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'select', TRANSPORT_TYPES, true), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/transport-assets', title: 'Transport Assets', titleKm: 'ទ្រព្យដឹកជញ្ជូន', singular: 'Transport Asset', singularKm: 'ទ្រព្យដឹកជញ្ជូន', description: 'Vehicles, vessels and other transport identities.', descriptionKm: 'យានយន្ត នាវា និងអត្តសញ្ញាណដឹកជញ្ជូន។',
    icon: 'i-lucide-truck-front', group: 'master', permission: 'master.reference.view', collection: 'transportAssets', titleField: 'identity', kind: 'standard', canCreate: true,
    columns: [column('assetCode', 'Asset Code', 'លេខកូដទ្រព្យ'), column('transportType', 'Transport Type', 'ប្រភេទដឹកជញ្ជូន'), column('identity', 'Identity', 'អត្តសញ្ញាណ'), column('identityType', 'Identity Type', 'ប្រភេទអត្តសញ្ញាណ'), column('ownerParty', 'Owner', 'ម្ចាស់'), column('operatorParty', 'Operator', 'ប្រតិបត្តិករ'), column('registrationCountry', 'Registration Country', 'ប្រទេសចុះបញ្ជី'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('assetCode', 'Asset Code', 'លេខកូដទ្រព្យ', undefined, undefined, 'text', undefined, true), field('transportType', 'Transport Type', 'ប្រភេទដឹកជញ្ជូន', undefined, undefined, 'select', TRANSPORT_TYPES), field('identity', 'Identity', 'អត្តសញ្ញាណ', undefined, undefined, 'text', undefined, true), field('identityType', 'Identity Type', 'ប្រភេទអត្តសញ្ញាណ'), field('registrationCountry', 'Registration Country', 'ប្រទេសចុះបញ្ជី', 'Registration', 'ការចុះបញ្ជី', 'select', COUNTRIES), field('ownerParty', 'Owner Party', 'ភាគីម្ចាស់', 'Ownership', 'កម្មសិទ្ធិ'), field('operatorParty', 'Operator Party', 'ភាគីប្រតិបត្តិករ', 'Ownership', 'កម្មសិទ្ធិ'), field('description', 'Description', 'បរិយាយ', 'Details', 'ព័ត៌មានលម្អិត', 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('transportType', 'Transport Type', 'ប្រភេទដឹកជញ្ជូន', '', '', 'select', TRANSPORT_TYPES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/master-data/fee-types', title: 'Fee Types', titleKm: 'ប្រភេទថ្លៃ', singular: 'Fee Type', singularKm: 'ប្រភេទថ្លៃ', description: 'Reusable operational and financial fee definitions.', descriptionKm: 'និយមន័យថ្លៃប្រតិបត្តិការ និងហិរញ្ញវត្ថុដែលប្រើឡើងវិញ។',
    icon: 'i-lucide-receipt-text', group: 'master', permission: 'master.reference.view', collection: 'feeTypes', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('description', 'Description', 'បរិយាយ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),

  module({
    path: '/configuration/component-groups', title: 'Component Groups', titleKm: 'ក្រុមសមាសភាគ', singular: 'Component Group', singularKm: 'ក្រុមសមាសភាគ', description: 'Display grouping for dynamic service-order components.', descriptionKm: 'ក្រុមបង្ហាញសម្រាប់សមាសភាគបញ្ជាសេវាកម្ម។',
    icon: 'i-lucide-folders', group: 'configuration', permission: 'configuration.manage', collection: 'componentGroups', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('description', 'Description', 'បរិយាយ'), column('displayOrder', 'Display Order', 'លំដាប់បង្ហាញ'), column('showOnJobWorkspace', 'Job Tab', 'ផ្ទាំងការងារ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('displayOrder', 'Display Order', 'លំដាប់បង្ហាញ', 'Display', 'ការបង្ហាញ', 'number'), field('showOnJobWorkspace', 'Show on Service Order', 'បង្ហាញលើបញ្ជាសេវាកម្ម', 'Display', 'ការបង្ហាញ', 'checkbox', YES_NO), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/configuration/component-templates', title: 'Component Templates', titleKm: 'គំរូសមាសភាគ', singular: 'Component Template', singularKm: 'គំរូសមាសភាគ', description: 'Versioned dynamic service-order component definitions.', descriptionKm: 'និយមន័យសមាសភាគការងារដែលមានកំណែ។',
    icon: 'i-lucide-blocks', group: 'configuration', permission: 'configuration.manage', collection: 'componentTemplates', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('code', 'Code', 'លេខកូដ'), column('name', 'Name', 'ឈ្មោះ'), column('group', 'Group', 'ក្រុម'), column('instanceMode', 'Instance Mode', 'របៀបកំណត់ត្រា'), column('version', 'Version', 'កំណែ'), column('description', 'Description', 'បរិយាយ'), column('attributeCount', 'Attribute Count', 'ចំនួនលក្ខណៈ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('code', 'Code', 'លេខកូដ', undefined, undefined, 'text', undefined, true), field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true), field('description', 'Description', 'បរិយាយ', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }), field('group', 'Component Group', 'ក្រុមសមាសភាគ', 'Classification', 'ចំណាត់ថ្នាក់', 'text', undefined, true), field('instanceMode', 'Instance Mode', 'របៀបកំណត់ត្រា', 'Behavior', 'ឥរិយាបថ', 'select', COMPONENT_INSTANCE_MODES, true), field('minimumInstances', 'Minimum Instances', 'ចំនួនអប្បបរមា', 'Behavior', 'ឥរិយាបថ', 'number'), field('maximumInstances', 'Maximum Instances', 'ចំនួនអតិបរមា', 'Behavior', 'ឥរិយាបថ', 'number'), field('version', 'Version', 'កំណែ', 'Version', 'កំណែ', 'text', undefined, true), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    tables: [{
      key: 'attributes', title: 'Template Attributes', titleKm: 'លក្ខណៈគំរូ', addLabel: 'Add attribute',
      columns: [
        { key: 'code', label: 'Code', labelKm: 'លេខកូដ', required: true }, { key: 'label', label: 'Label', labelKm: 'ស្លាក', required: true }, { key: 'dataType', label: 'Data Type', labelKm: 'ប្រភេទទិន្នន័យ', type: 'select', options: ['Text', 'Number', 'Date', 'DateTime', 'Boolean', 'Reference', 'JSON', 'Table'], required: true },
        { key: 'inputType', label: 'Input Type', labelKm: 'ប្រភេទបញ្ចូល' }, { key: 'tableColumns', label: 'Table Columns', labelKm: 'ជួរឈរ', type: 'table-columns' }, { key: 'required', label: 'Required', labelKm: 'តម្រូវ', type: 'checkbox', options: YES_NO }, { key: 'repeatable', label: 'Multiple Values', labelKm: 'តម្លៃច្រើន', type: 'checkbox', options: YES_NO }, { key: 'showInSummary', label: 'Show in Summary', labelKm: 'បង្ហាញក្នុងសេចក្តីសង្ខេប', type: 'checkbox', options: YES_NO },
        { key: 'referenceType', label: 'Reference Type', labelKm: 'ប្រភេទយោង' }, { key: 'displayOrder', label: 'Display Order', labelKm: 'លំដាប់បង្ហាញ', type: 'number' }, { key: 'validationRules', label: 'Validation Rules', labelKm: 'ច្បាប់សុពលភាព', type: 'textarea' }, { key: 'status', label: 'Status', labelKm: 'ស្ថានភាព', type: 'select', options: ACTIVE_STATUS },
      ],
    }],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/configuration/trade-direction-components', title: 'Trade Direction Components', titleKm: 'សមាសភាគតាមទិសដៅ', singular: 'Direction Component', singularKm: 'សមាសភាគទិសដៅ', description: 'Controls which versioned components appear for each trade direction.', descriptionKm: 'គ្រប់គ្រងសមាសភាគដែលបង្ហាញតាមទិសដៅពាណិជ្ជកម្ម។',
    icon: 'i-lucide-workflow', group: 'configuration', permission: 'configuration.manage', collection: 'tradeDirectionComponents', titleField: 'componentTemplate', kind: 'standard', canCreate: true,
    columns: [column('tradeDirection', 'Trade Direction', 'ទិសដៅពាណិជ្ជកម្ម'), column('componentGroup', 'Component Group', 'ក្រុមសមាសភាគ'), column('componentTemplate', 'Component Template', 'គំរូសមាសភាគ'), column('templateVersion', 'Template Version', 'កំណែគំរូ'), column('required', 'Required', 'តម្រូវ'), column('instanceModeOverride', 'Instance Mode Override', 'ប្ដូររបៀបកំណត់ត្រា'), column('displayOrder', 'Display Order', 'លំដាប់បង្ហាញ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('tradeDirection', 'Trade Direction', 'ទិសដៅពាណិជ្ជកម្ម', undefined, undefined, 'select', DIRECTIONS, true), field('componentGroup', 'Component Group', 'ក្រុមសមាសភាគ', undefined, undefined, 'text', undefined, true), field('componentTemplate', 'Component Template', 'គំរូសមាសភាគ', undefined, undefined, 'text', undefined, true), field('templateVersion', 'Template Version', 'កំណែគំរូ', 'Version', 'កំណែ', 'text', undefined, false, { computed: true }), field('required', 'Required', 'តម្រូវ', 'Rules', 'ច្បាប់', 'checkbox', YES_NO), field('instanceModeOverride', 'Instance Mode Override', 'ប្ដូររបៀបកំណត់ត្រា', 'Rules', 'ច្បាប់', 'select', COMPONENT_INSTANCE_MODE_OVERRIDES), field('displayOrder', 'Display Order', 'លំដាប់បង្ហាញ', 'Display', 'ការបង្ហាញ', 'number'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('tradeDirection', 'Trade Direction', 'ទិសដៅពាណិជ្ជកម្ម', '', '', 'select', DIRECTIONS), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/configuration/posting-rules', title: 'Posting Rules', titleKm: 'ច្បាប់ចុះបញ្ជី', singular: 'Posting Rule', singularKm: 'ច្បាប់ចុះបញ្ជី', description: 'Resolve debit, credit and tax accounts by document and fee type.', descriptionKm: 'កំណត់គណនីឥណពន្ធ ឥណទាន និងពន្ធ។',
    icon: 'i-lucide-scale', group: 'configuration', permission: 'configuration.manage', collection: 'postingRules', titleField: 'documentType', kind: 'standard', canCreate: true,
    columns: [column('documentType', 'Document Type', 'ប្រភេទឯកសារ'), column('feeType', 'Fee Type', 'ប្រភេទថ្លៃ'), column('debitAccount', 'Debit Account', 'គណនីឥណពន្ធ'), column('creditAccount', 'Credit Account', 'គណនីឥណទាន'), column('taxAccount', 'Tax Account', 'គណនីពន្ធ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('documentType', 'Document Type', 'ប្រភេទឯកសារ', undefined, undefined, 'select', FINANCE_DOCUMENT_TYPES, true), field('feeType', 'Fee Type', 'ប្រភេទថ្លៃ'), field('debitAccount', 'Debit Account', 'គណនីឥណពន្ធ', 'Accounts', 'គណនី', 'text', undefined, true), field('creditAccount', 'Credit Account', 'គណនីឥណទាន', 'Accounts', 'គណនី', 'text', undefined, true), field('taxAccount', 'Tax Account', 'គណនីពន្ធ', 'Accounts', 'គណនី'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('documentType', 'Document Type', 'ប្រភេទឯកសារ', '', '', 'select', FINANCE_DOCUMENT_TYPES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),

  module({
    path: '/administration/organizations', title: 'Organizations', titleKm: 'អង្គភាព', singular: 'Organization', singularKm: 'អង្គភាព', description: 'Legal organization, localization and default accounting context.', descriptionKm: 'អង្គភាពផ្លូវការ ភាសា និងបរិបទគណនេយ្យលំនាំដើម។',
    icon: 'i-lucide-landmark', group: 'admin', permission: 'admin.organization.view', collection: 'organizations', titleField: 'displayName', kind: 'standard', canCreate: true,
    columns: [column('organizationCode', 'Organization Code', 'លេខកូដអង្គភាព'), column('legalName', 'Legal Name', 'ឈ្មោះផ្លូវការ'), column('displayName', 'Display Name', 'ឈ្មោះបង្ហាញ'), column('taxIdentifier', 'Tax Identifier', 'លេខសម្គាល់ពន្ធ'), column('country', 'Country', 'ប្រទេស'), column('defaultCurrency', 'Default Currency', 'រូបិយប័ណ្ណលំនាំដើម'), column('timezone', 'Timezone', 'តំបន់ពេលវេលា'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [
      field('organizationCode', 'Organization Code', 'លេខកូដអង្គភាព', undefined, undefined, 'text', undefined, true),
      field('legalName', 'Legal Name', 'ឈ្មោះផ្លូវការ', undefined, undefined, 'text', undefined, true),
      field('displayName', 'Display Name', 'ឈ្មោះបង្ហាញ'),
      field('taxIdentifier', 'Tax Identifier', 'លេខសម្គាល់ពន្ធ'),
      field('country', 'Country', 'ប្រទេស', undefined, undefined, 'select', COUNTRIES),
      field('defaultCurrency', 'Default Currency', 'រូបិយប័ណ្ណលំនាំដើម', undefined, undefined, 'select', CURRENCIES),
      field('timezone', 'Timezone', 'តំបន់ពេលវេលា', undefined, undefined, 'select', TIMEZONES),
      field('status', 'Status', 'ស្ថានភាព', undefined, undefined, 'select', ACTIVE_STATUS),
    ],
    filters: [field('country', 'Country', 'ប្រទេស', '', '', 'select', COUNTRIES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/administration/branches', title: 'Branches', titleKm: 'សាខា', singular: 'Branch', singularKm: 'សាខា', description: 'Branch ownership, location and contact context.', descriptionKm: 'កម្មសិទ្ធិសាខា ទីតាំង និងព័ត៌មានទំនាក់ទំនង។',
    icon: 'i-lucide-git-branch', group: 'admin', permission: 'admin.organization.view', collection: 'branches', titleField: 'name', kind: 'standard', canCreate: true,
    columns: [column('branchCode', 'Branch Code', 'លេខកូដសាខា'), column('name', 'Name', 'ឈ្មោះ'), column('organizationName', 'Organization', 'អង្គភាព'), column('place', 'Place', 'ទីកន្លែង'), column('phone', 'Phone', 'ទូរស័ព្ទ'), column('email', 'Email', 'អ៊ីមែល'), column('headOffice', 'Head Office', 'ការិយាល័យកណ្តាល'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [
      field('branchCode', 'Branch Code', 'លេខកូដសាខា', undefined, undefined, 'text', undefined, true),
      field('headOffice', 'Head Office', 'ការិយាល័យកណ្តាល', undefined, undefined, 'checkbox', YES_NO),
      field('status', 'Status', 'ស្ថានភាព', undefined, undefined, 'select', ACTIVE_STATUS),
      field('name', 'Name', 'ឈ្មោះ', undefined, undefined, 'text', undefined, true),
      field('place', 'Place', 'ទីកន្លែង'),
      field('phone', 'Phone', 'ទូរស័ព្ទ'),
      field('email', 'Email', 'អ៊ីមែល'),
      field('address', 'Address', 'អាសយដ្ឋាន', undefined, undefined, 'textarea', undefined, false, { colSpan: 2 }),
    ],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/administration/document-sequences', title: 'Document Sequences', titleKm: 'លំដាប់លេខឯកសារ', singular: 'Document Sequence', singularKm: 'លំដាប់ឯកសារ', description: 'Manage organization-scoped automatic document numbering by document type and year.', descriptionKm: 'គ្រប់គ្រងលេខឯកសារស្វ័យប្រវត្តិតាមអង្គភាព ប្រភេទឯកសារ និងឆ្នាំ។',
    icon: 'i-lucide-list-ordered', group: 'admin', permission: 'configuration.manage', collection: 'documentSequences', titleField: 'documentType', kind: 'standard', canCreate: true,
    columns: [
      column('documentType', 'Document Type', 'ប្រភេទឯកសារ'), column('year', 'Year', 'ឆ្នាំ'), column('prefix', 'Prefix', 'បុព្វបទ'),
      column('lastValue', 'Last Value', 'តម្លៃចុងក្រោយ'), column('paddingLength', 'Padding Length', 'ប្រវែងលេខ'), column('nextNumberPreview', 'Next Number Preview', 'លេខបន្ទាប់'), column('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      field('organizationName', 'Organization', 'អង្គភាព', undefined, undefined, 'text', undefined, false, { computed: true }),
      field('documentType', 'Document Type', 'ប្រភេទឯកសារ', undefined, undefined, 'select', DOCUMENT_SEQUENCE_TYPES, true),
      field('year', 'Year', 'ឆ្នាំ', undefined, undefined, 'number', undefined, true),
      field('prefix', 'Prefix', 'បុព្វបទ', undefined, undefined, 'text', undefined, true),
      field('lastValue', 'Starting / Last Value', 'តម្លៃចាប់ផ្តើម / ចុងក្រោយ', undefined, undefined, 'number', undefined, true),
      field('paddingLength', 'Padding Length', 'ប្រវែងលេខ', undefined, undefined, 'number', undefined, true),
      field('nextNumberPreview', 'Next Number Preview', 'លេខបន្ទាប់', undefined, undefined, 'text', undefined, false, { computed: true }),
      field('status', 'Status', 'ស្ថានភាព', undefined, undefined, 'select', DOCUMENT_SEQUENCE_STATUSES, true),
    ],
    filters: [
      field('documentType', 'Document Type', 'ប្រភេទឯកសារ', '', '', 'select', DOCUMENT_SEQUENCE_TYPES),
      field('year', 'Year', 'ឆ្នាំ', '', '', 'select'),
      field('status', 'Status', 'ស្ថានភាព', '', '', 'select', DOCUMENT_SEQUENCE_STATUSES),
    ],
  }),

  module({
    path: '/finance/chart-of-accounts', title: 'Chart of Accounts', titleKm: 'បញ្ជីគណនី', singular: 'Ledger Account', singularKm: 'គណនី', description: 'Organization-scoped double-entry ledger accounts.', descriptionKm: 'គណនីសៀវភៅធំតាមអង្គភាពសម្រាប់គណនេយ្យទ្វេភាគ។',
    icon: 'i-lucide-list-tree', group: 'finance', permission: 'finance.accounting.view', collection: 'chartOfAccounts', titleField: 'accountName', kind: 'standard', canCreate: true,
    columns: [column('accountCode', 'Account Code', 'លេខកូដគណនី'), column('accountName', 'Account Name', 'ឈ្មោះគណនី'), column('accountType', 'Account Type', 'ប្រភេទគណនី'), column('parentCode', 'Parent Account', 'គណនីមេ'), column('normalBalance', 'Normal Balance', 'សមតុល្យធម្មតា'), column('postable', 'Postable', 'អាចចុះបញ្ជី'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('accountCode', 'Account Code', 'លេខកូដគណនី', undefined, undefined, 'text', undefined, true), field('accountName', 'Account Name', 'ឈ្មោះគណនី', undefined, undefined, 'text', undefined, true), field('accountType', 'Account Type', 'ប្រភេទគណនី', undefined, undefined, 'select', ACCOUNT_TYPES), field('parentCode', 'Parent Account', 'គណនីមេ', 'Structure', 'រចនាសម្ព័ន្ធ'), field('normalBalance', 'Normal Balance', 'សមតុល្យធម្មតា', 'Structure', 'រចនាសម្ព័ន្ធ', 'select', ['Debit', 'Credit']), field('postable', 'Is Postable', 'អាចចុះបញ្ជី', 'Control', 'ការគ្រប់គ្រង', 'checkbox', YES_NO), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('accountType', 'Account Type', 'ប្រភេទគណនី', '', '', 'select', ACCOUNT_TYPES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/finance/financial-accounts', title: 'Financial Accounts', titleKm: 'គណនីហិរញ្ញវត្ថុ', singular: 'Financial Account', singularKm: 'គណនីហិរញ្ញវត្ថុ', description: 'Cash, bank and settlement accounts linked to the ledger.', descriptionKm: 'គណនីសាច់ប្រាក់ ធនាគារ និងទូទាត់ភ្ជាប់សៀវភៅធំ។',
    icon: 'i-lucide-wallet-cards', group: 'finance', permission: 'finance.accounting.view', collection: 'financialAccounts', titleField: 'accountName', kind: 'standard', canCreate: true,
    columns: [column('accountName', 'Account Name', 'ឈ្មោះគណនី'), column('ledgerCode', 'Ledger Account', 'គណនីសៀវភៅ'), column('accountType', 'Type', 'ប្រភេទ'), column('currency', 'Currency', 'រូបិយប័ណ្ណ'), column('bankName', 'Bank', 'ធនាគារ'), column('accountNumberMasked', 'Account No.', 'លេខគណនី'), column('balance', 'Balance', 'សមតុល្យ'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('ledgerCode', 'Ledger Account', 'គណនីសៀវភៅ', undefined, undefined, 'text', undefined, true), field('accountName', 'Account Name', 'ឈ្មោះគណនី', undefined, undefined, 'text', undefined, true), field('accountType', 'Account Type', 'ប្រភេទគណនី', undefined, undefined, 'select', ['Bank', 'Cash']), field('currency', 'Currency', 'រូបិយប័ណ្ណ', undefined, undefined, 'select', CURRENCIES), field('bankName', 'Bank Name', 'ឈ្មោះធនាគារ', 'Bank Details', 'ព័ត៌មានធនាគារ'), field('accountNumberMasked', 'Masked Account Number', 'លេខគណនីបិទបាំង', 'Bank Details', 'ព័ត៌មានធនាគារ'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ACTIVE_STATUS)],
    filters: [field('accountType', 'Account Type', 'ប្រភេទគណនី', '', '', 'select', ['Bank', 'Cash']), field('currency', 'Currency', 'រូបិយប័ណ្ណ', '', '', 'select', CURRENCIES), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS)],
  }),
  module({
    path: '/finance/journals', title: 'Journal Entries', titleKm: 'បញ្ជីទិនានុប្បវត្តិ', singular: 'Journal Entry', singularKm: 'ទិនានុប្បវត្តិ', description: 'Balanced debit and credit entries with source traceability.', descriptionKm: 'ឥណពន្ធ និងឥណទានមានតុល្យភាព និងប្រភពតាមដាន។',
    icon: 'i-lucide-book-check', group: 'finance', permission: 'finance.accounting.view', collection: 'journals', titleField: 'entryNo', kind: 'standard', canCreate: true,
    columns: [column('entryNo', 'Entry No.', 'លេខទិនានុប្បវត្តិ'), column('postingDate', 'Posting Date', 'កាលបរិច្ឆេទចុះបញ្ជី'), column('sourceDocumentNo', 'Source', 'ប្រភព'), column('branchName', 'Branch', 'សាខា'), column('description', 'Description', 'បរិយាយ'), column('debitTotal', 'Debit', 'ឥណពន្ធ'), column('creditTotal', 'Credit', 'ឥណទាន'), column('status', 'Status', 'ស្ថានភាព')],
    fields: [field('entryNo', 'Entry No.', 'លេខទិនានុប្បវត្តិ', undefined, undefined, 'text', undefined, true, { computed: true }), field('entryType', 'Entry Type', 'ប្រភេទទិនានុប្បវត្តិ', undefined, undefined, 'select', ['MANUAL', 'AUTOMATIC', 'REVERSAL']), field('entryDate', 'Entry Date', 'កាលបរិច្ឆេទទិនានុប្បវត្តិ', undefined, undefined, 'date'), field('postingDate', 'Posting Date', 'កាលបរិច្ឆេទចុះបញ្ជី', undefined, undefined, 'date'), field('periodId', 'Accounting Period', 'រយៈពេលគណនេយ្យ'), field('branchName', 'Branch', 'សាខា'), field('sourceDocumentNo', 'Source Document', 'ឯកសារប្រភព'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', ['DRAFT', 'POSTED', 'REVERSED', 'VOIDED']), field('description', 'Description', 'បរិយាយ', 'Details', 'ព័ត៌មានលម្អិត', 'textarea', undefined, false, { colSpan: 2 }), field('debitTotal', 'Total Debit', 'ឥណពន្ធសរុប', 'Balance', 'តុល្យភាព', 'number', undefined, false, { computed: true }), field('creditTotal', 'Total Credit', 'ឥណទានសរុប', 'Balance', 'តុល្យភាព', 'number', undefined, false, { computed: true }), field('balanceDifference', 'Balance Difference', 'ភាពខុសគ្នា', 'Balance', 'តុល្យភាព', 'number', undefined, false, { computed: true })],
    tables: [{ key: 'lines', title: 'Journal Lines', titleKm: 'ជួរទិនានុប្បវត្តិ', addLabel: 'Add journal line', columns: [
      { key: 'account_code', label: 'Account', labelKm: 'គណនី', required: true }, { key: 'party', label: 'Party', labelKm: 'ដៃគូ' }, { key: 'serviceOrder', label: 'Service Job', labelKm: 'បញ្ជាសេវាកម្ម' }, { key: 'description', label: 'Description', labelKm: 'បរិយាយ' }, { key: 'debit_amount', label: 'Debit', labelKm: 'ឥណពន្ធ', type: 'number' }, { key: 'credit_amount', label: 'Credit', labelKm: 'ឥណទាន', type: 'number' }, { key: 'currency', label: 'Currency', labelKm: 'រូបិយប័ណ្ណ', type: 'select', options: CURRENCIES },
    ] }],
    actions: [{ key: 'postJournal', label: 'Post', labelKm: 'ចុះបញ្ជី', icon: 'i-lucide-book-check', color: 'success' }],
    filters: [field('entryType', 'Entry Type', 'ប្រភេទទិនានុប្បវត្តិ', '', '', 'select', ['MANUAL', 'AUTOMATIC', 'REVERSAL']), field('branchName', 'Branch', 'សាខា'), field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ['DRAFT', 'POSTED', 'REVERSED', 'VOIDED']), field('periodId', 'Accounting Period', 'រយៈពេលគណនេយ្យ')],
  }),
  module({
    path: '/finance/accounting-periods', title: 'Accounting Periods', titleKm: 'រយៈពេលគណនេយ្យ', singular: 'Accounting Period', singularKm: 'រយៈពេលគណនេយ្យ', description: 'Posting periods and closure control.', descriptionKm: 'រយៈពេលចុះគណនី និងការគ្រប់គ្រងការបិទ។',
    icon: 'i-lucide-calendar-range', group: 'finance', permission: 'finance.accounting.view', collection: 'accountingPeriods', titleField: 'name', kind: 'standard', canCreate: false, readOnly: true,
    columns: [column('name', 'Period', 'រយៈពេល'), column('startDate', 'Start Date', 'ថ្ងៃចាប់ផ្តើម'), column('endDate', 'End Date', 'ថ្ងៃបញ្ចប់'), column('status', 'Status', 'ស្ថានភាព'), column('postingCount', 'Posting Count', 'ចំនួនការចុះបញ្ជី'), column('closedBy', 'Closed By', 'បិទដោយ'), column('closedAt', 'Closed At', 'ពេលបិទ')],
    fields: [field('year', 'Year', 'ឆ្នាំ', undefined, undefined, 'number'), field('month', 'Month', 'ខែ', undefined, undefined, 'number'), field('startDate', 'Start Date', 'ថ្ងៃចាប់ផ្តើម', undefined, undefined, 'date'), field('endDate', 'End Date', 'ថ្ងៃបញ្ចប់', undefined, undefined, 'date'), field('status', 'Status', 'ស្ថានភាព', 'Control', 'ការគ្រប់គ្រង', 'select', PERIOD_STATUS), field('postingCount', 'Posting Count', 'ចំនួនការចុះបញ្ជី', 'Control', 'ការគ្រប់គ្រង', 'number', undefined, false, { computed: true }), field('closedBy', 'Closed By', 'បិទដោយ', 'Closure', 'ការបិទ', 'text', undefined, false, { computed: true }), field('closedAt', 'Closed At', 'ពេលបិទ', 'Closure', 'ការបិទ', 'datetime', undefined, false, { computed: true })],
    filters: [field('status', 'Status', 'ស្ថានភាព', '', '', 'select', ['OPEN', 'CLOSED', 'REOPENED'])],
  }),
]

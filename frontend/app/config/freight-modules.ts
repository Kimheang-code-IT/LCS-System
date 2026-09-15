import type { DocumentTabSchema } from '~/types/docetra/common'
import {
  ACTIVE_STATUS,
  CHARGE_CATEGORIES,
  CONTAINER_TYPES,
  COUNTRIES,
  CURRENCIES,
  CUSTOMS_STATUS,
  DEBIT_CHARGE_TYPES,
  DEBIT_NOTE_STATUS,
  DELIVERY_STATUS,
  DIRECTIONS,
  DOCUMENT_STATUS,
  DOCUMENT_TYPES,
  EQUIPMENT_CATEGORIES,
  JOB_STATUS,
  JOB_WORKFLOW_STATUS,
  LOCATION_TYPES,
  PAYMENT_METHODS,
  PAYMENT_STATUS,
  PLACE_ROLES,
  QUOTATION_CONDITIONS,
  QUOTATION_STATUS,
  SERVICE_CHARGE_STATUS,
  SERVICE_TYPES,
  SHIPMENT_STATUS,
  TRANSPORT_BY,
  TRANSPORT_MODES,
  TRUCK_TYPES,
} from './freight-options'
import { lcsReferenceModules } from './lcs-reference-modules'

export type FreightFieldType = 'text' | 'date' | 'datetime' | 'number' | 'select' | 'multiselect' | 'textarea' | 'file' | 'password' | 'checkbox'

export type FreightSelectOption = string | { label: string, value: string }

export type FreightField = {
  key: string
  label: string
  labelKm?: string
  section?: string
  sectionKm?: string
  type?: FreightFieldType
  options?: readonly FreightSelectOption[] | FreightSelectOption[]
  required?: boolean
  colSpan?: 1 | 2
  computed?: boolean
  helpKey?: string
  help?: string
  /** Prefer this i18n key for list/filter labels when collection-level field copy differs. */
  labelKey?: string
}

export type FreightLineColumn = {
  key: string
  label: string
  labelKm?: string
  type?: 'text' | 'number' | 'select' | 'textarea' | 'checkbox' | 'date' | 'datetime' | 'table-columns'
  options?: readonly string[] | string[]
  /** Select labels when they differ from stored values (e.g. container requirement id). */
  optionItems?: Array<{ label: string, value: string }>
  width?: string
  computed?: boolean
  required?: boolean
  labelKey?: string
  /** Small editable money fields rendered inside the same cell under the main value. */
  inlineFields?: Array<{ key: string, label: string, labelKm?: string, labelKey?: string }>
}

export type FreightTable = {
  key: string
  title: string
  titleKm?: string
  columns: FreightLineColumn[]
  addLabel?: string
  addLabelKey?: string
  presets?: Array<Record<string, unknown>>
  lockedPresets?: boolean
  /** Native file picker + File name / By / Created columns. */
  kind?: 'files'
}

export const FILE_ATTACHMENT_COLUMNS: FreightLineColumn[] = [
  { key: 'fileName', label: 'File name', labelKm: 'ឈ្មោះឯកសារ', labelKey: 'freight.ui.fileNameCol', computed: true },
  { key: 'uploadedBy', label: 'By', labelKm: 'ដោយ', labelKey: 'freight.ui.byCol', computed: true },
  { key: 'uploadedAt', label: 'Created', labelKm: 'បង្កើត', labelKey: 'freight.ui.createdCol', type: 'datetime', computed: true },
]

export const SOURCE_RELATIONSHIP_COLUMNS: FreightLineColumn[] = [
  { key: 'sourceType', label: 'Source Type', labelKm: 'ប្រភេទប្រភព', labelKey: 'freight.fields.sourceType' },
  { key: 'sourceNo', label: 'Source Record', labelKm: 'កំណត់ត្រាប្រភព', labelKey: 'freight.fields.sourceNo' },
  { key: 'createdAt', label: 'Linked At', labelKm: 'ភ្ជាប់នៅ', labelKey: 'freight.ui.createdCol' },
]

export type FreightRelated = {
  path: string
  title: string
  titleKm?: string
  foreignKey: string
  localKey: string
}

export type FreightAction = {
  key: string
  label: string
  labelKm?: string
  icon: string
  color?: 'primary' | 'neutral' | 'success' | 'warning' | 'error'
}

/** Named document-form recipes compiled by `moduleDocumentTabs`. */
export type FreightDocumentForm = 'quotation' | 'charges' | 'finance' | 'roles'

export type FreightModule = {
  path: string
  title: string
  titleKm: string
  singular: string
  singularKm: string
  description: string
  descriptionKm: string
  icon: string
  group: string
  permission: string
  collection: string
  titleField: string
  columns: FreightField[]
  fields: FreightField[]
  filters?: FreightField[]
  tables?: FreightTable[]
  /** Nested document tabs (tab → section → field). When omitted, compiled from `documentForm` or fields/tables. */
  tabs?: DocumentTabSchema[]
  /** Quotation / charge / finance / roles tab recipes. Master data omits this (one Details tab). */
  documentForm?: FreightDocumentForm
  /** Hide line-table tabs on the create form (rows can be added after saving). */
  hideTablesOnCreate?: boolean
  related?: FreightRelated[]
  actions?: FreightAction[]
  progress?: readonly string[]
  statuses?: readonly string[] | string[]
  readOnly?: boolean
  /** Render records as a non-navigable table without selection or row actions. */
  tableOnly?: boolean
  canCreate?: boolean
  /** i18n key for the list/header title when collection-level copy is shared (e.g. jobs vs service orders). */
  titleKey?: string
  kind?: 'standard' | 'job' | 'quotation' | 'debit-note' | 'job-charges' | 'reports'
}

const f = (
  key: string,
  label: string,
  labelKm: string,
  section = 'General Information',
  sectionKm = 'ព័ត៌មានទូទៅ',
  type: FreightFieldType = 'text',
  options?: readonly FreightSelectOption[] | FreightSelectOption[],
  extra: Partial<FreightField> = {},
): FreightField => ({ key, label, labelKm, section, sectionKm, type, options, ...extra })

const col = (key: string, label: string, labelKm?: string, extra: Partial<FreightField> = {}): FreightField => ({
  key,
  label,
  labelKm: labelKm || label,
  ...extra,
})

function createModule(partial: Omit<FreightModule, 'canCreate'> & { canCreate?: boolean }): FreightModule {
  return {
    canCreate: partial.readOnly ? false : partial.canCreate !== false,
    kind: partial.kind || 'standard',
    ...partial,
  }
}

export const freightModules: FreightModule[] = [
  createModule({
    path: '/sales/companies',
    title: 'Companies / Customers',
    titleKm: 'ក្រុមហ៊ុន / អតិថិជន',
    singular: 'Company',
    singularKm: 'ក្រុមហ៊ុន',
    description: 'Factory and customer records from company information, customs credentials and logistics defaults.',
    descriptionKm: 'កំណត់ត្រារោងចក្រ និងអតិថិជន រួមព័ត៌មានគយ និងដឹកជញ្ជូនលំនាំដើម។',
    icon: 'i-lucide-building-2',
    group: 'sales',
    permission: 'sales.companies.view',
    collection: 'companies',
    titleField: 'name',
    columns: [
      col('code', 'Company Code', 'លេខកូដ'),
      col('factoryName', 'Company / Factory Name', 'ឈ្មោះក្រុមហ៊ុន / រោងចក្រ'),
      col('zone', 'Zone', 'តំបន់'),
      col('patentNo', 'Patent No.', 'លេខប៉ាតង់'),
      col('contact', 'Contact Person', 'អ្នកទំនាក់ទំនង'),
      col('phone', 'Telephone', 'ទូរស័ព្ទ'),
      col('address', 'Address', 'អាសយដ្ឋាន'),
      col('direction', 'Default Direction', 'ទិសដៅលំនាំដើម'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('code', 'Company Code', 'លេខកូដក្រុមហ៊ុន', 'General Information', 'ព័ត៌មានទូទៅ', 'text', undefined, { required: true }),
      f('factoryName', 'Factory Name', 'ឈ្មោះរោងចក្រ'),
      f('name', 'Company Name', 'ឈ្មោះក្រុមហ៊ុន', 'General Information', 'ព័ត៌មានទូទៅ', 'text', undefined, { required: true }),
      f('zone', 'Zone', 'តំបន់'),
      f('patentNo', 'Patent No.', 'លេខប៉ាតង់'),
      f('contact', 'Contact Person', 'អ្នកទំនាក់ទំនង'),
      f('phone', 'Telephone', 'ទូរស័ព្ទ'),
      f('email', 'Email', 'អ៊ីមែល'),
      f('address', 'Address', 'អាសយដ្ឋាន', 'General Information', 'ព័ត៌មានទូទៅ', 'textarea', undefined, { colSpan: 2 }),
      f('customsAccount', 'Customs Account', 'គណនីគយ', 'Customs Information', 'ព័ត៌មានគយ'),
      f('customsUsername', 'Customs Account Username', 'ឈ្មោះអ្នកប្រើគណនីគយ', 'Customs Information', 'ព័ត៌មានគយ'),
      f('credentialReference', 'Customs Account Password / Credential Reference', 'ពាក្យសម្ងាត់ / ឯកសារយោង', 'Customs Information', 'ព័ត៌មានគយ', 'password'),
      f('patent', 'Patent', 'ប៉ាតង់', 'Customs Information', 'ព័ត៌មានគយ'),
      f('direction', 'Default Direction', 'ទិសដៅលំនាំដើម', 'Customs Information', 'ព័ត៌មានគយ', 'select', DIRECTIONS),
      f('containerType', 'Default Container Type', 'ប្រភេទកុងតឺន័រលំនាំដើម', 'Logistics Information', 'ព័ត៌មានដឹកជញ្ជូន', 'select', CONTAINER_TYPES),
      f('truckType', 'Default Truck Type', 'ប្រភេទឡានលំនាំដើម', 'Logistics Information', 'ព័ត៌មានដឹកជញ្ជូន', 'select', TRUCK_TYPES),
      f('defaultZone', 'Default Zone', 'តំបន់លំនាំដើម', 'Logistics Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('deliveryLocation', 'Default Delivery Location', 'ទីកន្លែងប្រគល់លំនាំដើម', 'Logistics Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('status', 'Status', 'ស្ថានភាព', 'Status', 'ស្ថានភាព', 'select', ACTIVE_STATUS),
    ],
    filters: [
      f('zone', 'Zone', 'តំបន់', '', '', 'select'),
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', '', '', 'select', DIRECTIONS),
      f('status', 'Status', 'ស្ថានភាព', '', '', 'select', ACTIVE_STATUS),
    ],
    related: [
      { path: '/sales/quotations', title: 'Quotations', titleKm: 'សម្រង់តម្លៃ', foreignKey: 'customer', localKey: 'name' },
      { path: '/operations/jobs', title: 'Jobs', titleKm: 'ការងារ', foreignKey: 'customer', localKey: 'name' },
      { path: '/operations/shipments', title: 'Containers', titleKm: 'កុងតឺន័រ', foreignKey: 'customer', localKey: 'name' },
      { path: '/finance/debit-notes', title: 'Debit Notes', titleKm: 'ប័ណ្ណឥណពន្ធ', foreignKey: 'customer', localKey: 'name' },
      { path: '/finance/customer-payments', title: 'Payments', titleKm: 'ការទូទាត់', foreignKey: 'customer', localKey: 'name' },
      { path: '/operations/documents', title: 'Documents', titleKm: 'ឯកសារ', foreignKey: 'customer', localKey: 'name' },
    ],
  }),

  createModule({
    path: '/sales/quotations',
    title: 'Quotations',
    titleKm: 'សម្រង់តម្លៃ',
    singular: 'Quotation',
    singularKm: 'សម្រង់តម្លៃ',
    description: 'Import and export quotations with route, container rates, other charges and conditions.',
    descriptionKm: 'សម្រង់តម្លៃនាំចូល និងនាំចេញ រួមផ្លូវ អត្រាកុងតឺន័រ និងលក្ខខណ្ឌ។',
    icon: 'i-lucide-file-check-2',
    group: 'sales',
    permission: 'sales.quotations.view',
    collection: 'quotations',
    titleField: 'quotationNo',
    kind: 'quotation',
    columns: [
      col('quotationNo', 'Quotation No.', 'លេខសម្រង់'),
      col('date', 'Date', 'កាលបរិច្ឆេទ'),
      col('customer', 'Customer', 'អតិថិជន'),
      col('attention', 'Attention To', 'ជូនចំពោះ'),
      col('direction', 'Import / Export', 'នាំចូល / នាំចេញ'),
      col('pickup', 'Pickup Location', 'ទីកន្លែងទទួល'),
      col('border', 'Border', 'ព្រំដែន'),
      col('delivery', 'Delivery Location', 'ទីកន្លែងប្រគល់'),
      col('transportBy', 'Transport By', 'មធ្យោបាយដឹក'),
      col('validUntil', 'Valid Until', 'មានសុពលភាពដល់'),
      col('currency', 'Currency', 'រូបិយប័ណ្ណ'),
      col('amount', 'Amount', 'ចំនួនទឹកប្រាក់'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('quotationNo', 'Quotation No.', 'លេខសម្រង់', 'Header', 'ក្បាល', 'text', undefined, { required: true }),
      f('date', 'Quotation Date', 'កាលបរិច្ឆេទសម្រង់', 'Header', 'ក្បាល', 'date', undefined, { required: true }),
      f('status', 'Status', 'ស្ថានភាព', 'Header', 'ក្បាល', 'select', QUOTATION_STATUS),
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', 'Header', 'ក្បាល', 'select', DIRECTIONS),
      f('customer', 'Company', 'ក្រុមហ៊ុន', 'Customer Information', 'ព័ត៌មានអតិថិជន', 'text', undefined, { required: true }),
      f('attention', 'Attention To', 'ជូនចំពោះ', 'Customer Information', 'ព័ត៌មានអតិថិជន'),
      f('phone', 'Phone', 'ទូរស័ព្ទ', 'Customer Information', 'ព័ត៌មានអតិថិជន'),
      f('email', 'Email', 'អ៊ីមែល', 'Customer Information', 'ព័ត៌មានអតិថិជន'),
      f('pickup', 'Pickup Point', 'ចំណុចទទួល', 'Route Information', 'ព័ត៌មានផ្លូវ'),
      f('border', 'Border / Transit Point', 'ព្រំដែន / ចំណុចឆ្លង', 'Route Information', 'ព័ត៌មានផ្លូវ'),
      f('delivery', 'Delivery Point', 'ចំណុចប្រគល់', 'Route Information', 'ព័ត៌មានផ្លូវ'),
      f('transportBy', 'Transport By', 'មធ្យោបាយដឹក', 'Route Information', 'ព័ត៌មានផ្លូវ', 'select', TRANSPORT_BY),
      f('route', 'Route Summary', 'សង្ខេបផ្លូវ', 'Route Information', 'ព័ត៌មានផ្លូវ', 'text', undefined, { colSpan: 2, computed: true }),
      f('buying20', '20GP Buying Rate', 'អត្រាទិញ 20GP', 'Container Rates', 'អត្រាកុងតឺន័រ', 'number'),
      f('selling20', '20GP Selling Rate', 'អត្រាលក់ 20GP', 'Container Rates', 'អត្រាកុងតឺន័រ', 'number'),
      f('currency20', '20GP Currency', 'រូបិយប័ណ្ណ 20GP', 'Container Rates', 'អត្រាកុងតឺន័រ', 'select', CURRENCIES),
      f('buying40', '40GP / 40HC Buying Rate', 'អត្រាទិញ 40GP / 40HC', 'Container Rates', 'អត្រាកុងតឺន័រ', 'number'),
      f('selling40', '40GP / 40HC Selling Rate', 'អត្រាលក់ 40GP / 40HC', 'Container Rates', 'អត្រាកុងតឺន័រ', 'number'),
      f('currency40', '40GP / 40HC Currency', 'រូបិយប័ណ្ណ 40GP / 40HC', 'Container Rates', 'អត្រាកុងតឺន័រ', 'select', CURRENCIES),
      f('buying45', '45GP / 45HC Buying Rate', 'អត្រាទិញ 45GP / 45HC', 'Container Rates', 'អត្រាកុងតឺន័រ', 'number'),
      f('selling45', '45GP / 45HC Selling Rate', 'អត្រាលក់ 45GP / 45HC', 'Container Rates', 'អត្រាកុងតឺន័រ', 'number'),
      f('currency45', '45GP / 45HC Currency', 'រូបិយប័ណ្ណ 45GP / 45HC', 'Container Rates', 'អត្រាកុងតឺន័រ', 'select', CURRENCIES),
      f('totalBuying', 'Total Buying', 'សរុបការទិញ', 'Summary', 'សង្ខេប', 'number', undefined, { computed: true }),
      f('totalSelling', 'Total Selling', 'សរុបការលក់', 'Summary', 'សង្ខេប', 'number', undefined, { computed: true }),
      f('profit', 'Profit', 'ប្រាក់ចំណេញ', 'Summary', 'សង្ខេប', 'number', undefined, { computed: true }),
      f('margin', 'Margin %', 'អត្រាប្រាក់ចំណេញ %', 'Summary', 'សង្ខេប', 'number', undefined, { computed: true }),
      f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Summary', 'សង្ខេប', 'select', CURRENCIES),
      f('validUntil', 'Valid Until', 'មានសុពលភាពដល់', 'Summary', 'សង្ខេប', 'date'),
    ],
    tables: [
      {
        key: 'containerRequirements',
        title: 'Container Requirements',
        titleKm: 'តម្រូវការកុងតឺន័រ',
        addLabel: 'Add container requirement',
        columns: [
          { key: 'containerType', label: 'Container Type', labelKm: 'ប្រភេទកុងតឺន័រ' },
          { key: 'quantity', label: 'Quantity', labelKm: 'បរិមាណ', type: 'number' },
          { key: 'grossWeightKg', label: 'Estimated Gross Weight (kg)', labelKm: 'ទម្ងន់សរុបប៉ាន់ស្មាន', type: 'number' },
          { key: 'remarks', label: 'Remarks', labelKm: 'កំណត់សម្គាល់' },
        ],
      },
      {
        key: 'pricingLines',
        title: 'Pricing Lines',
        titleKm: 'ជួរតម្លៃ',
        addLabel: 'Add pricing line',
        columns: [
          { key: 'feeType', label: 'Fee Type', labelKm: 'ប្រភេទថ្លៃ' },
          { key: 'containerType', label: 'Container', labelKm: 'កុងតឺន័រ' },
          { key: 'description', label: 'Description', labelKm: 'បរិយាយ' },
          { key: 'quantity', label: 'Quantity', labelKm: 'បរិមាណ', type: 'number' },
          { key: 'unit', label: 'Unit', labelKm: 'ឯកតា' },
          { key: 'unitPrice', label: 'Unit Price', labelKm: 'តម្លៃឯកតា', type: 'number' },
          {
            key: 'total',
            label: 'Line Total',
            labelKm: 'សរុបជួរ',
            labelKey: 'freight.ui.lineTotal',
            type: 'number',
            computed: true,
            inlineFields: [
              { key: 'discount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
              { key: 'tax', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
            ],
          },
        ],
      },
      {
        key: 'otherCharges',
        title: 'Other Charges',
        titleKm: 'ថ្លៃផ្សេងទៀត',
        addLabel: 'Add charge',
        columns: [
          { key: 'description', label: 'Charge Description', labelKm: 'បរិយាយ' },
          { key: 'quantity', label: 'Quantity', labelKm: 'បរិមាណ', type: 'number' },
          { key: 'unit', label: 'Unit', labelKm: 'ឯកតា' },
          { key: 'buyingRate', label: 'Buying Rate', labelKm: 'អត្រាទិញ', type: 'number' },
          { key: 'sellingRate', label: 'Selling Rate', labelKm: 'អត្រាលក់', type: 'number' },
          { key: 'amount', label: 'Amount', labelKm: 'ចំនួន', type: 'number' },
          { key: 'remark', label: 'Remark', labelKm: 'កំណត់សម្គាល់' },
        ],
      },
      {
        key: 'conditions',
        title: 'Not Included / Conditions',
        titleKm: 'មិនរួមបញ្ចូល / លក្ខខណ្ឌ',
        addLabel: 'Add condition',
        lockedPresets: true,
        presets: QUOTATION_CONDITIONS.map(condition => ({
          condition,
          description: condition,
          amount: '',
          unit: '',
          remark: 'Charged separately if required',
        })),
        columns: [
          { key: 'condition', label: 'Condition', labelKm: 'លក្ខខណ្ឌ' },
          { key: 'description', label: 'Description', labelKm: 'បរិយាយ' },
          { key: 'amount', label: 'Amount', labelKm: 'ចំនួន', type: 'number' },
          { key: 'unit', label: 'Unit', labelKm: 'ឯកតា' },
          { key: 'remark', label: 'Remark', labelKm: 'កំណត់សម្គាល់' },
        ],
      },
    ],
    actions: [
      { key: 'saveDraft', label: 'Save Draft', labelKm: 'រក្សាទុកព្រាង', icon: 'i-lucide-save' },
      { key: 'send', label: 'Send', labelKm: 'ផ្ញើ', icon: 'i-lucide-send' },
      { key: 'accept', label: 'Accept', labelKm: 'ទទួលយក', icon: 'i-lucide-check', color: 'success' },
      { key: 'createRevision', label: 'Create Revision', labelKm: 'បង្កើតកំណែថ្មី', icon: 'i-lucide-git-branch' },
      { key: 'print', label: 'Print / PDF', labelKm: 'បោះពុម្ព / PDF', icon: 'i-lucide-printer' },
      { key: 'convertJob', label: 'Convert to Job', labelKm: 'ប្តូរទៅជាការងារ', icon: 'i-lucide-container', color: 'primary' },
    ],
    filters: [
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', '', '', 'select', DIRECTIONS),
      f('status', 'Status', 'ស្ថានភាព', '', '', 'select', QUOTATION_STATUS),
      f('date', 'Date', 'កាលបរិច្ឆេទ', '', '', 'date'),
    ],
    statuses: QUOTATION_STATUS,
  }),

  createModule({
    path: '/operations/jobs',
    title: 'Jobs',
    titleKm: 'ការងារ',
    singular: 'Job',
    singularKm: 'ការងារ',
    description: 'Operational control center for every freight movement, replacing PALAN and SQL tracking sheets.',
    descriptionKm: 'ទំព័រគ្រប់គ្រងប្រតិបត្តិការសម្រាប់រាល់ការដឹកជញ្ជូន។',
    icon: 'i-lucide-container',
    group: 'operations',
    permission: 'operations.jobs.view',
    collection: 'jobs',
    titleField: 'jobNo',
    kind: 'job',
    progress: JOB_STATUS,
    columns: [
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('date', 'Date', 'កាលបរិច្ឆេទ'),
      col('soNo', 'SO No.', 'លេខ SO'),
      col('blNo', 'B/L No.', 'លេខ B/L'),
      col('zone', 'Zone', 'តំបន់'),
      col('customer', 'Factory / Company', 'រោងចក្រ / ក្រុមហ៊ុន'),
      col('patentNo', 'Patent No.', 'លេខប៉ាតង់'),
      col('invoiceNo', 'Invoice No.', 'លេខវិក្កយបត្រ'),
      col('packingListNo', 'Packing List No.', 'លេខបញ្ជីវេចខ្ចប់'),
      col('direction', 'Import / Export', 'នាំចូល / នាំចេញ'),
      col('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      col('containerType', 'Container Size', 'ទំហំកុងតឺន័រ'),
      col('etaPort', 'ETA Port', 'ម៉ោងមកដល់កំពង់ផែ'),
      col('etaFactory', 'ETA Factory', 'ម៉ោងមកដល់រោងចក្រ'),
      col('status', 'Status', 'ស្ថានភាព'),
      col('workflowStatus', 'Workflow', 'លំហូរ'),
      col('referenceNo', 'Reference No.', 'លេខយោង'),
    ],
    fields: [
      f('jobNo', 'Job No.', 'លេខការងារ', 'Job Information', 'ព័ត៌មានការងារ', 'text', undefined, { required: true }),
      f('date', 'Job Date', 'កាលបរិច្ឆេទការងារ', 'Job Information', 'ព័ត៌មានការងារ', 'date'),
      f('customer', 'Customer / Factory', 'អតិថិជន / រោងចក្រ', 'Job Information', 'ព័ត៌មានការងារ', 'text', undefined, { required: true }),
      f('factory', 'Factory', 'រោងចក្រ', 'Job Information', 'ព័ត៌មានការងារ'),
      f('zone', 'Zone', 'តំបន់', 'Job Information', 'ព័ត៌មានការងារ'),
      f('contact', 'Contact Person', 'អ្នកទំនាក់ទំនង', 'Job Information', 'ព័ត៌មានការងារ'),
      f('direction', 'Trade Directions', 'ទិសដៅពាណិជ្ជកម្ម', 'Job Information', 'ព័ត៌មានការងារ', 'select', DIRECTIONS, { labelKey: 'freight.ui.cols.direction' }),
      f('serviceType', 'Service Type', 'ប្រភេទសេវា', 'Job Information', 'ព័ត៌មានការងារ', 'select', SERVICE_TYPES),
      f('status', 'Job Status', 'ស្ថានភាពការងារ', 'Job Information', 'ព័ត៌មានការងារ', 'select', JOB_STATUS),
      f('workflowStatus', 'Workflow Status', 'ស្ថានភាពលំហូរ', 'Job Information', 'ព័ត៌មានការងារ', 'select', JOB_WORKFLOW_STATUS),
      f('assignedStaff', 'Assigned Staff', 'បុគ្គលិកទទួលបន្ទុក', 'Job Information', 'ព័ត៌មានការងារ'),
      f('quotationNo', 'Related Quotation', 'សម្រង់តម្លៃពាក់ព័ន្ធ', 'Job Information', 'ព័ត៌មានការងារ'),
      f('soNo', 'SO No.', 'លេខ SO', 'Commercial Information', 'ព័ត៌មានពាណិជ្ជកម្ម'),
      f('invoiceNo', 'Invoice No.', 'លេខវិក្កយបត្រ', 'Commercial Information', 'ព័ត៌មានពាណិជ្ជកម្ម'),
      f('packingListNo', 'Packing List No.', 'លេខបញ្ជីវេចខ្ចប់', 'Commercial Information', 'ព័ត៌មានពាណិជ្ជកម្ម'),
      f('blNo', 'B/L No.', 'លេខ B/L', 'Commercial Information', 'ព័ត៌មានពាណិជ្ជកម្ម'),
      f('patentNo', 'Patent No.', 'លេខប៉ាតង់', 'Commercial Information', 'ព័ត៌មានពាណិជ្ជកម្ម'),
      f('transportMode', 'Transport Mode', 'មធ្យោបាយដឹក', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន', 'select', TRANSPORT_MODES),
      f('containerNo', 'Container No.', 'លេខកុងតឺន័រ', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('containerType', 'Container Size / Type', 'ទំហំ / ប្រភេទកុងតឺន័រ', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន', 'select', CONTAINER_TYPES),
      f('sealNo', 'Seal No.', 'លេខត្រា', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('truckNo', 'Truck No.', 'លេខឡាន', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('licensePlate', 'License Plate No.', 'ស្លាកលេខ', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('carrier', 'Shipping Line / Carrier', 'ក្រុមហ៊ុនដឹក', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('vessel', 'Vessel', 'នាវា', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('voyage', 'Voyage', 'ជើងនាវា', 'Shipment Information', 'ព័ត៌មានដឹកជញ្ជូន'),
      f('origin', 'Origin', 'ចំណុចដើម', 'Route', 'ផ្លូវ'),
      f('pickup', 'Pickup Location', 'ទីកន្លែងទទួល', 'Route', 'ផ្លូវ'),
      f('port', 'Port', 'កំពង់ផែ', 'Route', 'ផ្លូវ'),
      f('border', 'Border / Transit Point', 'ព្រំដែន / ចំណុចឆ្លង', 'Route', 'ផ្លូវ'),
      f('destination', 'Destination', 'ទិសដៅ', 'Route', 'ផ្លូវ'),
      f('deliveryLocation', 'Factory / Delivery Location', 'រោងចក្រ / ទីកន្លែងប្រគល់', 'Route', 'ផ្លូវ'),
      f('shipmentDate', 'Shipment Date', 'កាលបរិច្ឆេទដឹក', 'Dates', 'កាលបរិច្ឆេទ', 'date'),
      f('registeredDate', 'Registered Shipping Date', 'កាលបរិច្ឆេទចុះឈ្មោះដឹក', 'Dates', 'កាលបរិច្ឆេទ', 'date'),
      f('etaPort', 'ETA Port', 'ម៉ោងមកដល់កំពង់ផែ', 'Dates', 'កាលបរិច្ឆេទ', 'date'),
      f('etaBorder', 'ETA Border', 'ម៉ោងមកដល់ព្រំដែន', 'Dates', 'កាលបរិច្ឆេទ', 'date'),
      f('etaFactory', 'ETA Factory', 'ម៉ោងមកដល់រោងចក្រ', 'Dates', 'កាលបរិច្ឆេទ', 'date'),
      f('actualArrival', 'Actual Arrival Factory', 'ម៉ោងមកដល់រោងចក្រពិតប្រាកដ', 'Dates', 'កាលបរិច្ឆេទ', 'datetime'),
      f('deliveryDate', 'Delivery Date', 'កាលបរិច្ឆេទប្រគល់', 'Dates', 'កាលបរិច្ឆេទ', 'date'),
      f('internalReference', 'Internal Reference No.', 'លេខយោងផ្ទៃក្នុង', 'Reference', 'លេខយោង'),
      f('transportReference', 'Transport Reference No.', 'លេខយោងដឹកជញ្ជូន', 'Reference', 'លេខយោង'),
      f('externalReference', 'External Reference No.', 'លេខយោងខាងក្រៅ', 'Reference', 'លេខយោង'),
      f('referenceNo', 'Reference No.', 'លេខយោង', 'Reference', 'លេខយោង'),
      f('operationalRemark', 'Operational Remark', 'កំណត់សម្គាល់ប្រតិបត្តិការ', 'Remarks', 'កំណត់សម្គាល់', 'textarea'),
      f('customsRemark', 'Customs Remark', 'កំណត់សម្គាល់គយ', 'Remarks', 'កំណត់សម្គាល់', 'textarea'),
      f('deliveryRemark', 'Delivery Remark', 'កំណត់សម្គាល់ការប្រគល់', 'Remarks', 'កំណត់សម្គាល់', 'textarea'),
      f('internalNote', 'Internal Note', 'កំណត់ចំណាំផ្ទៃក្នុង', 'Remarks', 'កំណត់សម្គាល់', 'textarea'),
    ],
    filters: [
      f('date', 'Date', 'កាលបរិច្ឆេទ', '', '', 'date'),
      f('customer', 'Company', 'ក្រុមហ៊ុន', '', '', 'select'),
      f('zone', 'Zone', 'តំបន់', '', '', 'select'),
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', '', '', 'select', DIRECTIONS),
      f('containerType', 'Container Type', 'ប្រភេទកុងតឺន័រ', '', '', 'select', CONTAINER_TYPES),
      f('status', 'Job Status', 'ស្ថានភាពការងារ', '', '', 'select', JOB_STATUS),
      f('workflowStatus', 'Workflow', 'លំហូរ', '', '', 'select', JOB_WORKFLOW_STATUS),
      f('customsStatus', 'Customs Status', 'ស្ថានភាពគយ', '', '', 'select', CUSTOMS_STATUS),
    ],
    statuses: JOB_STATUS,
  }),

  createModule({
    path: '/operations/shipments',
    title: 'Shipments / Transport',
    titleKm: 'ការដឹកជញ្ជូន',
    singular: 'Shipment',
    singularKm: 'ការដឹកជញ្ជូន',
    description: 'Register vehicles, containers, transport providers and factory ETA.',
    descriptionKm: 'ចុះឈ្មោះយានយន្ត កុងតឺន័រ អ្នកផ្តល់សេវាដឹក និងម៉ោងមកដល់រោងចក្រ។',
    icon: 'i-lucide-truck',
    group: 'operations',
    permission: 'operations.shipments.view',
    collection: 'shipments',
    titleField: 'transportNo',
    columns: [
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('registeredDate', 'Registered Date', 'កាលបរិច្ឆេទចុះឈ្មោះ'),
      col('transportNo', 'Transport No.', 'លេខដឹកជញ្ជូន'),
      col('truckBill', 'Truck Bill', 'ប័ណ្ណឡាន'),
      col('truckNo', 'Truck No.', 'លេខឡាន'),
      col('licensePlate', 'License Plate No.', 'ស្លាកលេខ'),
      col('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      col('containerType', 'Container Size', 'ទំហំ'),
      col('sealNo', 'Seal No.', 'លេខត្រា'),
      col('port', 'Import / Export Port', 'កំពង់ផែ'),
      col('etaFactory', 'ETA Factory', 'ម៉ោងមកដល់រោងចក្រ'),
      col('supplier', 'Provider', 'អ្នកផ្តល់សេវា'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('jobNo', 'Job No.', 'លេខការងារ', 'Shipment', 'ការដឹកជញ្ជូន', 'text', undefined, { required: true }),
      f('customer', 'Customer', 'អតិថិជន', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('registeredDate', 'Registered Shipping Date', 'កាលបរិច្ឆេទចុះឈ្មោះដឹក', 'Shipment', 'ការដឹកជញ្ជូន', 'date'),
      f('transportNo', 'Transport No.', 'លេខដឹកជញ្ជូន', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('truckBill', 'Truck Bill', 'ប័ណ្ណឡាន', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('truckNo', 'Truck No.', 'លេខឡាន', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('licensePlate', 'License Plate No.', 'ស្លាកលេខ', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('containerNo', 'Container No.', 'លេខកុងតឺន័រ', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('containerType', 'Container Size', 'ទំហំកុងតឺន័រ', 'Shipment', 'ការដឹកជញ្ជូន', 'select', CONTAINER_TYPES),
      f('sealNo', 'Seal No.', 'លេខត្រា', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('port', 'Import / Export Port', 'កំពង់ផែនាំចូល / នាំចេញ', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('etaFactory', 'ETA Factory', 'ម៉ោងមកដល់រោងចក្រ', 'Shipment', 'ការដឹកជញ្ជូន', 'date'),
      f('referenceNo', 'Reference No.', 'លេខយោង', 'Shipment', 'ការដឹកជញ្ជូន'),
      f('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់', 'Transport Provider', 'អ្នកផ្តល់សេវាដឹក'),
      f('driver', 'Driver Name', 'ឈ្មោះអ្នកបើកបរ', 'Transport Provider', 'អ្នកផ្តល់សេវាដឹក'),
      f('driverPhone', 'Driver Phone', 'ទូរស័ព្ទអ្នកបើកបរ', 'Transport Provider', 'អ្នកផ្តល់សេវាដឹក'),
      f('truckCompany', 'Truck Company', 'ក្រុមហ៊ុនឡាន', 'Transport Provider', 'អ្នកផ្តល់សេវាដឹក'),
      f('transportCost', 'Transport Cost', 'ថ្លៃដឹក', 'Transport Provider', 'អ្នកផ្តល់សេវាដឹក', 'number'),
      f('status', 'Status', 'ស្ថានភាព', 'Transport Provider', 'អ្នកផ្តល់សេវាដឹក', 'select', SHIPMENT_STATUS),
    ],
    statuses: SHIPMENT_STATUS,
  }),

  createModule({
    path: '/operations/customs',
    title: 'Customs',
    titleKm: 'គយ',
    singular: 'Customs Record',
    singularKm: 'កំណត់ត្រាគយ',
    description: 'Track declarations, clearance dates, supporting documents and customs costs.',
    descriptionKm: 'តាមដានសេចក្តីប្រកាស ថ្ងៃបញ្ចេញ ឯកសារ និងថ្លៃគយ។',
    icon: 'i-lucide-stamp',
    group: 'operations',
    permission: 'operations.customs.view',
    collection: 'customs',
    titleField: 'customsNo',
    columns: [
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('date', 'Date', 'កាលបរិច្ឆេទ'),
      col('company', 'Company', 'ក្រុមហ៊ុន'),
      col('zone', 'Zone', 'តំបន់'),
      col('direction', 'Import / Export', 'នាំចូល / នាំចេញ'),
      col('invoiceNo', 'Invoice No.', 'លេខវិក្កយបត្រ'),
      col('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      col('customsNo', 'Customs No.', 'លេខគយ'),
      col('customsFeeNo', 'Customs Fee No.', 'លេខថ្លៃគយ'),
      col('referenceNo', 'Reference No.', 'លេខយោង'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('jobNo', 'Job No.', 'លេខការងារ', 'General', 'ទូទៅ', 'text', undefined, { required: true }),
      f('customer', 'Customer', 'អតិថិជន', 'General', 'ទូទៅ'),
      f('company', 'Company', 'ក្រុមហ៊ុន', 'General', 'ទូទៅ'),
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', 'General', 'ទូទៅ', 'select', DIRECTIONS),
      f('zone', 'Zone', 'តំបន់', 'General', 'ទូទៅ'),
      f('containerNo', 'Container No.', 'លេខកុងតឺន័រ', 'General', 'ទូទៅ'),
      f('containerType', 'Container Size', 'ទំហំកុងតឺន័រ', 'General', 'ទូទៅ', 'select', CONTAINER_TYPES),
      f('customsNo', 'Customs Declaration No.', 'លេខសេចក្តីប្រកាសគយ', 'Declaration', 'សេចក្តីប្រកាស'),
      f('referenceNo', 'Customs Reference No.', 'លេខយោងគយ', 'Declaration', 'សេចក្តីប្រកាស'),
      f('customsFeeNo', 'Customs / Seal Fee No.', 'លេខថ្លៃគយ / ត្រា', 'Declaration', 'សេចក្តីប្រកាស'),
      f('declarationDate', 'Declaration Date', 'កាលបរិច្ឆេទប្រកាស', 'Declaration', 'សេចក្តីប្រកាស', 'date'),
      f('submissionDate', 'Submission Date', 'កាលបរិច្ឆេទដាក់', 'Declaration', 'សេចក្តីប្រកាស', 'date'),
      f('clearanceDate', 'Clearance Date', 'កាលបរិច្ឆេទបញ្ចេញ', 'Declaration', 'សេចក្តីប្រកាស', 'date'),
      f('status', 'Customs Status', 'ស្ថានភាពគយ', 'Declaration', 'សេចក្តីប្រកាស', 'select', CUSTOMS_STATUS),
      f('invoiceDoc', 'Invoice', 'វិក្កយបត្រ', 'Related Documents', 'ឯកសារពាក់ព័ន្ធ'),
      f('packingListDoc', 'Packing List', 'បញ្ជីវេចខ្ចប់', 'Related Documents', 'ឯកសារពាក់ព័ន្ធ'),
      f('blDoc', 'B/L', 'B/L', 'Related Documents', 'ឯកសារពាក់ព័ន្ធ'),
      f('patentDoc', 'Patent', 'ប៉ាតង់', 'Related Documents', 'ឯកសារពាក់ព័ន្ធ'),
      f('soDoc', 'SO', 'SO', 'Related Documents', 'ឯកសារពាក់ព័ន្ធ'),
      f('declarationDoc', 'Customs Declaration', 'សេចក្តីប្រកាសគយ', 'Related Documents', 'ឯកសារពាក់ព័ន្ធ', 'file'),
      f('receiptDoc', 'Customs Receipt', 'បង្កាន់ដៃគយ', 'Related Documents', 'ឯកសារពាក់ព័ន្ធ', 'file'),
      f('clearanceFee', 'Clearance Fee', 'ថ្លៃបញ្ចេញ', 'Customs Costs', 'ថ្លៃគយ', 'number'),
      f('sealFee', 'Seal Fee', 'ថ្លៃត្រា', 'Customs Costs', 'ថ្លៃគយ', 'number'),
      f('inspectionFee', 'Inspection Fee', 'ថ្លៃត្រួតពិនិត្យ', 'Customs Costs', 'ថ្លៃគយ', 'number'),
      f('overtime', 'Overtime', 'ថ្លៃម៉ោងបន្ថែម', 'Customs Costs', 'ថ្លៃគយ', 'number'),
      f('fine', 'Fine', 'ពិន័យ', 'Customs Costs', 'ថ្លៃគយ', 'number'),
      f('otherCharges', 'Other Charges', 'ថ្លៃផ្សេងទៀត', 'Customs Costs', 'ថ្លៃគយ', 'number'),
      f('notes', 'Customs Notes', 'កំណត់សម្គាល់គយ', 'Remark', 'កំណត់សម្គាល់', 'textarea'),
      f('holdReason', 'Issue / Hold Reason', 'មូលហេតុផ្អាក', 'Remark', 'កំណត់សម្គាល់', 'textarea'),
    ],
    filters: [
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', '', '', 'select', DIRECTIONS),
      f('zone', 'Zone', 'តំបន់', '', '', 'select'),
      f('status', 'Status', 'ស្ថានភាព', '', '', 'select', CUSTOMS_STATUS),
    ],
    statuses: CUSTOMS_STATUS,
  }),

  createModule({
    path: '/operations/documents',
    title: 'Documents',
    titleKm: 'ឯកសារ',
    singular: 'Document',
    singularKm: 'ឯកសារ',
    description: 'Upload, approve and monitor required shipment documents.',
    descriptionKm: 'ផ្ទុកឡើង អនុម័ត និងតាមដានឯកសារដឹកជញ្ជូន។',
    icon: 'i-lucide-files',
    group: 'operations',
    permission: 'operations.documents.view',
    collection: 'documents',
    titleField: 'documentNo',
    columns: [
      col('documentNo', 'Document No.', 'លេខឯកសារ'),
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('customer', 'Customer', 'អតិថិជន'),
      col('documentType', 'Document Type', 'ប្រភេទឯកសារ'),
      col('referenceNo', 'Document Reference', 'លេខយោង'),
      col('uploadDate', 'Upload Date', 'កាលបរិច្ឆេទផ្ទុក'),
      col('uploadedBy', 'Uploaded By', 'អ្នកផ្ទុក'),
      col('status', 'Status', 'ស្ថានភាព'),
      col('remark', 'Remark', 'កំណត់សម្គាល់'),
    ],
    fields: [
      f('documentNo', 'Document No.', 'លេខឯកសារ'),
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('customer', 'Customer', 'អតិថិជន'),
      f('documentType', 'Document Type', 'ប្រភេទឯកសារ', 'Document', 'ឯកសារ', 'select', DOCUMENT_TYPES),
      f('referenceNo', 'Document Reference', 'លេខយោងឯកសារ', 'Document', 'ឯកសារ'),
      f('file', 'File', 'ឯកសារ', 'Document', 'ឯកសារ', 'file'),
      f('uploadDate', 'Upload Date', 'កាលបរិច្ឆេទផ្ទុក', 'Document', 'ឯកសារ', 'date'),
      f('uploadedBy', 'Uploaded By', 'អ្នកផ្ទុក', 'Document', 'ឯកសារ'),
      f('status', 'Status', 'ស្ថានភាព', 'Document', 'ឯកសារ', 'select', DOCUMENT_STATUS),
      f('remark', 'Remark', 'កំណត់សម្គាល់', 'Document', 'ឯកសារ', 'textarea'),
    ],
    filters: [
      f('documentType', 'Document Type', 'ប្រភេទឯកសារ', '', '', 'select', DOCUMENT_TYPES),
      f('status', 'Status', 'ស្ថានភាព', '', '', 'select', DOCUMENT_STATUS),
    ],
  }),

  createModule({
    path: '/operations/deliveries',
    title: 'Deliveries',
    titleKm: 'ការប្រគល់',
    singular: 'Delivery',
    singularKm: 'ការប្រគល់',
    description: 'Track factory arrival, unloading, proof of delivery and completion.',
    descriptionKm: 'តាមដានការមកដល់រោងចក្រ ការដោះទំនិញ និងភស្តុតាងប្រគល់។',
    icon: 'i-lucide-package-check',
    group: 'operations',
    permission: 'operations.deliveries.view',
    collection: 'deliveries',
    titleField: 'jobNo',
    columns: [
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('customer', 'Customer', 'អតិថិជន'),
      col('factory', 'Factory', 'រោងចក្រ'),
      col('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      col('containerType', 'Container Type', 'ប្រភេទកុងតឺន័រ'),
      col('etaFactory', 'ETA Factory', 'ម៉ោងមកដល់រោងចក្រ'),
      col('actualArrival', 'Actual Arrival', 'ម៉ោងមកដល់ពិត'),
      col('status', 'Delivery Status', 'ស្ថានភាពប្រគល់'),
    ],
    fields: [
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('customer', 'Customer', 'អតិថិជន'),
      f('factory', 'Factory', 'រោងចក្រ'),
      f('deliveryAddress', 'Delivery Address', 'អាសយដ្ឋានប្រគល់', 'General', 'ទូទៅ', 'textarea'),
      f('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      f('truckNo', 'Truck No.', 'លេខឡាន'),
      f('driver', 'Driver', 'អ្នកបើកបរ'),
      f('etaFactory', 'ETA Factory', 'ម៉ោងមកដល់រោងចក្រ', 'Timing', 'ពេលវេលា', 'date'),
      f('arrivalTime', 'Arrival Time', 'ម៉ោងមកដល់', 'Timing', 'ពេលវេលា', 'datetime'),
      f('unloadingTime', 'Unloading Time', 'ម៉ោងដោះទំនិញ', 'Timing', 'ពេលវេលា', 'datetime'),
      f('completedTime', 'Completed Time', 'ម៉ោងបញ្ចប់', 'Timing', 'ពេលវេលា', 'datetime'),
      f('receiver', 'Receiver Name', 'ឈ្មោះអ្នកទទួល', 'Completion', 'ការបញ្ចប់'),
      f('pod', 'POD', 'ភស្តុតាងប្រគល់', 'Completion', 'ការបញ្ចប់', 'file'),
      f('remark', 'Remark', 'កំណត់សម្គាល់', 'Completion', 'ការបញ្ចប់', 'textarea'),
      f('status', 'Delivery Status', 'ស្ថានភាពប្រគល់', 'Completion', 'ការបញ្ចប់', 'select', DELIVERY_STATUS),
    ],
    statuses: DELIVERY_STATUS,
  }),

  createModule({
    path: '/finance/debit-notes',
    title: 'Debit Notes',
    titleKm: 'ប័ណ្ណឥណពន្ធ',
    singular: 'Debit Note',
    singularKm: 'ប័ណ្ណឥណពន្ធ',
    description: 'Bill customer charges across Cambodia, Vietnam and cash expenses.',
    descriptionKm: 'ចេញប័ណ្ណឥណពន្ធសម្រាប់ថ្លៃកម្ពុជា វៀតណាម និងសាច់ប្រាក់។',
    icon: 'i-lucide-receipt-text',
    group: 'finance',
    permission: 'finance.debit_notes.view',
    collection: 'debitNotes',
    titleField: 'debitNoteNo',
    kind: 'debit-note',
    columns: [
      col('debitNoteNo', 'Debit Note No.', 'លេខប័ណ្ណ'),
      col('date', 'Date', 'កាលបរិច្ឆេទ'),
      col('customer', 'Customer', 'អតិថិជន'),
      col('invoiceNo', 'Invoice No.', 'លេខវិក្កយបត្រ'),
      col('blNo', 'B/L No.', 'លេខ B/L'),
      col('containerNo', 'Truck / Container No.', 'លេខឡាន / កុងតឺន័រ'),
      col('direction', 'Import / Export', 'នាំចូល / នាំចេញ'),
      col('amount', 'Amount', 'ចំនួន'),
      col('vat', 'VAT', 'អាករ'),
      col('total', 'Total Amount', 'សរុប'),
      col('status', 'Posting Status', 'ស្ថានភាពចុះគណនី'),
    ],
    fields: [
      f('debitNoteNo', 'Debit Note No.', 'លេខប័ណ្ណឥណពន្ធ', 'Customer', 'អតិថិជន', 'text', undefined, { required: true }),
      f('date', 'Date', 'កាលបរិច្ឆេទ', 'Customer', 'អតិថិជន', 'date'),
      f('customer', 'Customer Name', 'ឈ្មោះអតិថិជន', 'Customer', 'អតិថិជន'),
      f('customerAddress', 'Customer Address', 'អាសយដ្ឋានអតិថិជន', 'Customer', 'អតិថិជន', 'textarea'),
      f('jobNo', 'Job No.', 'លេខការងារ', 'Customer', 'អតិថិជន'),
      f('invoiceNo', 'Invoice No.', 'លេខវិក្កយបត្រ', 'Shipment Reference', 'យោងដឹកជញ្ជូន'),
      f('blNo', 'B/L No.', 'លេខ B/L', 'Shipment Reference', 'យោងដឹកជញ្ជូន'),
      f('containerNo', 'Truck / Container No.', 'លេខឡាន / កុងតឺន័រ', 'Shipment Reference', 'យោងដឹកជញ្ជូន'),
      f('quantity', 'Quantity', 'បរិមាណ', 'Shipment Reference', 'យោងដឹកជញ្ជូន', 'number'),
      f('containerType', 'Container Type', 'ប្រភេទកុងតឺន័រ', 'Shipment Reference', 'យោងដឹកជញ្ជូន', 'select', CONTAINER_TYPES),
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', 'Shipment Reference', 'យោងដឹកជញ្ជូន', 'select', DIRECTIONS),
      f('cambodiaSubtotal', 'Cambodia Subtotal', 'សរុបកម្ពុជា', 'Totals', 'សរុប', 'number', undefined, { computed: true }),
      f('vietnamSubtotal', 'Vietnam Subtotal', 'សរុបវៀតណាម', 'Totals', 'សរុប', 'number', undefined, { computed: true }),
      f('cashSubtotal', 'Cash Subtotal', 'សរុបសាច់ប្រាក់', 'Totals', 'សរុប', 'number', undefined, { computed: true }),
      f('amount', 'Total', 'សរុប', 'Totals', 'សរុប', 'number', undefined, { computed: true }),
      f('vatRate', 'VAT %', 'អាករ %', 'Totals', 'សរុប', 'number'),
      f('vat', 'VAT Amount', 'ចំនួនអាករ', 'Totals', 'សរុប', 'number', undefined, { computed: true }),
      f('total', 'Grand Total', 'សរុបរួម', 'Totals', 'សរុប', 'number', undefined, { computed: true }),
      f('status', 'Posting Status', 'ស្ថានភាពចុះគណនី', 'Totals', 'សរុប', 'select', DEBIT_NOTE_STATUS),
    ],
    tables: [
      {
        key: 'charges',
        title: 'Charge Table',
        titleKm: 'តារាងថ្លៃ',
        addLabel: 'Add charge',
        presets: DEBIT_CHARGE_TYPES.map(description => ({
          description,
          cambodia: 0,
          vietnam: 0,
          cash: 0,
          remark: '',
        })),
        columns: [
          { key: 'description', label: 'Charge Description', labelKm: 'បរិយាយថ្លៃ', type: 'select', options: DEBIT_CHARGE_TYPES },
          { key: 'cambodia', label: 'Cambodia Amount', labelKm: 'ចំនួនកម្ពុជា', type: 'number' },
          { key: 'vietnam', label: 'Vietnam Amount', labelKm: 'ចំនួនវៀតណាម', type: 'number' },
          { key: 'cash', label: 'Cash Amount', labelKm: 'ចំនួនសាច់ប្រាក់', type: 'number' },
          { key: 'remark', label: 'Remark', labelKm: 'កំណត់សម្គាល់' },
        ],
      },
    ],
    actions: [
      { key: 'save', label: 'Save Draft', labelKm: 'រក្សាទុកព្រាង', icon: 'i-lucide-save' },
      { key: 'post', label: 'Post', labelKm: 'ចុះគណនី', icon: 'i-lucide-check-circle-2', color: 'success' },
      { key: 'reverse', label: 'Reverse', labelKm: 'បញ្ច្រាស', icon: 'i-lucide-undo-2', color: 'warning' },
      { key: 'print', label: 'Print', labelKm: 'បោះពុម្ព', icon: 'i-lucide-printer' },
      { key: 'recordPayment', label: 'Record Payment', labelKm: 'កត់ត្រាការទូទាត់', icon: 'i-lucide-hand-coins', color: 'primary' },
    ],
    filters: [
      f('status', 'Status', 'ស្ថានភាព', '', '', 'select', DEBIT_NOTE_STATUS),
      f('date', 'Date', 'កាលបរិច្ឆេទ', '', '', 'date'),
    ],
    statuses: DEBIT_NOTE_STATUS,
  }),

  createModule({
    path: '/finance/customer-payments',
    title: 'Customer Payments',
    titleKm: 'ការទូទាត់អតិថិជន',
    singular: 'Customer Payment',
    singularKm: 'ការទូទាត់អតិថិជន',
    description: 'Record receipts and outstanding balances against jobs and debit notes.',
    descriptionKm: 'កត់ត្រាប្រាក់ទទួល និងសមតុល្យនៅសល់តាមការងារ និងប័ណ្ណឥណពន្ធ។',
    icon: 'i-lucide-hand-coins',
    group: 'finance',
    permission: 'finance.customer_payments.view',
    collection: 'customerPayments',
    titleField: 'paymentNo',
    columns: [
      col('paymentNo', 'Payment No.', 'លេខទូទាត់'),
      col('date', 'Payment Date', 'កាលបរិច្ឆេទទូទាត់'),
      col('customer', 'Customer', 'អតិថិជន'),
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('invoiceNo', 'Invoice No.', 'លេខវិក្កយបត្រ'),
      col('customsNo', 'SAD / Customs No.', 'លេខ SAD / គយ'),
      col('direction', 'Import / Export', 'នាំចូល / នាំចេញ'),
      col('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      col('containerType', 'Container Size', 'ទំហំ'),
      col('sealNo', 'Seal No.', 'លេខត្រា'),
      col('debitNoteNo', 'Debit Note No.', 'លេខប័ណ្ណឥណពន្ធ'),
      col('amountDue', 'Amount Due', 'ចំនួនត្រូវបង់'),
      col('received', 'Received Amount', 'ចំនួនបានទទួល'),
      col('outstanding', 'Outstanding Amount', 'នៅសល់'),
      col('paymentMethod', 'Payment Method', 'វិធីទូទាត់'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('paymentNo', 'Payment No.', 'លេខទូទាត់'),
      f('date', 'Payment Date', 'កាលបរិច្ឆេទទូទាត់', 'Payment', 'ការទូទាត់', 'date'),
      f('customer', 'Customer', 'អតិថិជន', 'Payment', 'ការទូទាត់'),
      f('jobNo', 'Job No.', 'លេខការងារ', 'References', 'យោង'),
      f('invoiceNo', 'Invoice No.', 'លេខវិក្កយបត្រ', 'References', 'យោង'),
      f('customsNo', 'SAD / Customs No.', 'លេខ SAD / គយ', 'References', 'យោង'),
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', 'References', 'យោង', 'select', DIRECTIONS),
      f('containerNo', 'Container No.', 'លេខកុងតឺន័រ', 'References', 'យោង'),
      f('containerType', 'Container Size', 'ទំហំកុងតឺន័រ', 'References', 'យោង', 'select', CONTAINER_TYPES),
      f('sealNo', 'Seal No.', 'លេខត្រា', 'References', 'យោង'),
      f('referenceNo', 'Reference No.', 'លេខយោង', 'References', 'យោង'),
      f('debitNoteNo', 'Debit Note No.', 'លេខប័ណ្ណឥណពន្ធ', 'References', 'យោង'),
      f('amountDue', 'Amount Due', 'ចំនួនត្រូវបង់', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number'),
      f('received', 'Received Amount', 'ចំនួនបានទទួល', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number'),
      f('allocatedAmount', 'Allocated Amount', 'ចំនួនបានបែងចែក', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number', undefined, { computed: true }),
      f('unallocatedAmount', 'Available Amount', 'ចំនួននៅសល់សម្រាប់បែងចែក', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number', undefined, { computed: true }),
      f('outstanding', 'Outstanding Amount', 'នៅសល់', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number', undefined, { computed: true }),
      f('paymentMethod', 'Payment Method', 'វិធីទូទាត់', 'Payment', 'ការទូទាត់', 'select', PAYMENT_METHODS),
      f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Payment', 'ការទូទាត់', 'select', CURRENCIES),
      f('remark', 'Remark', 'កំណត់សម្គាល់', 'Payment', 'ការទូទាត់', 'textarea'),
      f('status', 'Status', 'ស្ថានភាព', 'Payment', 'ការទូទាត់', 'select', PAYMENT_STATUS),
    ],
    filters: [
      f('status', 'Status', 'ស្ថានភាព', '', '', 'select', PAYMENT_STATUS),
      f('customer', 'Customer', 'អតិថិជន', '', '', 'select'),
    ],
    statuses: PAYMENT_STATUS,
    tables: [
      {
        key: 'allocations',
        title: 'Payment Allocations',
        titleKm: 'ការបែងចែកការទូទាត់',
        addLabel: 'Allocate invoice',
        columns: [
          { key: 'targetDocumentNo', label: 'Target Invoice / Bill', labelKm: 'វិក្កយបត្រគោលដៅ' },
          { key: 'targetOutstanding', label: 'Outstanding', labelKm: 'នៅសល់', type: 'number' },
          { key: 'amount', label: 'Allocation Amount', labelKm: 'ចំនួនបែងចែក', type: 'number' },
          { key: 'currency', label: 'Currency', labelKm: 'រូបិយប័ណ្ណ' },
          { key: 'exchangeRate', label: 'Exchange Rate', labelKm: 'អត្រាប្តូរប្រាក់', type: 'number' },
        ],
      },
    ],
  }),

  createModule({
    path: '/finance/job-charges',
    title: 'Job Charges / Cost',
    titleKm: 'ថ្លៃការងារ / ថ្លៃដើម',
    singular: 'Job Charge',
    singularKm: 'ថ្លៃការងារ',
    description: 'Connect jobs with customer revenue, debit notes and supplier expenses.',
    descriptionKm: 'ភ្ជាប់ការងារជាមួយចំណូលអតិថិជន ប័ណ្ណឥណពន្ធ និងថ្លៃអ្នកផ្គត់ផ្គង់។',
    icon: 'i-lucide-layers',
    group: 'finance',
    permission: 'finance.job_charges.view',
    collection: 'jobCharges',
    titleField: 'jobNo',
    kind: 'job-charges',
    columns: [
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('chargeSide', 'Side', 'ភាគី'),
      col('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      col('chargeType', 'Charge Type', 'ប្រភេទថ្លៃ'),
      col('description', 'Description', 'បរិយាយ'),
      col('quantity', 'Qty', 'បរិមាណ'),
      col('unitPrice', 'Unit Price / Cost', 'តម្លៃឯកតា'),
      col('amount', 'Amount', 'ចំនួន'),
      col('currency', 'Currency', 'រូបិយប័ណ្ណ'),
      col('invoiceNo', 'Invoice / Debit Note', 'វិក្កយបត្រ / ប័ណ្ណ'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('chargeSide', 'Customer / Supplier', 'អតិថិជន / អ្នកផ្គត់ផ្គង់', 'General', 'ទូទៅ', 'select', ['Customer', 'Supplier']),
      f('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      f('chargeType', 'Charge Type', 'ប្រភេទថ្លៃ'),
      f('description', 'Description', 'បរិយាយ'),
      f('quantity', 'Quantity', 'បរិមាណ', 'Amounts', 'ចំនួន', 'number'),
      f('unitPrice', 'Unit Price / Cost', 'តម្លៃឯកតា', 'Amounts', 'ចំនួន', 'number'),
      f('amount', 'Amount', 'ចំនួន', 'Amounts', 'ចំនួន', 'number'),
      f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Amounts', 'ចំនួន', 'select', CURRENCIES),
      f('tax', 'Tax', 'ពន្ធ', 'Amounts', 'ចំនួន', 'number'),
      f('invoiceNo', 'Customer Invoice / Debit Note / Supplier Invoice', 'វិក្កយបត្រ / ប័ណ្ណឥណពន្ធ', 'References', 'យោង'),
      f('status', 'Status', 'ស្ថានភាព', 'References', 'យោង', 'select', SERVICE_CHARGE_STATUS),
    ],
    actions: [
      { key: 'saveDraft', label: 'Save Draft', labelKm: 'រក្សាទុកព្រាង', icon: 'i-lucide-save' },
      { key: 'issue', label: 'Issue Charge', labelKm: 'ចេញថ្លៃ', icon: 'i-lucide-badge-check', color: 'success' },
      { key: 'createInvoice', label: 'Create Draft Invoice', labelKm: 'បង្កើតវិក្កយបត្រព្រាង', icon: 'i-lucide-receipt-text', color: 'primary' },
    ],
  }),

  createModule({
    path: '/finance/supplier-costs',
    title: 'Supplier Costs',
    titleKm: 'ថ្លៃអ្នកផ្គត់ផ្គង់',
    singular: 'Supplier Cost',
    singularKm: 'ថ្លៃអ្នកផ្គត់ផ្គង់',
    description: 'Record every supplier expense as an individual job charge, not a spreadsheet column.',
    descriptionKm: 'កត់ត្រាថ្លៃអ្នកផ្គត់ផ្គង់ជាកំណត់ត្រានីមួយៗ មិនមែនជាជួរឈរក្នុងសន្លឹក។',
    icon: 'i-lucide-badge-dollar-sign',
    group: 'finance',
    permission: 'finance.supplier_costs.view',
    collection: 'supplierCosts',
    titleField: 'jobNo',
    columns: [
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      col('chargeType', 'Charge Type', 'ប្រភេទថ្លៃ'),
      col('description', 'Description', 'បរិយាយ'),
      col('quantity', 'Qty', 'បរិមាណ'),
      col('unitCost', 'Unit Cost', 'ថ្លៃឯកតា'),
      col('amount', 'Amount', 'ចំនួន'),
      col('currency', 'Currency', 'រូបិយប័ណ្ណ'),
      col('invoiceNo', 'Supplier Invoice', 'វិក្កយបត្រអ្នកផ្គត់ផ្គង់'),
      col('status', 'Payment Status', 'ស្ថានភាពទូទាត់'),
    ],
    fields: [
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      f('chargeType', 'Charge Type', 'ប្រភេទថ្លៃ'),
      f('description', 'Description', 'បរិយាយ'),
      f('quantity', 'Quantity', 'បរិមាណ', 'Cost', 'ថ្លៃ', 'number'),
      f('unitCost', 'Unit Cost', 'ថ្លៃឯកតា', 'Cost', 'ថ្លៃ', 'number'),
      f('amount', 'Amount', 'ចំនួន', 'Cost', 'ថ្លៃ', 'number'),
      f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Cost', 'ថ្លៃ', 'select', CURRENCIES),
      f('invoiceNo', 'Supplier Invoice', 'វិក្កយបត្រអ្នកផ្គត់ផ្គង់'),
      f('status', 'Payment Status', 'ស្ថានភាពទូទាត់', 'Cost', 'ថ្លៃ', 'select', PAYMENT_STATUS),
    ],
  }),

  createModule({
    path: '/finance/supplier-payments',
    title: 'Supplier Payments',
    titleKm: 'ការទូទាត់អ្នកផ្គត់ផ្គង់',
    singular: 'Supplier Payment',
    singularKm: 'ការទូទាត់អ្នកផ្គត់ផ្គង់',
    description: 'Pay supplier invoices as individual records instead of one column per supplier.',
    descriptionKm: 'ទូទាត់វិក្កយបត្រអ្នកផ្គត់ផ្គង់ជាកំណត់ត្រានីមួយៗ។',
    icon: 'i-lucide-landmark',
    group: 'finance',
    permission: 'finance.supplier_payments.view',
    collection: 'supplierPayments',
    titleField: 'paymentNo',
    columns: [
      col('paymentNo', 'Supplier Payment No.', 'លេខទូទាត់'),
      col('date', 'Date', 'កាលបរិច្ឆេទ'),
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      col('invoiceNo', 'Supplier Invoice No.', 'លេខវិក្កយបត្រ'),
      col('service', 'Service / Charge', 'សេវា / ថ្លៃ'),
      col('amount', 'Amount', 'ចំនួន'),
      col('currency', 'Currency', 'រូបិយប័ណ្ណ'),
      col('paymentMethod', 'Payment Method', 'វិធីទូទាត់'),
      col('paidBy', 'Paid By', 'អ្នកបង់'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('paymentNo', 'Supplier Payment No.', 'លេខទូទាត់អ្នកផ្គត់ផ្គង់'),
      f('date', 'Date', 'កាលបរិច្ឆេទ', 'Payment', 'ការទូទាត់', 'date'),
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      f('invoiceNo', 'Supplier Invoice No.', 'លេខវិក្កយបត្រអ្នកផ្គត់ផ្គង់'),
      f('service', 'Service / Charge', 'សេវា / ថ្លៃ'),
      f('amount', 'Amount', 'ចំនួន', 'Payment', 'ការទូទាត់', 'number'),
      f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Payment', 'ការទូទាត់', 'select', CURRENCIES),
      f('paymentMethod', 'Payment Method', 'វិធីទូទាត់', 'Payment', 'ការទូទាត់', 'select', PAYMENT_METHODS),
      f('referenceNo', 'Payment Reference', 'លេខយោងទូទាត់', 'Payment', 'ការទូទាត់'),
      f('paidBy', 'Paid By', 'អ្នកបង់', 'Payment', 'ការទូទាត់'),
      f('status', 'Status', 'ស្ថានភាព', 'Payment', 'ការទូទាត់', 'select', PAYMENT_STATUS),
      f('remark', 'Remark', 'កំណត់សម្គាល់', 'Payment', 'ការទូទាត់', 'textarea'),
    ],
    filters: [
      f('status', 'Status', 'ស្ថានភាព', '', '', 'select', PAYMENT_STATUS),
      f('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់', '', '', 'select'),
    ],
    statuses: PAYMENT_STATUS,
  }),

  createModule({
    path: '/finance/accounts-receivable',
    title: 'Accounts Receivable',
    titleKm: 'គណនីត្រូវទទួល',
    singular: 'Receivable',
    singularKm: 'គណនីត្រូវទទួល',
    description: 'Monitor customer invoices, due dates and days outstanding.',
    descriptionKm: 'តាមដានវិក្កយបត្រអតិថិជន ថ្ងៃផុតកំណត់ និងថ្ងៃនៅសល់។',
    icon: 'i-lucide-circle-dollar-sign',
    group: 'finance',
    permission: 'finance.accounts_receivable.view',
    collection: 'receivables',
    titleField: 'invoiceNo',
    readOnly: true,
    columns: [
      col('customer', 'Customer', 'អតិថិជន'),
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('invoiceNo', 'Debit Note / Invoice No.', 'លេខប័ណ្ណ / វិក្កយបត្រ'),
      col('invoiceDate', 'Invoice Date', 'កាលបរិច្ឆេទវិក្កយបត្រ'),
      col('dueDate', 'Due Date', 'ថ្ងៃផុតកំណត់'),
      col('amount', 'Invoice Amount', 'ចំនួនវិក្កយបត្រ'),
      col('received', 'Received', 'បានទទួល'),
      col('outstanding', 'Outstanding', 'នៅសល់'),
      col('daysOutstanding', 'Days Outstanding', 'ថ្ងៃនៅសល់'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('customer', 'Customer', 'អតិថិជន'),
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('invoiceNo', 'Debit Note / Invoice No.', 'លេខប័ណ្ណ / វិក្កយបត្រ'),
      f('invoiceDate', 'Invoice Date', 'កាលបរិច្ឆេទវិក្កយបត្រ', 'Invoice', 'វិក្កយបត្រ', 'date'),
      f('dueDate', 'Due Date', 'ថ្ងៃផុតកំណត់', 'Invoice', 'វិក្កយបត្រ', 'date'),
      f('amount', 'Invoice Amount', 'ចំនួនវិក្កយបត្រ', 'Amounts', 'ចំនួន', 'number'),
      f('received', 'Received', 'បានទទួល', 'Amounts', 'ចំនួន', 'number'),
      f('outstanding', 'Outstanding', 'នៅសល់', 'Amounts', 'ចំនួន', 'number'),
      f('daysOutstanding', 'Days Outstanding', 'ថ្ងៃនៅសល់', 'Amounts', 'ចំនួន', 'number'),
      f('status', 'Status', 'ស្ថានភាព', 'Amounts', 'ចំនួន', 'select', PAYMENT_STATUS),
    ],
    filters: [f('status', 'Status', 'ស្ថានភាព', '', '', 'select', PAYMENT_STATUS)],
    statuses: PAYMENT_STATUS,
  }),

  createModule({
    path: '/finance/accounts-payable',
    title: 'Accounts Payable',
    titleKm: 'គណនីត្រូវបង់',
    singular: 'Payable',
    singularKm: 'គណនីត្រូវបង់',
    description: 'Monitor supplier invoices, payments and outstanding balances.',
    descriptionKm: 'តាមដានវិក្កយបត្រអ្នកផ្គត់ផ្គង់ ការទូទាត់ និងសមតុល្យនៅសល់។',
    icon: 'i-lucide-wallet-cards',
    group: 'finance',
    permission: 'finance.accounts_payable.view',
    collection: 'payables',
    titleField: 'invoiceNo',
    readOnly: true,
    columns: [
      col('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('invoiceNo', 'Supplier Invoice', 'វិក្កយបត្រអ្នកផ្គត់ផ្គង់'),
      col('invoiceDate', 'Invoice Date', 'កាលបរិច្ឆេទ'),
      col('dueDate', 'Due Date', 'ថ្ងៃផុតកំណត់'),
      col('amount', 'Amount', 'ចំនួន'),
      col('paid', 'Paid Amount', 'បានបង់'),
      col('outstanding', 'Outstanding', 'នៅសល់'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('supplier', 'Supplier', 'អ្នកផ្គត់ផ្គង់'),
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('invoiceNo', 'Supplier Invoice', 'វិក្កយបត្រអ្នកផ្គត់ផ្គង់'),
      f('invoiceDate', 'Invoice Date', 'កាលបរិច្ឆេទ', 'Invoice', 'វិក្កយបត្រ', 'date'),
      f('dueDate', 'Due Date', 'ថ្ងៃផុតកំណត់', 'Invoice', 'វិក្កយបត្រ', 'date'),
      f('amount', 'Amount', 'ចំនួន', 'Amounts', 'ចំនួន', 'number'),
      f('paid', 'Paid Amount', 'បានបង់', 'Amounts', 'ចំនួន', 'number'),
      f('outstanding', 'Outstanding', 'នៅសល់', 'Amounts', 'ចំនួន', 'number'),
      f('status', 'Status', 'ស្ថានភាព', 'Amounts', 'ចំនួន', 'select', PAYMENT_STATUS),
    ],
    filters: [f('status', 'Status', 'ស្ថានភាព', '', '', 'select', PAYMENT_STATUS)],
    statuses: PAYMENT_STATUS,
  }),

  createModule({
    path: '/finance/job-profitability',
    title: 'Job Profitability',
    titleKm: 'ប្រាក់ចំណេញតាមការងារ',
    singular: 'Profitability Record',
    singularKm: 'កំណត់ត្រាប្រាក់ចំណេញ',
    description: 'Profit = Customer Revenue − Total Supplier / Operational Cost.',
    descriptionKm: 'ប្រាក់ចំណេញ = ចំណូលអតិថិជន − ថ្លៃអ្នកផ្គត់ផ្គង់ / ប្រតិបត្តិការ។',
    icon: 'i-lucide-chart-no-axes-combined',
    group: 'finance',
    permission: 'finance.job_profitability.view',
    collection: 'profitability',
    titleField: 'jobNo',
    readOnly: true,
    columns: [
      col('jobNo', 'Job No.', 'លេខការងារ'),
      col('customer', 'Customer', 'អតិថិជន'),
      col('direction', 'Import / Export', 'នាំចូល / នាំចេញ'),
      col('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      col('revenue', 'Revenue', 'ចំណូល'),
      col('cambodiaCost', 'Cambodia Cost', 'ថ្លៃកម្ពុជា'),
      col('vietnamCost', 'Vietnam Cost', 'ថ្លៃវៀតណាម'),
      col('truckingCost', 'Trucking Cost', 'ថ្លៃឡាន'),
      col('customsCost', 'Customs Cost', 'ថ្លៃគយ'),
      col('otherCost', 'Other Cost', 'ថ្លៃផ្សេង'),
      col('totalCost', 'Total Cost', 'ថ្លៃសរុប'),
      col('profit', 'Profit', 'ប្រាក់ចំណេញ'),
      col('margin', 'Margin %', 'អត្រា %'),
    ],
    fields: [
      f('jobNo', 'Job No.', 'លេខការងារ'),
      f('customer', 'Customer', 'អតិថិជន'),
      f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', 'General', 'ទូទៅ', 'select', DIRECTIONS),
      f('containerNo', 'Container No.', 'លេខកុងតឺន័រ'),
      f('revenue', 'Revenue', 'ចំណូល', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('cambodiaCost', 'Cambodia Cost', 'ថ្លៃកម្ពុជា', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('vietnamCost', 'Vietnam Cost', 'ថ្លៃវៀតណាម', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('truckingCost', 'Trucking Cost', 'ថ្លៃឡាន', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('customsCost', 'Customs Cost', 'ថ្លៃគយ', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('otherCost', 'Other Cost', 'ថ្លៃផ្សេង', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('totalCost', 'Total Cost', 'ថ្លៃសរុប', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('profit', 'Profit', 'ប្រាក់ចំណេញ', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
      f('margin', 'Margin %', 'អត្រា %', 'Profitability', 'ប្រាក់ចំណេញ', 'number'),
    ],
    filters: [f('direction', 'Import / Export', 'នាំចូល / នាំចេញ', '', '', 'select', DIRECTIONS)],
  }),

  ...([
    ['/master-data/zones', 'Zones', 'តំបន់', 'Zone', 'តំបន់', 'i-lucide-map', 'zones', [['code', 'Zone Code', 'លេខកូដតំបន់'], ['name', 'Zone Name', 'ឈ្មោះតំបន់'], ['status', 'Status', 'ស្ថានភាព']]],
    ['/master-data/locations', 'Ports / Locations', 'កំពង់ផែ / ទីតាំង', 'Location', 'ទីតាំង', 'i-lucide-map-pin', 'locations', [['code', 'Location Code', 'លេខកូដ'], ['name', 'Location Name', 'ឈ្មោះ'], ['country', 'Country', 'ប្រទេស'], ['category', 'Location Type', 'ប្រភេទទីតាំង'], ['status', 'Status', 'ស្ថានភាព']]],
    ['/master-data/equipment-types', 'Container / Truck Types', 'ប្រភេទកុងតឺន័រ / ឡាន', 'Equipment Type', 'ប្រភេទឧបករណ៍', 'i-lucide-box', 'equipmentTypes', [['code', 'Code', 'លេខកូដ'], ['name', 'Name', 'ឈ្មោះ'], ['category', 'Category', 'ប្រភេទ'], ['status', 'Status', 'ស្ថានភាព']]],
    ['/master-data/directions', 'Import / Export Types', 'ប្រភេទនាំចូល / នាំចេញ', 'Direction', 'ទិសដៅ', 'i-lucide-arrow-left-right', 'directions', [['code', 'Code', 'លេខកូដ'], ['name', 'Name', 'ឈ្មោះ'], ['status', 'Status', 'ស្ថានភាព']]],
    ['/master-data/charge-types', 'Charge Types', 'ប្រភេទថ្លៃ', 'Charge Type', 'ប្រភេទថ្លៃ', 'i-lucide-tags', 'chargeTypes', [['code', 'Charge Code', 'លេខកូដថ្លៃ'], ['name', 'Charge Name', 'ឈ្មោះថ្លៃ'], ['category', 'Category', 'ប្រភេទ'], ['unit', 'Default Unit', 'ឯកតាលំនាំដើម'], ['status', 'Status', 'ស្ថានភាព']]],
    ['/master-data/currencies', 'Currencies', 'រូបិយប័ណ្ណ', 'Currency', 'រូបិយប័ណ្ណ', 'i-lucide-coins', 'currencies', [['code', 'Currency Code', 'លេខកូដ'], ['name', 'Currency Name', 'ឈ្មោះ'], ['exchangeRate', 'Exchange Rate', 'អត្រាប្តូរ'], ['status', 'Status', 'ស្ថានភាព']]],
  ] as Array<[string, string, string, string, string, string, string, Array<[string, string, string]>]>).map(([path, title, titleKm, singular, singularKm, icon, collection, columns]) =>
    createModule({
      path,
      title,
      titleKm,
      singular,
      singularKm,
      description: `Manage reusable ${title.toLowerCase()} used throughout freight forms.`,
      descriptionKm: `គ្រប់គ្រង${titleKm}សម្រាប់ប្រើក្នុងទម្រង់ដឹកជញ្ជូន។`,
      icon,
      group: 'master',
      permission: `master.${collection.replace(/[A-Z]/g, m => `_${m.toLowerCase()}`).replace(/^_/, '')}.view`.replace('equipment_types', 'equipment_types'),
      collection,
      titleField: 'name',
      columns: columns.map(([key, label, labelKm]) => col(key, label, labelKm)),
      fields: columns.map(([key, label, labelKm]) => {
        if (key === 'status') return f(key, label, labelKm, 'General', 'ទូទៅ', 'select', ACTIVE_STATUS)
        if (key === 'category' && collection === 'locations') return f(key, label, labelKm, 'General', 'ទូទៅ', 'select', LOCATION_TYPES)
        if (key === 'category' && collection === 'equipmentTypes') return f(key, label, labelKm, 'General', 'ទូទៅ', 'select', EQUIPMENT_CATEGORIES)
        if (key === 'category' && collection === 'chargeTypes') return f(key, label, labelKm, 'General', 'ទូទៅ', 'select', CHARGE_CATEGORIES)
        if (key === 'country') return f(key, label, labelKm, 'General', 'ទូទៅ', 'select', COUNTRIES)
        if (key === 'exchangeRate') return f(key, label, labelKm, 'General', 'ទូទៅ', 'number')
        return f(key, label, labelKm)
      }),
    }),
  ),

  createModule({
    path: '/administration/users',
    title: 'Users',
    titleKm: 'អ្នកប្រើប្រាស់',
    singular: 'User',
    singularKm: 'អ្នកប្រើ',
    description: 'Manage staff access by role and department.',
    descriptionKm: 'គ្រប់គ្រងសិទ្ធិបុគ្គលិកតាមតួនាទី និងនាយកដ្ឋាន។',
    icon: 'i-lucide-users',
    group: 'admin',
    permission: 'admin.users.view',
    collection: 'users',
    titleField: 'displayName',
    columns: [
      col('userCode', 'User Code', 'លេខកូដអ្នកប្រើ'),
      col('username', 'Username', 'ឈ្មោះអ្នកប្រើ'),
      col('displayName', 'Display Name', 'ឈ្មោះបង្ហាញ'),
      col('email', 'Email', 'អ៊ីមែល'),
      col('phone', 'Phone', 'ទូរស័ព្ទ'),
      col('status', 'Status', 'ស្ថានភាព'),
      col('defaultBranch', 'Default Branch', 'សាខាលំនាំដើម'),
      col('lastLogin', 'Last Login', 'ចូលចុងក្រោយ'),
    ],
    fields: [
      f('userCode', 'User Code', 'លេខកូដអ្នកប្រើ', 'General', 'ទូទៅ'),
      f('username', 'Username', 'ឈ្មោះអ្នកប្រើ', 'General', 'ទូទៅ'),
      f('displayName', 'Display Name', 'ឈ្មោះបង្ហាញ', 'General', 'ទូទៅ'),
      f('email', 'Email', 'អ៊ីមែល', 'General', 'ទូទៅ'),
      f('telegram', 'Telegram', 'តេលេក្រាម', 'General', 'ទូទៅ'),
      f('organization', 'Organization', 'អង្គភាព', 'General', 'ទូទៅ'),
      f('branch', 'Branch', 'សាខា', 'General', 'ទូទៅ'),
      f('role', 'Role Name', 'ឈ្មោះតួនាទី', 'General', 'ទូទៅ'),
      f('status', 'Status', 'ស្ថានភាព', 'General', 'ទូទៅ', 'select', ACTIVE_STATUS),
    ],
  }),

  createModule({
    path: '/administration/roles',
    title: 'Roles & Permissions',
    titleKm: 'តួនាទី និងសិទ្ធិ',
    singular: 'Role',
    singularKm: 'តួនាទី',
    description: 'Define module permissions for freight-forwarding teams.',
    descriptionKm: 'កំណត់សិទ្ធិម៉ូឌុលសម្រាប់ក្រុមដឹកជញ្ជូន។',
    icon: 'i-lucide-shield-check',
    group: 'admin',
    permission: 'admin.roles.view',
    collection: 'roles',
    documentForm: 'roles',
    titleField: 'name',
    columns: [
      col('name', 'Role name', 'ឈ្មោះតួនាទី'),
      col('userCount', 'Users', 'អ្នកប្រើ'),
      col('permissionCount', 'Permissions', 'សិទ្ធិ'),
      col('status', 'Status', 'ស្ថានភាព'),
    ],
    fields: [
      f('code', 'Code', 'លេខកូដ', 'Main information', 'ព័ត៌មានទូទៅ', 'text', undefined, { required: true }),
      f('name', 'Role name', 'ឈ្មោះតួនាទី', 'Main information', 'ព័ត៌មានទូទៅ', 'text', undefined, { required: true }),
      f('status', 'Status', 'ស្ថានភាព', 'Main information', 'ព័ត៌មានទូទៅ', 'select', ACTIVE_STATUS, { colSpan: 2 }),
      f('description', 'Description', 'បរិយាយ', 'Main information', 'ព័ត៌មានទូទៅ', 'textarea', undefined, { colSpan: 2 }),
    ],
  }),

  ...lcsReferenceModules,

  createModule({
    path: '/administration/audit-logs',
    title: 'Audit Logs',
    titleKm: 'កំណត់ហេតុសវនកម្ម',
    singular: 'Audit Log',
    singularKm: 'កំណត់ហេតុ',
    description: 'Trace create, update, approve, send and payment actions across the system.',
    descriptionKm: 'តាមដានសកម្មភាពបង្កើត កែប្រែ អនុម័ត ផ្ញើ និងទូទាត់។',
    icon: 'i-lucide-scroll-text',
    group: 'admin',
    permission: 'admin.audit_logs.view',
    collection: 'auditLogs',
    titleField: 'action',
    readOnly: true,
    tableOnly: true,
    columns: [
      col('occurredAt', 'Date / Time', 'កាលបរិច្ឆេទ / ពេលវេលា'),
      col('user', 'User', 'អ្នកប្រើ'),
      col('eventType', 'Event Type', 'ប្រភេទព្រឹត្តិការណ៍'),
      col('action', 'Action', 'សកម្មភាព'),
      col('entityType', 'Entity Type', 'ប្រភេទអង្គភាពទិន្នន័យ'),
      col('entity', 'Entity', 'អង្គភាពទិន្នន័យ'),
      col('organizationName', 'Organization', 'អង្គភាព'),
      col('branchName', 'Branch', 'សាខា'),
      col('result', 'Result', 'លទ្ធផល'),
      col('reason', 'Reason', 'មូលហេតុ'),
      col('requestId', 'Request ID', 'លេខសំណើ'),
    ],
    fields: [
      f('occurredAt', 'Time', 'ពេលវេលា', 'Log', 'កំណត់ហេតុ', 'datetime'),
      f('user', 'User', 'អ្នកប្រើ', 'Log', 'កំណត់ហេតុ'),
      f('eventType', 'Event Type', 'ប្រភេទព្រឹត្តិការណ៍', 'Log', 'កំណត់ហេតុ'),
      f('action', 'Action', 'សកម្មភាព', 'Log', 'កំណត់ហេតុ'),
      f('entityType', 'Entity Type', 'ប្រភេទអង្គភាពទិន្នន័យ', 'Entity', 'អង្គភាពទិន្នន័យ'),
      f('entity', 'Entity', 'អង្គភាពទិន្នន័យ', 'Entity', 'អង្គភាពទិន្នន័យ'),
      f('organizationName', 'Organization', 'អង្គភាព', 'Scope', 'វិសាលភាព'),
      f('branchName', 'Branch', 'សាខា', 'Scope', 'វិសាលភាព'),
      f('result', 'Result', 'លទ្ធផល', 'Result', 'លទ្ធផល'),
      f('reason', 'Reason', 'មូលហេតុ', 'Result', 'លទ្ធផល', 'textarea'),
      f('requestId', 'Request ID', 'លេខសំណើ', 'Traceability', 'ការតាមដាន'),
      f('correlationId', 'Correlation ID', 'លេខទំនាក់ទំនង', 'Traceability', 'ការតាមដាន'),
      f('beforeData', 'Before Data', 'ទិន្នន័យមុន', 'Data', 'ទិន្នន័យ', 'textarea'),
      f('afterData', 'After Data', 'ទិន្នន័យបន្ទាប់', 'Data', 'ទិន្នន័យ', 'textarea'),
      f('metadata', 'Metadata', 'មេតាទិន្នន័យ', 'Data', 'ទិន្នន័យ', 'textarea'),
    ],
    filters: [
      f('user', 'Actor', 'អ្នកប្រើ', '', ''),
      f('eventType', 'Event Type', 'ប្រភេទព្រឹត្តិការណ៍', '', ''),
      f('entityType', 'Entity Type', 'ប្រភេទអង្គភាពទិន្នន័យ', '', ''),
      f('organizationName', 'Organization', 'អង្គភាព', '', ''),
      f('branchName', 'Branch', 'សាខា', '', ''),
      f('result', 'Result', 'លទ្ធផល', '', '', 'select', ['SUCCESS', 'FAILED', 'DENIED']),
    ],
  }),

  createModule({
    path: '/reports',
    title: 'General Ledger',
    titleKm: 'សៀវភៅគណនី',
    singular: 'Ledger Entry',
    singularKm: 'ជួរគណនី',
    description: 'All finance postings in one ERPNext-style general ledger.',
    descriptionKm: 'កំណត់ត្រាហិរញ្ញវត្ថុទាំងអស់ក្នុងសៀវភៅគណនីតែមួយ។',
    icon: 'i-lucide-book-open-text',
    group: 'reports',
    permission: 'reports.view',
    collection: 'reports',
    titleField: 'voucherNo',
    kind: 'reports',
    canCreate: false,
    readOnly: true,
    columns: [
      col('postingDate', 'Posting Date', 'កាលបរិច្ឆេទ'),
      col('account', 'Account', 'គណនី'),
      col('debit', 'Debit', 'ឥណពន្ធ'),
      col('credit', 'Credit', 'ឥណទាន'),
      col('voucherNo', 'Voucher No', 'លេខប័ណ្ណ'),
    ],
    fields: [f('account', 'Account', 'គណនី')],
  }),
]

// Canonical routes from freight-forwarder-v1. Legacy definitions are retained only as
// reusable schemas for the canonical pages; the legacy page routes are not exposed.
const quotationModule = freightModules.find(item => item.path === '/sales/quotations')
const jobsModule = freightModules.find(item => item.path === '/operations/jobs')
const chargesModule = freightModules.find(item => item.path === '/finance/job-charges')
const invoicesModule = freightModules.find(item => item.path === '/finance/debit-notes')

if (quotationModule) freightModules.push({
  ...quotationModule,
  path: '/quotations',
  documentForm: 'quotation',
  columns: [
    col('quotationNo', 'Quotation No.', 'លេខសម្រង់'), col('customer', 'Customer', 'អតិថិជន'), col('branchName', 'Branch', 'សាខា'),
    col('direction', 'Trade Directions', 'ទិសដៅពាណិជ្ជកម្ម', { labelKey: 'freight.ui.cols.direction' }), col('revisionNo', 'Current Revision', 'កំណែបច្ចុប្បន្ន'), col('date', 'Quotation Date', 'កាលបរិច្ឆេទសម្រង់'),
    col('validUntil', 'Valid Until', 'មានសុពលភាពដល់'), col('currency', 'Currency', 'រូបិយប័ណ្ណ'), col('total', 'Total', 'សរុប'), col('status', 'Status', 'ស្ថានភាព'), col('createdAt', 'Created At', 'បង្កើតនៅ'),
  ],
  fields: [
    f('quotationNo', 'Quotation No.', 'លេខសម្រង់', 'Header', 'ក្បាល', 'text', undefined, { required: true, computed: true }),
    f('customer', 'Customer', 'អតិថិជន', 'Header', 'ក្បាល', 'text', undefined, { required: true }), f('branchName', 'Branch', 'សាខា', 'Header', 'ក្បាល', 'text', undefined, { required: true }),
    f('direction', 'Trade Directions', 'ទិសដៅពាណិជ្ជកម្ម', 'Header', 'ក្បាល', 'select', DIRECTIONS, { required: true, labelKey: 'freight.ui.cols.direction' }), f('revisionNo', 'Revision No.', 'លេខកំណែ', 'Header', 'ក្បាល', 'number', undefined, { computed: true }),
    f('date', 'Quotation Date', 'កាលបរិច្ឆេទសម្រង់', 'Header', 'ក្បាល', 'date', undefined, { required: true }), f('validUntil', 'Valid Until', 'មានសុពលភាពដល់', 'Header', 'ក្បាល', 'date'),
    f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Header', 'ក្បាល', 'select', CURRENCIES, { required: true }), f('description', 'Description', 'បរិយាយ', 'Header', 'ក្បាល', 'textarea', undefined, { colSpan: 2 }), f('notes', 'Notes', 'កំណត់សម្គាល់', 'Header', 'ក្បាល', 'textarea', undefined, { colSpan: 2 }),
    f('status', 'Status', 'ស្ថានភាព', 'Header', 'ក្បាល', 'select', QUOTATION_STATUS),
    f('subtotal', 'Subtotal', 'សរុបរង', 'Totals', 'សរុប', 'number', undefined, { computed: true }), f('discount', 'Discount', 'បញ្ចុះតម្លៃ', 'Totals', 'សរុប', 'number', undefined, { computed: true }), f('tax', 'Tax', 'ពន្ធ', 'Totals', 'សរុប', 'number', undefined, { computed: true }), f('total', 'Total', 'សរុប', 'Totals', 'សរុប', 'number', undefined, { computed: true }),
  ],
  tables: [
    { key: 'places', title: 'Route', titleKm: 'ផ្លូវ', addLabel: 'Add Route', columns: [
      { key: 'placeRole', label: 'Role', labelKm: 'តួនាទី', type: 'select', options: PLACE_ROLES, required: true }, { key: 'place', label: 'Place', labelKm: 'ទីកន្លែង', required: true }, { key: 'plannedActual', label: 'Planned / Actual', labelKm: 'គ្រោង / ពិត', type: 'date' }, { key: 'notes', label: 'Notes', labelKm: 'កំណត់សម្គាល់' },
    ] },
    { key: 'containerRequirements', title: 'Containers', titleKm: 'កុងតឺន័រ', addLabel: 'Add Container', columns: [
      { key: 'containerType', label: 'Container Type', labelKm: 'ប្រភេទកុងតឺន័រ', type: 'select', options: CONTAINER_TYPES, required: true }, { key: 'quantity', label: 'Qty', labelKm: 'បរិមាណ', type: 'number', required: true }, { key: 'description', label: 'Description', labelKm: 'បរិយាយ' },
    ] },
    { key: 'pricingLines', title: 'Pricing', titleKm: 'តម្លៃ', addLabel: 'Add Pricing Line', columns: [
      { key: 'feeType', label: 'Service / Fee', labelKm: 'សេវា / ថ្លៃ', required: true }, { key: 'containerRequirement', label: 'Container', labelKm: 'កុងតឺន័រ' },
      { key: 'quantity', label: 'Qty', labelKm: 'បរិមាណ', type: 'number', required: true }, { key: 'unitPrice', label: 'Unit Price', labelKm: 'តម្លៃឯកតា', type: 'number', required: true },
      {
        key: 'lineTotal',
        label: 'Line Total',
        labelKm: 'សរុបជួរ',
        labelKey: 'freight.ui.lineTotal',
        type: 'number',
        computed: true,
        inlineFields: [
          { key: 'discountAmount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
          { key: 'taxAmount', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
        ],
      },
    ] },
    { key: 'attachments', title: 'Files', titleKm: 'ឯកសារ', addLabel: 'Upload File', addLabelKey: 'freight.ui.uploadFile', kind: 'files', columns: FILE_ATTACHMENT_COLUMNS },
    { key: 'revisionHistory', title: 'Revisions', titleKm: 'កំណែ', columns: [
      { key: 'revisionNo', label: 'Rev', labelKm: 'កំណែ' }, { key: 'status', label: 'Status', labelKm: 'ស្ថានភាព' }, { key: 'quotationDate', label: 'Date', labelKm: 'កាលបរិច្ឆេទ', type: 'date' }, { key: 'validUntil', label: 'Valid Until', labelKm: 'មានសុពលភាពដល់', type: 'date' }, { key: 'total', label: 'Total', labelKm: 'សរុប', type: 'number' }, { key: 'createdBy', label: 'Created By', labelKm: 'បង្កើតដោយ' },
    ] },
  ],
  actions: [
    { key: 'saveDraft', label: 'Save Draft', labelKm: 'រក្សាទុកព្រាង', icon: 'i-lucide-save' },
    { key: 'submit', label: 'Submit', labelKm: 'ដាក់ស្នើ', icon: 'i-lucide-check-circle', color: 'primary' },
    { key: 'send', label: 'Send', labelKm: 'ផ្ញើ', icon: 'i-lucide-send' },
    { key: 'createRevision', label: 'Create Revision', labelKm: 'បង្កើតកំណែ', icon: 'i-lucide-git-branch' },
    { key: 'accept', label: 'Accept', labelKm: 'ទទួលយក', icon: 'i-lucide-check', color: 'success' },
    { key: 'reject', label: 'Reject', labelKm: 'បដិសេធ', icon: 'i-lucide-x', color: 'error' },
    { key: 'convertJob', label: 'Convert to Service Order', labelKm: 'បម្លែងទៅបញ្ជាសេវាកម្ម', icon: 'i-lucide-arrow-right', color: 'primary' },
    { key: 'cancel', label: 'Cancel', labelKm: 'បោះបង់', icon: 'i-lucide-ban', color: 'warning' },
  ],
  filters: [f('customer', 'Customer', 'អតិថិជន', '', '', 'select'), f('branchName', 'Branch', 'សាខា', '', '', 'select'), f('direction', 'Trade Directions', 'ទិសដៅពាណិជ្ជកម្ម', '', '', 'select', DIRECTIONS, { labelKey: 'freight.ui.cols.direction' })],
})

if (jobsModule) freightModules.push({
  ...jobsModule,
  path: '/service-orders',
  permission: 'operations.service_orders.view',
  title: 'Service Orders',
  titleKm: 'បញ្ជាសេវាកម្ម',
  titleKey: 'freight.pages.serviceOrders',
  singular: 'Service Order',
  singularKm: 'បញ្ជាសេវាកម្ម',
  description: 'Branch-scoped operational orders, containers, components, charges, documents and audit history.',
  descriptionKm: 'បញ្ជាប្រតិបត្តិការតាមសាខា កុងតឺន័រ សមាសភាគ ថ្លៃ ឯកសារ និងប្រវត្តិសវនកម្ម។',
  columns: [
    col('jobNo', 'Job No.', 'លេខការងារ', { labelKey: 'freight.ui.cols.jobNo' }),
    col('customer', 'Customer', 'អតិថិជន', { labelKey: 'freight.ui.cols.customer' }),
    col('direction', 'Trade Directions', 'ទិសដៅពាណិជ្ជកម្ម', { labelKey: 'freight.ui.cols.direction' }),
    col('branchName', 'Branch', 'សាខា', { labelKey: 'freight.ui.branchCol' }),
    col('containersCount', 'Containers', 'កុងតឺន័រ', { labelKey: 'freight.jobSections.containers' }),
    col('tasksProgress', 'Documents', 'ឯកសារ', { labelKey: 'freight.jobSections.documents' }),
    col('chargesTotal', 'Total Charges', 'ថ្លៃសរុប', { labelKey: 'freight.ui.totalCharges' }),
    col('workflowStatus', 'Status', 'ស្ថានភាព', { labelKey: 'freight.ui.status' }),
  ],
  fields: [
    ...jobsModule.fields,
    f('branchName', 'Branch', 'សាខា', 'Job Information', 'ព័ត៌មានការងារ'), f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Job Information', 'ព័ត៌មានការងារ', 'select', CURRENCIES), f('description', 'Description', 'បរិយាយ', 'Job Information', 'ព័ត៌មានការងារ', 'textarea', undefined, { colSpan: 2 }), f('createdBy', 'Created By', 'បង្កើតដោយ', 'Audit', 'សវនកម្ម', 'text', undefined, { computed: true }), f('createdAt', 'Created At', 'បង្កើតនៅ', 'Audit', 'សវនកម្ម', 'datetime', undefined, { computed: true }),
  ],
  filters: [
    f('customer', 'Customer', 'អតិថិជន', '', '', 'select', undefined, { labelKey: 'freight.ui.cols.customer' }),
    f('branchName', 'Branch', 'សាខា', '', '', 'select', undefined, { labelKey: 'freight.ui.branchCol' }),
    f('direction', 'Trade Directions', 'ទិសដៅពាណិជ្ជកម្ម', '', '', 'select', DIRECTIONS, { labelKey: 'freight.ui.cols.direction' }),
  ],
  statuses: JOB_WORKFLOW_STATUS,
  actions: [
    { key: 'openJob', label: 'Open', labelKm: 'បើក', icon: 'i-lucide-folder-open' },
    { key: 'start', label: 'Start', labelKm: 'ចាប់ផ្តើម', icon: 'i-lucide-play' },
    { key: 'complete', label: 'Complete', labelKm: 'បញ្ចប់', icon: 'i-lucide-check-circle-2' },
    { key: 'hold', label: 'Put On Hold', labelKm: 'ផ្អាក', icon: 'i-lucide-pause' },
    { key: 'resume', label: 'Resume', labelKm: 'បន្ត', icon: 'i-lucide-play' },
    { key: 'addCharge', label: 'Add charge', labelKm: 'បន្ថែមថ្លៃ', icon: 'i-lucide-receipt' },
    { key: 'close', label: 'Close', labelKm: 'បិទ', icon: 'i-lucide-lock' },
    { key: 'cancel', label: 'Cancel', labelKm: 'បោះបង់', icon: 'i-lucide-ban', color: 'warning' },
  ],
})

if (chargesModule) freightModules.push({
  ...chargesModule,
  path: '/service-charges',
  documentForm: 'charges',
  permission: 'finance.service_charges.view',
  title: 'Service Charges',
  titleKm: 'ថ្លៃសេវាកម្ម',
  singular: 'Service Charge',
  singularKm: 'ថ្លៃសេវាកម្ម',
  description: 'Informational customer charges that do not post accounting until explicitly converted and posted.',
  descriptionKm: 'ថ្លៃព័ត៌មានអតិថិជនដែលមិនចុះគណនី រហូតដល់បម្លែង និងចុះបញ្ជីដោយច្បាស់លាស់។',
  titleField: 'chargeNo',
  columns: [
    col('chargeNo', 'Charge No.', 'លេខថ្លៃ'), col('jobNo', 'Service Order', 'បញ្ជាសេវាកម្ម'), col('customer', 'Customer', 'អតិថិជន'), col('branchName', 'Branch', 'សាខា'), col('documentType', 'Document Type', 'ប្រភេទឯកសារ'), col('documentDate', 'Document Date', 'កាលបរិច្ឆេទ'), col('currency', 'Currency', 'រូបិយប័ណ្ណ'), col('subtotal', 'Subtotal', 'សរុបរង'), col('discount', 'Discount', 'បញ្ចុះតម្លៃ'), col('tax', 'Tax', 'ពន្ធ'), col('total', 'Total', 'សរុប'), col('status', 'Status', 'ស្ថានភាព'), col('invoiceNo', 'Invoice', 'វិក្កយបត្រ'), col('createdBy', 'Created By', 'បង្កើតដោយ'), col('createdAt', 'Created At', 'បង្កើតនៅ'),
  ],
  fields: [
    f('chargeNo', 'Charge No.', 'លេខថ្លៃ', 'General', 'ទូទៅ', 'text', undefined, { required: true, computed: true }), f('documentDate', 'Document Date', 'កាលបរិច្ឆេទ', 'General', 'ទូទៅ', 'date', undefined, { required: true }), f('documentType', 'Document Type', 'ប្រភេទឯកសារ', 'General', 'ទូទៅ', 'select', ['SERVICE_NOTE', 'DEBIT_NOTE', 'PRO_FORMA']), f('status', 'Status', 'ស្ថានភាព', 'General', 'ទូទៅ', 'select', SERVICE_CHARGE_STATUS),
    f('jobNo', 'Service Order', 'បញ្ជាសេវាកម្ម', 'General', 'ទូទៅ', 'text', undefined, { helpKey: 'freight.fieldHelp.chargeJobNo' }), f('customer', 'Customer', 'អតិថិជន', 'General', 'ទូទៅ', 'text', undefined, { required: true }), f('branchName', 'Branch', 'សាខា', 'General', 'ទូទៅ'), f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'General', 'ទូទៅ', 'select', CURRENCIES), f('remarks', 'Remarks', 'កំណត់សម្គាល់', 'General', 'ទូទៅ', 'textarea', undefined, { colSpan: 2, helpKey: 'freight.fieldHelp.remarks' }),
    f('invoiceNo', 'Finance Invoice', 'វិក្កយបត្រហិរញ្ញវត្ថុ', 'Traceability', 'ការតាមដាន', 'text', undefined, { computed: true, helpKey: 'freight.fieldHelp.chargeInvoiceNo' }),
    f('journalId', 'Posted Journal', 'ទិនានុប្បវត្តិបានចុះបញ្ជី', 'Traceability', 'ការតាមដាន', 'text', undefined, { computed: true, helpKey: 'freight.fieldHelp.chargeJournalId' }),
  ],
  tables: [{
    key: 'feeLines', title: 'Fee Lines', titleKm: 'ជួរថ្លៃ', addLabel: 'Add fee line', addLabelKey: 'freight.ui.addFeeLine',
    columns: [
      { key: 'feeType', label: 'Fee Type', labelKm: 'ប្រភេទថ្លៃ', required: true }, { key: 'description', label: 'Description', labelKm: 'បរិយាយ' },
      { key: 'quantity', label: 'Quantity', labelKm: 'បរិមាណ', type: 'number', required: true }, { key: 'unitAmount', label: 'Unit Price', labelKm: 'តម្លៃឯកតា', type: 'number', required: true },
      {
        key: 'amount', label: 'Grand Total', labelKm: 'សរុប', labelKey: 'freight.fields.total', type: 'number', computed: true,
        inlineFields: [
          { key: 'discount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
          { key: 'taxAmount', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
        ],
      },
    ],
  }, {
    key: 'sourceRelationships', title: 'Source Relationships', titleKm: 'ទំនាក់ទំនងប្រភព', columns: SOURCE_RELATIONSHIP_COLUMNS,
  }],
  actions: [
    { key: 'saveDraft', label: 'Save Draft', labelKm: 'រក្សាទុកព្រាង', icon: 'i-lucide-save' }, { key: 'issue', label: 'Issue', labelKm: 'ចេញ', icon: 'i-lucide-send', color: 'success' }, { key: 'print', label: 'Print / Download', labelKm: 'បោះពុម្ព / ទាញយក', icon: 'i-lucide-printer' }, { key: 'createInvoice', label: 'Create Finance Invoice', labelKm: 'បង្កើតវិក្កយបត្រហិរញ្ញវត្ថុ', icon: 'i-lucide-file-plus-2', color: 'primary' }, { key: 'viewInvoice', label: 'View Finance Invoice', labelKm: 'មើលវិក្កយបត្រហិរញ្ញវត្ថុ', icon: 'i-lucide-receipt-text', color: 'primary' },
  ],
  filters: [f('jobNo', 'Service Order', 'បញ្ជាសេវាកម្ម'), f('customer', 'Customer', 'អតិថិជន'), f('branchName', 'Branch', 'សាខា'), f('documentType', 'Document Type', 'ប្រភេទឯកសារ', '', '', 'select', ['SERVICE_NOTE', 'DEBIT_NOTE', 'PRO_FORMA']), f('status', 'Status', 'ស្ថានភាព', '', '', 'select', SERVICE_CHARGE_STATUS)],
})

if (invoicesModule) freightModules.push({
  ...invoicesModule,
  path: '/finance/documents',
  documentForm: 'finance',
  permission: 'finance.financial_documents.view',
  title: 'Financial Documents',
  titleKm: 'ឯកសារហិរញ្ញវត្ថុ',
  singular: 'Financial Document',
  singularKm: 'ឯកសារហិរញ្ញវត្ថុ',
  description: 'Reusable invoices, bills, receipts, payments, income and expense documents with posting controls.',
  descriptionKm: 'វិក្កយបត្រ បំណុល បង្កាន់ដៃ ការទូទាត់ ចំណូល និងចំណាយដែលមានការគ្រប់គ្រងចុះបញ្ជី។',
  columns: [
    col('debitNoteNo', 'Document No.', 'លេខឯកសារ'), col('documentType', 'Type', 'ប្រភេទ'), col('customer', 'Party', 'ដៃគូ'), col('date', 'Date', 'កាលបរិច្ឆេទ'), col('dueDate', 'Due Date', 'ថ្ងៃផុតកំណត់'), col('jobNo', 'Service Job', 'បញ្ជាសេវាកម្ម'), col('total', 'Total', 'សរុប'), col('outstanding', 'Outstanding', 'នៅសល់'), col('status', 'Status', 'ស្ថានភាព'),
  ],
  fields: [
    f('debitNoteNo', 'Document No.', 'លេខឯកសារ', 'Header', 'ក្បាល', 'text', undefined, { required: true, computed: true }),
    f('documentType', 'Document Type', 'ប្រភេទឯកសារ', 'Header', 'ក្បាល', 'select', ['CUSTOMER_INVOICE', 'SUPPLIER_BILL', 'CUSTOMER_RECEIPT', 'SUPPLIER_PAYMENT', 'OTHER_INCOME', 'OTHER_EXPENSE', 'TRANSFER', 'ADJUSTMENT']),
    f('date', 'Document Date', 'កាលបរិច្ឆេទឯកសារ', 'Header', 'ក្បាល', 'date', undefined, { required: true }),
    f('postingDate', 'Posting Date', 'កាលបរិច្ឆេទចុះបញ្ជី', 'Header', 'ក្បាល', 'date'), f('dueDate', 'Due Date', 'ថ្ងៃផុតកំណត់', 'Header', 'ក្បាល', 'date'), f('status', 'Status', 'ស្ថានភាព', 'Header', 'ក្បាល', 'select', DEBIT_NOTE_STATUS),
    f('customer', 'Party', 'ដៃគូ', 'Party & Scope', 'ដៃគូ និងវិសាលភាព', 'text', undefined, { required: true }), f('jobNo', 'Service Order', 'បញ្ជាសេវាកម្ម', 'Party & Scope', 'ដៃគូ និងវិសាលភាព'), f('branchName', 'Branch', 'សាខា', 'Party & Scope', 'ដៃគូ និងវិសាលភាព'),
    f('currency', 'Currency', 'រូបិយប័ណ្ណ', 'Amounts', 'ចំនួនទឹកប្រាក់', 'select', CURRENCIES), f('exchangeRate', 'Exchange Rate', 'អត្រាប្តូរប្រាក់', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number'), f('amount', 'Subtotal', 'សរុបរង', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number', undefined, { computed: true }), f('vat', 'Tax', 'ពន្ធ', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number', undefined, { computed: true }), f('total', 'Total', 'សរុប', 'Amounts', 'ចំនួនទឹកប្រាក់', 'number', undefined, { computed: true }),
    f('paymentMethod', 'Payment Method', 'វិធីទូទាត់', 'Settlement', 'ការទូទាត់', 'select', PAYMENT_METHODS), f('financialAccount', 'Financial Account', 'គណនីហិរញ្ញវត្ថុ', 'Settlement', 'ការទូទាត់'), f('valueDate', 'Value Date', 'កាលបរិច្ឆេទតម្លៃ', 'Settlement', 'ការទូទាត់', 'date'), f('referenceNo', 'Reference Number', 'លេខយោង', 'Settlement', 'ការទូទាត់'),
    f('sourceChargeId', 'Source Service Charge', 'ប្រភពថ្លៃសេវា', 'Traceability', 'ការតាមដាន', 'text', undefined, { computed: true, helpKey: 'freight.fieldHelp.sourceChargeId' }), f('journalId', 'Posted Journal', 'ទិនានុប្បវត្តិបានចុះបញ្ជី', 'Traceability', 'ការតាមដាន', 'text', undefined, { computed: true, helpKey: 'freight.fieldHelp.journalId' }), f('remark', 'Description', 'បរិយាយ', 'Notes', 'កំណត់សម្គាល់', 'textarea'),
  ],
  filters: [
    f('documentType', 'Document Type', 'ប្រភេទឯកសារ', '', '', 'select', ['CUSTOMER_INVOICE', 'SUPPLIER_BILL', 'CUSTOMER_RECEIPT', 'SUPPLIER_PAYMENT', 'OTHER_INCOME', 'OTHER_EXPENSE', 'TRANSFER', 'ADJUSTMENT']), f('customer', 'Party', 'ដៃគូ', '', '', 'select'), f('branchName', 'Branch', 'សាខា', '', '', 'select'), f('jobNo', 'Service Order', 'បញ្ជាសេវាកម្ម', '', '', 'select'), f('status', 'Status', 'ស្ថានភាព', '', '', 'select', DEBIT_NOTE_STATUS), f('currency', 'Currency', 'រូបិយប័ណ្ណ', '', '', 'select', CURRENCIES),
  ],
  tables: [
    {
      key: 'lines', title: 'Financial Lines', titleKm: 'ជួរហិរញ្ញវត្ថុ', addLabel: 'Add financial line',
      columns: [
        { key: 'description', label: 'Description', labelKm: 'បរិយាយ', required: true }, { key: 'accountCode', label: 'Account', labelKm: 'គណនី', required: true }, { key: 'quantity', label: 'Qty', labelKm: 'បរិមាណ', type: 'number', required: true }, { key: 'unitAmount', label: 'Unit Price', labelKm: 'តម្លៃឯកតា', type: 'number', required: true },
        {
          key: 'amount',
          label: 'Line Total',
          labelKm: 'សរុបជួរ',
          labelKey: 'freight.ui.lineTotal',
          type: 'number',
          computed: true,
          inlineFields: [
            { key: 'discount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
            { key: 'taxAmount', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
          ],
        },
      ],
    },
    {
      key: 'allocations', title: 'Payment Allocations', titleKm: 'ការបែងចែកការទូទាត់', addLabel: 'Allocate document',
      columns: [
        { key: 'targetDocumentNo', label: 'Document', labelKm: 'ឯកសារ', required: true }, { key: 'party', label: 'Party', labelKm: 'ដៃគូ' }, { key: 'originalAmount', label: 'Original Amount', labelKm: 'ចំនួនដើម', type: 'number' }, { key: 'amount', label: 'Allocated', labelKm: 'បានបែងចែក', type: 'number', required: true }, { key: 'targetOutstanding', label: 'Outstanding', labelKm: 'នៅសល់', type: 'number' }, { key: 'currency', label: 'Currency', labelKm: 'រូបិយប័ណ្ណ' }, { key: 'allocatedAt', label: 'Date', labelKm: 'កាលបរិច្ឆេទ', type: 'date' },
      ],
    },
    { key: 'sourceRelationships', title: 'Source Relationships', titleKm: 'ទំនាក់ទំនងប្រភព', columns: SOURCE_RELATIONSHIP_COLUMNS },
    { key: 'journalEntries', title: 'Journal', titleKm: 'ទិនានុប្បវត្តិ', columns: [{ key: 'account', label: 'Account', labelKm: 'គណនី', required: true }, { key: 'description', label: 'Description', labelKm: 'បរិយាយ' }, { key: 'debit', label: 'Debit', labelKm: 'ឥណពន្ធ', type: 'number' }, { key: 'credit', label: 'Credit', labelKm: 'ឥណទាន', type: 'number' }, { key: 'branch', label: 'Branch', labelKm: 'សាខា' }] },
    { key: 'attachments', title: 'Files', titleKm: 'ឯកសារ', addLabel: 'Upload File', addLabelKey: 'freight.ui.uploadFile', kind: 'files', columns: FILE_ATTACHMENT_COLUMNS },
    { key: 'auditTimeline', title: 'Audit Timeline', titleKm: 'ពេលវេលាសវនកម្ម', columns: [{ key: 'occurredAt', label: 'Date / Time', labelKm: 'កាលបរិច្ឆេទ / ពេលវេលា' }, { key: 'user', label: 'User', labelKm: 'អ្នកប្រើ' }, { key: 'action', label: 'Action', labelKm: 'សកម្មភាព' }, { key: 'result', label: 'Result', labelKm: 'លទ្ធផល' }] },
  ],
  actions: [
    ...(invoicesModule.actions || []).filter(action => action.key !== 'print'),
    { key: 'backToServiceCharge', label: 'Back to Service Charge', labelKm: 'ត្រឡប់ទៅថ្លៃសេវាកម្ម', icon: 'i-lucide-arrow-left' },
  ],
})

export function getFreightModule(path: string) {
  const clean = path.replace(/\/$/, '') || '/'
  const sorted = freightModules
    .slice()
    .sort((a, b) => b.path.length - a.path.length)
  const exact = sorted.find(module => clean === module.path || clean.startsWith(`${module.path}/`))
  if (exact) return exact
  const compact = (value: string) => value.replace(/-/g, '')
  const needle = compact(clean)
  return sorted.find(module => {
    const candidate = compact(module.path)
    return needle === candidate || needle.startsWith(`${candidate}/`)
  })
}

import type { InjectionKey, Ref } from 'vue'
import type {
  DocumentFieldSchema,
  DocumentSectionSchema,
  DocumentTabSchema,
  FieldOption,
  FieldType,
} from '~/types/docetra/common'
import type {
  FreightField,
  FreightFieldType,
  FreightModule,
  FreightTable,
} from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'

export const RELATED_FIELD_KEY = '__related'

export const freightDocumentLineActionKey: InjectionKey<
  (action: 'view', row: Record<string, unknown>) => void
> = Symbol('freightDocumentLineAction')

export type FreightDocumentLineMenuItem = {
  label: string
  icon?: string
  color?: 'primary' | 'neutral' | 'error'
  onSelect: () => void
}

export const freightDocumentLineMenuKey: InjectionKey<
  (tableKey: string, row: Record<string, unknown>) => FreightDocumentLineMenuItem[]
> = Symbol('freightDocumentLineMenu')

export type FreightDocumentLineTableHeaderAction = {
  label: string
  icon?: string
  disabled?: boolean
  onClick: () => void
}

export const freightDocumentLineTableHeaderKey: InjectionKey<
  (tableKey: string) => FreightDocumentLineTableHeaderAction[]
> = Symbol('freightDocumentLineTableHeader')

export const freightDocumentRecordKey: InjectionKey<{
  get: (key: string) => unknown
}> = Symbol('freightDocumentRecord')

export const freightDocumentModelKey: InjectionKey<Ref<FreightRecord>> = Symbol('freightDocumentModel')

const TYPE_MAP: Record<FreightFieldType, FieldType> = {
  text: 'text',
  date: 'date',
  datetime: 'datetime',
  number: 'number',
  select: 'select',
  multiselect: 'multiselect',
  textarea: 'textarea',
  file: 'file',
  password: 'secret',
  checkbox: 'boolean',
}

const QUOTATION_OVERVIEW_KEYS = [
  'customer',
  'branchName',
  'direction',
  'date',
  'validUntil',
  'currency',
  'description',
  'notes',
] as const

const FINANCE_OVERVIEW_KEYS = [
  'debitNoteNo',
  'documentType',
  'customer',
  'branchName',
  'jobNo',
  'date',
  'postingDate',
  'dueDate',
  'currency',
  'exchangeRate',
  'referenceNo',
  'paymentMethod',
  'financialAccount',
  'status',
] as const

export type ModuleDocumentTabsOptions = {
  isCreate?: boolean
  includeRelated?: boolean
  compact?: boolean
  chargeLinkedToJob?: boolean
  chargeManualNumber?: boolean
  readOnlyKeys?: string[]
}

export function freightSelectOptions(
  options?: FreightField['options'],
): FieldOption[] | undefined {
  if (!options?.length) return undefined
  return [...options].map((item) => {
    if (item && typeof item === 'object' && 'value' in item) {
      return { label: String(item.label ?? item.value), value: String(item.value) }
    }
    const value = String(item)
    return { label: value, value }
  })
}

export function freightFieldToDocumentField(
  field: FreightField,
  extra: Partial<DocumentFieldSchema> = {},
): DocumentFieldSchema {
  const type = extra.type || TYPE_MAP[field.type || 'text'] || 'text'
  const options = extra.options || freightSelectOptions(field.options)
  const checkboxPair = (field.type === 'checkbox' || type === 'boolean') && options && options.length >= 1
    ? {
        trueValue: options[0]!.value,
        ...(options[1] ? { falseValue: options[1].value } : {}),
      }
    : undefined
  const meta = {
    ...checkboxPair,
    ...extra.meta,
  }
  return {
    labelKey: field.labelKey || `freight.fields.${field.key}`,
    label: field.label,
    required: field.required,
    colSpan: field.colSpan,
    help: field.help,
    helpKey: field.helpKey,
    rows: type === 'textarea' ? 4 : undefined,
    ...extra,
    key: field.key,
    type,
    options: type === 'boolean' ? extra.options : options,
    readOnly: Boolean(field.computed || extra.readOnly),
    meta: Object.keys(meta).length ? meta : extra.meta,
  }
}

function hasTable(module: FreightModule, key: string) {
  return Boolean(module.tables?.some(table => table.key === key))
}

function visibleTables(module: FreightModule, isCreate?: boolean): FreightTable[] {
  if (!module.tables?.length) return []
  if (isCreate && module.hideTablesOnCreate) return []
  return module.tables
}

const VIEW_ONLY_TABLES = new Set(['revisionHistory', 'sourceRelationships'])

function withChargeColumns(table: FreightTable, _chargeLinkedToJob?: boolean): FreightTable {
  if (table.key !== 'feeLines') return table
  return {
    ...table,
    columns: table.columns.map((column) => {
      if (column.key !== 'amount') return column
      return {
        ...column,
        label: 'Grand Total',
        labelKey: 'freight.fields.total',
        inlineFields: [
          { key: 'discount', label: 'Disc.', labelKm: 'បញ្ចុះ.', labelKey: 'freight.ui.discountCol' },
          { key: 'taxAmount', label: 'Tax', labelKm: 'ពន្ធ', labelKey: 'freight.ui.taxCol' },
        ],
      }
    }),
  }
}

export function lineTableField(
  table: FreightTable,
  options: ModuleDocumentTabsOptions = {},
): DocumentFieldSchema {
  const resolved = withChargeColumns(table, options.chargeLinkedToJob)
  return {
    key: table.key,
    labelKey: `freight.tables.${table.key}`,
    label: table.title,
    type: 'line-table',
    colSpan: 2,
    readOnly: VIEW_ONLY_TABLES.has(table.key),
    meta: {
      table: resolved,
      compact: options.compact,
      viewOnly: VIEW_ONLY_TABLES.has(table.key),
      showPricingTotals: table.key === 'pricingLines' || table.key === 'feeLines',
      includeTax: table.key === 'pricingLines' || table.key === 'feeLines',
    },
  }
}

function relatedField(): DocumentFieldSchema {
  return {
    key: RELATED_FIELD_KEY,
    labelKey: 'freight.ui.related',
    type: 'related-records',
    colSpan: 2,
  }
}

function relatedTab(): DocumentTabSchema {
  return {
    id: 'related',
    labelKey: 'freight.ui.related',
    sections: [{ id: 'related', fields: [relatedField()] }],
  }
}

function mapFields(
  fields: FreightField[],
  readOnlyKeys?: string[],
): DocumentFieldSchema[] {
  return fields.map(field => freightFieldToDocumentField(field, {
    readOnly: readOnlyKeys?.includes(field.key) || undefined,
  }))
}

function i18nSlug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'general'
}

function groupedFields(fields: FreightField[]) {
  const groups: Array<{ title: string, titleKm?: string, fields: FreightField[] }> = []
  for (const field of fields) {
    const title = field.section || 'General'
    const current = groups.find(group => group.title === title)
    if (current) current.fields.push(field)
    else groups.push({ title, titleKm: field.sectionKm, fields: [field] })
  }
  return groups
}

function fieldsToSections(
  fields: FreightField[],
  readOnlyKeys?: string[],
): DocumentSectionSchema[] {
  return groupedFields(fields).map(group => ({
    id: i18nSlug(group.title),
    titleKey: `freight.sections.${i18nSlug(group.title)}`,
    title: group.title,
    fields: mapFields(group.fields, readOnlyKeys),
  }))
}

function tableTab(table: FreightTable, options: ModuleDocumentTabsOptions): DocumentTabSchema {
  return {
    id: table.key,
    labelKey: `freight.tables.${table.key}`,
    label: table.title,
    sections: [{
      id: table.key,
      fields: [lineTableField(table, options)],
    }],
  }
}

function fieldsTab(
  id: string,
  labelKey: string,
  fields: DocumentFieldSchema[],
): DocumentTabSchema {
  return {
    id,
    labelKey,
    sections: [{ id, fields }],
  }
}

function fieldsByKeys(
  module: FreightModule,
  keys: readonly string[],
  readOnlyKeys?: string[],
) {
  const allow = new Set(keys)
  return mapFields(module.fields.filter(field => allow.has(field.key)), readOnlyKeys)
}

function tableOrThrow(module: FreightModule, key: string) {
  const table = module.tables?.find(item => item.key === key)
  if (!table) throw new Error(`Missing table ${key} on ${module.collection}`)
  return table
}

function quotationTabs(module: FreightModule, options: ModuleDocumentTabsOptions): DocumentTabSchema[] {
  const tabs: DocumentTabSchema[] = [
    fieldsTab('overview', 'freight.quotationTabs.overview', fieldsByKeys(module, QUOTATION_OVERVIEW_KEYS, options.readOnlyKeys)),
    {
      id: 'route',
      labelKey: 'freight.quotationTabs.route',
      sections: [{ id: 'route', fields: [lineTableField(tableOrThrow(module, 'places'), options)] }],
    },
    {
      id: 'containers',
      labelKey: 'freight.quotationTabs.containers',
      sections: [{ id: 'containers', fields: [lineTableField(tableOrThrow(module, 'containerRequirements'), options)] }],
    },
    {
      id: 'pricing',
      labelKey: 'freight.quotationTabs.pricing',
      sections: [{ id: 'pricing', fields: [lineTableField(tableOrThrow(module, 'pricingLines'), options)] }],
    },
    {
      id: 'files',
      labelKey: 'freight.quotationTabs.files',
      sections: [{ id: 'files', fields: [lineTableField(tableOrThrow(module, 'attachments'), options)] }],
    },
    {
      id: 'revisions',
      labelKey: 'freight.quotationTabs.revisions',
      sections: [{ id: 'revisions', fields: [lineTableField(tableOrThrow(module, 'revisionHistory'), options)] }],
    },
  ]

  return tabs
}

function mapChargeOverviewFields(
  fields: FreightField[],
  options: ModuleDocumentTabsOptions,
): DocumentFieldSchema[] {
  return fields.map((field) => {
    const base = freightFieldToDocumentField(field, {
      readOnly: options.readOnlyKeys?.includes(field.key) || undefined,
    })
    if (field.key !== 'chargeNo') return base
    if (options.chargeManualNumber) {
      return {
        ...base,
        readOnly: false,
        helpKey: 'freight.fieldHelp.chargeNoManual',
        required: true,
      }
    }
    return {
      ...base,
      readOnly: true,
      helpKey: 'freight.fieldHelp.chargeNo',
    }
  })
}

function chargeTabs(module: FreightModule, options: ModuleDocumentTabsOptions): DocumentTabSchema[] {
  const overviewFields = module.fields.filter(field => field.section !== 'Traceability')
  const traceFields = module.fields.filter(field => field.section === 'Traceability')
  const tabs: DocumentTabSchema[] = [
    {
      id: 'general',
      labelKey: 'freight.sections.general',
      sections: [{ id: 'general', fields: mapChargeOverviewFields(overviewFields, options) }],
    },
    {
      id: 'fee-lines',
      labelKey: 'freight.tables.feeLines',
      sections: [{ id: 'fee-lines', fields: [lineTableField(tableOrThrow(module, 'feeLines'), options)] }],
    },
  ]
  if (traceFields.length || hasTable(module, 'sourceRelationships')) {
    tabs.push({
      id: 'traceability',
      labelKey: 'freight.documentTabs.traceability',
      sections: [{
        id: 'traceability',
        fields: [
          ...mapFields(traceFields, options.readOnlyKeys),
          ...(hasTable(module, 'sourceRelationships')
            ? [lineTableField(tableOrThrow(module, 'sourceRelationships'), options)]
            : []),
        ],
      }],
    })
  }
  return tabs
}

function financeTabs(module: FreightModule, options: ModuleDocumentTabsOptions): DocumentTabSchema[] {
  return [
    fieldsTab('overview', 'freight.documentTabs.overview', fieldsByKeys(module, FINANCE_OVERVIEW_KEYS, options.readOnlyKeys)),
    {
      id: 'lines',
      labelKey: 'freight.documentTabs.lines',
      sections: [{ id: 'lines', fields: [lineTableField(tableOrThrow(module, 'lines'), options)] }],
    },
    {
      id: 'allocation',
      labelKey: 'freight.documentTabs.allocation',
      sections: [{ id: 'allocation', fields: [lineTableField(tableOrThrow(module, 'allocations'), options)] }],
    },
    {
      id: 'journal',
      labelKey: 'freight.documentTabs.journal',
      sections: [{ id: 'journal', fields: [lineTableField(tableOrThrow(module, 'journalEntries'), options)] }],
    },
    {
      id: 'traceability',
      labelKey: 'freight.documentTabs.traceability',
      sections: [{
        id: 'traceability',
        fields: [
          ...fieldsByKeys(module, ['sourceChargeId', 'journalId'], options.readOnlyKeys),
          ...(hasTable(module, 'sourceRelationships')
            ? [lineTableField(tableOrThrow(module, 'sourceRelationships'), options)]
            : []),
        ],
      }],
    },
    {
      id: 'files',
      labelKey: 'freight.documentTabs.files',
      sections: [{ id: 'files', fields: [lineTableField(tableOrThrow(module, 'attachments'), options)] }],
    },
    {
      id: 'activity',
      labelKey: 'freight.documentTabs.activity',
      sections: [{ id: 'activity', fields: [lineTableField(tableOrThrow(module, 'auditTimeline'), options)] }],
    },
  ]
}

function rolesTabs(module: FreightModule, options: ModuleDocumentTabsOptions): DocumentTabSchema[] {
  return [{
    id: 'general',
    labelKey: 'freight.sections.general',
    sections: [
      {
        id: 'main',
        titleKey: 'docetra.sections.main',
        fields: mapFields(module.fields, options.readOnlyKeys),
      },
      {
        id: 'permissions',
        titleKey: 'docetra.sections.permissions',
        fields: [{
          key: 'permissionRows',
          labelKey: 'docetra.sections.permissions',
          type: 'permission-matrix',
          colSpan: 2,
        }],
      },
    ],
  }]
}

function recipeTabs(module: FreightModule, options: ModuleDocumentTabsOptions): DocumentTabSchema[] | null {
  switch (module.documentForm) {
    case 'roles':
      return rolesTabs(module, options)
    case 'quotation':
      return hasTable(module, 'places') ? quotationTabs(module, options) : null
    case 'charges':
      return hasTable(module, 'feeLines') ? chargeTabs(module, options) : null
    case 'finance':
      return hasTable(module, 'lines') ? financeTabs(module, options) : null
    default:
      return null
  }
}

function defaultTabs(module: FreightModule, options: ModuleDocumentTabsOptions): DocumentTabSchema[] {
  const tabs: DocumentTabSchema[] = [{
    id: 'details',
    labelKey: 'freight.sections.details',
    sections: fieldsToSections(module.fields, options.readOnlyKeys),
  }]
  for (const table of visibleTables(module, options.isCreate)) {
    tabs.push(tableTab(table, options))
  }
  return tabs
}

function withoutLineTables(tabs: DocumentTabSchema[]): DocumentTabSchema[] {
  return tabs.filter(tab =>
    !tab.sections.some(section => section.fields.some(field => field.type === 'line-table')),
  )
}

function withRuntimeLineTables(
  tabs: DocumentTabSchema[],
  module: FreightModule,
  options: ModuleDocumentTabsOptions,
): DocumentTabSchema[] {
  return tabs.map(tab => ({
    ...tab,
    sections: tab.sections.map(section => ({
      ...section,
      fields: section.fields.map((field) => {
        if (field.type !== 'line-table') return field
        const table = module.tables?.find(item => item.key === field.key)
        return table ? lineTableField(table, options) : field
      }),
    })),
  }))
}

/** Compile module fields/tables into AppDocumentForm tabs (tab → section → field). */
export function moduleDocumentTabs(
  module: FreightModule,
  options: ModuleDocumentTabsOptions = {},
): DocumentTabSchema[] {
  let tabs: DocumentTabSchema[]
  if (module.tabs?.length) {
    tabs = withRuntimeLineTables(module.tabs, module, options)
  }
  else {
    tabs = recipeTabs(module, options) || defaultTabs(module, options)
  }
  if (options.isCreate && module.hideTablesOnCreate) tabs = withoutLineTables(tabs)
  if (options.includeRelated && module.related?.length && !tabs.some(tab => tab.id === 'related')) {
    tabs = [...tabs, relatedTab()]
  }
  return tabs
}

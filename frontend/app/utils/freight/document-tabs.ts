import type { InjectionKey, Ref } from 'vue'
import type {
  DocumentFieldSchema,
  DocumentSectionSchema,
  DocumentTabSchema,
  FieldOption,
  FieldType,
} from '~/types/common'
import { slugify } from '~/utils/text/slug'
import type {
  FreightField,
  FreightFieldType,
  FreightModule,
  FreightTable,
} from '~/config/freight-modules'
import { ALLOCATION_DOCUMENT_TYPES } from '~/config/freight-options'
import type { FreightRecord } from '~/types/record'

export const RELATED_FIELD_KEY = '__related'

/**
 * Tab id carrying two tables instead of a field grid: a posting rule's changes
 * and the journals it posted. `DocumentView` appends it and renders its content
 * through the document page's `tab-extra` slot, so no other module can
 * accidentally inherit an empty tab.
 */
export const freightDocumentLineActionKey: InjectionKey<
  (action: 'view', row: Record<string, unknown>) => void
> = Symbol('freightDocumentLineAction')

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

/**
 * Collections whose document chrome shows the comments & activity panel.
 * Only quotations, service orders and service charges keep this feature.
 */
export const COMMENT_ACTIVITY_COLLECTIONS = new Set(['quotations', 'jobs', 'jobCharges'])

export function supportsCommentActivity(collection: string | null | undefined): boolean {
  return Boolean(collection && COMMENT_ACTIVITY_COLLECTIONS.has(collection))
}

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
  'customerPartyId',
  'customer',
  'direction',
  'date',
  'validUntil',
  'currency',
  'description',
] as const

const FINANCE_OVERVIEW_KEYS = [
  'debitNoteNo',
  'documentType',
  'partyId',
  'jobNo',
  'date',
  'postingDate',
  'dueDate',
  'currency',
  'exchangeRate',
  'rateDirection',
  'baseCurrency',
  'baseTotalAmount',
  'total',
  'referenceNo',
  'paymentMethod',
  'financialAccountId',
  'valueDate',
  'status',
  'remark',
] as const

export type ModuleDocumentTabsOptions = {
  isCreate?: boolean
  includeRelated?: boolean
  compact?: boolean
  chargeLinkedToJob?: boolean
  chargeManualNumber?: boolean
  readOnlyKeys?: string[]
  /**
   * Document type of the record being edited (`financial_documents.document_type`).
   * When given, tabs and fields scoped to other types are dropped; omitting it
   * leaves every declared tab and field in place.
   */
  documentType?: string
  /** Record status, used to hide a tab that has nothing to show yet (e.g. an unposted journal). */
  status?: string
  /**
   * The record being edited. Only read to evaluate a field's `visibleWhen` rule
   * (e.g. the exchange rate while the document currency is not the base
   * currency); omitting it leaves every conditioned field visible.
   */
  record?: FreightRecord | null
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
    documentTypes: field.documentTypes,
    visibleWhen: field.visibleWhen,
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

/**
 * Tables the form never edits. A journal is produced by posting and an allocation
 * by `allocate_payment`, so both are shown as the server recorded them; nothing
 * typed into them would be saved.
 */
const VIEW_ONLY_TABLES = new Set(['revisionHistory', 'sourceRelationships', 'journalEntries', 'allocations'])

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
    labelKey: table.titleKey || `freight.tables.${table.key}`,
    label: table.title,
    type: 'line-table',
    colSpan: 2,
    readOnly: VIEW_ONLY_TABLES.has(table.key),
    meta: {
      table: resolved,
      compact: options.compact,
      viewOnly: VIEW_ONLY_TABLES.has(table.key),
      showPricingTotals: Boolean(table.pricing),
      // A table whose prices are already the customer price has no discount or
      // tax step, so neither line is shown.
      showDiscountTotals: Boolean(table.pricing) && !table.hideDiscountTax,
      includeTax: Boolean(table.pricing) && !table.hideDiscountTax,
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
    id: slugify(group.title),
    titleKey: `freight.sections.${slugify(group.title)}`,
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
      // Only an invoice or bill can be allocated against, and only a receipt or
      // payment allocates; every other type has no allocation to show.
      documentTypes: ALLOCATION_DOCUMENT_TYPES,
      sections: [{ id: 'allocation', fields: [lineTableField(tableOrThrow(module, 'allocations'), options)] }],
    },
    {
      id: 'journal',
      labelKey: 'freight.documentTabs.journal',
      // The journal exists once the document is posted (and stays visible after a
      // reversal, which posts a second one).
      statuses: ['POSTED', 'REVERSED'],
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
  ]
}

function rolesTabs(module: FreightModule, options: ModuleDocumentTabsOptions): DocumentTabSchema[] {
  return [{
    id: 'general',
    labelKey: 'freight.sections.general',
    sections: [
      {
        id: 'main',
        titleKey: 'lcs.sections.main',
        fields: mapFields(module.fields, options.readOnlyKeys),
      },
      {
        id: 'permissions',
        titleKey: 'lcs.sections.permissions',
        fields: [{
          key: 'permissionRows',
          labelKey: 'lcs.sections.permissions',
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
  // Create-only fields (e.g. the initial user password) are not part of an
  // update, so they are hidden while editing an existing record.
  const editableFields = options.isCreate === false
    ? module.fields.filter(field => !field.createOnly)
    : module.fields
  // Reference (Master Data / Configuration) status is changed from each row's
  // "..." menu, not from the document form, so keep it off the form here.
  const fields = (module.group === 'master' || module.group === 'configuration')
    ? editableFields.filter(field => field.key !== 'status')
    : editableFields
  const tabs: DocumentTabSchema[] = [{
    id: 'details',
    labelKey: 'freight.sections.details',
    sections: fieldsToSections(fields, options.readOnlyKeys),
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

/**
 * Whether a tab or field applies to the record being edited. A constraint that is
 * absent or empty matches everything, and so does an unknown document type or
 * status (a record mid-creation must not lose its fields before a type is chosen).
 */
function appliesTo(
  constraint: { documentTypes?: readonly string[], statuses?: readonly string[] },
  options: ModuleDocumentTabsOptions,
): boolean {
  const within = (values: readonly string[] | undefined, actual: string | undefined) => {
    if (!values?.length || !actual) return true
    const wanted = String(actual).trim().toUpperCase()
    return values.some(value => String(value).trim().toUpperCase() === wanted)
  }
  return within(constraint.documentTypes, options.documentType)
    && within(constraint.statuses, options.status)
}

/**
 * Whether a field's `visibleWhen` rule holds for the record being edited. A rule
 * that cannot be evaluated (no record, missing values) keeps the field visible:
 * hiding a field the operator may need is worse than showing one they do not.
 */
function conditionHolds(
  field: DocumentFieldSchema,
  record: FreightRecord | null | undefined,
): boolean {
  const rule = field.visibleWhen
  if (!rule?.differs?.length || !record) return true
  const [left, right] = rule.differs
  const leftValue = String(record[left] ?? '').trim().toUpperCase()
  const rightValue = String(record[right] ?? '').trim().toUpperCase()
  if (!leftValue || !rightValue) return true
  return leftValue !== rightValue
}

/** Drop the tabs and fields that do not apply to this document type / status / record. */
function scopedTabs(tabs: DocumentTabSchema[], options: ModuleDocumentTabsOptions): DocumentTabSchema[] {
  return tabs
    .filter(tab => appliesTo(tab, options))
    .map(tab => ({
      ...tab,
      sections: tab.sections.map(section => ({
        ...section,
        fields: section.fields.filter(field => appliesTo(field, options) && conditionHolds(field, options.record)),
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
  return withoutStatusFields(scopedTabs(tabs, options))
}

/**
 * Status is never an editable form field.
 *
 * Every collection changes status from the row's "..." menu, where the backend
 * validates the transition, checks the permission and the accounting rules, and
 * audits the result. Leaving the field on the form would let a create/edit save
 * write any status directly — a posted journal could be relabelled, a reference
 * record reactivated, a closed period reopened — bypassing all of that.
 */
function withoutStatusFields(tabs: DocumentTabSchema[]): DocumentTabSchema[] {
  return tabs.map(tab => ({
    ...tab,
    sections: tab.sections.map(section => ({
      ...section,
      fields: section.fields.filter(field => field.key !== 'status'),
    })),
  }))
}

/**
 * `/configuration/component-*` grids, expressed as the shared `FreightTable`
 * contract so they render through `AppLineTable` exactly like the quotation
 * line tables.
 *
 * Keep this module a leaf (types + table definitions only): the pages own the
 * persistence calls, and the renderer owns cell behaviour. Each builder returns
 * the column set for one grid plus the row projection that `AppLineTable`
 * edits, so a cell edit never has to know which entity it belongs to.
 */

import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import type {
  ComponentAttribute,
  ComponentAttributeInput,
  ComponentDataType,
  ComponentGroupAttribute,
  ComponentReferenceType,
  ComponentTabGroupLink,
} from '~/types/component-config'
import { COMPONENT_DATA_TYPES } from '~/types/component-config'

export type ComponentConfigRow = Record<string, unknown>

/** Data types the configuration grid may assign. Every backend type renders. */
const ATTRIBUTE_DATA_TYPES = COMPONENT_DATA_TYPES

const COMPONENT_REFERENCE_TYPES: ComponentReferenceType[] = [
  'business_party',
  'transport_asset',
  'transport_type',
  'container',
  'fee_type',
  'user',
]

const ATTRIBUTE_RULE_KEYS = ['min', 'max', 'minLength', 'maxLength'] as const
const ATTRIBUTE_FLAG_RULE_KEYS = ['email', 'url', 'integer', 'nonNegative', 'positive'] as const

export function componentDataTypeItems() {
  return ATTRIBUTE_DATA_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
}

function text(value: unknown) {
  return String(value ?? '').trim()
}

/** A new attribute row starts blank. A blank code is derived from the label. */
export function blankComponentAttributeRow(): ComponentConfigRow {
  return {
    code: '',
    label: '',
    dataType: 'text',
    options: '',
    referenceType: '',
    validationRules: '',
    isRequired: false,
    helpText: '',
    displayOrder: 0,
  }
}

/** Project an attribute onto the flat row the grid edits. */
export function componentAttributeToRow(attribute: ComponentAttribute): ComponentConfigRow {
  return {
    id: attribute.id,
    code: attribute.code,
    label: attribute.label,
    dataType: attribute.dataType,
    options: formatAttributeOptions(attribute.options),
    referenceType: attribute.referenceType || '',
    validationRules: formatAttributeRules(attribute.validationRules),
    validationRuleExtras: attributeRuleExtras(attribute.validationRules),
    isRequired: Boolean(attribute.isRequired),
    helpText: text(attribute.placeholder),
    displayOrder: attribute.displayOrder ?? 0,
    status: attribute.status,
  }
}

export function componentAttributeRows(attributes: ComponentAttribute[]): ComponentConfigRow[] {
  return attributes.map(componentAttributeToRow)
}

/** Cell values are strings; the API only accepts a known enum value. */
export function componentAttributeDataType(value: unknown): ComponentDataType {
  return componentEnumValue(value, COMPONENT_DATA_TYPES) || 'text'
}

function componentEnumValue<T extends string>(value: unknown, allowed: readonly T[]): T | null {
  const candidate = text(value)
  return (allowed as readonly string[]).includes(candidate) ? candidate as T : null
}

export function componentReferenceType(value: unknown): ComponentReferenceType | null {
  return componentEnumValue(value, COMPONENT_REFERENCE_TYPES)
}

/**
 * Static select choices as one cell: `Open, Closed` or `Draft|DRAFT`.
 * `shortcut: a label or value containing a comma cannot be typed here, use the
 * API for that; upgrade to a choices editor when one is asked for.`
 */
export function formatAttributeOptions(options: unknown): string {
  if (!Array.isArray(options)) return ''
  return options
    .map((option) => {
      if (option && typeof option === 'object') {
        const item = option as { label?: unknown, value?: unknown }
        const label = text(item.label)
        const value = text(item.value)
        if (!label || label === value) return value || label
        return `${label}|${value}`
      }
      return text(option)
    })
    .filter(Boolean)
    .join(', ')
}

export function parseAttributeOptions(value: unknown): Array<string | { label: string, value: string }> {
  const seen = new Set<string>()
  const options: Array<string | { label: string, value: string }> = []
  for (const token of String(value ?? '').split(',')) {
    const part = token.trim()
    if (!part) continue
    const pipe = part.indexOf('|')
    if (pipe < 0) {
      if (seen.has(part)) continue
      seen.add(part)
      options.push(part)
      continue
    }
    const label = part.slice(0, pipe).trim()
    const optionValue = part.slice(pipe + 1).trim()
    if (!optionValue || seen.has(optionValue)) continue
    seen.add(optionValue)
    options.push({ label: label || optionValue, value: optionValue })
  }
  return options
}

/**
 * `min=0; maxLength=12; email=true; pattern=^[A-Z]+$` in the cell, an object on
 * the wire.
 * `shortcut: a pattern containing ';' cannot be typed here, use the API for
 * that; upgrade to a rule editor when one is asked for.`
 */
export function formatAttributeRules(rules: unknown): string {
  if (!rules || typeof rules !== 'object' || Array.isArray(rules)) return ''
  const record = rules as Record<string, unknown>
  const parts = [...ATTRIBUTE_RULE_KEYS, 'pattern', ...ATTRIBUTE_FLAG_RULE_KEYS]
    .filter(key => record[key] !== undefined && record[key] !== null && record[key] !== '')
    .map(key => `${key}=${String(record[key])}`)
  return parts.join('; ')
}

export type AttributeRulesParse = {
  rules: Record<string, unknown>
  error: string | null
}

/** Keys the Rules cell shows; anything else is kept hidden and merged back. */
const ATTRIBUTE_KNOWN_RULE_KEYS = new Set<string>([
  ...ATTRIBUTE_RULE_KEYS,
  'pattern',
  ...ATTRIBUTE_FLAG_RULE_KEYS,
])

export function attributeRuleExtras(rules: unknown): Record<string, unknown> {
  if (!rules || typeof rules !== 'object' || Array.isArray(rules)) return {}
  return Object.fromEntries(
    Object.entries(rules as Record<string, unknown>).filter(([key]) => !ATTRIBUTE_KNOWN_RULE_KEYS.has(key)),
  )
}

/** Rules the cell can edit plus the keys it must not silently drop. */
export function mergeAttributeRules(value: unknown, extras: unknown): Record<string, unknown> {
  return { ...attributeRuleExtras(extras), ...parseAttributeRules(value).rules }
}

export function parseAttributeRules(value: unknown): AttributeRulesParse {
  const raw = String(value ?? '').trim()
  if (!raw) return { rules: {}, error: null }
  const rules: Record<string, unknown> = {}
  for (const token of raw.split(';')) {
    const part = token.trim()
    if (!part) continue
    const separator = part.indexOf('=')
    if (separator < 1) {
      return { rules: {}, error: 'Use key=value, for example min=0; max=100.' }
    }
    const key = part.slice(0, separator).trim()
    const ruleValue = part.slice(separator + 1).trim()
    if (key === 'pattern') {
      if (!ruleValue) return { rules: {}, error: 'pattern needs a value.' }
      rules.pattern = ruleValue
      continue
    }
    if ((ATTRIBUTE_FLAG_RULE_KEYS as readonly string[]).includes(key)) {
      if (!['true', 'false'].includes(ruleValue.toLowerCase())) {
        return { rules: {}, error: `Rule "${key}" must be true or false.` }
      }
      rules[key] = ruleValue.toLowerCase() === 'true'
      continue
    }
    if (!(ATTRIBUTE_RULE_KEYS as readonly string[]).includes(key)) {
      return { rules: {}, error: `Unknown rule "${key}". Use min, max, minLength, maxLength, pattern or a flag.` }
    }
    const number = Number(ruleValue)
    if (!ruleValue || !Number.isFinite(number) || number < 0) {
      return { rules: {}, error: `Rule "${key}" must be a number of zero or more.` }
    }
    if ((key === 'minLength' || key === 'maxLength') && !Number.isInteger(number)) {
      return { rules: {}, error: `Rule "${key}" must be a whole number.` }
    }
    rules[key] = number
  }
  const min = typeof rules.min === 'number' ? rules.min : undefined
  const max = typeof rules.max === 'number' ? rules.max : undefined
  if (min !== undefined && max !== undefined && min > max) {
    return { rules: {}, error: 'min cannot be greater than max.' }
  }
  const minLength = typeof rules.minLength === 'number' ? rules.minLength : undefined
  const maxLength = typeof rules.maxLength === 'number' ? rules.maxLength : undefined
  if (minLength !== undefined && maxLength !== undefined && minLength > maxLength) {
    return { rules: {}, error: 'minLength cannot be greater than maxLength.' }
  }
  return { rules, error: null }
}

/** Server-normalised code shape; used to compare two codes for equality. */
export function normalizeAttributeCode(value: unknown): string {
  return text(value).toLowerCase().replace(/[\s_]+/g, '-')
}

/** The attribute payload `POST`/`PATCH /component-attributes` expects. */
export function componentAttributePayload(row: ComponentConfigRow, fallbackCode: string): ComponentAttributeInput {
  const dataType = componentAttributeDataType(row.dataType)
  return {
    label: text(row.label),
    code: text(row.code) || fallbackCode,
    dataType,
    isRequired: Boolean(row.isRequired),
    placeholder: text(row.helpText),
    options: parseAttributeOptions(row.options),
    referenceType: componentReferenceType(row.referenceType),
    validationRules: mergeAttributeRules(row.validationRules, row.validationRuleExtras),
  }
}

export function componentAttributeColumns(): FreightLineColumn[] {
  return [
    { key: '_reorder', label: '', type: 'reorder' },
    {
      key: 'label',
      label: 'Field Name',
      labelKm: 'ឈ្មោះចំណុច',
      type: 'text',
      required: true,
      rule: { required: true, maxLength: 255 },
    },
    {
      key: 'code',
      label: 'Field Key',
      labelKm: 'លេខកូដចំណុច',
      type: 'text',
      required: true,
      rule: { required: true, maxLength: 64 },
    },
    {
      key: 'dataType',
      label: 'Data Type',
      labelKm: 'ប្រភេទ',
      type: 'select',
      required: true,
      options: ATTRIBUTE_DATA_TYPES.map(value => value.replace(/_/g, ' ')),
      rule: { required: true },
    },
    { key: 'isRequired', label: 'Required', labelKm: 'ត្រូវសម្រាប់', type: 'checkbox' },
    {
      key: 'displayOrder',
      label: 'Display Order',
      labelKm: 'លំដាប់បង្ហាញ',
      type: 'number',
      computed: true,
    },
    {
      key: 'status',
      label: 'Status',
      labelKm: 'ស្ថានភាព',
      type: 'text',
      computed: true,
    },
    {
      key: 'options',
      label: 'Choices (a, b)',
      labelKm: 'ជម្រើស',
      type: 'text',
      rule: { maxLength: 1000 },
    },
    {
      key: 'referenceType',
      label: 'Master Data',
      labelKm: 'ទិន្នន័យមេ',
      type: 'select',
      options: COMPONENT_REFERENCE_TYPES,
    },
    {
      key: 'validationRules',
      label: 'Rules (key=value)',
      labelKm: 'ច្បាប់ផ្ទៀងផ្ទាត់',
      type: 'text',
      rule: { maxLength: 500 },
    },
    {
      key: 'helpText',
      label: 'Help Text',
      labelKm: 'អត្ថបទជំនួយ',
      type: 'text',
      rule: { maxLength: 255 },
    },
  ]
}

/** Assigned-attributes grid for a component group. */
export function componentGroupAttributeRows(rows: ComponentGroupAttribute[]): ComponentConfigRow[] {
  return rows.map(row => ({
    id: row.id,
    attributeId: row.attributeId,
    label: row.label,
    code: row.code,
    dataType: row.dataType,
    isRequired: Boolean(row.isRequired),
  }))
}

export function componentGroupAttributeColumns(): FreightLineColumn[] {
  return [
    { key: 'label', label: 'Attribute', labelKm: 'គំលេង', type: 'text' },
    { key: 'code', label: 'Code', labelKm: 'លេខកូដ', type: 'text' },
    { key: 'dataType', label: 'Type', labelKm: 'ប្រភេទ', type: 'text', computed: true },
    { key: 'isRequired', label: 'Required', labelKm: 'ត្រូវសម្រាប់', type: 'checkbox' },
    { key: '_reorder', label: '', type: 'reorder' },
    { key: '_delete', label: '', type: 'delete' },
  ]
}

/** Groups assigned to a component tab. */
export function componentTabGroupRows(rows: ComponentTabGroupLink[]): ComponentConfigRow[] {
  return rows.map(row => ({
    id: row.id,
    tabGroupId: row.tabGroupId,
    name: row.name,
    code: row.code,
    renderMode: row.renderMode,
  }))
}

export function componentTabGroupColumns(): FreightLineColumn[] {
  return [
    { key: 'name', label: 'Group', labelKm: 'ក្រុម', type: 'text' },
    { key: 'code', label: 'Code', labelKm: 'លេខកូដ', type: 'text' },
    { key: 'renderMode', label: 'Render', labelKm: 'បង្ហាញ', type: 'text', computed: true },
    { key: '_reorder', label: '', type: 'reorder' },
    { key: '_delete', label: '', type: 'delete' },
  ]
}

/**
 * Wrap a column list into the `FreightTable` the renderer takes. Config grids
 * manage their own add/delete outside the grid, so they declare no `addLabel`
 * and no row arithmetic.
 */
export function componentConfigTable(options: {
  key: string
  title: string
  titleKm?: string
  columns: FreightLineColumn[]
  hideTitle?: boolean
  hideAddRow?: boolean
}): FreightTable {
  return {
    key: options.key,
    title: options.title,
    titleKm: options.titleKm,
    columns: options.columns,
    hideTitle: options.hideTitle,
    hideAddRow: options.hideAddRow,
  }
}
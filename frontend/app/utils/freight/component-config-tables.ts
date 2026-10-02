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
import { COMPONENT_DATA_TYPES, COMPONENT_REFERENCE_TYPES } from '~/types/component-config'

export type ComponentConfigRow = Record<string, unknown>

/** Data types that carry a fixed list of allowed values. */
const OPTION_DATA_TYPES = new Set(['select', 'multi_select', 'currency'])

export function componentDataTypeItems() {
  return COMPONENT_DATA_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
}

export function componentReferenceTypeItems() {
  return COMPONENT_REFERENCE_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
}

export function componentNeedsOptions(dataType: unknown): boolean {
  return OPTION_DATA_TYPES.has(String(dataType ?? ''))
}

function text(value: unknown) {
  return String(value ?? '').trim()
}

/** Options live as a JSON array on the entity but must be edited as one string. */
export function componentOptionsText(attribute: Pick<ComponentAttribute, 'options'>): string {
  return (attribute.options || [])
    .map(option => (typeof option === 'string' ? option : option?.value))
    .map(value => text(value))
    .filter(Boolean)
    .join(', ')
}

export function parseComponentOptionsText(value: unknown): string[] {
  return String(value ?? '')
    .split(',')
    .map(part => part.trim())
    .filter(Boolean)
}

/** A new attribute row starts blank; `code` is derived from `label` on save. */
export function blankComponentAttributeRow(): ComponentConfigRow {
  return { label: '', code: '', dataType: 'text', referenceType: undefined, isRequired: false, optionsText: '' }
}

/** Project an attribute onto the flat row the grid edits. */
export function componentAttributeToRow(attribute: ComponentAttribute): ComponentConfigRow {
  return {
    id: attribute.id,
    label: attribute.label,
    code: attribute.code,
    dataType: attribute.dataType,
    referenceType: attribute.referenceType || undefined,
    isRequired: Boolean(attribute.isRequired),
    optionsText: componentOptionsText(attribute),
  }
}

export function componentAttributeRows(attributes: ComponentAttribute[]): ComponentConfigRow[] {
  return attributes.map(componentAttributeToRow)
}

/** Cell values are strings; the API only accepts a known enum value. */
export function componentAttributeDataType(value: unknown): ComponentDataType {
  return componentEnumValue(value, COMPONENT_DATA_TYPES) || 'text'
}

export function componentReferenceTypeValue(value: unknown): ComponentReferenceType | null {
  return componentEnumValue(value, COMPONENT_REFERENCE_TYPES)
}

function componentEnumValue<T extends string>(value: unknown, allowed: readonly T[]): T | null {
  const candidate = text(value)
  return (allowed as readonly string[]).includes(candidate) ? candidate as T : null
}

/** The attribute payload `POST`/`PATCH /component-attributes` expects. */
export function componentAttributePayload(row: ComponentConfigRow, fallbackCode: string): ComponentAttributeInput {
  const dataType = componentAttributeDataType(row.dataType)
  return {
    label: text(row.label),
    code: text(row.code) || fallbackCode,
    dataType,
    referenceType: dataType === 'reference' ? componentReferenceTypeValue(row.referenceType) : null,
    isRequired: Boolean(row.isRequired),
    options: componentNeedsOptions(dataType) ? parseComponentOptionsText(row.optionsText) : [],
  }
}

/**
 * Reference column is only meaningful for `reference` attributes, and the
 * options column only for the option-carrying data types, so both cells hide
 * rather than showing an irrelevant editor.
 */
export function componentAttributeColumns(): FreightLineColumn[] {
  return [
    { key: 'label', label: 'Label', labelKm: 'ស្លាកសញ្ញា', type: 'text', required: true },
    { key: 'code', label: 'Code', labelKm: 'លេខកូដ', type: 'text' },
    { key: 'dataType', label: 'Type', labelKm: 'ប្រភេទ', type: 'select', options: COMPONENT_DATA_TYPES.map(value => value.replace(/_/g, ' ')) },
    { key: 'referenceType', label: 'Reference', labelKm: 'យោង', type: 'select', options: COMPONENT_REFERENCE_TYPES.map(value => value.replace(/_/g, ' ')) },
    { key: 'isRequired', label: 'Required', labelKm: 'ត្រូវសម្រាប់', type: 'checkbox' },
    { key: 'optionsText', label: 'Options', labelKm: 'ជម្រើស', type: 'text' },
    { key: '_delete', label: '', type: 'delete' },
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
}): FreightTable {
  return { key: options.key, title: options.title, titleKm: options.titleKm, columns: options.columns }
}
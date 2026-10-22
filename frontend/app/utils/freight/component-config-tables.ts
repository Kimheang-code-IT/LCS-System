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
  ComponentTabGroupLink,
} from '~/types/component-config'
import { COMPONENT_DATA_TYPES } from '~/types/component-config'

export type ComponentConfigRow = Record<string, unknown>

/**
 * Types a lone attribute row cannot configure yet. `reference` needs a
 * reference type (the grid has no column for it), so offering it would create
 * an attribute the backend rejects. Every other backend type is rendered by
 * the dynamic form and may be selected here.
 */
const ATTRIBUTE_EXCLUDED_DATA_TYPES = new Set(['reference'])
const ATTRIBUTE_DATA_TYPES = COMPONENT_DATA_TYPES.filter(value => !ATTRIBUTE_EXCLUDED_DATA_TYPES.has(value))

export function componentDataTypeItems() {
  return ATTRIBUTE_DATA_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
}

function text(value: unknown) {
  return String(value ?? '').trim()
}

/** A new attribute row starts blank; `code` is derived from `label` on save. */
export function blankComponentAttributeRow(): ComponentConfigRow {
  return { label: '', dataType: 'text', isRequired: false, helpText: '' }
}

/** Project an attribute onto the flat row the grid edits. */
export function componentAttributeToRow(attribute: ComponentAttribute): ComponentConfigRow {
  return {
    id: attribute.id,
    label: attribute.label,
    dataType: attribute.dataType,
    isRequired: Boolean(attribute.isRequired),
    helpText: text(attribute.placeholder),
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

/** The attribute payload `POST`/`PATCH /component-attributes` expects. */
export function componentAttributePayload(row: ComponentConfigRow, fallbackCode: string): ComponentAttributeInput {
  const dataType = componentAttributeDataType(row.dataType)
  return {
    label: text(row.label),
    code: text(row.code) || fallbackCode,
    dataType,
    isRequired: Boolean(row.isRequired),
    placeholder: text(row.helpText),
  }
}

export function componentAttributeColumns(): FreightLineColumn[] {
  return [
    {
      key: 'label',
      label: 'Label',
      labelKm: 'ស្លាកសញ្ញា',
      type: 'text',
      required: true,
      rule: { required: true, maxLength: 255 },
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
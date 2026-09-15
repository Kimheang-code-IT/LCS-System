import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import type { DynamicTab, DynamicTabColumn, DynamicTabRow } from '~/types/freight/dynamic-tabs'

export function dynamicColumnCellType(column: DynamicTabColumn): FreightLineColumn['type'] {
  switch (column.fieldType) {
    case 'number':
    case 'decimal':
    case 'money':
      return 'number'
    case 'date':
    case 'datetime':
      return 'date'
    case 'select':
    case 'currency':
    case 'multi_select':
    case 'reference':
      return 'select'
    case 'checkbox':
      return 'checkbox'
    case 'textarea':
      return 'textarea'
    default:
      return 'text'
  }
}

function columnOptions(column: DynamicTabColumn) {
  if (!Array.isArray(column.options)) return undefined
  const values = column.options
    .map(option => (typeof option === 'string' ? option : option?.value ?? option?.label))
    .map(value => String(value ?? '').trim())
    .filter(Boolean)
  return values.length ? values : undefined
}

function columnOptionItems(column: DynamicTabColumn, references: Record<string, Record<string, string>>) {
  if (column.fieldType !== 'reference' || !column.referenceType) return undefined
  const entries = Object.entries(references[column.referenceType] || {})
  if (!entries.length) return undefined
  return entries.map(([value, label]) => ({ label: String(label), value: String(value) }))
}

/** Convert a configured dynamic tab into the shared `FreightTable` contract. */
export function dynamicTabToFreightTable(
  tab: DynamicTab,
  references: Record<string, Record<string, string>> = {},
): FreightTable | null {
  const columns: FreightLineColumn[] = tab.columns
    .filter(column => !column.isArchived)
    .sort((a, b) => a.sortOrder - b.sortOrder)
    .map(column => ({
      key: column.fieldKey,
      label: column.label,
      labelKm: column.labelKm || undefined,
      type: dynamicColumnCellType(column),
      required: column.isRequired,
      options: columnOptions(column),
      optionItems: columnOptionItems(column, references),
    }))
  if (!columns.length) return null
  return {
    key: `dynamic-${tab.code}`,
    title: tab.name,
    columns,
    addLabelKey: 'freight.ui.addRow',
  }
}

const META_KEYS = new Set(['id', 'tabId', 'tabCode', 'rowNo', 'values', 'createdAt', 'updatedAt'])

export function flatRowToValues(row: Record<string, unknown>): Record<string, unknown> {
  const values: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(row)) {
    if (key.startsWith('_') || META_KEYS.has(key)) continue
    values[key] = value
  }
  return values
}

export function rowToFlatRow(row: DynamicTabRow): Record<string, unknown> {
  return { ...(row.values || {}), id: row.id, _rowNo: row.rowNo }
}

export function isPersistedRowId(value: unknown): boolean {
  const id = String(value ?? '')
  return Boolean(id) && !id.startsWith('row_') && !id.startsWith('tab_') && !id.startsWith('col_')
}

import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import type { ComponentGroupRow, ComponentTabAttribute, ComponentTabGroup } from '~/types/freight/component-config'

export function componentAttributeCellType(attribute: ComponentTabAttribute): FreightLineColumn['type'] {
  switch (attribute.fieldType) {
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
    case 'boolean':
      return 'checkbox'
    case 'textarea':
      return 'textarea'
    default:
      return 'text'
  }
}

function attributeOptions(attribute: ComponentTabAttribute) {
  if (!Array.isArray(attribute.options)) return undefined
  const values = attribute.options
    .map(option => (typeof option === 'string' ? option : option?.value ?? option?.label))
    .map(value => String(value ?? '').trim())
    .filter(Boolean)
  return values.length ? values : undefined
}

function attributeOptionItems(attribute: ComponentTabAttribute, references: Record<string, Record<string, string>>) {
  if (attribute.fieldType !== 'reference' || !attribute.referenceType) return undefined
  const entries = Object.entries(references[attribute.referenceType] || {})
  if (!entries.length) return undefined
  return entries.map(([value, label]) => ({ label: String(label), value: String(value) }))
}

/** Convert a table-mode component group into the shared `FreightTable` contract. */
export function componentGroupToFreightTable(
  group: ComponentTabGroup,
  references: Record<string, Record<string, string>> = {},
): FreightTable | null {
  const columns: FreightLineColumn[] = [...group.attributes]
    .sort((a, b) => a.sortOrder - b.sortOrder)
    .map(attribute => ({
      key: attribute.code,
      label: attribute.label,
      labelKm: attribute.labelKm || undefined,
      type: componentAttributeCellType(attribute),
      required: attribute.isRequired,
      options: attributeOptions(attribute),
      optionItems: attributeOptionItems(attribute, references),
    }))
  if (!columns.length) return null
  return {
    key: `component-${group.id}`,
    title: group.name,
    columns,
    addLabelKey: 'freight.ui.addRow',
  }
}

const META_KEYS = new Set(['id', 'groupId', 'rowNo', 'values', 'createdAt', 'updatedAt'])

export function componentRowToFlatRow(row: ComponentGroupRow): Record<string, unknown> {
  return { ...(row.values || {}), id: row.id, _rowNo: row.rowNo }
}

export function componentFlatRowToValues(row: Record<string, unknown>): Record<string, unknown> {
  const values: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(row)) {
    if (key.startsWith('_') || META_KEYS.has(key)) continue
    values[key] = value
  }
  return values
}

export function isPersistedComponentRowId(value: unknown): boolean {
  const id = String(value ?? '')
  return Boolean(id) && !id.startsWith('row_') && !id.startsWith('group_')
}

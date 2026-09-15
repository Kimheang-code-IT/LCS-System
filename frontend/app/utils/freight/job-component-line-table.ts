import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import { isTableAttribute } from '~/utils/freight/dynamic-table'
import {
  applyTaskValue,
  isAttributeRequired,
  mergeTemplateValues,
  taskValueModel,
} from '~/utils/freight/job-task-fields'

function normalizeKind(value: unknown) {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function attributeOptions(attribute: Record<string, unknown>) {
  const raw = attribute.options
  if (!Array.isArray(raw)) return undefined
  const options = raw.flatMap((item) => {
    if (item && typeof item === 'object') {
      const next = String((item as Record<string, unknown>).value ?? (item as Record<string, unknown>).label ?? '').trim()
      return next ? [next] : []
    }
    const next = String(item ?? '').trim()
    return next ? [next] : []
  })
  return options.length ? options : undefined
}

function attributeColumnType(attribute: Record<string, unknown>): FreightLineColumn['type'] {
  const data = normalizeKind(attribute.dataType)
  const input = normalizeKind(attribute.inputType)
  const kind = input || data || 'text'
  if (['date', 'datetime'].includes(kind)) return 'date'
  if (['number', 'decimal', 'integer', 'currency'].includes(kind)) return 'number'
  if (['select', 'radio', 'reference'].includes(kind) || data === 'select') return 'select'
  if (['textarea', 'long_text', 'json'].includes(kind)) return 'textarea'
  return 'text'
}

function activeAttributes(attributes: Array<Record<string, unknown>>) {
  return [...attributes]
    .filter((attribute) => {
      const status = String(attribute.status || 'Active').trim().toUpperCase()
      return !status || status === 'ACTIVE'
    })
    .filter(attribute => !isTableAttribute(attribute))
    .sort((a, b) => Number(a.displayOrder || 0) - Number(b.displayOrder || 0))
}

export function componentAttributesToLineTable(
  attributes: Array<Record<string, unknown>>,
  key: string,
  title: string,
): FreightTable | null {
  const scalar = activeAttributes(attributes)
  if (!scalar.length) return null
  const columns: FreightLineColumn[] = scalar.map((attribute) => {
    const code = String(attribute.code || '')
    const options = attributeOptions(attribute)
    return {
      key: code,
      label: String(attribute.label || code),
      type: attributeColumnType(attribute),
      options,
      required: isAttributeRequired(attribute),
    }
  })
  columns.push({
    key: '_status',
    label: 'Status',
    labelKey: 'freight.ui.status',
    type: 'text',
    computed: true,
  })
  return {
    key,
    title,
    columns,
    addLabelKey: 'freight.ui.addRow',
  }
}

export function componentRecordsToLineRows(
  records: FreightRecord[],
  attributes: Array<Record<string, unknown>>,
) {
  return records.map((record) => {
    const values = mergeTemplateValues(attributes, Array.isArray(record.values) ? record.values as Array<Record<string, unknown>> : [])
    const row: Record<string, unknown> = {
      _componentId: String(record.id || ''),
      _status: String(record.status || ''),
    }
    for (const value of values) {
      if (isTableAttribute(value)) continue
      row[String(value.code || '')] = taskValueModel(value) ?? ''
    }
    return row
  })
}

export function lineRowToComponentValues(
  row: Record<string, unknown>,
  attributes: Array<Record<string, unknown>>,
  captured: Array<Record<string, unknown>> = [],
) {
  const values = mergeTemplateValues(attributes, captured)
  for (const value of values) {
    const code = String(value.code || '')
    if (!(code in row) && !isTableAttribute(value)) continue
    if (isTableAttribute(value)) continue
    applyTaskValue(value, row[code])
  }
  return values
}

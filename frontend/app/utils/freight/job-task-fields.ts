import type { DocumentFieldSchema, FieldOption, FieldType } from '~/types/docetra/common'
import { isConfigFlagYes } from '~/utils/freight/job-component-tabs'
import {
  dynamicTableColumnsToFreightTable,
  isTableAttribute,
  parseDynamicTableRows,
  tableColumnsFromAttribute,
  tableRowsFromValue,
} from '~/utils/freight/dynamic-table'

function normalizeKind(value: unknown) {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_')
}

export function isAttributeRequired(value: Record<string, unknown> | unknown) {
  if (value && typeof value === 'object' && 'required' in (value as Record<string, unknown>)) {
    return isConfigFlagYes((value as Record<string, unknown>).required)
  }
  return isConfigFlagYes(value)
}

export function taskValueStorageKey(value: Record<string, unknown>) {
  const kind = normalizeKind(value.dataType || value.inputType || 'text')
  if (kind === 'table') return 'valueJson'
  if (['number', 'decimal', 'integer', 'currency'].includes(kind)) return 'valueNumber'
  if (['date', 'datetime', 'time'].includes(kind)) return 'valueDate'
  if (['boolean', 'checkbox'].includes(kind)) return 'valueBoolean'
  return 'valueText'
}

function optionList(value: Record<string, unknown>): FieldOption[] | undefined {
  const raw = value.options
  if (!Array.isArray(raw) || !raw.length) return undefined
  const options = raw.flatMap((item): FieldOption[] => {
    if (item && typeof item === 'object') {
      const rec = item as Record<string, unknown>
      const next = String(rec.value ?? rec.code ?? rec.label ?? '').trim()
      if (!next) return []
      return [{ label: String(rec.label ?? next), value: next }]
    }
    const next = String(item ?? '').trim()
    return next ? [{ label: next, value: next }] : []
  })
  return options.length ? options : undefined
}

function fieldTypeFromAttribute(value: Record<string, unknown>, hasOptions: boolean): FieldType {
  const data = normalizeKind(value.dataType)
  const input = normalizeKind(value.inputType)
  const kind = input || data || 'text'

  if (['boolean', 'checkbox'].includes(kind) || data === 'boolean') return 'boolean'
  if (['json', 'long_text', 'textarea', 'rich_text'].includes(kind) || data === 'json') return 'textarea'
  if (kind === 'datetime' || data === 'datetime') return 'datetime'
  if (kind === 'date' || data === 'date') return 'date'
  if (['number', 'decimal', 'integer', 'currency'].includes(kind) || ['number', 'decimal', 'integer', 'currency'].includes(data)) {
    return 'number'
  }
  if (['multiselect', 'multi_select', 'checkbox_group'].includes(kind)) {
    return hasOptions ? 'multiselect' : 'text'
  }
  if (['select', 'radio', 'reference'].includes(kind) || data === 'select') {
    return hasOptions ? 'select' : 'text'
  }
  if (kind === 'file' || data === 'file' || data === 'image') return 'file'
  if (kind === 'url' || data === 'url') return 'url'
  if (kind === 'table' || data === 'table') return 'dynamic-table'
  return 'text'
}

/** Map a captured component-template value to the shared document field renderer. */
export function taskValueToDocumentField(
  value: Record<string, unknown>,
  readOnly = false,
): DocumentFieldSchema {
  const code = String(value.code || '')
  const options = optionList(value)
  const type = fieldTypeFromAttribute(value, Boolean(options?.length))
  const help = String(value.helpText || value.help || '')
  const tableColumns = tableColumnsFromAttribute(value)
  const table = type === 'dynamic-table'
    ? dynamicTableColumnsToFreightTable(tableColumns, code, String(value.label || code))
    : undefined
  return {
    key: code,
    labelKey: '',
    label: String(value.label || code),
    type,
    required: isAttributeRequired(value),
    readOnly,
    help: help || undefined,
    options,
    rows: type === 'textarea' ? 4 : undefined,
    colSpan: type === 'dynamic-table' ? 2 : undefined,
    meta: {
      dataType: value.dataType,
      inputType: value.inputType,
      table,
      tableColumns,
    },
  }
}

export function taskValueModel(value: Record<string, unknown>) {
  if (isTableAttribute(value)) return tableRowsFromValue(value)
  return value[taskValueStorageKey(value)]
}

export function applyTaskValue(value: Record<string, unknown>, next: unknown) {
  if (isTableAttribute(value)) {
    value.valueJson = parseDynamicTableRows(next)
    return
  }
  value[taskValueStorageKey(value)] = next
}

function isActiveAttribute(attribute: Record<string, unknown>) {
  const status = String(attribute.status || 'Active').trim().toUpperCase()
  return !status || status === 'ACTIVE'
}

function normalizeValueRecord(attr: Record<string, unknown>, existing?: Record<string, unknown>) {
  const code = String(existing?.code || attr.code || '')
  const requiredSource = existing && existing.required !== undefined ? existing : attr
  return {
    ...attr,
    ...existing,
    code,
    label: existing?.label || attr.label || code,
    dataType: existing?.dataType || attr.dataType || 'Text',
    inputType: existing?.inputType || attr.inputType || existing?.dataType || attr.dataType,
    required: isAttributeRequired(requiredSource),
    helpText: String(existing?.helpText || attr.helpText || attr.help || ''),
    options: existing?.options || attr.options,
    tableColumns: existing?.tableColumns || attr.tableColumns,
  }
}

/** Build editable values from the current template attribute catalog. */
export function valuesFromTemplateAttributes(attributes: Array<Record<string, unknown>>) {
  return mergeTemplateValues(attributes, [])
}

/** Overlay captured instance values onto template attributes; keep leftover historical fields. */
export function mergeTemplateValues(
  attributes: Array<Record<string, unknown>>,
  captured: Array<Record<string, unknown>> = [],
) {
  const capturedByCode = new Map(
    captured.map(value => [String(value.code || ''), { ...value }]),
  )
  const ordered = [...attributes]
    .filter(isActiveAttribute)
    .sort((a, b) => Number(a.displayOrder || 0) - Number(b.displayOrder || 0))
  if (!ordered.length) {
    return captured.map(value => normalizeValueRecord({}, value))
  }
  const merged = ordered.map((attr) => {
    const code = String(attr.code || '')
    const existing = capturedByCode.get(code)
    capturedByCode.delete(code)
    return normalizeValueRecord(attr, existing)
  })
  for (const leftover of capturedByCode.values()) merged.push(normalizeValueRecord({}, leftover))
  return merged
}

export function missingRequiredValues(values: Array<Record<string, unknown>>) {
  return values.filter((value) => {
    if (!isAttributeRequired(value)) return false
    if (isTableAttribute(value)) return !tableRowsFromValue(value).length
    return !String(value.valueText || value.valueDate || '').trim()
      && value.valueNumber == null
      && value.valueBoolean == null
  })
}

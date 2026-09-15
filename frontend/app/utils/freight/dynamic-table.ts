import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import type { DynamicTableColumnDef } from '~/types/docetra/configuration'
import { createClientId } from '~/utils/client-id'

export function normalizeTableColumnType(value: unknown): DynamicTableColumnDef['type'] {
  const kind = String(value || 'text').trim().toLowerCase()
  if (kind === 'number' || kind === 'integer' || kind === 'decimal' || kind === 'currency') return 'number'
  if (kind === 'date' || kind === 'datetime') return 'date'
  if (kind === 'select') return 'select'
  return 'text'
}

export function parseDynamicTableColumns(source: unknown): DynamicTableColumnDef[] {
  if (!Array.isArray(source)) return []
  return source.flatMap((item, index) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const key = String(row.key || row.code || '').trim()
    if (!key) return []
    const label = String(row.label || key).trim()
    const options = Array.isArray(row.options)
      ? row.options.map(option => String(option ?? '').trim()).filter(Boolean)
      : undefined
    return [{
      id: String(row.id || createClientId('col')),
      key,
      label,
      labelKm: String(row.labelKm || '').trim() || undefined,
      type: normalizeTableColumnType(row.type),
      options: options?.length ? options : undefined,
      required: row.required === true || String(row.required || '').toLowerCase() === 'yes',
      order: Number.isFinite(Number(row.order)) ? Number(row.order) : index,
    }]
  }).sort((a, b) => a.order - b.order)
}

export function parseDynamicTableRows(source: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(source)) {
    return source.map(row => ({ ...(row && typeof row === 'object' ? row as Record<string, unknown> : {}) }))
  }
  if (typeof source === 'string' && source.trim()) {
    try {
      const parsed = JSON.parse(source)
      return parseDynamicTableRows(parsed)
    }
    catch {
      return []
    }
  }
  return []
}

export function dynamicTableColumnsToFreightTable(
  columns: DynamicTableColumnDef[],
  key: string,
  title: string,
): FreightTable {
  const freightColumns: FreightLineColumn[] = columns.map(column => ({
    key: column.key,
    label: column.label,
    labelKm: column.labelKm,
    type: column.type === 'number' ? 'number' : column.type === 'date' ? 'date' : column.type === 'select' ? 'select' : 'text',
    options: column.options,
    required: column.required,
  }))
  return {
    key,
    title,
    columns: freightColumns,
    addLabelKey: 'docetra.config.addTableRow',
  }
}

export function isTableAttribute(value: Record<string, unknown>) {
  const kind = String(value.dataType || value.inputType || '').trim().toLowerCase()
  return kind === 'table'
}

export function tableColumnsFromAttribute(attribute: Record<string, unknown>) {
  return parseDynamicTableColumns(attribute.tableColumns ?? attribute.columns)
}

export function tableRowsFromValue(value: Record<string, unknown>) {
  return parseDynamicTableRows(value.valueJson ?? value.valueText)
}

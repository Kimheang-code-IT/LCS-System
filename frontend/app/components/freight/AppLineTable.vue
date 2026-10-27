<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { h, type Component } from 'vue'
import { CommonAppReferenceSelect, CommonAppInputDate, UButton, UCheckbox, UDropdownMenu, UIcon, UInput, UInputNumber } from '#components'
import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import { FREIGHT_LINE_UTILITY_COLUMN_TYPES } from '~/config/freight-modules'
import { useFreightLabel } from '~/composables/freight/useFreight'
import { useLcsRepositories } from '~/repositories'
import { hasSourcePermission } from '~/utils/freight/permissions'
import { apiErrorMessage } from '~/utils/validation/api-error'
import type { DatePickerGranularity } from '~/utils/date-picker'
import { fileTableRowBy, fileTableRowCreated, fileTableRowName, filePreviewHref, revokeFilePreview, useFileAttachments } from '~/utils/freight/attachments'
import { fileTypeIcon } from '~/utils/file-icon'
import { formatDate, formatDateTime, formatMoney, formatNumber } from '~/utils/format/format-service'
import { freightTableUiCompactReadonly, freightTableUiLine } from '~/utils/table/theme'
import { isMoneyColumnKey, lineTableColumnCellClass, lineTableColumnMetrics, lineTableNumericColumnKeys } from '~/utils/table/line-table-columns'
import { applyLineAdjustments, lineSubtotal } from '~/utils/table/line-adjustments'
import { referenceItemForValue, referenceOptionSource, referenceSelectItems } from '~/utils/freight/reference-options'

const props = withDefaults(defineProps<{
  table: FreightTable
  modelValue: Array<Record<string, unknown>>
  disabled?: boolean
  compact?: boolean
  viewOnlyActions?: boolean
  /** Locks individual rows (not the whole table) — used by mixed read-only/editable grids. */
  rowDisabled?: (row: Record<string, unknown>) => boolean
  headerActions?: Array<{
    label: string
    icon?: string
    disabled?: boolean
    onClick: () => void
  }>
  extraRowMenuItems?: (row: Record<string, unknown>) => Array<{
    label: string
    icon?: string
    color?: 'primary' | 'neutral' | 'error'
    onSelect: () => void
  }>
  rowInlineActions?: (row: Record<string, unknown>) => Array<{
    label: string
    icon?: string
    color?: 'primary' | 'neutral' | 'error'
    disabled?: boolean
    loading?: boolean
    onSelect: () => void
  }>
  /**
   * Handler for `type: 'action'` columns. Receives the column's `action`
   * identifier and the row; returning `null` hides the cell. Unlike data cells
   * these are not locked by `disabled`, because a read-only grid still needs
   * its row actions (e.g. printing a document).
   */
  rowActions?: (action: string, row: Record<string, unknown>) => {
    label: string
    icon: string
    color?: 'primary' | 'neutral' | 'error'
    onSelect: () => void
  } | null
  /**
   * Called after a `type: 'reorder'` cell moves a row. Receives the whole row
   * list in its new order, so the parent can persist display order.
   */
  onReorder?: (rows: Array<Record<string, unknown>>) => void
  /**
   * Cell-level validation errors keyed `<table>.<rowIndex>.<column>`. Rendered
   * inside the offending cell so a bad row is identifiable without counting.
   */
  fieldErrors?: Record<string, string>
  /** Overrides the table key used to build cell error keys. */
  errorKey?: string
  /** Fired after a cell edit so the host can clear that cell's error. */
  onCellEdit?: (
    cellKey: string,
    change?: { index: number, key: string, value: unknown },
  ) => void
  /**
   * Fired when an editable text/number/date cell loses focus. Hosts that save
   * per field use this rather than a per-keystroke callback.
   */
  onCellBlur?: (cellKey: string, change: { index: number, key: string }) => void
}>(), {
  compact: false,
  rowDisabled: undefined,
  headerActions: () => [],
  extraRowMenuItems: undefined,
  rowInlineActions: undefined,
  rowActions: undefined,
  onReorder: undefined,
  fieldErrors: undefined,
  errorKey: undefined,
  onCellEdit: undefined,
  onCellBlur: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [Array<Record<string, unknown>>]
  'rowAction': [action: 'view', row: Record<string, unknown>]
}>()

const { t, te } = useI18n()
const { fieldLabel, tableTitle } = useFreightLabel()
const {
  inputRef,
  openPicker,
  rowsFromInput,
  rejected,
  uploading,
  removeUploaded,
} = useFileAttachments({ upload: () => props.table.upload })

const auth = useAuthStore()
const canEditFileNote = computed(() => hasSourcePermission(auth.user, 'attachment.upload'))
/** Note value when a file row's cell gained focus, keyed by attachment id. */
const noteAtFocus = new Map<string, string>()

/** Per-line discount / tax dialog, opened from the row menu. */
const detailsOpen = ref(false)
const detailsIndex = ref(-1)
const detailsRow = computed(() => rows.value[detailsIndex.value] || {})
const detailsSubtotal = computed(() => lineSubtotal(detailsRow.value))

function openLineDetails(index: number) {
  const row = rows.value[index]
  if (!row || props.disabled || rowLocked(row)) return
  detailsIndex.value = index
  detailsOpen.value = true
}

function saveLineDetails(values: { discount: number, taxRate: number }) {
  const index = detailsIndex.value
  const row = rows.value[index]
  if (!row) return
  const adjusted = applyLineAdjustments(row, values)
  const derived = props.table.computeRow?.({ row: adjusted, rows: rows.value, index }) || {}
  const next = { ...adjusted, ...derived }
  rows.value = rows.value.map((item, i) => i === index ? next : item)
}

const TableButton = UButton as Component
const TableCheckbox = UCheckbox as Component
const TableDate = CommonAppInputDate as Component
const TableIcon = UIcon as Component
const TableInput = UInput as Component
const TableInputNumber = UInputNumber as Component
const TableMenu = UDropdownMenu as Component
const TableReferenceSelect = CommonAppReferenceSelect as Component

const isFileTable = computed(() => props.table.kind === 'files')
const hasDeleteColumn = computed(() => props.table.columns.some(column => column.type === 'delete'))
const hasReorderColumn = computed(() => props.table.columns.some(column => column.type === 'reorder'))
const hasActionColumn = computed(() => props.table.columns.some(column => column.type === 'action'))

/** Utility columns never render as cells; their commands live in the row menu. */
function isMenuOnlyColumn(column: FreightLineColumn) {
  return column.type === 'delete' || column.type === 'reorder' || column.type === 'action'
}

const cellSize = 'sm' as const
const cellInputUi = { base: 'text-sm' }
const cellNumberInputUi = { base: 'text-sm text-right tabular-nums' }
const tableUi = computed(() => props.compact ? freightTableUiCompactReadonly : freightTableUiLine)

const numericKeys = lineTableNumericColumnKeys()

const store = useFreightStore()

// Master Data pages drive these line-table selects; static `column.options` are
// ignored when a reference source matches the column key. The filter is applied
// per row so a location can be narrowed by the role chosen in that same row.
function referenceItemsFor(column: FreightLineColumn, row?: Record<string, unknown>) {
  const source = referenceOptionSource(column.key)
  if (!source) return []
  const records = store.list(source.collection) || []
  const filtered = row && column.referenceFilter ? column.referenceFilter(row, records) : records
  const items = referenceSelectItems(filtered, source)
  // Keep an already-saved inactive value visible and selected while editing, so
  // deactivating a role does not silently blank an existing route row.
  const current = row ? String(row[column.key] ?? '') : ''
  if (current && !items.some(item => item.value === current)) {
    const fallback = referenceItemForValue(records, source, current)
    if (fallback) items.push(fallback)
  }
  return items
}

function columnCellClass(column: FreightLineColumn) {
  return lineTableColumnCellClass(column)
}

/**
 * Padding and borders a line-table cell spends on itself, per theme. A column
 * declared as N pixels of field therefore gets N + this much, and the field
 * inside fills exactly the rest.
 */
const cellChromePx = computed(() => props.compact ? 18 : 26)

/** Icon-only columns stay as narrow as their button whatever the table width is. */
const iconOnlyColumnMeta = {
  class: { th: 'w-px', td: 'w-px' },
  style: { th: { width: '1px' } },
}

/**
 * Column geometry for `UTable`: the field width from the shared resolver plus the
 * cell chrome, so every column has a deliberate width and the field fits it.
 */
function columnMeta(column: FreightLineColumn) {
  const { width, iconOnly } = lineTableColumnMetrics(column)
  if (iconOnly) return iconOnlyColumnMeta
  return {
    class: { th: '', td: '' },
    style: { th: { width: `${width + cellChromePx.value}px` } },
  }
}

function displayValue(column: FreightLineColumn, value: unknown, row?: Record<string, unknown>) {
  if (isFileTable.value && row) {
    if (column.key === 'fileName') return fileTableRowName(row) || '—'
    if (column.key === 'uploadedBy') return fileTableRowBy(row) || '—'
    if (column.key === 'uploadedAt') {
      const created = fileTableRowCreated(row)
      return created ? formatDateTime(created) : '—'
    }
  }
  if (value === undefined || value === null || value === '') return '—'
  if (column.type === 'number') {
    const number = Number(value)
    if (!Number.isFinite(number)) return String(value)
    if (isMoneyColumnKey(column.key)) {
      const currency = row?.currency ? String(row.currency) : undefined
      return formatMoney(number, currency)
    }
    return formatNumber(number, { maximumFractionDigits: 2, minimumFractionDigits: 0 })
  }
  if (column.type === 'date') return formatDate(value)
  if (column.type === 'datetime') return formatDateTime(value)
  if (column.type === 'select') {
    const items = column.optionItems?.length
      ? column.optionItems
      : referenceItemsFor(column, row)
    const match = items.find(item => item.value === String(value))
    if (match) return match.label
  }
  return String(value)
}

function lineDateGranularity(column: FreightLineColumn): DatePickerGranularity | null {
  if (column.type === 'datetime') return 'minute'
  if (column.type === 'date') return 'day'
  if (/At$|Time$/i.test(column.key)) return 'minute'
  if (/Date$/i.test(column.key)) return 'day'
  return null
}

function columnHeader(column: FreightLineColumn) {
  return h('div', {
    class: numericKeys.has(column.key) ? 'text-right' : '',
    // A derived column explains itself in a tooltip rather than a visible hint, so
    // the header row stays one line high.
    title: column.helpKey ? t(column.helpKey) : undefined,
  }, [
    h('span', fieldLabel(column)),
    column.required
      ? h('span', { class: 'ms-0.5 text-error', 'aria-hidden': 'true' }, '*')
      : null,
  ])
}

function inlineNumberFieldsCell(column: FreightLineColumn, row: Record<string, unknown>, index: number, disabled: boolean) {
  const inlineFields = column.inlineFields || []
  const formatInlineNumber = (value: unknown) =>
    formatNumber(value, { maximumFractionDigits: 2, minimumFractionDigits: 0 })
  const summary = inlineFields
    .map(field => formatInlineNumber(row[field.key]))
    .join(' / ')
  const main = h('span', {
    class: [columnCellClass(column), 'block truncate tabular-nums text-sm'],
    title: summary,
  }, summary || '—')
  if (!inlineFields.length) return main
  if (disabled) return main
  return h('div', { class: 'space-y-0.5 text-right' }, [
    inlineFields.map(field =>
      h('div', { class: 'flex items-center justify-end gap-1' }, [
        h('span', { class: 'text-[11px] leading-none text-muted' }, fieldLabel(field)),
        cellWithError(index, field.key, extra => h(TableInputNumber, {
          ...extra,
          'modelValue': Number(row[field.key] || 0),
          'increment': false,
          'decrement': false,
          'stepSnapping': false,
          'size': cellSize,
          'class': 'w-20',
          'ui': cellNumberInputUi,
          'aria-label': fieldLabel(field),
          'onUpdate:modelValue': (value: number | null) => updateCell(index, field.key, value ?? 0),
        })),
      ]),
    ),
  ])
}

function inlineMoneyCell(column: FreightLineColumn, row: Record<string, unknown>, index: number, disabled: boolean) {
  const inlineFields = column.inlineFields || []
  const main = h('span', {
    class: [columnCellClass(column), 'block truncate text-sm'],
    title: String(row[column.key] ?? ''),
  }, displayValue(column, row[column.key], row))
  if (!inlineFields.length) return main
  const formatInlineMoney = (value: unknown) => formatMoney(value)
  if (disabled) {
    const parts = inlineFields
      .map(field => ({ label: fieldLabel(field), value: Number(row[field.key] ?? 0) }))
      .filter(part => Number.isFinite(part.value) && part.value !== 0)
    if (!parts.length) return main
    return h('div', { class: 'space-y-0.5' }, [
      main,
      h('div', { class: 'space-y-0.5 text-right text-[11px] leading-tight text-muted tabular-nums' }, parts.map(part =>
        h('div', { title: `${part.label} ${formatInlineMoney(part.value)}` }, `${part.label} ${formatInlineMoney(part.value)}`),
      )),
    ])
  }
  return h('div', { class: 'space-y-0.5 text-right' }, [
    main,
    h('div', { class: 'space-y-0.5' }, inlineFields.map(field =>
      h('div', { class: 'flex items-center justify-end gap-1' }, [
        h('span', { class: 'text-[11px] leading-none text-muted' }, fieldLabel(field)),
        cellWithError(index, field.key, extra => h(TableInputNumber, {
          ...extra,
          'modelValue': Number(row[field.key] || 0),
          'increment': false,
          'decrement': false,
          'stepSnapping': false,
          'size': cellSize,
          'class': 'w-20',
          'ui': cellNumberInputUi,
          'aria-label': fieldLabel(field),
          'onUpdate:modelValue': (value: number | null) => updateCell(index, field.key, value ?? 0),
        })),
      ]),
    )),
  ])
}

const rows = computed({
  get: () => props.modelValue || [],
  set: value => emit('update:modelValue', value),
})

/** Stable prefix for cell error keys so a row error lands on its own cell. */
const errorPrefix = computed(() => props.errorKey || props.table.key)

function cellErrorKey(index: number, columnKey: string) {
  return `${errorPrefix.value}.${index}.${columnKey}`
}

/**
 * Build a cell control and hang its inline error underneath.
 *
 * The wrapper carries `data-field-key`, which is what first-invalid-field
 * navigation scrolls to and focuses. The message is a plain text node referenced
 * with `aria-describedby`, so it is announced with the control's value instead
 * of sitting next to it unattached.
 */
function cellWithError(
  index: number,
  columnKey: string,
  build: (extra: Record<string, unknown>) => ReturnType<typeof h>,
) {
  const key = cellErrorKey(index, columnKey)
  const error = props.fieldErrors?.[key]
  const extras: Record<string, unknown> = { 'data-field-key': key }
  if (error) {
    extras['aria-invalid'] = true
    extras['aria-describedby'] = `${key}-error`
  }
  const control = build(extras)
  if (!error) return control
  return h('div', { 'data-field-key': key, 'class': 'min-w-0 rounded-md ring-1 ring-error/60' }, [
    control,
    h('p', {
      'data-slot': 'cell-error',
      'id': `${key}-error`,
      'class': 'mt-1 text-[11px] leading-tight text-error',
    }, error),
  ])
}

function tagCell(control: ReturnType<typeof h>, index: number, columnKey: string) {
  return h('div', { 'data-field-key': cellErrorKey(index, columnKey), 'class': 'min-w-0' }, [control])
}

function rowLocked(row: Record<string, unknown>) {
  return props.disabled || Boolean(props.rowDisabled?.(row))
}

const tableRows = computed(() => rows.value.map((row, index) => ({ ...row, _rowIndex: index })))

function updateCell(index: number, key: string, value: unknown) {
  // Clear this cell's error as soon as the user starts correcting it.
  props.onCellEdit?.(cellErrorKey(index, key), { index, key, value })
  const edited = rows.value.map((row, i) => i === index ? { ...row, [key]: value } : row)
  const target = edited[index]
  if (!target) return
  // Derived values come from the table's own `computeRow`, never from a
  // table-key branch here.
  const computed = props.table.computeRow?.({ row: target, rows: edited, index }) || {}
  rows.value = edited.map((row, i) => i === index ? { ...row, ...computed } : row)
}

/** Enter commits the cell like Tab, so inline grids stay keyboard-operable. */
function cellKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  event.preventDefault()
  // Blurring commits through the regular `onBlur` path exactly once.
  const target = event.target as HTMLElement | null
  target?.blur()
}

function cellBlur(index: number, key: string) {
  props.onCellBlur?.(cellErrorKey(index, key), { index, key })
}

function addRow() {
  if (isFileTable.value) {
    openPicker()
    return
  }
  const blank = Object.fromEntries(props.table.columns.filter(column => !FREIGHT_LINE_UTILITY_COLUMN_TYPES.has(column.type)).map((column) => {
    if (column.type === 'number') return [column.key, 0]
    if (column.type === 'checkbox') return [column.key, String(column.options?.[1] ?? 'No')]
    if (column.type === 'select') {
      const referenceItems = referenceItemsFor(column)
      return [column.key, column.optionItems?.[0]?.value || referenceItems?.[0]?.value || column.options?.[0] || '']
    }
    return [column.key, '']
  }))
  for (const column of props.table.columns) {
    for (const inline of column.inlineFields || []) {
      if (!(inline.key in blank)) blank[inline.key] = 0
    }
  }
  // Seed values come from the table's own `rowDefaults` (e.g. carry the previous
  // payment row's container number), never from a table-key branch here.
  const seeded = props.table.rowDefaults?.({ rows: rows.value, blank }) || {}
  rows.value = [...rows.value, { ...blank, ...seeded }]
}

async function onFilesChosen(event: Event) {
  const added = await rowsFromInput(event)
  if (added.length) rows.value = [...rows.value, ...added]
}

function fileNameCell(row: Record<string, unknown>) {
  const name = fileTableRowName(row) || '—'
  const icon = fileTypeIcon({ name, mimeType: String(row.mimeType || '') })
  const href = name === '—' ? null : filePreviewHref(row)
  const labelClass = 'block min-w-0 truncate text-sm font-medium text-highlighted'
  const label = href
    ? h('a', {
      href,
      target: '_blank',
      rel: 'noopener noreferrer',
      class: [labelClass, 'hover:text-primary hover:underline'],
      title: name,
      'aria-label': t('freight.ui.previewFile', { name }),
    }, name)
    : h('span', { class: labelClass, title: name }, name)
  return h('div', { class: 'flex min-w-0 items-center gap-1.5' }, [
    h(TableIcon, { name: icon.icon, class: ['size-4 shrink-0', icon.class] }),
    label,
  ])
}

async function removeRow(index: number) {
  const row = rows.value[index]
  if (row && isFileTable.value) await removeUploaded(row)
  if (row) revokeFilePreview(row)
  rows.value = rows.value.filter((_, i) => i !== index)
}

/**
 * Persist a file note as soon as the cell is left. The file itself is never
 * touched; a pending (not yet saved) upload keeps the note in its row and the
 * document save stores it. `previous` is captured on focus so an unchanged cell
 * does not send a write.
 */
async function persistFileNote(index: number, value: string, previous?: string) {
  const row = rows.value[index]
  const id = String(row?.id || '')
  if (!id || previous === value) return
  try {
    const updated = await useLcsRepositories().attachments.updateNote(id, value)
    const note = String((updated as Record<string, unknown>).note || '')
    rows.value = rows.value.map((item, i) => i === index ? { ...item, note } : item)
  }
  catch (error) {
    rejected.value = [apiErrorMessage(error, t('api.somethingWentWrong'))]
  }
}

/** Move a row one position up/down for the row menu; shared by every table. */
function moveRow(index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= rows.value.length) return
  const next = [...rows.value]
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved!)
  rows.value = next
  props.onReorder?.(next)
}

const columns = computed<TableColumn<Record<string, unknown>>[]>(() => {
  const cols: TableColumn<Record<string, unknown>>[] = [
    {
      id: 'rowNumber',
      header: '#',
      cell: ({ row }) => h('span', { class: props.compact ? 'text-[11px] tabular-nums text-muted' : 'text-xs tabular-nums text-muted' }, Number(row.original._rowIndex || 0) + 1),
      enableSorting: false,
      meta: iconOnlyColumnMeta,
    },
    ...props.table.columns.filter(column => !isMenuOnlyColumn(column)).map(column => ({
      accessorKey: column.key,
      header: () => columnHeader(column),
      enableSorting: false,
      meta: columnMeta(column),
      cell: ({ row }: { row: { original: Record<string, unknown> } }) => {
        const index = Number(row.original._rowIndex || 0)
        const disabled = rowLocked(row.original)
        if (isFileTable.value && column.key === 'fileName') return fileNameCell(row.original)
        if (column.inlineFields?.length && !isMoneyColumnKey(column.key)) {
          return tagCell(inlineNumberFieldsCell(column, row.original, index, disabled), index, column.key)
        }
        const fileNote = isFileTable.value && column.key === 'note'
        if (disabled || column.computed || (isFileTable.value && !fileNote)) {
          return tagCell(inlineMoneyCell(column, row.original, index, disabled), index, column.key)
        }
        if (column.type === 'checkbox') {
          // A boolean model gets boolean checkbox values. Rows that store a
          // Yes/No string keep the declared option pair, so this stays generic.
          const booleanModel = typeof row.original[column.key] === 'boolean'
          return cellWithError(index, column.key, extra => h(TableCheckbox, {
            'modelValue': booleanModel ? Boolean(row.original[column.key]) : row.original[column.key],
            'trueValue': booleanModel ? true : String(column.options?.[0] ?? 'Yes'),
            'falseValue': booleanModel ? false : String(column.options?.[1] ?? 'No'),
            'disabled': disabled || column.computed,
            'size': cellSize,
            'aria-label': fieldLabel(column),
            'onUpdate:modelValue': (value: unknown) => updateCell(index, column.key, value),
            ...extra,
          }))
        }
        if (column.type === 'select') {
          const referenceItems = referenceItemsFor(column, row.original)
          const items = column.optionItems?.length
            ? column.optionItems
            : referenceItems.length
              ? referenceItems
              : (column.options || []).filter(Boolean).map(option => ({ label: option, value: option }))
          return cellWithError(index, column.key, extra => h(TableReferenceSelect, {
            'modelValue': String(row.original[column.key] || '') || undefined,
            'items': items,
            'referenceKey': column.key,
            'rowIndex': index,
            'placeholder': fieldLabel(column),
            'disabled': disabled || column.computed,
            'size': cellSize,
            'class': ['w-full', columnCellClass(column)],
            'ui': cellInputUi,
            'onUpdate:modelValue': (value: unknown) => updateCell(index, column.key, value),
            ...extra,
          }))
        }
        if (column.type === 'number') {
          return cellWithError(index, column.key, extra => h(TableInputNumber, {
            'modelValue': Number(row.original[column.key] || 0),
            'disabled': disabled || column.computed,
            'increment': false,
            'decrement': false,
            'stepSnapping': false,
            'size': cellSize,
            'class': ['w-full', columnCellClass(column)],
            'ui': cellNumberInputUi,
            'onUpdate:modelValue': (value: number | null) => updateCell(index, column.key, value ?? 0),
            'onBlur': () => cellBlur(index, column.key),
            'onKeydown': (event: KeyboardEvent) => cellKeydown(event),
            ...extra,
          }))
        }
        const dateGranularity = lineDateGranularity(column)
        if (dateGranularity) {
          const dateDisabled = disabled || column.computed
          const dateValue = String(row.original[column.key] ?? '')
          // A read-only cell shows the same placeholder as a text column rather
          // than an empty disabled input.
          if (dateDisabled && !dateValue) {
            return h('span', {
              class: [columnCellClass(column), 'block truncate text-sm text-muted'],
            }, '—')
          }
          return cellWithError(index, column.key, extra => h(TableDate, {
            'modelValue': dateValue,
            'granularity': dateGranularity,
            'disabled': dateDisabled,
            'size': cellSize,
            'class': `w-full ${columnCellClass(column)}`,
            'onUpdate:modelValue': (value: string) => updateCell(index, column.key, value),
            'onBlur': () => cellBlur(index, column.key),
            ...extra,
          }))
        }
        return cellWithError(index, column.key, extra => h(TableInput, {
          'modelValue': String(row.original[column.key] ?? ''),
          'disabled': disabled || column.computed || (fileNote && !canEditFileNote.value),
          'maxlength': column.rule?.maxLength,
          'size': cellSize,
          'class': `w-full ${columnCellClass(column)}`,
          'ui': cellInputUi,
          'onUpdate:modelValue': (value: string) => updateCell(index, column.key, value),
          'onFocus': () => {
            if (fileNote) noteAtFocus.set(String(row.original.id || ''), String(row.original[column.key] ?? ''))
          },
          'onBlur': (event: FocusEvent) => {
            cellBlur(index, column.key)
            if (fileNote) {
              const id = String(row.original.id || '')
              const previous = noteAtFocus.get(id)
              noteAtFocus.delete(id)
              void persistFileNote(index, (event.target as HTMLInputElement | null)?.value ?? '', previous)
            }
          },
          'onKeydown': (event: KeyboardEvent) => cellKeydown(event),
          ...extra,
        }))
      },
    })),
  ]
  if (hasDeleteColumn.value || hasReorderColumn.value || hasActionColumn.value
    || props.extraRowMenuItems || props.rowActions || props.rowInlineActions || isFileTable.value) {
    cols.push({
      id: 'actions',
      header: () => h(
        'span',
        { class: props.rowInlineActions ? '' : 'sr-only' },
        t('common.actions'),
      ),
      enableSorting: false,
      meta: iconOnlyColumnMeta,
      cell: ({ row }) => {
        const index = Number(row.original._rowIndex || 0)
        const inlineButtons = (props.rowInlineActions?.(row.original) || []).map(item =>
          h(TableButton, {
            label: item.label,
            icon: item.icon,
            color: item.color || 'neutral',
            variant: 'soft',
            size: 'xs',
            class: 'whitespace-nowrap',
            disabled: item.disabled,
            loading: item.loading,
            onClick: item.onSelect,
          }),
        )
        const menuItems: Array<Array<{ label: string, icon: string, color?: 'error', disabled?: boolean, onSelect?: () => void }>> = [[]]
        const actions = menuItems[0]!
        for (const item of props.extraRowMenuItems?.(row.original) || []) {
          actions.push({
            label: item.label,
            icon: item.icon || 'i-lucide-file',
            ...(item.color === 'error' ? { color: 'error' as const } : {}),
            onSelect: item.onSelect,
          })
        }
        for (const column of props.table.columns.filter(item => item.type === 'action')) {
          const action = props.rowActions?.(column.action || column.key, row.original)
          if (!action) continue
          actions.push({
            label: action.label,
            icon: action.icon,
            ...(action.color === 'error' ? { color: 'error' as const } : {}),
            onSelect: action.onSelect,
          })
        }
        if (props.table.lineDetails && !props.disabled && !rowLocked(row.original)) {
          actions.push({
            label: t('freight.ui.additionalDetails'),
            icon: 'i-lucide-sliders-horizontal',
            onSelect: () => openLineDetails(index),
          })
        }
        if (isFileTable.value && filePreviewHref(row.original)) {
          actions.push({
            label: t('freight.ui.preview'),
            icon: 'i-lucide-external-link',
            onSelect: () => {
              const href = filePreviewHref(row.original)
              if (href && import.meta.client) window.open(href, '_blank', 'noopener,noreferrer')
            },
          })
        }
        if (hasReorderColumn.value) {
          actions.push({
            label: t('actions.moveUp'),
            icon: 'i-lucide-arrow-up',
            disabled: rowLocked(row.original) || index === 0,
            onSelect: () => moveRow(index, -1),
          })
          actions.push({
            label: t('actions.moveDown'),
            icon: 'i-lucide-arrow-down',
            disabled: rowLocked(row.original) || index === rows.value.length - 1,
            onSelect: () => moveRow(index, 1),
          })
        }
        if (hasDeleteColumn.value && !inlineButtons.length) {
          actions.push({
            label: t('actions.delete'),
            icon: 'i-lucide-trash-2',
            color: 'error',
            disabled: rowLocked(row.original),
            onSelect: () => removeRow(index),
          })
        }
        const menu = actions.length
          ? h(TableMenu, { items: menuItems }, {
              default: () => h(TableButton, {
                icon: 'i-lucide-ellipsis',
                color: 'neutral',
                variant: 'ghost',
                size: 'xs',
                square: true,
                'aria-label': t('common.actions'),
              }),
            })
          : null
        if (!inlineButtons.length && !menu) return null
        return h('div', { class: 'flex items-center justify-end gap-1' }, [...inlineButtons, menu].filter(Boolean))
      },
    })
  }
  else if (props.viewOnlyActions) {
    cols.push({
      id: 'actions',
      header: () => h('span', { class: 'sr-only' }, t('common.actions')),
      enableSorting: false,
      meta: iconOnlyColumnMeta,
      cell: ({ row }) => h(TableButton, {
        label: 'View',
        color: 'neutral',
        variant: 'ghost',
        size: 'xs',
        onClick: () => emit('rowAction', 'view', row.original),
      }),
    })
  }
  return cols
})
</script>

<template>
  <section :class="compact ? 'space-y-2' : 'space-y-3'">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <h3 v-if="!table.hideTitle" :class="compact ? 'text-xs font-semibold text-highlighted' : 'text-sm font-semibold text-highlighted'">
        {{ tableTitle(table) }}
      </h3>
      <div class="flex flex-wrap items-center justify-end gap-1.5">
        <UButton
          v-for="(action, index) in headerActions"
          :key="index"
          :size="compact ? 'xs' : 'sm'"
          color="neutral"
          variant="soft"
          :icon="action.icon"
          :label="action.label"
          :disabled="action.disabled"
          @click="action.onClick"
        />
        <UButton
v-if="!disabled && !table.hideAddRow"
:size="compact ? 'xs' : 'sm'"
color="neutral"
variant="soft"
          :icon="isFileTable ? 'i-lucide-upload' : 'i-lucide-plus'"
          :label="isFileTable && uploading
            ? t('freight.ui.uploading')
            : (table.addLabelKey && te(table.addLabelKey) ? t(table.addLabelKey) : (table.addLabel || t('freight.ui.addRow')))"
          :loading="isFileTable && uploading"
          @click="addRow" />
      </div>
    </div>
    <input
v-if="isFileTable && !disabled"
ref="inputRef"
type="file"
multiple
class="hidden"
:disabled="uploading"
@change="onFilesChosen">
    <FreightAppLineDetailsDialog
      v-if="table.lineDetails"
      v-model:open="detailsOpen"
      :max-discount="detailsSubtotal"
      :discount="Number(detailsRow.discountAmount ?? detailsRow.discount) || 0"
      :tax-rate="Number(detailsRow.taxRate) || 0"
      :disabled="disabled"
      @save="saveLineDetails" />
    <CommonAppFormErrorSummary
      v-if="rejected.length"
      :form-errors="rejected"
      :title="t('freight.ui.fileRejectedTitle')"
    />
    <div class="overflow-x-auto">
      <UTable
:data="tableRows"
:columns="columns"
        :get-row-id="(row: Record<string, unknown>) => String(row._rowIndex ?? '')"
        :class="['freight-table w-full min-w-max', compact ? 'freight-table-compact' : '']"
:ui="tableUi" />
    </div>
  </section>
</template>

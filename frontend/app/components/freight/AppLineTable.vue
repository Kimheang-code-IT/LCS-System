<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { h, type Component } from 'vue'
import { CommonAppReferenceSelect, CommonAppInputDate, UButton, UCheckbox, UDropdownMenu, UIcon, UInput, UInputNumber } from '#components'
import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import { FREIGHT_LINE_UTILITY_COLUMN_TYPES } from '~/config/freight-modules'
import { useFreightLabel } from '~/composables/freight/useFreight'
import type { DatePickerGranularity } from '~/utils/date-picker'
import { fileTableRowBy, fileTableRowCreated, fileTableRowName, filePreviewHref, revokeFilePreview, useFileAttachments } from '~/utils/freight/attachments'
import { fileTypeIcon } from '~/utils/file-icon'
import { formatDate, formatDateTime, formatMoney, formatNumber } from '~/utils/format/format-service'
import { freightTableUiCompactReadonly, freightTableUiLine } from '~/utils/table/theme'
import { isMoneyColumnKey, lineTableColumnCellClass, lineTableNumericColumnKeys } from '~/utils/table/line-table-columns'
import { referenceOptionSource, referenceSelectItems } from '~/utils/freight/reference-options'

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
}>(), {
  compact: false,
  rowDisabled: undefined,
  headerActions: () => [],
  extraRowMenuItems: undefined,
  rowInlineActions: undefined,
  rowActions: undefined,
  onReorder: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [Array<Record<string, unknown>>]
  'rowAction': [action: 'view', row: Record<string, unknown>]
}>()

const { t, te } = useI18n()
const { fieldLabel, tableTitle } = useFreightLabel()
const { inputRef, openPicker, rowsFromInput } = useFileAttachments()

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
const cellSize = 'sm' as const
const cellInputUi = { base: 'text-sm' }
const cellNumberInputUi = { base: 'text-sm text-right tabular-nums' }
const tableUi = computed(() => props.compact ? freightTableUiCompactReadonly : freightTableUiLine)

const numericKeys = lineTableNumericColumnKeys()

const store = useFreightStore()

// Master Data pages drive these line-table selects; static `column.options` are
// ignored when a reference source matches the column key.
const referenceColumnItems = computed<Record<string, Array<{ label: string, value: string }>>>(() => {
  const map: Record<string, Array<{ label: string, value: string }>> = {}
  for (const column of props.table.columns) {
    const source = referenceOptionSource(column.key)
    if (source) map[column.key] = referenceSelectItems(store.list(source.collection), source)
  }
  return map
})

function columnCellClass(column: FreightLineColumn) {
  return lineTableColumnCellClass(column)
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
      if (column.key === 'total' && currency) return formatMoney(number, currency)
      return formatMoney(number, currency)
    }
    return formatNumber(number, { maximumFractionDigits: 2, minimumFractionDigits: 0 })
  }
  if (column.type === 'date') return formatDate(value)
  if (column.type === 'datetime') return formatDateTime(value)
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
  return h('div', { class: numericKeys.has(column.key) ? 'text-right' : '' }, [
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
        h(TableInputNumber, {
          'modelValue': Number(row[field.key] || 0),
          'increment': false,
          'decrement': false,
          'size': cellSize,
          'class': 'w-20',
          'ui': cellNumberInputUi,
          'aria-label': fieldLabel(field),
          'onUpdate:modelValue': (value: number | null) => updateCell(index, field.key, value ?? 0),
        }),
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
        h(TableInputNumber, {
          'modelValue': Number(row[field.key] || 0),
          'increment': false,
          'decrement': false,
          'size': cellSize,
          'class': 'w-20',
          'ui': cellNumberInputUi,
          'aria-label': fieldLabel(field),
          'onUpdate:modelValue': (value: number | null) => updateCell(index, field.key, value ?? 0),
        }),
      ]),
    )),
  ])
}

const rows = computed({
  get: () => props.modelValue || [],
  set: value => emit('update:modelValue', value),
})

function rowLocked(row: Record<string, unknown>) {
  return props.disabled || Boolean(props.rowDisabled?.(row))
}

const tableRows = computed(() => rows.value.map((row, index) => ({ ...row, _rowIndex: index })))

function updateCell(index: number, key: string, value: unknown) {
  const edited = rows.value.map((row, i) => i === index ? { ...row, [key]: value } : row)
  const target = edited[index]
  if (!target) return
  // Derived values come from the table's own `computeRow`, never from a
  // table-key branch here.
  const computed = props.table.computeRow?.({ row: target, rows: edited, index }) || {}
  rows.value = edited.map((row, i) => i === index ? { ...row, ...computed } : row)
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
      const referenceItems = referenceColumnItems.value[column.key]
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

function onFilesChosen(event: Event) {
  const added = rowsFromInput(event)
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

function removeRow(index: number) {
  const row = rows.value[index]
  if (row) revokeFilePreview(row)
  rows.value = rows.value.filter((_, i) => i !== index)
}

function reorderCell(column: FreightLineColumn, row: Record<string, unknown>, index: number, disabled: boolean) {
  const move = (direction: -1 | 1) => {
    const target = index + direction
    if (target < 0 || target >= rows.value.length) return
    const next = [...rows.value]
    const [moved] = next.splice(index, 1)
    next.splice(target, 0, moved!)
    rows.value = next
    props.onReorder?.(next)
  }
  return h('div', { class: 'flex items-center gap-0.5' }, [
    h(TableButton, {
      'icon': 'i-lucide-arrow-up',
      'color': 'neutral',
      'variant': 'ghost',
      'size': 'xs',
      'square': true,
      'disabled': disabled || index === 0,
      'aria-label': t('actions.moveUp'),
      'title': t('actions.moveUp'),
      'onClick': () => move(-1),
    }),
    h(TableButton, {
      'icon': 'i-lucide-arrow-down',
      'color': 'neutral',
      'variant': 'ghost',
      'size': 'xs',
      'square': true,
      'disabled': disabled || index === rows.value.length - 1,
      'aria-label': t('actions.moveDown'),
      'title': t('actions.moveDown'),
      'onClick': () => move(1),
    }),
  ])
}

const columns = computed<TableColumn<Record<string, unknown>>[]>(() => {
  const cols: TableColumn<Record<string, unknown>>[] = [
    {
      id: 'rowNumber',
      header: '#',
      cell: ({ row }) => h('span', { class: props.compact ? 'text-[11px] tabular-nums text-muted' : 'text-xs tabular-nums text-muted' }, Number(row.original._rowIndex || 0) + 1),
      enableSorting: false,
    },
    ...props.table.columns.map(column => ({
      accessorKey: column.key,
      header: () => columnHeader(column),
      enableSorting: false,
      cell: ({ row }: { row: { original: Record<string, unknown> } }) => {
        const index = Number(row.original._rowIndex || 0)
        const disabled = rowLocked(row.original)
        if (isFileTable.value && column.key === 'fileName') return fileNameCell(row.original)
        if (column.type === 'delete') {
          return h(TableButton, {
            icon: 'i-lucide-trash-2',
            color: 'error',
            variant: 'ghost',
            size: 'xs',
            square: true,
            disabled,
            'aria-label': t('actions.delete'),
            onClick: () => removeRow(index),
          })
        }
        if (column.type === 'reorder') {
          return reorderCell(column, row.original, index, disabled)
        }
        if (column.type === 'action') {
          const action = props.rowActions?.(column.action || column.key, row.original)
          if (!action) return null
          return h(TableButton, {
            'icon': action.icon,
            'color': action.color || 'neutral',
            'variant': 'ghost',
            'size': 'xs',
            'square': true,
            'aria-label': action.label,
            'title': action.label,
            'onClick': action.onSelect,
          })
        }
        if (column.inlineFields?.length && !isMoneyColumnKey(column.key)) {
          return inlineNumberFieldsCell(column, row.original, index, disabled)
        }
        if (disabled || column.computed || isFileTable.value) {
          return inlineMoneyCell(column, row.original, index, disabled)
        }
        if (column.type === 'checkbox') {
          return h(TableCheckbox, {
            'modelValue': row.original[column.key],
            'trueValue': String(column.options?.[0] ?? 'Yes'),
            'falseValue': String(column.options?.[1] ?? 'No'),
            'disabled': disabled || column.computed,
            'size': cellSize,
            'aria-label': fieldLabel(column),
            'onUpdate:modelValue': (value: unknown) => updateCell(index, column.key, value),
          })
        }
        if (column.type === 'select') {
          const referenceItems = referenceColumnItems.value[column.key]
          const items = column.optionItems?.length
            ? column.optionItems
            : referenceItems
              ? referenceItems
              : (column.options || []).filter(Boolean).map(option => ({ label: option, value: option }))
          return h(TableReferenceSelect, {
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
          })
        }
        if (column.type === 'number') {
          return h(TableInputNumber, {
            'modelValue': Number(row.original[column.key] || 0),
            'disabled': disabled || column.computed,
            'increment': false,
            'decrement': false,
            'size': cellSize,
            'class': ['w-full', columnCellClass(column)],
            'ui': cellNumberInputUi,
            'onUpdate:modelValue': (value: number | null) => updateCell(index, column.key, value ?? 0),
          })
        }
        const dateGranularity = lineDateGranularity(column)
        if (dateGranularity) {
          return h(TableDate, {
            'modelValue': String(row.original[column.key] ?? ''),
            'granularity': dateGranularity,
            'disabled': disabled || column.computed,
            'size': cellSize,
            'class': `w-full ${columnCellClass(column)}`,
            'onUpdate:modelValue': (value: string) => updateCell(index, column.key, value),
          })
        }
        return h(TableInput, {
          'modelValue': String(row.original[column.key] ?? ''),
          'disabled': disabled || column.computed,
          'size': cellSize,
          'class': `w-full ${columnCellClass(column)}`,
          'ui': cellInputUi,
          'onUpdate:modelValue': (value: string) => updateCell(index, column.key, value),
        })
      },
    })),
  ]
  if (!hasDeleteColumn.value && (!props.disabled || props.rowDisabled || props.extraRowMenuItems || props.rowInlineActions)) {
    cols.push({
      id: 'actions',
      header: () => h('span', { class: 'sr-only' }, t('common.actions')),
      enableSorting: false,
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
            onClick: item.onSelect,
          }),
        )
        const menuItems: Array<Array<{ label: string, icon: string, color?: 'error', onSelect: () => void }>> = [[]]
        const actions = menuItems[0]!
        for (const item of props.extraRowMenuItems?.(row.original) || []) {
          actions.push({
            label: item.label,
            icon: item.icon || 'i-lucide-file',
            ...(item.color === 'error' ? { color: 'error' as const } : {}),
            onSelect: item.onSelect,
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
        if (!rowLocked(row.original)) {
          actions.push({
            label: t('actions.delete'),
            icon: 'i-lucide-trash-2',
            color: 'error',
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
      <h3 :class="compact ? 'text-xs font-semibold text-highlighted' : 'text-sm font-semibold text-highlighted'">
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
v-if="!disabled"
:size="compact ? 'xs' : 'sm'"
color="neutral"
variant="soft"
          :icon="isFileTable ? 'i-lucide-upload' : 'i-lucide-plus'"
          :label="table.addLabelKey && te(table.addLabelKey) ? t(table.addLabelKey) : (table.addLabel || t('freight.ui.addRow'))"
          @click="addRow" />
      </div>
    </div>
    <input
v-if="isFileTable && !disabled"
ref="inputRef"
type="file"
multiple
class="hidden"
@change="onFilesChosen">
    <div class="overflow-x-auto">
      <UTable
:data="tableRows"
:columns="columns"
        :get-row-id="(row: Record<string, unknown>) => String(row._rowIndex ?? '')"
        :class="['freight-table min-w-max', compact ? 'freight-table-compact' : '']"
:ui="tableUi" />
    </div>
  </section>
</template>

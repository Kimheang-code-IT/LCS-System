import type { DropdownMenuItem, TableColumn } from '@nuxt/ui'
import { h } from 'vue'
import { TableAppTableRowMeta, UCheckbox } from '#components'
import { freightTableCheckboxMeta } from '~/utils/table/theme'

type Translate = (key: string) => string
/** Leading checkbox column for list tables (header + row). */
export function listTableSelectColumn<T extends Record<string, unknown>>(
  t: Translate,
): TableColumn<T> {
  return {
    id: 'select',
    meta: freightTableCheckboxMeta,
    header: ({ table }) => h('div', { class: 'flex items-center justify-center' }, [
      h(UCheckbox, {
        'modelValue': table.getIsSomePageRowsSelected() ? 'indeterminate' : table.getIsAllPageRowsSelected(),
        'onUpdate:modelValue': (value: unknown) => table.toggleAllPageRowsSelected(Boolean(value)),
        'aria-label': t('freight.ui.selectAll'),
      }),
    ]),
    cell: ({ row }) => h('div', { class: 'flex items-center justify-center' }, [
      h(UCheckbox, {
        'modelValue': row.getIsSelected(),
        'onUpdate:modelValue': (value: unknown) => row.toggleSelected(Boolean(value)),
        'aria-label': t('freight.ui.selectRow'),
      }),
    ]),
    enableSorting: false,
    enableHiding: false,
  }
}

/** The row label behind the menu trigger's accessible name ("Actions for INV…"). */
function rowLabel(row: Record<string, unknown>): string {
  return String(row.documentNo || row.quotationNo || row.jobNo || row.code || row.name || row.id || '')
}

/** Trailing row-actions column: sticky "Actions" header and a ⋯ menu per row. */
export function listTableRowMetaColumn<T extends Record<string, unknown>>(options: {
  items: (row: T) => DropdownMenuItem[][]
  loadingId?: string
}): TableColumn<T> {
  return {
    id: 'actions',
    header: () => h('div', { class: 'flex items-center justify-center gap-1.5 text-xs font-normal text-muted' }, 'Actions'),
    enableSorting: false,
    enableHiding: false,
    // Sticks to the right edge so the ⋯ menu stays reachable while the table
    // scrolls horizontally (financial document lists are wide). Header and
    // trigger are centred, like every other list table.
    meta: { class: { td: 'text-center whitespace-nowrap sticky right-0 bg-default', th: 'sticky right-0 bg-default w-20 text-center' } },
    cell: ({ row }) => h(TableAppTableRowMeta, {
      items: options.items(row.original),
      loading: options.loadingId === String((row.original as Record<string, unknown>).id || ''),
      label: rowLabel(row.original as Record<string, unknown>),
    }),
  }
}

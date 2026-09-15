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

/** Trailing avatar / relative time / comments / ⋯ column. */
export function listTableRowMetaColumn<T extends Record<string, unknown>>(options: {
  summary: string
  items: (row: T) => DropdownMenuItem[][]
  loadingId?: string
}): TableColumn<T> {
  return {
    id: 'actions',
    header: () => h('div', { class: 'flex items-center justify-end gap-1.5 text-xs font-normal text-muted' }, [
      h('span', options.summary),
    ]),
    enableSorting: false,
    enableHiding: false,
    meta: { class: { td: 'text-end whitespace-nowrap', th: 'w-52' } },
    cell: ({ row }) => h(TableAppTableRowMeta, {
      row: row.original,
      items: options.items(row.original),
      loading: options.loadingId === String(row.original.id || ''),
    }),
  }
}

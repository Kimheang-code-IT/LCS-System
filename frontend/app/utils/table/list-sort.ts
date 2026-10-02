import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import { isMoneyKey, isNumericKey } from '~/utils/freight/job-workspace'

export type ListSortKind = 'date' | 'number' | 'text'
export type ListSortDir = 'asc' | 'desc'

export interface ListSortOption {
  /** Menu item id (`columnKey:dir`). */
  id: string
  columnKey: string
  /** Column header this option belongs to. */
  header: string
  kind: ListSortKind
  dir: ListSortDir
}

/**
 * One sortable column with its two directions, in the order the toolbar menu
 * renders them: the column is a submenu trigger, the directions its items.
 */
export interface ListSortColumn {
  key: string
  header: string
  kind: ListSortKind
  /** Ascending first, then descending. */
  options: ListSortOption[]
}

export type ListSortSelection = { key: string, dir: ListSortDir } | null

type Translate = (key: string, values?: Record<string, unknown>) => string

/**
 * Direction labels per value kind: dates read old→new, numbers and document
 * sequence numbers read small→large, everything else reads A→Z.
 */
export function listSortDirectionLabel(kind: ListSortKind, dir: ListSortDir, t: Translate): string {
  if (kind === 'date') return t(dir === 'asc' ? 'freight.ui.sortOldToNew' : 'freight.ui.sortNewToOld')
  if (kind === 'number') return t(dir === 'asc' ? 'freight.ui.sortSmallToLarge' : 'freight.ui.sortLargeToSmall')
  return t(dir === 'asc' ? 'freight.ui.sortAToZ' : 'freight.ui.sortZToA')
}

/** Fallback kind derived from the column key when the page didn't declare one. */
export function listSortKindFor(key: string): ListSortKind {
  if (/date/i.test(key) || /(_at|At)$/.test(key)) return 'date'
  if (/no$/i.test(key) || isNumericKey(key) || isMoneyKey(key)) return 'number'
  return 'text'
}

/** Reads the `meta.sortKind` a page declared on a column, if it is a known kind. */
export function listSortColumnKind<T extends Record<string, unknown>>(column: TableColumn<T>): ListSortKind | null {
  const declared = (column.meta as { sortKind?: ListSortKind } | undefined)?.sortKind
  return declared === 'date' || declared === 'number' || declared === 'text' ? declared : null
}

/** Reads the `meta.sortDisabled` a page declared on a column. */
export function listSortColumnDisabled<T extends Record<string, unknown>>(column: TableColumn<T>): boolean {
  return column.enableSorting === false || (column.meta as { sortDisabled?: boolean } | undefined)?.sortDisabled === true
}

/** Human description of the active sort, used for the toolbar button tooltip. */
export function listSortSummary(option: ListSortOption | null, t: Translate): string {
  if (!option) return t('freight.ui.sortDefault')
  return t('freight.ui.sortActive', {
    column: option.header,
    direction: listSortDirectionLabel(option.kind, option.dir, t),
  })
}

/**
 * One entry per sortable column, each carrying its ascending and descending
 * option. Columns without an accessor (select/actions) and columns excluded via
 * `enableSorting: false` or `meta.sortDisabled` are skipped.
 */
export function listSortColumns<T extends Record<string, unknown>>(columns: TableColumn<T>[]): ListSortColumn[] {
  const result: ListSortColumn[] = []
  for (const column of columns) {
    if (listSortColumnDisabled(column)) continue
    if (!('accessorKey' in column) || !column.accessorKey) continue
    const key = String(column.accessorKey)
    const header = typeof column.header === 'string' && column.header.trim() ? column.header : key
    const kind = listSortColumnKind(column) ?? listSortKindFor(key)
    result.push({
      key,
      header,
      kind,
      options: [
        { id: `${key}:asc`, columnKey: key, header, kind, dir: 'asc' },
        { id: `${key}:desc`, columnKey: key, header, kind, dir: 'desc' },
      ],
    })
  }
  return result
}

/** Flat option list (asc + desc per column), used to resolve the active sort. */
export function listSortOptions<T extends Record<string, unknown>>(columns: TableColumn<T>[]): ListSortOption[] {
  return listSortColumns(columns).flatMap(column => column.options)
}

/** The option matching the active TanStack sorting state, if any. */
export function listSortActive(options: ListSortOption[], sorting: SortingState): ListSortOption | null {
  const entry = sorting[0]
  if (!entry) return null
  return options.find(option => option.columnKey === entry.id && option.dir === (entry.desc ? 'desc' : 'asc')) ?? null
}

/** TanStack sorting state for an option (empty when clearing the sort). */
export function listSortToState(option: ListSortOption | null): SortingState {
  return option ? [{ id: option.columnKey, desc: option.dir === 'desc' }] : []
}

/** Option matching an externally supplied selection, if the column still exists. */
export function listSortFromSelection(options: ListSortOption[], selection: ListSortSelection): ListSortOption | null {
  if (!selection) return null
  return options.find(option => option.columnKey === selection.key && option.dir === selection.dir) ?? null
}

/** Selection payload for an option (null clears the sort). */
export function listSortSelectionOf(option: ListSortOption | null): ListSortSelection {
  return option ? { key: option.columnKey, dir: option.dir } : null
}

/** Selection matching a TanStack sorting state (null when unsorted). */
export function listSortSelectionFrom(options: ListSortOption[], sorting: SortingState): ListSortSelection {
  return listSortSelectionOf(listSortActive(options, sorting))
}

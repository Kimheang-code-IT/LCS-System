import type { TableColumn } from '@nuxt/ui'
import { describe, expect, it } from 'vitest'
import {
  listSortActive,
  listSortColumns,
  listSortDirectionLabel,
  listSortFromSelection,
  listSortKindFor,
  listSortOptions,
  listSortSelectionFrom,
  listSortSelectionOf,
  listSortSummary,
  listSortToState,
} from '../app/utils/table/list-sort'

type Row = Record<string, unknown>

const t = (key: string, values?: Record<string, unknown>) => {
  if (key === 'freight.ui.sortDefault') return 'Default order'
  if (key === 'freight.ui.sortActive') return `${values?.column} · ${values?.direction}`
  if (key === 'freight.ui.sortOldToNew') return 'Oldest to newest'
  if (key === 'freight.ui.sortNewToOld') return 'Newest to oldest'
  if (key === 'freight.ui.sortSmallToLarge') return 'Smallest to largest'
  if (key === 'freight.ui.sortLargeToSmall') return 'Largest to smallest'
  if (key === 'freight.ui.sortAToZ') return 'A to Z'
  if (key === 'freight.ui.sortZToA') return 'Z to A'
  return key
}

const columns: TableColumn<Row>[] = [
  { id: 'select', enableSorting: false, header: '' } as unknown as TableColumn<Row>,
  { accessorKey: 'documentNo', header: 'Document No' },
  { accessorKey: 'status', header: 'Status' },
  { accessorKey: 'issueDate', header: 'Issue Date', meta: { sortKind: 'date' } },
  { accessorKey: 'archivedOn', header: 'Archived On', meta: { sortKind: 'date' } },
  { id: 'actions', enableSorting: false, header: 'Actions' } as unknown as TableColumn<Row>,
]

describe('list sort direction labels', () => {
  it('reads dates as old to new / new to old', () => {
    expect(listSortDirectionLabel('date', 'asc', t)).toBe('Oldest to newest')
    expect(listSortDirectionLabel('date', 'desc', t)).toBe('Newest to oldest')
  })

  it('reads numbers and document sequence numbers as small to large / large to small', () => {
    expect(listSortDirectionLabel('number', 'asc', t)).toBe('Smallest to largest')
    expect(listSortDirectionLabel('number', 'desc', t)).toBe('Largest to smallest')
  })

  it('reads everything else as A to Z / Z to A', () => {
    expect(listSortDirectionLabel('text', 'asc', t)).toBe('A to Z')
    expect(listSortDirectionLabel('text', 'desc', t)).toBe('Z to A')
  })
})

describe('list sort kind inference', () => {
  it('detects dates, numbers and text from the column key', () => {
    expect(listSortKindFor('issueDate')).toBe('date')
    expect(listSortKindFor('createdAt')).toBe('date')
    expect(listSortKindFor('documentNo')).toBe('number')
    expect(listSortKindFor('serviceOrderNo')).toBe('number')
    expect(listSortKindFor('totalAmount')).toBe('number')
    expect(listSortKindFor('partyCode')).toBe('text')
  })
})

describe('list sort columns', () => {
  const entries = listSortColumns(columns)

  it('lists one menu entry per sortable column, each with two directions', () => {
    expect(entries.map(entry => entry.key)).toEqual([
      'documentNo',
      'status',
      'issueDate',
      'archivedOn',
    ])
    expect(entries.every(entry => entry.options.map(option => option.dir).join(',') === 'asc,desc')).toBe(true)
  })

  it('skips columns without an accessor key or with sorting disabled', () => {
    expect(entries.some(entry => entry.key === 'select')).toBe(false)
    expect(entries.some(entry => entry.key === 'actions')).toBe(false)
  })

  it('honours meta.sortKind over the key heuristic', () => {
    expect(entries.map(entry => `${entry.key}:${entry.kind}`)).toEqual([
      'documentNo:number',
      'status:text',
      'issueDate:date',
      'archivedOn:date',
    ])
  })

  it('falls back to the column key when the header is not a plain string', () => {
    const [entry] = listSortColumns([{ accessorKey: 'amount', header: () => 'Amount' }])
    expect(entry.header).toBe('amount')
  })

  it('flattens to one asc + one desc option per column', () => {
    expect(listSortOptions(columns).map(option => option.id)).toEqual([
      'documentNo:asc',
      'documentNo:desc',
      'status:asc',
      'status:desc',
      'issueDate:asc',
      'issueDate:desc',
      'archivedOn:asc',
      'archivedOn:desc',
    ])
  })
})

describe('list sort state round trip', () => {
  const options = listSortOptions(columns)

  it('maps an option to TanStack sorting state and back', () => {
    const option = options.find(item => item.id === 'documentNo:desc')!
    expect(listSortToState(option)).toEqual([{ id: 'documentNo', desc: true }])
    expect(listSortActive(options, listSortToState(option))?.id).toBe('documentNo:desc')
    expect(listSortSelectionFrom(options, listSortToState(option))).toEqual({ key: 'documentNo', dir: 'desc' })
  })

  it('clears the sort', () => {
    expect(listSortToState(null)).toEqual([])
    expect(listSortActive(options, [])).toBeNull()
    expect(listSortSelectionOf(null)).toBeNull()
    expect(listSortSummary(null, t)).toBe('Default order')
  })

  it('resolves an external selection and drops it when the column is gone', () => {
    expect(listSortFromSelection(options, { key: 'status', dir: 'asc' })?.id).toBe('status:asc')
    expect(listSortFromSelection(options, { key: 'missing', dir: 'asc' })).toBeNull()
  })

  it('describes the active sort for the toolbar tooltip', () => {
    const option = options.find(item => item.id === 'issueDate:asc')!
    expect(listSortSummary(option, t)).toBe('Issue Date · Oldest to newest')
  })
})
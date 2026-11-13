import { describe, expect, it } from 'vitest'
import { createTable, getCoreRowModel, getFilteredRowModel, getPaginationRowModel } from '@tanstack/vue-table'
import { listTableCountFooter, listTableSumFooter } from '../app/utils/table/list-footers'
import { formatMoney } from '../app/utils/format/format-service'

const t = (key: string, params?: Record<string, unknown>) =>
  key === 'freight.ui.recordsFooter' ? `${params!.n} records` : key

/** Build a minimal TanStack table so footer callbacks run against real APIs. */
function table(rows: Array<Record<string, unknown>>) {
  const columns = [
    { accessorKey: 'documentNo' },
    { accessorKey: 'total' },
  ]
  const built = createTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: { pagination: { pageIndex: 0, pageSize: 20 } },
    onStateChange: () => {},
    renderFallbackValue: null,
  })
  built.getAllColumns()
  return built
}

/** Footer context matching TanStack's own: `{ table }` / `{ column }`. */
const countFooter = listTableCountFooter(t)

describe('list table footers', () => {
  it('counts the rows the table holds and shows the empty state', () => {
    const data = table([
      { documentNo: 'INV-1', total: 100 },
      { documentNo: 'INV-2', total: 200 },
    ])
    const footer = countFooter({ table: data }) as unknown as { children: string }
    expect(String(footer.children)).toContain('2 records')
    const empty = countFooter({ table: table([]) }) as unknown as { children: string }
    expect(String(empty.children)).toContain('0 records')
  })

  it('sums a money column per currency without floating-point drift', () => {
    const data = table([
      { documentNo: 'INV-1', total: 0.1, currency: 'USD' },
      { documentNo: 'INV-2', total: 0.2, currency: 'USD' },
      { documentNo: 'INV-3', total: 40_000, currency: 'KHR' },
    ])
    const column = data.getAllColumns()[1]!
    const footer = listTableSumFooter({
      currencyOf: row => String(row.currency || ''),
    })({ column }) as unknown as { children: string }
    const text = String(footer.children)
    // 0.1 + 0.2 renders as 0.30, never 0.30000000000000004; KHR is its own sum.
    expect(text).toContain(formatMoney(0.3, 'USD'))
    expect(text).toContain(formatMoney(40_000, 'KHR'))
  })

  it('prefers authoritative server totals over the loaded-page sum', () => {
    const data = table([
      { documentNo: 'INV-1', total: 100, currency: 'USD' },
      { documentNo: 'INV-2', total: 200, currency: 'USD' },
    ])
    const column = data.getAllColumns()[1]!
    const footer = listTableSumFooter({
      currencyOf: row => String(row.currency || ''),
      serverTotals: () => new Map([['USD', 12_345.5]]),
    })({ column }) as unknown as { children: string }
    expect(String(footer.children)).toContain(formatMoney(12_345.5, 'USD'))
  })

  it('shows one base-currency total when rows carry a stored conversion', () => {
    const data = table([
      { documentNo: 'INV-1', total: 100, currency: 'USD', baseTotalAmount: 100 },
      { documentNo: 'INV-2', total: 40_000, currency: 'KHR', baseTotalAmount: 10 },
    ])
    const column = data.getAllColumns()[1]!
    const footer = listTableSumFooter({
      currencyOf: row => String(row.currency || ''),
      baseCurrency: 'USD',
      baseAmountOf: row => (row.baseTotalAmount as number | undefined) ?? null,
    })({ column }) as unknown as { children: string }
    const text = String(footer.children)
    expect(text).toContain(formatMoney(110, 'USD'))
    // Never two currencies joined together.
    expect(text).not.toContain('·')
  })

  it('falls back to per-currency totals when a row has no stored conversion', () => {
    const data = table([
      { documentNo: 'INV-1', total: 100, currency: 'USD', baseTotalAmount: 100 },
      { documentNo: 'INV-2', total: 40_000, currency: 'KHR' },
    ])
    const column = data.getAllColumns()[1]!
    const footer = listTableSumFooter({
      currencyOf: row => String(row.currency || ''),
      baseCurrency: 'USD',
      baseAmountOf: row => (row.baseTotalAmount as number | undefined) ?? null,
    })({ column }) as unknown as { children: string }
    const text = String(footer.children)
    expect(text).toContain(formatMoney(100, 'USD'))
    expect(text).toContain(formatMoney(40_000, 'KHR'))
  })

  it('renders nothing for an empty table', () => {
    const data = table([])
    const column = data.getAllColumns()[1]!
    expect(listTableSumFooter({ currencyOf: row => String(row.currency || '') })({ column })).toBeNull()
  })
})

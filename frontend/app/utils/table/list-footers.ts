import type { Column, Table } from '@tanstack/vue-table'
import { h } from 'vue'
import { scaledDecimal, scaledNumber } from '~/utils/freight/finance-summary'
import { formatMoney } from '~/utils/format/format-service'

/**
 * Reusable list-table footers (the `<tfoot>` row TanStack renders whenever a
 * column defines `footer`). Two shared shapes:
 *
 * - a record count under the first column ("20 records"),
 * - a decimal-safe sum under a money column.
 *
 * Sums group by the row's currency — mixed-currency tables never collapse two
 * currencies into one number. Scope is the rows the table holds after the
 * list's own filters ("loaded rows"): the freight workspace loads its whole
 * filtered dataset per module, and the one genuinely paginated collection
 * (financial documents) passes authoritative per-currency totals from the
 * server via `serverTotals` instead of summing the loaded page.
 */

type Translate = (key: string, params?: Record<string, unknown>) => string

export interface ListTableSumFooterOptions<T> {
  /** Row currency accessor; rows without one share an unlabeled total. */
  currencyOf?: (row: T) => string
  /**
   * Authoritative per-currency values for this column, supplied by the server
   * for a paginated list. When it returns a non-empty map it replaces the
   * client-side sum entirely.
   */
  serverTotals?: () => Map<string, number> | null
  /**
   * The configured base currency. When supplied together with `baseAmountOf`,
   * the footer shows ONE base-currency total instead of per-currency groups.
   */
  baseCurrency?: string
  /**
   * A row's amount already expressed in the base currency (a stored conversion:
   * `baseTotalAmount`, or amount × the row's stored `exchangeRate`). Returning
   * null for any row falls back to the per-currency display, so an amount is
   * never converted with a guessed rate.
   */
  baseAmountOf?: (row: T) => number | null
}

/** "N records" cell for the first footer column; scope = rows the table holds. */
export function listTableCountFooter<T>(t: Translate) {
  return ({ table }: { table: Table<T> }) => {
    const count = table.getCoreRowModel().rows.length
    return h('span', { class: 'text-xs font-semibold text-highlighted' }, t('freight.ui.recordsFooter', { n: count }))
  }
}

/** Per-currency, decimal-safe sum cell for one money column. */
export function listTableSumFooter<T extends Record<string, unknown>>(
  options: ListTableSumFooterOptions<T> = {},
) {
  return ({ column }: { column: Column<T, unknown> }) => {
    const server = options.serverTotals?.()
    if (server && server.size) {
      return footerText([...server.entries()].map(([currency, value]) => formatMoney(value, currency)))
    }
    const rows = column.getFacetedRowModel().rows
    // One base-currency total when every row carries its own stored conversion.
    if (options.baseCurrency && options.baseAmountOf) {
      let total = 0n
      let complete = rows.length > 0
      for (const row of rows) {
        const value = options.baseAmountOf(row.original)
        if (value == null) {
          complete = false
          break
        }
        total += scaledDecimal(value)
      }
      if (complete) return footerText([formatMoney(scaledNumber(total), options.baseCurrency)])
    }
    const sums = new Map<string, bigint>()
    for (const row of rows) {
      const currency = (options.currencyOf?.(row.original) || '').trim()
      sums.set(currency, (sums.get(currency) || 0n) + scaledDecimal(row.getValue(column.id)))
    }
    if (!sums.size) return null
    return footerText([...sums.entries()]
      .map(([currency, value]) => formatMoney(scaledNumber(value), currency || undefined)))
  }
}

function footerText(parts: string[]) {
  return h('div', { class: 'text-xs font-semibold tabular-nums text-highlighted' }, parts.join(' · '))
}

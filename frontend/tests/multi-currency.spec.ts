/**
 * Multi-currency in the document form and in Master Data.
 *
 * The backend owns the arithmetic and stores it (`backend/tests/test_multi_currency.py`);
 * what is pinned here is what the operator sees against a record:
 *
 *  - the exchange rate is hidden while the document currency *is* the base
 *    currency, and appears the moment they differ;
 *  - a base-currency document converts at 1, whatever was typed before the
 *    currency was changed;
 *  - the converted total follows the rate, the document total and the currency's
 *    configured precision, and stays empty rather than showing a misleading zero
 *    when no usable rate is present;
 *  - the rate reads in the direction a person reads it ("1 USD = 4,000 KHR");
 *  - the rate store is a Master Data page, and no hardcoded currency list is left.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { getFreightModule } from '../app/config/freight-modules'
import { lcsReferenceModules } from '../app/config/lcs-reference-modules'
import { REMOTE_ENDPOINTS, endpointFor } from '../app/utils/api/freight-remote'
import { recalculateFreightRecord } from '../app/utils/freight/document-calculations'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'
import { rateDirection } from '../app/utils/freight/fx'
import { referenceOptionSource } from '../app/utils/freight/reference-options'
import type { FreightRecord } from '../app/types/record'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const finance = getFreightModule('/finance/documents')!
const rateModule = lcsReferenceModules.find(item => item.path === '/master-data/currency-rates')

/** The Overview field keys the form compiles for a record. */
function overviewKeys(record: Record<string, unknown>, documentType = 'CUSTOMER_INVOICE'): string[] {
  const tabs = moduleDocumentTabs(finance, { documentType, record: record as FreightRecord })
  const overview = tabs.find(tab => tab.id === 'overview')!
  return overview.sections.flatMap(section => section.fields.map(field => field.key))
}

function recalculate(record: Record<string, unknown>): FreightRecord {
  // A finance document is line-driven: its totals are recomputed from `lines`, so a
  // test record carries the lines the form would hold for that total.
  const total = Number(record.total ?? 0)
  return recalculateFreightRecord(finance, {
    ...record,
    lines: [{ quantity: 1, unitAmount: total, discount: 0, taxAmount: 0 }],
  } as FreightRecord)
}

describe('financial document currency', () => {
  const inBaseCurrency = { currency: 'USD', baseCurrency: 'USD', currencyPrecision: 2, total: 100 }

  it('hides the exchange rate while the document is in the base currency', () => {
    const keys = overviewKeys(inBaseCurrency)

    expect(keys).not.toContain('exchangeRate')
    expect(keys).not.toContain('rateDirection')
    // What the document converts into is still stated, and so is the converted total.
    expect(keys).toContain('baseCurrency')
    expect(keys).toContain('baseTotalAmount')
  })

  it('shows the exchange rate as soon as the currencies differ', () => {
    const keys = overviewKeys({ ...inBaseCurrency, currency: 'KHR', exchangeRate: 0.00025 })

    expect(keys).toContain('exchangeRate')
    expect(keys).toContain('rateDirection')
  })

  it('keeps the rate visible when the record carries no base currency to compare with', () => {
    // A rule that cannot be evaluated must not hide a field the operator needs.
    expect(overviewKeys({ currency: 'KHR' })).toContain('exchangeRate')
  })

  it('always converts a base-currency document at 1', () => {
    const next = recalculate({ ...inBaseCurrency, exchangeRate: 5 })

    expect(next.exchangeRate).toBe(1)
    expect(next.baseTotalAmount).toBe(100)
    expect(next.rateDirection).toBe('')
  })

  it('recalculates the converted total from the rate and the document total', () => {
    const next = recalculate({
      currency: 'KHR',
      baseCurrency: 'USD',
      currencyPrecision: 2,
      exchangeRate: 0.00025,
      total: 1_000_000,
    })

    expect(next.baseTotalAmount).toBe(250)
  })

  it('rounds with the precision the currency is configured with', () => {
    const next = recalculate({
      currency: 'KHR',
      baseCurrency: 'USD',
      currencyPrecision: 0,
      exchangeRate: 0.00025,
      total: 100,
    })

    // 100 KHR is 0.025 USD; the Riel is configured with no minor unit.
    expect(next.baseTotalAmount).toBe(0)
  })

  it('leaves the converted total empty instead of zero when no rate is usable', () => {
    const next = recalculate({ currency: 'KHR', baseCurrency: 'USD', currencyPrecision: 2, total: 100 })

    expect(next.baseTotalAmount).toBeNull()
    expect(next.rateDirection).toBe('')
  })

  it('reads the rate the way an operator reads it', () => {
    // A rate below 1 is what the ledger stores for a small unit against a large
    // one; the display inverts it rather than printing six zeros.
    expect(rateDirection('KHR', 'USD', 0.00025)).toMatch(/^1 USD = 4,?000 KHR$/)
    expect(rateDirection('USD', 'KHR', 4000)).toMatch(/^1 USD = 4,?000 KHR$/)
    expect(rateDirection('USD', 'USD', 1)).toBe('')
    expect(rateDirection('KHR', 'USD', 0)).toBe('')
    expect(rateDirection('', 'USD', 2)).toBe('')
  })

  it('gives the document form a base currency, a converted total and a direction', () => {
    const keys = finance.fields.map(field => field.key)
    expect(keys).toEqual(expect.arrayContaining(['baseCurrency', 'baseTotalAmount', 'rateDirection']))

    const rateField = finance.fields.find(field => field.key === 'exchangeRate')
    expect(rateField?.visibleWhen).toEqual({ differs: ['currency', 'baseCurrency'] })
  })
})

describe('the rate store is managed, not hardcoded', () => {
  it('is a registered collection with a routed API and no sidebar page', () => {
    expect(rateModule?.collection).toBe('currencyRates')
    expect(REMOTE_ENDPOINTS.currencyRates).toBeDefined()
    expect(endpointFor('currencyRates')?.path).toBe('/api/v1/currencyRates')

    // The owner asked for the rate store to stay out of the menu, and no page
    // directory exists for it, so the sidebar must not link to a route that
    // would 404. Re-adding a link means adding the page in the same change.
    const menu = readFileSync(`${APP}/composables/layout/useMenu.ts`, 'utf8')
    expect(menu).not.toContain('currency-rates')
    expect(menu).not.toContain('freight.pages.currencyRates')
  })

  it('requires the pair, the date and the rate, and offers the lifecycle as values', () => {
    const required = rateModule!.fields.filter(field => field.required).map(field => field.key)
    expect(required).toEqual(
      expect.arrayContaining(['fromCurrencyCode', 'toCurrencyCode', 'effectiveDate', 'rate', 'status']),
    )

    const status = rateModule!.fields.find(field => field.key === 'status')!
    const values = (status.options ?? []).map(option => (typeof option === 'string' ? option : option.value))
    // The values are stored verbatim and only APPROVED is ever applied.
    expect(values).toEqual(['PENDING', 'APPROVED', 'INACTIVE'])
  })

  it('takes both sides of the pair from the currency master', () => {
    for (const key of ['fromCurrencyCode', 'toCurrencyCode']) {
      expect(referenceOptionSource(key)?.collection, `${key} must read the currency master`).toBe('currencies')
    }
  })

  it('leaves no hardcoded currency list in the frontend', () => {
    const options = readFileSync(`${APP}/config/freight-options.ts`, 'utf8')
    expect(options).not.toMatch(/export const CURRENCIES\b/)
  })
})

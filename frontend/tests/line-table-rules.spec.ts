import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { FreightTable } from '../app/config/freight-modules'
import { FREIGHT_LINE_UTILITY_COLUMN_TYPES, getFreightModule } from '../app/config/freight-modules'
import {
  JOB_ACTUAL_CONTAINER_TABLE,
  JOB_CONTAINER_PAYMENT_TABLE,
  JOB_CONTAINER_REQUIREMENT_TABLE,
  JOB_FINANCE_LINES_TABLE,
  JOB_ROUTE_TABLE,
} from '../app/config/job-workspace-forms'
import {
  actualContainerRowDefaults,
  computeContainerPaymentLine,
  computeDocumentLine,
  computeFeeLine,
  computeJobFinanceLine,
  computeOtherChargeLine,
  computePricingLine,
  containerPaymentRowDefaults,
  containerRequirementRowDefaults,
  jobFinanceLineRowDefaults,
  routePlaceRowDefaults,
} from '../app/utils/table/line-table-rules'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'

/** Every table that declares arithmetic must round-trip it through the config. */
const tableOf = (path: string, key: string): FreightTable => {
  const table = getFreightModule(path)?.tables?.find(candidate => candidate.key === key)
  if (!table) throw new Error(`missing table ${key} on ${path}`)
  return table
}

const computed = (path: string, key: string, row: Record<string, unknown>) => {
  const table = tableOf(path, key)
  if (!table.computeRow) throw new Error(`table ${key} declares no computeRow`)
  return table.computeRow({ row, rows: [row], index: 0 })
}

describe('line table row rules', () => {
  it('keeps pricing lines at qty x unit price, less discount, plus tax', () => {
    expect(computed('/quotations', 'pricingLines', {
      quantity: 2,
      unitPrice: 1000,
      discountAmount: 100,
      taxAmount: 190,
    })).toEqual({ lineTotal: 2090 })
  })

  it('never lets a pricing line total go below zero', () => {
    expect(computed('/quotations', 'pricingLines', {
      quantity: 1,
      unitPrice: 100,
      discountAmount: 500,
      taxAmount: 0,
    })).toEqual({ lineTotal: 0 })
  })

  it('computes service charge fee lines without rounding, as stored totals expect', () => {
    // 3 x 33.335 = 100.005 -> deliberately left unrounded.
    const result = computed('/service-charges', 'feeLines', {
      quantity: 3,
      unitAmount: 33.335,
      discount: 0,
      taxAmount: 0,
    })
    expect(result.amount).toBeCloseTo(100.005, 10)
    expect(result.amount).not.toBe(100.01)
  })

  it('subtracts discount before adding tax on fee lines', () => {
    expect(computed('/service-charges', 'feeLines', {
      quantity: 2,
      unitAmount: 1000,
      discount: 100,
      taxAmount: 50,
    })).toEqual({ amount: 1950 })
  })

  it('falls back to the tax rate when a financial line carries no tax amount', () => {
    expect(computed('/finance/documents', 'lines', {
      quantity: 2,
      unitAmount: 1000,
      discount: 100,
      tax: 190,
    })).toEqual({ amount: 2090 })

    expect(computed('/finance/documents', 'lines', {
      quantity: 2,
      unitAmount: 1000,
      discount: 100,
      taxAmount: 50,
    })).toEqual({ amount: 1950 })
  })

  it('computes other charges and unified finance lines on their own bases', () => {
    expect(computeOtherChargeLine({ row: { quantity: 3, sellingRate: 12.5 } })).toEqual({ amount: 37.5 })
    expect(computeJobFinanceLine({
      row: { _kind: 'EXPENSE', quantity: 3, unitPrice: 12.5 },
    })).toEqual({ amount: 37.5 })
  })

  it('never prices the locked charge and document rows of the finance grid', () => {
    expect(computeJobFinanceLine({
      row: { _kind: 'CHARGE', quantity: 3, unitPrice: 12.5, amount: 500 },
    })).toEqual({})
    expect(computeJobFinanceLine({
      row: { _kind: 'DOCUMENT', quantity: 1, unitPrice: 900, amount: 900 },
    })).toEqual({})
    // A row with no recognised kind is left alone rather than silently repriced.
    expect(computeJobFinanceLine({ row: { quantity: 3, unitPrice: 12.5 } })).toEqual({})
  })

  it('keeps an explicit container payment tax amount', () => {
    expect(computeContainerPaymentLine({
      row: { quantity: 2, unitPrice: 1000, discountAmount: 100, taxRate: 10, taxAmount: 50 },
    })).toMatchObject({ lineTotal: 1950 })
  })
})

describe('line table row defaults', () => {
  it('carries the previous payment container forward but falls back to the blank', () => {
    expect(containerPaymentRowDefaults({
      rows: [{ quantity: 3, containerNo: 'MSCU 1', feeType: 'Trucking' }],
      blank: { feeType: 'Customs' },
    })).toMatchObject({ quantity: 3, containerNo: 'MSCU 1', feeType: 'Trucking', lineTotal: 0 })

    // No previous row: the blank's own column default survives.
    expect(containerPaymentRowDefaults({ rows: [], blank: { feeType: 'Customs' } }))
      .toMatchObject({ quantity: 1, containerNo: '', feeType: 'Customs' })
  })

  it('numbers a new route row after the rows already present', () => {
    expect(routePlaceRowDefaults({ rows: [{}, {}] })).toEqual({
      place: '',
      planned: '',
      actual: '',
      notes: '',
      sequence: 3,
    })
  })

  it('seeds the remaining default rows', () => {
    expect(containerRequirementRowDefaults()).toMatchObject({ quantity: 1, remaining: 1 })
    expect(actualContainerRowDefaults()).toMatchObject({ status: 'Expected' })
  })

  it('always appends the finance grid as an expense row', () => {
    expect(jobFinanceLineRowDefaults()).toMatchObject({ _kind: 'EXPENSE', quantity: 1, amount: 0 })
  })
})

describe('line table config is self describing', () => {
  it('declares behaviour on the table instead of a table-key branch', () => {
    expect(tableOf('/quotations', 'pricingLines').computeRow).toBe(computePricingLine)
    expect(tableOf('/service-charges', 'feeLines').computeRow).toBe(computeFeeLine)
    expect(tableOf('/finance/documents', 'lines').computeRow).toBe(computeDocumentLine)
    expect(tableOf('/sales/quotations', 'otherCharges').computeRow).toBe(computeOtherChargeLine)
    expect(JOB_CONTAINER_PAYMENT_TABLE.computeRow).toBe(computeContainerPaymentLine)
    expect(JOB_CONTAINER_PAYMENT_TABLE.rowDefaults).toBe(containerPaymentRowDefaults)
    expect(JOB_FINANCE_LINES_TABLE.computeRow).toBe(computeJobFinanceLine)
    expect(JOB_FINANCE_LINES_TABLE.rowDefaults).toBe(jobFinanceLineRowDefaults)
    expect(JOB_CONTAINER_REQUIREMENT_TABLE.rowDefaults).toBe(containerRequirementRowDefaults)
    expect(JOB_ACTUAL_CONTAINER_TABLE.rowDefaults).toBe(actualContainerRowDefaults)
    expect(JOB_ROUTE_TABLE.rowDefaults).toBe(routePlaceRowDefaults)
  })

  it('marks pricing tables so tax fields and totals render', () => {
    const pricingMeta = (path: string, key: string) => moduleDocumentTabs(getFreightModule(path)!, {})
      .flatMap(tab => tab.sections.flatMap(section => section.fields))
      .find(field => field.key === key)?.meta as { showPricingTotals?: boolean, includeTax?: boolean }

    expect(pricingMeta('/quotations', 'pricingLines')).toMatchObject({ showPricingTotals: true, includeTax: true })
    expect(pricingMeta('/service-charges', 'feeLines')).toMatchObject({ showPricingTotals: true, includeTax: true })
    expect(pricingMeta('/finance/documents', 'lines')).toMatchObject({ showPricingTotals: true, includeTax: true })
    // A non-pricing table must not pull in tax handling.
    expect(pricingMeta('/quotations', 'places')).toMatchObject({ includeTax: false })
  })

  it('keeps the renderer free of table-key branches', () => {
    const source = readFileSync(
      fileURLToPath(new URL('../app/components/freight/AppLineTable.vue', import.meta.url)),
      'utf8',
    )
    expect(source).not.toMatch(/table\.key\s*===/)
    expect(source).not.toMatch(/table\.key\s*!==/)
  })

  it('treats delete, action and reorder columns as utility cells with no row data', () => {
    expect([...FREIGHT_LINE_UTILITY_COLUMN_TYPES].sort()).toEqual(['action', 'delete', 'reorder'])
    const dataColumns = JOB_CONTAINER_PAYMENT_TABLE.columns
      .filter(column => !FREIGHT_LINE_UTILITY_COLUMN_TYPES.has(column.type))
      .map(column => column.key)
    expect(dataColumns).not.toContain('_delete')
    expect(dataColumns).not.toContain('_invoice')

    // The blank row must come from the shared set, not a hardcoded `delete` check.
    const source = readFileSync(
      fileURLToPath(new URL('../app/components/freight/AppLineTable.vue', import.meta.url)),
      'utf8',
    )
    expect(source).toContain('FREIGHT_LINE_UTILITY_COLUMN_TYPES.has(column.type)')
    expect(source).not.toContain("column.type !== 'delete'")
  })
})
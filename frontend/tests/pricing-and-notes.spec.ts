/**
 * Pricing inputs and row notes.
 *
 * Two product decisions are pinned here:
 *
 * 1. **Discount and tax are enterable.** Discount and tax are per line, opened
 *    from the row menu's Additional Details dialog, and kept out of the grid so
 *    the table stays compact. The container payment sheet also keeps its
 *    sheet-level totals block; line adjustments win when present so the same
 *    allowance is never counted twice.
 *
 * 2. **A note is an inline field.** The route and container grids edit the note
 *    text in the cell, so the operator never leaves the table for a dialog.
 *
 * 3. **Row commands live in one menu.** Delete, move up/down and row actions are
 *    entries in the per-row "..." menu instead of extra icon columns.
 *
 * Both were silent failures before: the legacy sales table wrote `discount`/`tax`
 * while the calculators read `discountAmount`/`taxAmount`, so its inputs did
 * nothing. That mismatch is covered directly.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { getFreightModule } from '../app/config/freight-modules'
import { JOB_ACTUAL_CONTAINER_TABLE, JOB_CONTAINER_PAYMENT_TABLE, JOB_ROUTE_TABLE } from '../app/config/job-workspace-forms'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'
import { jobContainerPaymentTotals } from '../app/utils/freight/job-containers'
import { computePricingLine } from '../app/utils/table/line-table-rules'

const APP = fileURLToPath(new URL('../app', import.meta.url))

function source(relative: string): string {
  return readFileSync(`${APP}/${relative}`, 'utf8')
}

describe('pricing line arithmetic reads both discount and tax spellings', () => {
  const row = { quantity: 2, unitPrice: 1000 }

  it('accepts the canonical key spelling', () => {
    expect(computePricingLine({ row: { ...row, discountAmount: 100, taxAmount: 50 } }))
      .toMatchObject({ lineTotal: 1950 })
  })

  it('accepts the legacy key spelling', () => {
    // The legacy sales quotation table writes `discount`/`tax`. Reading only the
    // `...Amount` keys meant those inputs were ignored and the total never moved.
    expect(computePricingLine({ row: { ...row, discount: 100, tax: 50 } }))
      .toMatchObject({ lineTotal: 1950 })
  })

  it('treats a discount larger than the line as zero rather than negative', () => {
    expect(computePricingLine({ row: { ...row, discountAmount: 5000, taxAmount: 0 } }))
      .toMatchObject({ lineTotal: 0 })
  })

  it('adds tax on top of the discounted amount, not the gross', () => {
    expect(computePricingLine({ row: { ...row, discountAmount: 1000, taxAmount: 100 } }))
      .toMatchObject({ lineTotal: 1100 })
  })
})

describe('quotation pricing keeps adjustments out of the grid', () => {
  const field = moduleDocumentTabs(getFreightModule('/quotations')!)
    .find(tab => tab.id === 'pricing')?.sections[0]?.fields[0]

  it('offers neither as an inline field on the line total', () => {
    const columns = (field?.meta?.table as { columns: Array<{ key: string, inlineFields?: Array<{ key: string }> }> }).columns
    expect(columns.find(column => column.key === 'lineTotal')?.inlineFields).toBeUndefined()
  })

  it('keeps discount and tax out of the visible columns but offers the dialog', () => {
    const table = field?.meta?.table as { columns: Array<{ key: string }>, hideDiscountTax?: boolean, lineDetails?: boolean }
    const keys = table.columns.map(column => column.key)
    expect(keys).not.toContain('discountAmount')
    expect(keys).not.toContain('taxAmount')
    expect(table.hideDiscountTax).toBeFalsy()
    expect(table.lineDetails).toBe(true)
  })

  it('shows both totals lines from the line-level values', () => {
    expect(field?.meta?.showPricingTotals).toBe(true)
    expect(field?.meta?.showDiscountTotals).toBe(true)
    expect(field?.meta?.includeTax).toBe(true)
  })

  it('leaves the discount and tax lines on tables that do use them', () => {
    const charges = moduleDocumentTabs(getFreightModule('/service-charges')!)
      .find(tab => tab.id === 'fee-lines')?.sections[0]?.fields[0]
    expect(charges?.meta?.showDiscountTotals).toBe(true)
    expect(charges?.meta?.includeTax).toBe(true)
  })
})

describe('container payments own one discount and tax for the sheet', () => {
  it('has no per-row discount column', () => {
    expect(JOB_CONTAINER_PAYMENT_TABLE.columns.some(column => column.key === 'discountAmount')).toBe(false)
  })

  it('keeps the pricing totals block', () => {
    expect(JOB_CONTAINER_PAYMENT_TABLE.pricing).toBe(true)
  })

  it('renders editable discount and tax inputs in its own totals block', () => {
    // The payment sheet is composed by JobContainers.vue, not by the shared
    // document footer, so this is where the header-level inputs must live.
    const containers = source('components/freight/JobContainers.vue')
    expect(containers).toContain('jobContainerPaymentTotals(paymentRows.value, props.job.vatRate, props.job.discount)')
    expect(containers).toContain("emit('update:job', { discount: value ?? 0 })")
    expect(containers).toContain("emit('update:job', { vatRate: value ?? 0 })")
    expect(containers).toContain("t('freight.fields.grandTotal')")
  })

  it('labels the sheet discount and tax as header inputs, not row columns', () => {
    const columns = source('config/job-workspace-forms.ts')
    // The table definition must not reintroduce a discount column.
    const paymentTable = columns.slice(columns.indexOf('JOB_CONTAINER_PAYMENT_TABLE'))
    expect(paymentTable.slice(0, paymentTable.indexOf('}'))).not.toContain('discountAmount')
  })
})

describe('container payment totals apply one discount and tax to the sheet', () => {
  const rows = [
    { feeType: 'Trucking', quantity: 2, unitPrice: 100 },
    { feeType: 'Handling', quantity: 1, unitPrice: 50 },
  ]

  it('charges tax on the discounted amount, not the gross', () => {
    // 250 − 50 = 200 taxable; 10% of 200 is 20; grand total 220.
    expect(jobContainerPaymentTotals(rows, 10, 50)).toMatchObject({
      subtotal: 250,
      discount: 50,
      vat: 20,
      total: 220,
    })
  })

  it('is a no-op discount when none is given', () => {
    expect(jobContainerPaymentTotals(rows, 10)).toMatchObject({ subtotal: 250, discount: 0, vat: 25, total: 275 })
  })

  it('does not carry a discount larger than the subtotal', () => {
    expect(jobContainerPaymentTotals(rows, 0, 9999)).toMatchObject({ subtotal: 250, discount: 9999, vat: 0, total: 0 })
  })

  it('reads a legacy row amount when it has no line subtotal', () => {
    expect(jobContainerPaymentTotals([{ amount: 120 }], 10, 20)).toMatchObject({
      subtotal: 120,
      discount: 20,
      vat: 10,
      total: 110,
    })
  })
})
describe('notes are inline and row commands live in the menu', () => {
  it('declares a note column as a normal text field on the tables that need prose', () => {
    for (const table of [JOB_ACTUAL_CONTAINER_TABLE, JOB_CONTAINER_PAYMENT_TABLE, JOB_ROUTE_TABLE]) {
      const note = table.columns.find(column => column.type === 'note')
      expect(note, `${table.key} must expose a note column`).toBeDefined()
    }
  })

  it('renders notes as editable cells instead of a dialog icon', () => {
    const lineTable = source('components/freight/AppLineTable.vue')
    expect(lineTable).not.toContain('sticky-note')
    expect(lineTable).not.toContain('noteDialog')
    expect(lineTable).not.toContain('AppRowNoteDialog')
  })

  it('folds delete, reorder and row actions into the row menu', () => {
    const lineTable = source('components/freight/AppLineTable.vue')
    expect(lineTable).toContain('isMenuOnlyColumn(column)')
    expect(lineTable).toContain("column.type === 'delete' || column.type === 'reorder' || column.type === 'action'")
    expect(lineTable).toContain("t('actions.moveUp')")
    expect(lineTable).toContain("t('actions.moveDown')")
    expect(lineTable).toContain("t('actions.delete')")

    for (const table of [JOB_ACTUAL_CONTAINER_TABLE, JOB_CONTAINER_PAYMENT_TABLE, JOB_ROUTE_TABLE]) {
      expect(table.columns.some(column => column.type === 'delete'), `${table.key} must declare delete`).toBe(true)
      expect(table.columns.some(column => column.type === 'note'), `${table.key} must declare a note`).toBe(true)
    }
  })
})

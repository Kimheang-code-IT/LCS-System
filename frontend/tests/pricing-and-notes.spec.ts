/**
 * Pricing inputs and row notes.
 *
 * Two product decisions are pinned here:
 *
 * 1. **Discount and tax are enterable.** The quotation pricing table previously
 *    had no discount or tax input at all, so a quotation could not express
 *    either, and the container-payment sheet carried a discount column repeated
 *    on every row for what is really one discount per sheet. Quotation lines now
 *    take discount and tax inline on the line total; the container payment sheet
 *    takes them once, in the totals block.
 *
 * 2. **A note is prose behind an icon.** A one-line cell cannot hold a note, and a
 *    wide column pushes the real data off screen, so a note column renders an icon
 *    that opens a dialog.
 *
 * 3. **Note and delete share one icon column.** Both are one-icon row controls, so
 *    a table that declares both shows them side by side in a single cell instead
 *    of spending two narrow columns on every row.
 *
 * Both were silent failures before: the legacy sales table wrote `discount`/`tax`
 * while the calculators read `discountAmount`/`taxAmount`, so its inputs did
 * nothing. That mismatch is covered directly.
 */
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { getFreightModule } from '../app/config/freight-modules'
import { JOB_ACTUAL_CONTAINER_TABLE, JOB_CONTAINER_PAYMENT_TABLE, JOB_ROUTE_TABLE } from '../app/config/job-workspace-forms'
import { moduleDocumentTabs } from '../app/utils/freight/document-tabs'
import { jobContainerPaymentTotals } from '../app/utils/freight/job-containers'
import { sharedRowControls } from '../app/utils/table/line-table-columns'
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

describe('quotation pricing has no discount or tax step', () => {
  const field = moduleDocumentTabs(getFreightModule('/quotations')!)
    .find(tab => tab.id === 'pricing')?.sections[0]?.fields[0]

  it('offers neither as an inline field on the line total', () => {
    const columns = (field?.meta?.table as { columns: Array<{ key: string, inlineFields?: Array<{ key: string }> }> }).columns
    expect(columns.find(column => column.key === 'lineTotal')?.inlineFields).toBeUndefined()
  })

  it('declares no discount or tax at all on the table', () => {
    const table = field?.meta?.table as { columns: Array<{ key: string }>, hideDiscountTax?: boolean }
    const keys = table.columns.map(column => column.key)
    expect(keys).not.toContain('discountAmount')
    expect(keys).not.toContain('taxAmount')
    expect(table.hideDiscountTax).toBe(true)
  })

  it('hides both totals lines', () => {
    // A quoted rate is the rate the customer pays, so a Discount or Tax row would
    // only ever read zero.
    expect(field?.meta?.showPricingTotals).toBe(true)
    expect(field?.meta?.showDiscountTotals).toBe(false)
    expect(field?.meta?.includeTax).toBe(false)
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
describe('note columns are edited through a dialog', () => {
  it('declares a note column on the tables that need prose', () => {
    for (const table of [JOB_ACTUAL_CONTAINER_TABLE, JOB_CONTAINER_PAYMENT_TABLE, JOB_ROUTE_TABLE]) {
      const note = table.columns.find(column => column.type === 'note')
      expect(note, `${table.key} must expose a note column`).toBeDefined()
    }
  })

  it('renders a note column as an icon button, never as a text cell', () => {
    const lineTable = source('components/freight/AppLineTable.vue')
    // The note icon and the delete icon share a cell, so both types are handled
    // by the same branch.
    expect(lineTable).toContain("if (column.type === 'delete' || column.type === 'note')")
    // The icon carries the state: filled means the row already has text.
    expect(lineTable).toContain('i-lucide-sticky-note')
    expect(lineTable).toContain('i-lucide-sticky-note-plus')
    expect(lineTable).toContain('openNoteDialog(index, column.key)')
    // Saving goes through the normal cell update, so validation and dirty state
    // behave exactly like a typed edit.
    expect(lineTable).toContain('updateCell(noteDialog.value.index, noteDialog.value.key, value)')
  })

  it('folds note and delete into one icon column', () => {
    const lineTable = source('components/freight/AppLineTable.vue')
    // Which column hosts the group is decided by the shared column module, and a
    // folded column never reaches the grid as a column of its own.
    expect(lineTable).toContain('sharedRowControls(props.table.columns)')
    expect(lineTable).toContain('!sharedRowControlState.value.folded.has(column.key)')
    expect(lineTable).toContain('rowIconGroup(column)')

    for (const table of [JOB_ACTUAL_CONTAINER_TABLE, JOB_CONTAINER_PAYMENT_TABLE, JOB_ROUTE_TABLE]) {
      const { host, folded } = sharedRowControls(table.columns)
      const note = table.columns.find(column => column.type === 'note')
      const deletes = table.columns.filter(column => column.type === 'delete').map(column => column.key)
      expect(host, `${table.key} must host the icons on its note column`).toBe(note?.key)
      expect([...folded], `${table.key} must fold in exactly its delete columns`).toEqual(deletes)
    }
  })

  it('ships a dialog component that owns only the draft text', () => {
    const path = `${APP}/components/table/AppRowNoteDialog.vue`
    expect(existsSync(path)).toBe(true)
    const dialog = readFileSync(path, 'utf8')
    expect(dialog).toContain("'save': [value: string]")
    expect(dialog).toContain('UTextarea')
    // The draft reloads from the stored value every time it opens, so a cancelled
    // edit does not leak into the next row's dialog.
    expect(dialog).toContain("watch(() => props.open")
  })

  it('mounts the dialog once per table rather than once per row', () => {
    const lineTable = source('components/freight/AppLineTable.vue')
    expect(lineTable.match(/<TableAppRowNoteDialog/g)?.length).toBe(1)
  })
})

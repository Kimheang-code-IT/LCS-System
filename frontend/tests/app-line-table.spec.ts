import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const table = readFileSync(`${APP}/components/freight/AppLineTable.vue`, 'utf8')
const finance = readFileSync(`${APP}/components/freight/JobFinance.vue`, 'utf8')
const charges = readFileSync(`${APP}/components/freight/JobCharges.vue`, 'utf8')
const sharedForm = readFileSync(`${APP}/components/freight/ServiceChargeForm.vue`, 'utf8')

describe('AppLineTable shared table contract', () => {
  it('is the table implementation used by Finance and Service Charge', () => {
    expect(finance).toContain('<FreightAppLineTable')
    expect(finance).toContain('buildFinanceSummary')
    expect(finance).toContain('summaryMetrics')
    expect(charges).toContain('<FreightServiceChargeForm')
    expect(charges).toContain('fee-lines-only')
    expect(sharedForm).toContain('<DocumentAppDocumentForm')
    // The fee-lines renderer resolves to the same generic line table.
    expect(readFileSync(`${APP}/components/document/AppDynamicFieldRenderer.vue`, 'utf8'))
      .toContain('<FreightAppLineTable')
  })

  it('supports add, edit, delete, validation and read-only states', () => {
    expect(table).toContain('function addRow()')
    expect(table).toContain('function updateCell(')
    expect(table).toContain('function removeRow(')
    expect(table).toContain('props.fieldErrors')
    expect(table).toContain('rowLocked(row.original)')
  })

  it('supports loading and empty states without changing old callers', () => {
    expect(table).toContain('loading?: boolean')
    expect(table).toContain('emptyText?: string')
    expect(table).toContain('v-if="loading"')
    expect(table).toContain('!rows.length && emptyText')
  })

  it('uses a stable row identity first, falling back to the index', () => {
    expect(table).toContain("row.id || row.clientRowId || row._rowId || row._rowIndex")
    // Opt-in client row ids are stamped when a row is added, and stripped before
    // an API/draft write by the shared `_` key rules.
    expect(table).toContain('props.table.assignRowId === true')
    expect(table).toContain("createClientId('row')")
  })

  it('contains no Finance- or Service-Charge-specific formula', () => {
    expect(table).not.toContain('serviceChargeTotals')
    expect(table).not.toContain('buildFinanceSummary')
    expect(table).not.toContain('chargedAmount')
  })
})

/**
 * Service-order Service Charge tab, expressed as the shared `FreightTable`
 * contract so it renders through `AppLineTable` like the quotation grids.
 *
 * One grid row is one charge document (its `feeLines` stay nested, matching the
 * charge → finance-invoice workflow). A new row is a one-line draft, so the
 * grid carries description / quantity / unit price / tax as its own columns and
 * the payload builder collapses them back into a single fee line.
 */

import type { FreightLineColumn, FreightTable } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/record'

export type ServiceChargeRow = Record<string, unknown>

/** `ServiceOrderCharge.status` values the backend allows deleting. */
export const DELETABLE_CHARGE_STATUS = 'DRAFT'

export function isDeletableCharge(row: ServiceChargeRow): boolean {
  return String(row.status || '') === DELETABLE_CHARGE_STATUS
}

/** First fee line of a charge; a charge is created with exactly one. */
function firstFeeLine(row: ServiceChargeRow): ServiceChargeRow {
  const lines = Array.isArray(row.feeLines) ? row.feeLines as ServiceChargeRow[] : []
  return lines[0] || {}
}

/** Charge line amounts. Matches `computeFeeLine` in `line-table-rules.ts`. */
export function serviceChargeAmounts(row: ServiceChargeRow) {
  const quantity = Number(row.quantity || 0)
  const unitPrice = Number(row.unitAmount ?? row.unitPrice ?? 0)
  const discount = Number(row.discount || 0)
  const taxRate = Number(row.taxRate ?? row.tax ?? 0)
  const taxAmount = row.taxAmount != null
    ? Number(row.taxAmount)
    : Math.max(0, quantity * unitPrice - discount) * taxRate / 100
  return { quantity, unitPrice, discount, taxRate, taxAmount }
}

export function serviceChargeToRow(charge: FreightRecord): ServiceChargeRow {
  const line = firstFeeLine(charge as ServiceChargeRow)
  return {
    id: String(charge.id ?? ''),
    feeType: String(line.feeType || ''),
    description: String(line.description || charge.chargeNo || ''),
    documentDate: String(charge.documentDate || charge.date || ''),
    documentType: String(charge.documentType || 'SERVICE_NOTE'),
    status: String(charge.status || 'DRAFT'),
    invoiceNo: String(charge.invoiceNo || ''),
    total: Number(charge.total ?? 0),
    currency: String(charge.currency || ''),
    ...serviceChargeAmounts(line),
  }
}

export function serviceChargeRows(charges: FreightRecord[]): ServiceChargeRow[] {
  return charges.map(serviceChargeToRow)
}

/**
 * The `lines` payload `POST /service-orders/{id}/charges` expects. A charge is
 * informational until converted, so it is always created as a SERVICE_NOTE.
 */
export function serviceChargePayload(row: ServiceChargeRow, currency: string) {
  const amounts = serviceChargeAmounts(row)
  const description = String(row.description || '')
  return {
    documentType: String(row.documentType || 'SERVICE_NOTE'),
    documentDate: String(row.documentDate || new Date().toISOString().slice(0, 10)),
    currency,
    lines: [{
      feeType: row.feeType,
      description,
      quantity: amounts.quantity,
      unitPrice: amounts.unitPrice,
      discount: amounts.discount,
      taxRate: amounts.taxRate,
      taxAmount: amounts.taxAmount,
    }],
  }
}

/** A charge with no description cannot be created — the backend requires one. */
export function serviceChargeIsCreatable(row: ServiceChargeRow): boolean {
  return Boolean(String(row.description || '').trim())
}

export function serviceChargeColumns(): FreightLineColumn[] {
  // Review-first grid: date, document type, tax, status and invoice stay on the
  // charge detail page and in the payload, not in the every-day list. The row
  // menu owns open / print / delete so the grid stays narrow.
  return [
    { key: 'feeType', label: 'Fee Type', labelKm: 'ប្រភេទថ្លៃ', labelKey: 'freight.ui.feeTypeCol', type: 'select' },
    { key: 'description', label: 'Description', labelKm: 'បរិយាយ', required: true },
    { key: 'quantity', label: 'Qty', labelKm: 'ចំនួន', labelKey: 'freight.ui.qty', type: 'number' },
    { key: 'unitPrice', label: 'Unit Price', labelKm: 'តម្លៃឯកត្តរ', labelKey: 'freight.ui.unitPriceCol', type: 'number' },
    { key: 'total', label: 'Line Total', labelKm: 'សរុបជួរ', labelKey: 'freight.ui.lineTotal', type: 'number', computed: true },
  ]
}

/** Sheet totals. Line-level adjustments win; otherwise the sheet discount/rate applies. */
export function serviceChargeTotals(
  rows: ServiceChargeRow[],
  vatRate: unknown,
  discount: unknown = 0,
) {
  const subtotal = rows.reduce(
    (sum, row) => sum + (Number(row.quantity || 0) * Number(row.unitPrice || 0)),
    0,
  )
  const lineDiscount = rows.reduce((sum, row) => sum + (Number(row.discountAmount ?? row.discount) || 0), 0)
  const lineTax = rows.reduce((sum, row) => sum + (Number(row.taxAmount) || 0), 0)
  const hasLineAdjustments = lineDiscount > 0 || lineTax > 0
  if (hasLineAdjustments) {
    return {
      vatRate: 0,
      subtotal: Number(subtotal.toFixed(2)),
      discount: Number(lineDiscount.toFixed(2)),
      vat: Number(lineTax.toFixed(2)),
      total: Number((subtotal - lineDiscount + lineTax).toFixed(2)),
    }
  }
  const discountAmount = Math.max(0, Number(discount) || 0)
  const taxable = Math.max(0, subtotal - discountAmount)
  const rate = Number(vatRate) || 0
  const vat = taxable * rate / 100
  return {
    vatRate: rate,
    subtotal: Number(subtotal.toFixed(2)),
    discount: Number(discountAmount.toFixed(2)),
    vat: Number(vat.toFixed(2)),
    total: Number((taxable + vat).toFixed(2)),
  }
}

/** Grid rows carry the live amount so the total column is not stale mid-edit. */
export function computeServiceChargeLine({ row }: { row: ServiceChargeRow }) {
  const amounts = serviceChargeAmounts(row)
  const taxable = Math.max(0, amounts.quantity * amounts.unitPrice - amounts.discount)
  return { ...amounts, total: Number((taxable + amounts.taxAmount).toFixed(2)) }
}

export function serviceChargeTable(): FreightTable {
  return {
    key: 'serviceOrderCharges',
    title: 'Service charges',
    titleKm: 'ថ្លៃសេវាកម្ម',
    columns: serviceChargeColumns(),
    addLabelKey: 'freight.ui.addCharge',
    computeRow: computeServiceChargeLine,
    lineDetails: true,
  }
}
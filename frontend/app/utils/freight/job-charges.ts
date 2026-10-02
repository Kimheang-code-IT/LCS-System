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

export function blankServiceChargeRow(): ServiceChargeRow {
  return {
    description: '',
    documentDate: new Date().toISOString().slice(0, 10),
    documentType: 'SERVICE_NOTE',
    status: 'DRAFT',
    quantity: 1,
    unitPrice: 0,
    taxRate: 0,
    taxAmount: 0,
  }
}

export function serviceChargeToRow(charge: FreightRecord): ServiceChargeRow {
  const line = firstFeeLine(charge as ServiceChargeRow)
  return {
    id: String(charge.id ?? ''),
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
      description,
      quantity: amounts.quantity,
      unitPrice: amounts.unitPrice,
      discount: amounts.discount,
      taxAmount: amounts.taxAmount,
    }],
  }
}

export type ServiceChargePayload = ReturnType<typeof serviceChargePayload>

/** A charge with no description cannot be created — the backend requires one. */
export function serviceChargeIsCreatable(row: ServiceChargeRow): boolean {
  return Boolean(String(row.description || '').trim())
}

/**
 * Only a DRAFT charge may change, and only its own line values plus the date —
 * the backend never rewrites an issued charge's totals.
 */
export function serviceChargeIsMutable(row: ServiceChargeRow): boolean {
  return isDeletableCharge(row)
}

export function serviceChargeColumns(): FreightLineColumn[] {
  return [
    { key: 'description', label: 'Description', labelKm: 'បរិយាយ', required: true },
    { key: 'documentDate', label: 'Date', labelKm: 'កាលបរិច្ឆេទ', labelKey: 'freight.ui.cols.date', type: 'date' },
    { key: 'documentType', label: 'Type', labelKm: 'ប្រភេទ', labelKey: 'freight.ui.cols.documentType', type: 'text', computed: true },
    { key: 'quantity', label: 'Qty', labelKm: 'ចំនួន', labelKey: 'freight.ui.qty', type: 'number' },
    { key: 'unitPrice', label: 'Unit Price', labelKm: 'តម្លៃឯកត្តរ', labelKey: 'freight.ui.unitPriceCol', type: 'number' },
    { key: 'taxRate', label: 'Tax %', labelKm: 'ពន្ធ %', labelKey: 'freight.ui.taxCol', type: 'number' },
    { key: 'total', label: 'Total', labelKm: 'សរុប', labelKey: 'freight.ui.lineTotal', type: 'number', computed: true },
    { key: 'status', label: 'Status', labelKm: 'ស្ថានភាព', labelKey: 'freight.ui.cols.status', type: 'text', computed: true },
    { key: 'invoiceNo', label: 'Invoice', labelKm: 'វិក្កយបត្រ', labelKey: 'freight.ui.cols.invoice', type: 'text', computed: true },
    { key: '_print', label: '', type: 'action', action: 'print' },
    { key: '_delete', label: '', type: 'delete' },
  ]
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
  }
}
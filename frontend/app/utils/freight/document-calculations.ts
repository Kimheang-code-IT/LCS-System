/**
 * Aggregate recomputation for the generic document form (`DocumentView.vue`).
 *
 * These are the money/business rules that used to live inline in the component.
 * They are pure: given a module descriptor and a record, return the recalculated
 * record. Per-line arithmetic stays in `line-table-rules.ts`; this module owns
 * the document-level totals built from those lines.
 *
 * Rounding and tax fallbacks are reproduced exactly as the component computed
 * them before — changing them would silently move money.
 */

import type { FreightModule } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/record'
import { documentSequencePreview } from '~/utils/document-sequences'
import { toFiniteNumber } from '~/utils/format/number'

type Row = Record<string, unknown>

/** Structural subset of a module needed to pick the right recalculation branch. */
export type DocumentCalculationModule = Pick<FreightModule, 'kind' | 'collection' | 'path'>

const asNumber = toFiniteNumber

function round2(value: number): number {
  return Number(value.toFixed(2))
}

function rowsOf(record: FreightRecord, key: string): Row[] {
  return Array.isArray(record[key]) ? record[key] as Row[] : []
}

/** Quotation pricing lines, container pricing totals and the derived route. */
function recalculateQuotation(record: FreightRecord): FreightRecord {
  const pricingLines = rowsOf(record, 'pricingLines')
  let next = record
  if (pricingLines.length) {
    const normalized = pricingLines.map((row) => {
      const rowSubtotal = asNumber(row.quantity) * asNumber(row.unitPrice)
      const rowDiscount = asNumber(row.discountAmount)
      const taxable = Math.max(0, rowSubtotal - rowDiscount)
      const rowTax = asNumber(row.taxAmount)
      return {
        ...row,
        subtotal: round2(rowSubtotal),
        discountAmount: round2(rowDiscount),
        taxAmount: round2(rowTax),
        lineTotal: round2(taxable + rowTax),
      }
    })
    const subtotal = normalized.reduce((sum, row) => sum + asNumber(row.subtotal), 0)
    const discount = normalized.reduce((sum, row) => sum + asNumber(row.discountAmount), 0)
    const tax = normalized.reduce((sum, row) => sum + asNumber(row.taxAmount), 0)
    next = {
      ...next,
      pricingLines: normalized,
      subtotal: round2(subtotal),
      discount: round2(discount),
      tax: round2(tax),
      total: round2(subtotal - discount + tax),
      amount: round2(subtotal - discount + tax),
    }
  }
  else {
    next = { ...next, subtotal: 0, discount: 0, tax: 0, total: 0, amount: 0 }
  }

  const charges = rowsOf(next, 'otherCharges')
  const chargeBuy = charges.reduce((sum, row) => sum + asNumber(row.quantity) * asNumber(row.buyingRate), 0)
  const chargeSell = charges.reduce((sum, row) => sum + asNumber(row.amount || asNumber(row.quantity) * asNumber(row.sellingRate)), 0)
  const totalBuying = asNumber(next.buying20) + asNumber(next.buying40) + asNumber(next.buying45) + chargeBuy
  const totalSelling = asNumber(next.selling20) + asNumber(next.selling40) + asNumber(next.selling45) + chargeSell
  const profit = totalSelling - totalBuying
  const pickup = String(next.pickup || '')
  const border = String(next.border || '')
  const delivery = String(next.delivery || '')
  const hasLegacyPricing = charges.length > 0
    || ['buying20', 'buying40', 'buying45', 'selling20', 'selling40', 'selling45'].some(key => asNumber(next[key]) !== 0)
  return {
    ...next,
    route: [pickup, border, delivery].filter(Boolean).join(' → '),
    ...(hasLegacyPricing
      ? {
          totalBuying: round2(totalBuying),
          totalSelling: round2(totalSelling),
          amount: round2(totalSelling),
          profit: round2(profit),
          margin: totalSelling ? Number(((profit / totalSelling) * 100).toFixed(1)) : 0,
        }
      : {}),
  }
}

/** Debit-note header totals from its three-currency charge rows plus VAT. */
function recalculateDebitNoteCharges(record: FreightRecord): FreightRecord {
  const charges = rowsOf(record, 'charges')
  const cambodiaSubtotal = charges.reduce((sum, row) => sum + asNumber(row.cambodia), 0)
  const vietnamSubtotal = charges.reduce((sum, row) => sum + asNumber(row.vietnam), 0)
  const cashSubtotal = charges.reduce((sum, row) => sum + asNumber(row.cash), 0)
  const amount = cambodiaSubtotal + vietnamSubtotal + cashSubtotal
  const vat = amount * (asNumber(record.vatRate) / 100)
  return {
    ...record,
    cambodiaSubtotal: round2(cambodiaSubtotal),
    vietnamSubtotal: round2(vietnamSubtotal),
    cashSubtotal: round2(cashSubtotal),
    amount: round2(amount),
    vat: round2(vat),
    total: round2(amount + vat),
  }
}

/** Service charge `feeLines` totals. */
function recalculateFeeLines(record: FreightRecord): FreightRecord {
  const lines = rowsOf(record, 'feeLines')
  const subtotal = lines.reduce((sum, row) => sum + asNumber(row.quantity) * asNumber(row.unitAmount), 0)
  const discount = lines.reduce((sum, row) => sum + asNumber(row.discount), 0)
  const tax = lines.reduce((sum, row) => sum + asNumber(row.taxAmount || row.tax), 0)
  const total = subtotal - discount + tax
  return {
    ...record,
    subtotal: round2(subtotal),
    discount: round2(discount),
    tax: round2(tax),
    total: round2(total),
    amount: round2(total),
  }
}

/** Finance document `lines` totals (amount excludes VAT, total includes it). */
function recalculateDocumentLines(record: FreightRecord): FreightRecord {
  const lines = rowsOf(record, 'lines')
  const subtotal = lines.reduce((sum, row) => sum + asNumber(row.quantity) * asNumber(row.unitAmount), 0)
  const discount = lines.reduce((sum, row) => sum + asNumber(row.discount), 0)
  const tax = lines.reduce((sum, row) => sum + asNumber(row.taxAmount || row.tax), 0)
  return {
    ...record,
    amount: round2(subtotal - discount),
    vat: round2(tax),
    total: round2(subtotal - discount + tax),
  }
}

/** Journal entry debit/credit totals and balance difference. */
function recalculateJournalLines(record: FreightRecord): FreightRecord {
  const lines = rowsOf(record, 'lines')
  const debitTotal = lines.reduce((sum, row) => sum + asNumber(row.debit_amount), 0)
  const creditTotal = lines.reduce((sum, row) => sum + asNumber(row.credit_amount), 0)
  return {
    ...record,
    debitTotal: round2(debitTotal),
    creditTotal: round2(creditTotal),
    balanceDifference: round2(debitTotal - creditTotal),
  }
}

/** Customer receipt allocation totals and the derived payment status. */
function recalculateCustomerPayment(record: FreightRecord): FreightRecord {
  const allocations = rowsOf(record, 'allocations')
  const allocatedAmount = allocations.reduce((sum, row) => sum + asNumber(row.amount), 0)
  const unallocatedAmount = Math.max(0, asNumber(record.received) - allocatedAmount)
  const outstanding = asNumber(record.amountDue) - asNumber(record.received)
  let status = String(record.status || 'Unpaid')
  if (outstanding <= 0 && asNumber(record.received) > 0) status = 'Paid'
  else if (asNumber(record.received) > 0) status = 'Partial'
  return {
    ...record,
    outstanding: round2(outstanding),
    allocatedAmount: round2(allocatedAmount),
    unallocatedAmount: round2(unallocatedAmount),
    status,
  }
}

/**
 * Recompute every derived field on a document record. Returns the record
 * unchanged when the module has no calculation rules.
 */
export function recalculateFreightRecord(
  module: DocumentCalculationModule,
  record: FreightRecord,
): FreightRecord {
  let next = record
  if (module.collection === 'documentSequences') {
    next = {
      ...next,
      prefix: String(next.prefix || '').trimStart(),
      nextNumberPreview: documentSequencePreview(next),
    }
  }
  if (module.kind === 'quotation') next = recalculateQuotation(next)
  if (module.kind === 'debit-note') next = recalculateDebitNoteCharges(next)
  if (module.collection === 'jobCharges' && Array.isArray(next.feeLines)) next = recalculateFeeLines(next)
  if (module.collection === 'debitNotes' && Array.isArray(next.lines)) next = recalculateDocumentLines(next)
  if (module.collection === 'journals' && Array.isArray(next.lines)) next = recalculateJournalLines(next)
  if (module.path.includes('customer-payments') || String(next.documentType) === 'CUSTOMER_RECEIPT') {
    next = recalculateCustomerPayment(next)
  }
  return next
}

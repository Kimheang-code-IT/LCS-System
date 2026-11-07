import type { PrintDocumentMeta, PrintLine, PrintTotals, PrintViewModel } from './print-model'
import { amountInWords, formatDebitNoteAmountInWords, printNum } from './print-model'

type DecimalTransport<T> = { [K in keyof T]: T[K] extends number | undefined ? number | string | undefined : T[K] }

export type FinancialPrintData = {
  model: Omit<PrintViewModel, 'document' | 'lines' | 'totals'> & {
    document: DecimalTransport<PrintDocumentMeta>
    lines: DecimalTransport<PrintLine>[]
    totals: DecimalTransport<PrintTotals>
  }
  containers: Array<{ id: string, number: string, type: string }>
  selectedContainerId: string
  taxInvoiceEligible: boolean
  warnings: string[]
}

/** The server owns source selection/reconciliation. Convert decimal strings only for display. */
export function financialPrintModel(data: FinancialPrintData): PrintViewModel {
  const raw = data.model
  const totals = { ...raw.totals } as PrintTotals
  for (const key of ['subtotal', 'discount', 'taxableAmount', 'taxRate', 'taxAmount', 'grandTotal', 'totalDebit', 'totalCredit', 'balance', 'exchangeRate', 'grandTotalLocal', 'outstanding', 'localPrecision'] as const) {
    totals[key] = printNum(raw.totals[key])
  }
  const lines = raw.lines.map(line => ({
    ...line,
    no: printNum(line.no),
    quantity: printNum(line.quantity), unitPrice: printNum(line.unitPrice),
    amount: printNum(line.amount), debit: printNum(line.debit), credit: printNum(line.credit),
  }))
  return {
    ...raw, totals, lines,
    document: { ...raw.document, exchangeRate: printNum(raw.document.exchangeRate) },
    // Existing words formatter supports cents. Other precisions omit words rather than invent subunits.
    amountInWords: raw.precision === 2
      ? (raw.isContainerBreakdown ? formatDebitNoteAmountInWords(totals.balance, totals.currency) : amountInWords(totals.grandTotal, totals.currency))
      : '',
  }
}

export function financialContainerOptions(data: FinancialPrintData | null) {
  return (data?.containers || []).map(row => ({ label: row.number, value: row.id, description: row.type }))
}


import type { FreightRecord } from '~/types/freight/record'
import type { PrintTemplateId } from '~/config/print-templates'
import {
  buildPrintViewModel,
  feeLinesToPrintLines,
  printNum,
  printStr,
  type PrintLine,
  type PrintModelContext,
  type PrintViewModel,
} from '~/utils/freight/print-model'

type RawLine = Record<string, unknown>

function lineTotals(lines: PrintLine[], sourceLines: RawLine[]) {
  const subtotal = sourceLines.reduce((sum, row) => {
    const quantity = printNum(row.quantity) || 1
    const unitPrice = printNum(row.unitAmount ?? row.unitPrice)
    const discount = printNum(row.discount)
    return sum + Math.max(0, quantity * unitPrice - discount)
  }, 0)
  const tax = sourceLines.reduce((sum, row) => sum + printNum(row.taxAmount ?? row.tax), 0)
  const total = lines.reduce((sum, line) => sum + line.amount, 0)
  return {
    subtotal: Number(subtotal.toFixed(2)),
    tax: Number(tax.toFixed(2)),
    total: Number((total || subtotal + tax).toFixed(2)),
  }
}

function syntheticChargeRecord(
  charge: FreightRecord,
  templateId: PrintTemplateId,
  lines: PrintLine[],
  sourceLines: RawLine[],
  lineIndex?: number,
): FreightRecord {
  const chargeNo = printStr(charge.chargeNo) || printStr(charge.id)
  const suffix = lineIndex !== undefined ? `/${lineIndex + 1}` : ''
  const documentNumber = `${chargeNo}${suffix}`
  const totals = lineTotals(lines, sourceLines)
  const containerNo = lineIndex !== undefined
    ? printStr(sourceLines[lineIndex]?.containerNo)
    : printStr(sourceLines[0]?.containerNo)

  return {
    ...charge,
    date: printStr(charge.documentDate) || printStr(charge.date),
    containerNo,
    invoiceNo: documentNumber,
    debitNoteNo: documentNumber,
    documentType: templateId === 'tax-invoice' ? 'CUSTOMER_INVOICE' : printStr(charge.documentType) || 'DEBIT_NOTE',
    lines: sourceLines.map((row, index) => ({
      lineNo: index + 1,
      description: printStr(row.description) || printStr(row.feeType),
      feeType: printStr(row.feeType),
      quantity: printNum(row.quantity) || 1,
      unitAmount: printNum(row.unitAmount ?? row.unitPrice),
      discount: printNum(row.discount),
      taxAmount: printNum(row.taxAmount ?? row.tax),
      amount: printNum(row.amount),
      containerNo: printStr(row.containerNo),
    })),
    amount: totals.subtotal,
    subtotal: totals.subtotal,
    tax: totals.tax,
    vat: totals.tax,
    total: totals.total,
  } as FreightRecord
}

export type ChargePrintOptions = {
  lineIndex?: number
}

/** Build a print view model for a service charge (whole document or one fee line). */
export function buildChargePrintViewModel(
  charge: FreightRecord,
  templateId: PrintTemplateId,
  context: PrintModelContext = {},
  options: ChargePrintOptions = {},
): PrintViewModel {
  const feeLines = Array.isArray(charge.feeLines) ? charge.feeLines as RawLine[] : []
  const currency = printStr(charge.currency) || 'USD'
  const reference = printStr(charge.chargeNo) || printStr(charge.jobNo) || printStr(charge.id)
  const lineIndex = options.lineIndex
  const selectedSource = lineIndex !== undefined && feeLines[lineIndex]
    ? [feeLines[lineIndex]!]
    : feeLines
  const printLines = feeLinesToPrintLines(selectedSource, reference, currency).map((line, index) => ({
    ...line,
    no: index + 1,
  }))

  if (!printLines.length) {
    return buildPrintViewModel(charge, templateId, context)
  }

  const synthetic = syntheticChargeRecord(
    charge,
    templateId,
    printLines,
    selectedSource,
    lineIndex,
  )
  const model = buildPrintViewModel(synthetic, templateId, context)
  model.lines = printLines

  if (templateId === 'tax-invoice') {
    model.document.documentType = 'CUSTOMER_INVOICE'
  }

  const containerNo = printStr(selectedSource[0]?.containerNo)
  if (containerNo) model.shipment.containerNo = containerNo

  return model
}

import type { FreightRecord } from '~/types/freight/record'
import type { PrintTemplateId } from '~/config/print-templates'
import { normalizeActualContainer } from '~/utils/freight/job-containers'
import {
  buildPrintViewModel,
  printNum,
  printStr,
  type PrintLine,
  type PrintModelContext,
  type PrintViewModel,
} from '~/utils/freight/print-model'

type RawLine = Record<string, unknown>

export type JobContainerSlot = {
  index: number
  containerType: string
  containerNo: string
  label: string
}

/** One printable slot per actual container on the service order. */
export function expandJobContainerSlots(job: FreightRecord): JobContainerSlot[] {
  const actuals = Array.isArray(job.actualContainers) ? job.actualContainers as RawLine[] : []
  if (!actuals.length) {
    return [{
      index: 0,
      containerType: printStr(job.containerType) || '40HC',
      containerNo: printStr(job.containerNo),
      label: printStr(job.containerNo) || printStr(job.containerType) || 'Container',
    }]
  }

  return actuals.map((row, index) => {
    const normalized = normalizeActualContainer(row, index)
    const containerType = printStr(normalized.containerType) || '40HC'
    const containerNo = printStr(normalized.containerNo)
    return {
      index,
      containerType,
      containerNo,
      label: containerNo || containerType,
    }
  })
}

function containerPaymentLines(job: FreightRecord, containerNo: string): PrintLine[] {
  const currency = printStr(job.currency) || 'USD'
  const reference = printStr(job.jobNo) || printStr(job.id)
  const payments = Array.isArray(job.containerPayments) ? job.containerPayments as RawLine[] : []
  const filtered = containerNo
    ? payments.filter(row => printStr(row.containerNo) === containerNo)
    : payments

  return filtered.map((row, index) => {
    const quantity = printNum(row.quantity) || 1
    const unitPrice = printNum(row.unitPrice)
    const amount = printNum(row.lineTotal) || printNum(row.amount) || quantity * unitPrice
    return {
      no: index + 1,
      reference,
      description: printStr(row.description) || printStr(row.feeType) || 'Freight service',
      descriptionKh: printStr(row.descriptionKh) || printStr(row.description_kh),
      quantity,
      unit: printStr(row.unit) || 'Container',
      unitPrice,
      currency,
      debit: amount,
      credit: 0,
      amount,
    }
  }).filter(line => line.amount > 0 || line.description)
}

function syntheticJobRecord(
  job: FreightRecord,
  templateId: PrintTemplateId,
  slot: JobContainerSlot,
): FreightRecord {
  const jobNo = printStr(job.jobNo) || printStr(job.id)
  const documentNumber = `${jobNo}/${slot.index + 1}`
  const lines = containerPaymentLines(job, slot.containerNo)
  const subtotal = lines.reduce((sum, line) => sum + line.amount, 0)
  const vatRate = printNum(job.vatRate)
  const vat = Number((subtotal * (vatRate / 100)).toFixed(2))

  return {
    ...job,
    quantity: '1',
    containerNo: slot.containerNo,
    containerType: slot.containerType,
    invoiceNo: documentNumber,
    debitNoteNo: documentNumber,
    documentType: templateId === 'tax-invoice' ? 'CUSTOMER_INVOICE' : 'DEBIT_NOTE',
    lines,
    amount: Number(subtotal.toFixed(2)),
    vat,
    total: Number((subtotal + vat).toFixed(2)),
  } as FreightRecord
}

export type JobPrintOptions = {
  containerIndex?: number
}

/** Build a print view model for a service order (per actual container). */
export function buildJobPrintViewModel(
  job: FreightRecord,
  templateId: PrintTemplateId,
  context: PrintModelContext = {},
  options: JobPrintOptions = {},
): PrintViewModel {
  const slots = expandJobContainerSlots(job)
  const slot = slots[options.containerIndex ?? 0] ?? slots[0]
  if (!slot) {
    return buildPrintViewModel(job, templateId, context)
  }

  const synthetic = syntheticJobRecord(job, templateId, slot)
  const model = buildPrintViewModel(synthetic, templateId, context)

  if (templateId === 'debit-note') {
    model.shipment.containerType = slot.containerType
    model.shipment.packageQty = '1'
    model.shipment.packageUnit = slot.containerType
    if (slot.containerNo) model.shipment.containerNo = slot.containerNo
  }

  if (templateId === 'tax-invoice') {
    model.document.documentType = 'CUSTOMER_INVOICE'
  }

  return model
}

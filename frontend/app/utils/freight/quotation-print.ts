import type { FreightRecord } from '~/types/freight/record'
import type { PrintTemplateId } from '~/config/print-templates'
import {
  buildPrintViewModel,
  printNum,
  printStr,
  type PrintLine,
  type PrintModelContext,
  type PrintViewModel,
} from '~/utils/freight/print-model'

type RawLine = Record<string, unknown>

export type QuotationContainerSlot = {
  index: number
  containerType: string
  label: string
  containerNo: string
  requirementIndex: number
  slotInRequirement: number
}

/** Expand container requirements into one printable slot per physical container. */
export function expandQuotationContainerSlots(record: FreightRecord): QuotationContainerSlot[] {
  const requirements = Array.isArray(record.containerRequirements)
    ? record.containerRequirements as RawLine[]
    : []
  const slots: QuotationContainerSlot[] = []
  let globalIndex = 0

  for (const [requirementIndex, requirement] of requirements.entries()) {
    const containerType = printStr(requirement.containerType) || '40HC'
    const quantity = Math.max(1, Math.floor(printNum(requirement.quantity) || 1))
    const containerNo = printStr(requirement.containerNo)
    for (let slotInRequirement = 0; slotInRequirement < quantity; slotInRequirement += 1) {
      slots.push({
        index: globalIndex,
        containerType,
        label: quantity > 1
          ? `${containerType} (${slotInRequirement + 1}/${quantity})`
          : containerType,
        containerNo,
        requirementIndex,
        slotInRequirement,
      })
      globalIndex += 1
    }
  }

  if (!slots.length) {
    slots.push({
      index: 0,
      containerType: printStr(record.containerType) || '40HC',
      label: printStr(record.containerType) || 'Container',
      containerNo: '',
      requirementIndex: 0,
      slotInRequirement: 0,
    })
  }

  return slots
}

function quotationPricingRows(record: FreightRecord): RawLine[] {
  return Array.isArray(record.pricingLines) ? record.pricingLines as RawLine[] : []
}

function rowContainerType(row: RawLine) {
  return printStr(row.containerType) || printStr(row.containerRequirement)
}

function mapPricingLine(row: RawLine, index: number, reference: string, currency: string): PrintLine {
  const quantity = printNum(row.quantity) || 1
  const unitPrice = printNum(row.unitPrice)
  const amount = printNum(row.total) || printNum(row.lineTotal) || quantity * unitPrice
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
}

function pricingLinesForSlot(record: FreightRecord, slot: QuotationContainerSlot): PrintLine[] {
  const currency = printStr(record.currency) || 'USD'
  const reference = printStr(record.quotationNo) || printStr(record.id)
  const allRows = quotationPricingRows(record)
  const sameTypeSlots = expandQuotationContainerSlots(record)
    .filter(item => item.containerType === slot.containerType)
  const matched = allRows.filter(row => {
    const rowType = rowContainerType(row)
    return !rowType || rowType === slot.containerType
  })
  const source = matched.length ? matched : allRows
  const divisor = Math.max(1, sameTypeSlots.length)

  return source.map((row, index) => {
    const line = mapPricingLine(row, index, reference, currency)
    if (divisor > 1) {
      line.quantity = line.quantity / divisor
      line.amount = line.amount / divisor
      line.debit = line.debit / divisor
    }
    return line
  }).filter(line => line.amount > 0 || line.description)
}

function pricingLinesForQuotation(record: FreightRecord): PrintLine[] {
  const currency = printStr(record.currency) || 'USD'
  const reference = printStr(record.quotationNo) || printStr(record.id)
  const rows = quotationPricingRows(record)
  const lines = rows.map((row, index) => mapPricingLine(row, index, reference, currency))

  const otherCharges = Array.isArray(record.otherCharges) ? record.otherCharges as RawLine[] : []
  for (const row of otherCharges) {
    const amount = printNum(row.amount) || printNum(row.total)
    if (!amount && !printStr(row.description)) continue
    lines.push(mapPricingLine({
      description: printStr(row.description) || printStr(row.chargeType),
      quantity: printNum(row.quantity) || 1,
      unit: printStr(row.unit) || 'Service',
      unitPrice: printNum(row.unitPrice) || amount,
      total: amount,
    }, lines.length, reference, currency))
  }

  return lines
}

function linkedJob(record: FreightRecord, context: PrintModelContext) {
  const convertedJobNo = printStr(record.convertedJobNo)
  if (!convertedJobNo) return null
  return (context.jobs || []).find(row => printStr(row.jobNo) === convertedJobNo) || null
}

function syntheticQuotationRecord(
  record: FreightRecord,
  templateId: PrintTemplateId,
  slot: QuotationContainerSlot | null,
  context: PrintModelContext,
): FreightRecord {
  const job = linkedJob(record, context)
  const quotationNo = printStr(record.quotationNo) || printStr(record.id)
  const documentNumber = templateId === 'tax-invoice'
    ? quotationNo
    : `${quotationNo}/${(slot?.index ?? 0) + 1}`

  return {
    ...record,
    customer: printStr(record.customer),
    phone: printStr(record.phone),
    email: printStr(record.email),
    date: printStr(record.date),
    dueDate: printStr(record.validUntil),
    invoiceNo: documentNumber,
    debitNoteNo: documentNumber,
    documentType: templateId === 'tax-invoice' ? 'CUSTOMER_INVOICE' : 'DEBIT_NOTE',
    jobNo: printStr(record.convertedJobNo) || printStr(job?.jobNo),
    pickup: printStr(record.pickup),
    delivery: printStr(record.delivery),
    loadingPort: printStr(record.pickup) || printStr(job?.loadingPort),
    dischargePort: printStr(record.delivery) || printStr(job?.dischargePort),
    containerNo: slot?.containerNo || printStr(job?.containerNo),
    containerType: slot?.containerType || printStr(job?.containerType),
    quantity: '1',
    personInCharge: printStr(record.createdBy) || printStr(record.attention),
    remark: printStr(record.remarks),
    shipper: printStr(job?.shipper),
    consignee: printStr(job?.consignee) || printStr(record.customer),
    notifyParty: printStr(job?.notifyParty),
    blNo: printStr(job?.blNo),
    houseNo: printStr(job?.houseNo),
    masterNo: printStr(job?.masterNo),
    vessel: printStr(job?.vessel),
    voyage: printStr(job?.voyage),
    etd: printStr(job?.etd),
    eta: printStr(job?.eta),
    lines: templateId === 'debit-note' && slot
      ? pricingLinesForSlot(record, slot)
      : pricingLinesForQuotation(record),
    total: printNum(record.total) || printNum(record.amount),
    tax: printNum(record.tax),
    vat: printNum(record.tax),
  } as FreightRecord
}

export type QuotationPrintOptions = {
  containerIndex?: number
}

/** Build a print view model for a quotation (whole tax invoice or per-container debit note). */
export function buildQuotationPrintViewModel(
  record: FreightRecord,
  templateId: PrintTemplateId,
  context: PrintModelContext = {},
  options: QuotationPrintOptions = {},
): PrintViewModel {
  const slots = expandQuotationContainerSlots(record)
  const slot = templateId === 'debit-note'
    ? slots[options.containerIndex ?? 0] ?? slots[0] ?? null
    : null
  const synthetic = syntheticQuotationRecord(record, templateId, slot, context)
  const model = buildPrintViewModel(synthetic, templateId, context)

  if (templateId === 'debit-note' && slot) {
    model.shipment.containerType = slot.containerType
    model.shipment.packageQty = '1'
    model.shipment.packageUnit = slot.containerType
    if (!model.shipment.containerNo) model.shipment.containerNo = slot.label
  }

  if (templateId === 'tax-invoice') {
    model.document.documentType = 'CUSTOMER_INVOICE'
  }

  return model
}

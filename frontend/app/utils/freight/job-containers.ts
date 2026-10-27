/** Service-order container tab: requirements (from quotation), actual boxes, and charge lines. */

import { createClientId } from '~/utils/client-id'
import { toFiniteNumber as asNumber } from '~/utils/format/number'

function text(value: unknown) {
  return String(value ?? '').trim()
}

export function requirementOptionLabel(row: Record<string, unknown>) {
  const type = text(row.containerType) || 'Container'
  const description = text(row.description)
  const qty = asNumber(row.quantity)
  const qtyPart = qty > 0 ? ` × ${qty}` : ''
  return description ? `${type}${qtyPart} · ${description}` : `${type}${qtyPart}`
}

export function normalizeContainerRequirement(
  row: Record<string, unknown>,
  index = 0,
): Record<string, unknown> {
  return {
    id: text(row.id) || createClientId('cr'),
    containerType: text(row.containerType) || '40HC',
    quantity: asNumber(row.quantity) || 1,
    description: text(row.description || row.remarks),
    sourceQuotationContainerId: text(row.sourceQuotationContainerId),
    sequence: asNumber(row.sequence) || index + 1,
  }
}

export function normalizeActualContainer(
  row: Record<string, unknown>,
  index = 0,
): Record<string, unknown> {
  return {
    id: text(row.id) || createClientId('ac'),
    containerRequirementId: text(row.containerRequirementId || row.container_requirement_id),
    containerTypeId: row.containerTypeId ?? row.container_type_id ?? '',
    containerType: text(row.containerType),
    containerNo: text(row.containerNo || row.container_number || row.containerNumber),
    sealNo: text(row.sealNo || row.sealSerial || row.seal_serial),
    status: text(row.status) || 'Expected',
    netWeightKg: asNumber(row.netWeightKg ?? row.net_weight_kg),
    grossWeightKg: asNumber(row.grossWeightKg ?? row.gross_weight_kg),
    note: text(row.note ?? row.remarks ?? row.remark),
    pending: row.pending === true,
    sequence: asNumber(row.sequence) || index + 1,
  }
}

/** Charge-line amounts. Matches service_order_charge_lines (qty × price − discount + tax). */
export function containerPaymentAmounts(row: Record<string, unknown>) {
  const quantity = asNumber(row.quantity) || ((asNumber(row.unitPrice) || asNumber(row.amount)) ? 1 : 0)
  const unitPrice = asNumber(row.unitPrice)
  const discountAmount = asNumber(row.discountAmount ?? row.discount)
  const taxRate = asNumber(row.taxRate ?? row.taxPercent)
  const lineSubtotal = Number((quantity * unitPrice).toFixed(2))
  const taxable = Math.max(0, lineSubtotal - discountAmount)
  const taxAmount = row.taxAmount != null
    ? asNumber(row.taxAmount)
    : Number((taxable * taxRate / 100).toFixed(2))
  const lineTotal = Number((taxable + taxAmount).toFixed(2))
  return {
    quantity,
    unitPrice: Number(unitPrice.toFixed(2)),
    discountAmount: Number(discountAmount.toFixed(2)),
    taxRate: Number(taxRate.toFixed(2)),
    taxAmount,
    lineSubtotal,
    lineTotal,
    amount: lineTotal,
  }
}

export function normalizeContainerPayment(row: Record<string, unknown>): Record<string, unknown> {
  const unitPrice = asNumber(row.unitPrice)
  const legacyAmount = asNumber(row.amount)
  const hasNewShape = Boolean(text(row.feeType) || text(row.containerNo) || unitPrice || text(row.unit) || row.taxRate != null || row.discountAmount != null)
  const amounts = containerPaymentAmounts({
    ...row,
    unitPrice: hasNewShape || unitPrice ? (unitPrice || legacyAmount) : 0,
    quantity: asNumber(row.quantity) || (legacyAmount || unitPrice ? 1 : 0),
  })
  if (!hasNewShape && legacyAmount && !unitPrice) {
    const quantity = asNumber(row.quantity) || 1
    return {
      id: text(row.id) || createClientId('cp'),
      feeType: text(row.feeType || row.chargeType),
      containerNo: text(row.containerNo),
      serviceOrderContainerId: text(row.serviceOrderContainerId),
      description: text(row.description),
      unit: text(row.unit),
      blNo: text(row.blNo),
      truckNo: text(row.truckNo),
      note: text(row.note ?? row.remarks ?? row.remark),
      quantity,
      unitPrice: Number((legacyAmount / quantity).toFixed(2)),
      discountAmount: 0,
      taxRate: 0,
      taxAmount: 0,
      lineSubtotal: Number(legacyAmount.toFixed(2)),
      lineTotal: Number(legacyAmount.toFixed(2)),
      amount: Number(legacyAmount.toFixed(2)),
    }
  }
  return {
    id: text(row.id) || createClientId('cp'),
    feeType: text(row.feeType || row.chargeType),
    containerNo: text(row.containerNo),
    serviceOrderContainerId: text(row.serviceOrderContainerId),
    description: text(row.description),
    unit: text(row.unit),
    blNo: text(row.blNo),
    truckNo: text(row.truckNo),
    note: text(row.note ?? row.remarks ?? row.remark),
    ...amounts,
  }
}

export function withRequirementProgress(
  requirements: Array<Record<string, unknown>>,
  actuals: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const used = new Set<string>()
  return requirements.map((row) => {
    const id = text(row.id)
    const type = text(row.containerType)
    const required = asNumber(row.quantity)
    const assigned = actuals.filter((actual) => {
      if (!text(actual.containerNo)) return false
      const actualId = text(actual.id)
      if (actualId && used.has(actualId)) return false
      const requirementId = text(actual.containerRequirementId)
      const match = requirementId
        ? requirementId === id
        : !requirementId && text(actual.containerType) === type
      if (match && actualId) used.add(actualId)
      return match
    }).length
    return {
      ...row,
      actualQuantity: assigned,
      remaining: Math.max(0, required - assigned),
    }
  })
}

export function persistableRequirements(rows: Array<Record<string, unknown>>) {
  return rows.map((row, index) => {
    const next = normalizeContainerRequirement(row, index)
    delete next.actualQuantity
    delete next.remaining
    return next
  })
}

export function persistableActuals(rows: Array<Record<string, unknown>>) {
  // Prepared rows are kept without a number: the backend stores NULL, and the
  // JSON copy only mirrors what is on screen. Numbered rows carry their value.
  return rows.map((row, index) => normalizeActualContainer(row, index))
}

export function persistablePayments(rows: Array<Record<string, unknown>>) {
  return rows.map(row => normalizeContainerPayment(row))
}

export function jobContainerRequirements(
  job: Record<string, unknown>,
  related?: {
    requirements?: Array<Record<string, unknown>>
    quotation?: Record<string, unknown> | null
  },
): Array<Record<string, unknown>> {
  // The order's own rows are authoritative; the JSON copy is only a fallback for
  // documents created before the rows were exposed on the order payload.
  const collection = related?.requirements || []
  if (collection.length) return collection.map((row, index) => normalizeContainerRequirement(row, index))

  const stored = Array.isArray(job.containerRequirements) ? job.containerRequirements : []
  if (stored.length) return stored.map((row, index) => normalizeContainerRequirement(row as Record<string, unknown>, index))

  const quotation = related?.quotation
  const quoted = Array.isArray(quotation?.containerRequirements) ? quotation.containerRequirements as Array<Record<string, unknown>> : []
  if (quoted.length) {
    return quoted.map((row, index) => normalizeContainerRequirement({
      ...row,
      id: '',
      sourceQuotationContainerId: text(row.id),
    }, index))
  }

  if (text(job.containerType)) {
    return [normalizeContainerRequirement({
      containerType: job.containerType,
      quantity: 1,
      description: text(job.quotationNo) ? `From quotation ${text(job.quotationNo)}` : '',
    })]
  }
  return []
}

export function jobActualContainers(
  job: Record<string, unknown>,
  related?: {
    actuals?: Array<Record<string, unknown>>
    shipments?: Array<Record<string, unknown>>
  },
): Array<Record<string, unknown>> {
  // Persisted rows win over the JSON copy, which can be stale after a conversion
  // prepared rows the browser has not seen yet.
  const collection = related?.actuals || []
  if (collection.length) return collection.map((row, index) => normalizeActualContainer(row, index))

  const stored = Array.isArray(job.actualContainers) ? job.actualContainers : []
  if (stored.length) return stored.map((row, index) => normalizeActualContainer(row as Record<string, unknown>, index))

  const shipments = related?.shipments || []
  if (shipments.length) {
    return shipments
      .filter(row => text(row.containerNo))
      .map((row, index) => normalizeActualContainer({
        containerNo: row.containerNo,
        containerType: row.containerType || job.containerType,
        sealNo: row.sealNo,
        status: text(row.status) || 'Loaded',
      }, index))
  }

  if (text(job.containerNo)) {
    return [normalizeActualContainer({
      containerNo: job.containerNo,
      containerType: job.containerType,
      sealNo: job.sealNo,
      status: 'Loaded',
    })]
  }
  return []
}

/**
 * Container applicability of a quotation pricing line.
 *
 * The existing configuration rule is the line's own `containerType`: a line that
 * names a type is charged per box of that type, a line without one is a shipment
 * charge. No line is invented for a type it does not name.
 */
function lineContainerType(row: Record<string, unknown>) {
  return text(row.containerType || row.containerRequirement).toUpperCase()
}

function quotationPaymentRow(row: Record<string, unknown>, extra: Record<string, unknown> = {}) {
  return normalizeContainerPayment({
    feeType: row.feeType,
    containerNo: '',
    description: row.description || row.feeType,
    quantity: row.quantity,
    unit: row.unit || 'Container',
    unitPrice: row.unitPrice,
    discountAmount: row.discountAmount ?? row.discount,
    taxRate: row.taxPercent ?? row.taxRate ?? row.tax,
    taxAmount: row.taxAmount,
    ...extra,
  })
}

/**
 * Expand quotation pricing into container-payment rows.
 *
 * A container-based line becomes one row per prepared actual container of that
 * type (the row keeps the container id so a later number assignment updates the
 * reference), and a shipment-based line stays a single row. Lines whose type has
 * no actual container yet are kept once, unassigned, instead of being dropped.
 */
export function expandQuotationContainerPayments(
  lines: Array<Record<string, unknown>>,
  actuals: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const rows: Array<Record<string, unknown>> = []
  for (const line of lines) {
    const type = lineContainerType(line)
    if (!type) {
      rows.push(quotationPaymentRow(line))
      continue
    }
    const containers = actuals.filter(actual => text(actual.containerType).toUpperCase() === type)
    if (!containers.length) {
      rows.push(quotationPaymentRow(line))
      continue
    }
    for (const container of containers) {
      rows.push(quotationPaymentRow(line, {
        containerNo: text(container.containerNo),
        containerType: text(container.containerType),
        serviceOrderContainerId: text(container.id),
      }))
    }
  }
  return rows
}

/**
 * Keep a stored payment's displayed container reference aligned with the actual
 * container it points at. Prices, quantities and notes are never touched.
 */
export function syncPaymentContainerReferences(
  rows: Array<Record<string, unknown>>,
  actuals: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  if (!rows.length || !actuals.length) return rows
  const byId = new Map(
    actuals
      .map(actual => [text(actual.id), actual] as const)
      .filter(([id]) => Boolean(id)),
  )
  return rows.map((row) => {
    const containerId = text(row.serviceOrderContainerId)
    const actual = containerId ? byId.get(containerId) : undefined
    if (!actual) return row
    const containerNo = text(actual.containerNo)
    return containerNo === text(row.containerNo) ? row : { ...row, containerNo }
  })
}

export function jobContainerPaymentRows(
  job: Record<string, unknown>,
  related?: {
    shipments?: Array<Record<string, unknown>>
    charges?: Array<Record<string, unknown>>
    quotation?: Record<string, unknown> | null
    actuals?: Array<Record<string, unknown>>
  },
): Array<Record<string, unknown>> {
  const actuals = related?.actuals || []
  const stored = Array.isArray(job.containerPayments) ? job.containerPayments : []
  if (stored.length) {
    return syncPaymentContainerReferences(
      stored.map(row => normalizeContainerPayment(row as Record<string, unknown>)),
      actuals,
    )
  }

  const quoted = Array.isArray(related?.quotation?.pricingLines) ? related!.quotation!.pricingLines as Array<Record<string, unknown>> : []
  if (quoted.length) {
    return expandQuotationContainerPayments(quoted, actuals)
  }

  const customerCharges = (related?.charges || []).filter(row => String(row.chargeSide || 'Customer') !== 'Supplier')
  if (customerCharges.length) {
    return customerCharges.map(row => normalizeContainerPayment({
      feeType: row.feeType || row.chargeType,
      containerNo: row.containerNo,
      quantity: row.quantity,
      description: row.description || row.feeType || row.chargeType,
      unitPrice: row.unitPrice || row.unitAmount,
      amount: row.total || row.amount,
      taxAmount: row.tax || row.taxAmount,
    }))
  }

  return []
}

/**
 * Totals for the container payment sheet.
 *
 * The sheet carries **one** discount and one tax rate for the whole sheet, so both
 * arrive as arguments and are applied to the summed line amounts — unless a line
 * carries its own adjustment from the Additional Details dialog, in which case
 * the summed line values are authoritative and the sheet values are ignored so
 * the same allowance is never counted twice.
 *
 * Tax is charged on the discounted amount, not the gross, which is what the tax
 * authority expects and what the totals block shows.
 */
export function jobContainerPaymentTotals(
  rows: Array<Record<string, unknown>>,
  vatRate: unknown,
  discount: unknown = 0,
) {
  const normalized = rows.map(row => normalizeContainerPayment(row))
  const subtotal = normalized.reduce((sum, row) => sum + asNumber(row.lineSubtotal ?? row.amount), 0)
  const lineDiscount = normalized.reduce((sum, row) => sum + asNumber(row.discountAmount), 0)
  const lineTax = normalized.reduce((sum, row) => sum + asNumber(row.taxAmount), 0)
  if (lineDiscount > 0 || lineTax > 0) {
    return {
      vatRate: 0,
      subtotal: Number(subtotal.toFixed(2)),
      discount: Number(lineDiscount.toFixed(2)),
      vat: Number(lineTax.toFixed(2)),
      total: Number((subtotal - lineDiscount + lineTax).toFixed(2)),
    }
  }
  const discountAmount = Math.max(0, asNumber(discount))
  const taxable = Math.max(0, subtotal - discountAmount)
  const rate = asNumber(vatRate)
  const vat = taxable * rate / 100
  return {
    vatRate: rate,
    subtotal: Number(subtotal.toFixed(2)),
    discount: Number(discountAmount.toFixed(2)),
    vat: Number(vat.toFixed(2)),
    total: Number((taxable + vat).toFixed(2)),
  }
}

export function jobContainerCount(
  job: Record<string, unknown>,
  paymentRows?: Array<Record<string, unknown>>,
  actualRows?: Array<Record<string, unknown>>,
) {
  const actuals = (actualRows && actualRows.length) ? actualRows : jobActualContainers(job)
  const actualNos = actuals.map(row => text(row.containerNo)).filter(Boolean)
  if (actualNos.length) return new Set(actualNos).size

  const rows = paymentRows || jobContainerPaymentRows(job)
  const fromPayments = new Set(rows.map(row => text(row.containerNo)).filter(Boolean))
  if (fromPayments.size) return fromPayments.size

  const keys = new Set(
    rows
      .map(row => `${text(row.blNo)}|${text(row.truckNo)}`)
      .filter(key => key !== '|'),
  )
  return keys.size
}

export function invalidGrossWeight(rows: Array<Record<string, unknown>>) {
  return rows.find((row) => {
    const net = asNumber(row.netWeightKg)
    const gross = asNumber(row.grossWeightKg)
    return gross > 0 && net > 0 && gross < net
  }) || null
}

export function duplicateContainerNumber(
  rows: Array<Record<string, unknown>>,
  others: Array<Record<string, unknown>> = [],
) {
  const seen = new Set<string>()
  for (const row of rows) {
    const no = text(row.containerNo).toUpperCase()
    if (!no) continue
    if (seen.has(no)) return no
    seen.add(no)
  }
  for (const row of others) {
    const no = text(row.containerNo || row.container_number).toUpperCase()
    if (no && seen.has(no)) return no
  }
  return ''
}

/** One cell-level problem in the actual-container grid. */
export type ContainerRowIssue = {
  index: number
  column: 'containerNo' | 'grossWeightKg'
  code: 'missingContainerNo' | 'grossLessThanNet' | 'duplicateContainerNo' | 'containerNoInUse'
}

/**
 * Row-scoped form of the aggregate checks above.
 *
 * The aggregate helpers answer "is anything wrong?"; this one answers "which
 * cell is wrong?", which is what inline validation and first-invalid-field
 * navigation need. `others` are containers belonging to other service orders —
 * a clash there is reported as a reference conflict, not a duplicate row.
 */
export function containerRowIssues(
  rows: Array<Record<string, unknown>>,
  others: Array<Record<string, unknown>> = [],
): ContainerRowIssue[] {
  const issues: ContainerRowIssue[] = []
  const taken = new Set(
    others.map(row => text(row.containerNo || row.container_number).toUpperCase()).filter(Boolean),
  )
  const seen = new Set<string>()

  rows.forEach((row, index) => {
    const no = text(row.containerNo)
    if (no) {
      const key = no.toUpperCase()
      if (seen.has(key)) issues.push({ index, column: 'containerNo', code: 'duplicateContainerNo' })
      else if (taken.has(key)) issues.push({ index, column: 'containerNo', code: 'containerNoInUse' })
      seen.add(key)
    }
    const started = Boolean(text(row.sealNo) || asNumber(row.netWeightKg) || asNumber(row.grossWeightKg))
    if (started && !no) {
      issues.push({ index, column: 'containerNo', code: 'missingContainerNo' })
    }
    const net = asNumber(row.netWeightKg)
    const gross = asNumber(row.grossWeightKg)
    if (gross > 0 && net > 0 && gross < net) {
      issues.push({ index, column: 'grossWeightKg', code: 'grossLessThanNet' })
    }
  })

  return issues
}

export function firstOpenRequirement(requirements: Array<Record<string, unknown>>) {
  const withProgress = requirements
  return withProgress.find(row => asNumber(row.remaining) > 0) || withProgress[0] || null
}

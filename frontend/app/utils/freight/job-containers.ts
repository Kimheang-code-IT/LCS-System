/** Service-order container tab: requirements (from quotation), actual boxes, and charge lines. */

export function newLineId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

function asNumber(value: unknown) {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? n : 0
}

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
    id: text(row.id) || newLineId('cr'),
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
    id: text(row.id) || newLineId('ac'),
    containerRequirementId: text(row.containerRequirementId || row.container_requirement_id),
    containerType: text(row.containerType),
    containerNo: text(row.containerNo || row.container_number),
    sealNo: text(row.sealNo || row.seal_serial),
    status: text(row.status) || 'Expected',
    netWeightKg: asNumber(row.netWeightKg ?? row.net_weight_kg),
    grossWeightKg: asNumber(row.grossWeightKg ?? row.gross_weight_kg),
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
      id: text(row.id) || newLineId('cp'),
      feeType: text(row.feeType || row.chargeType),
      containerNo: text(row.containerNo),
      serviceOrderContainerId: text(row.serviceOrderContainerId),
      description: text(row.description),
      unit: text(row.unit),
      blNo: text(row.blNo),
      truckNo: text(row.truckNo),
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
    id: text(row.id) || newLineId('cp'),
    feeType: text(row.feeType || row.chargeType),
    containerNo: text(row.containerNo),
    serviceOrderContainerId: text(row.serviceOrderContainerId),
    description: text(row.description),
    unit: text(row.unit),
    blNo: text(row.blNo),
    truckNo: text(row.truckNo),
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
  return rows
    .filter(row => text(row.containerNo))
    .map((row, index) => normalizeActualContainer(row, index))
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
  const stored = Array.isArray(job.containerRequirements) ? job.containerRequirements : []
  if (stored.length) return stored.map((row, index) => normalizeContainerRequirement(row as Record<string, unknown>, index))

  const collection = related?.requirements || []
  if (collection.length) return collection.map((row, index) => normalizeContainerRequirement(row, index))

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
  const stored = Array.isArray(job.actualContainers) ? job.actualContainers : []
  if (stored.length) return stored.map((row, index) => normalizeActualContainer(row as Record<string, unknown>, index))

  const collection = related?.actuals || []
  if (collection.length) return collection.map((row, index) => normalizeActualContainer(row, index))

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

export function jobContainerPaymentRows(
  job: Record<string, unknown>,
  related?: {
    shipments?: Array<Record<string, unknown>>
    charges?: Array<Record<string, unknown>>
    quotation?: Record<string, unknown> | null
    actuals?: Array<Record<string, unknown>>
  },
): Array<Record<string, unknown>> {
  const stored = Array.isArray(job.containerPayments) ? job.containerPayments : []
  if (stored.length) return stored.map(row => normalizeContainerPayment(row as Record<string, unknown>))

  const quoted = Array.isArray(related?.quotation?.pricingLines) ? related!.quotation!.pricingLines as Array<Record<string, unknown>> : []
  if (quoted.length) {
    return quoted.map(row => normalizeContainerPayment({
      feeType: row.feeType,
      containerNo: '',
      description: row.description || row.feeType,
      quantity: row.quantity,
      unit: row.unit || 'Container',
      unitPrice: row.unitPrice,
      discountAmount: row.discountAmount ?? row.discount,
      taxRate: row.taxPercent ?? row.taxRate ?? row.tax,
      taxAmount: row.taxAmount,
    }))
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

export function jobContainerPaymentTotals(
  rows: Array<Record<string, unknown>>,
  vatRate: unknown,
) {
  const normalized = rows.map(row => normalizeContainerPayment(row))
  const hasPricedLines = normalized.some(row =>
    Boolean(text(row.feeType)) || asNumber(row.taxRate) > 0 || asNumber(row.taxAmount) > 0 || asNumber(row.discountAmount) > 0)
  if (hasPricedLines) {
    const subtotal = normalized.reduce((sum, row) => sum + asNumber(row.lineSubtotal), 0)
    const discount = normalized.reduce((sum, row) => sum + asNumber(row.discountAmount), 0)
    const vat = normalized.reduce((sum, row) => sum + asNumber(row.taxAmount), 0)
    const total = normalized.reduce((sum, row) => sum + asNumber(row.lineTotal), 0)
    return {
      vatRate: 0,
      subtotal: Number(subtotal.toFixed(2)),
      discount: Number(discount.toFixed(2)),
      vat: Number(vat.toFixed(2)),
      total: Number(total.toFixed(2)),
    }
  }
  const subtotal = normalized.reduce((sum, row) => sum + asNumber(row.amount), 0)
  const rate = asNumber(vatRate)
  const vat = subtotal * rate / 100
  const total = subtotal + vat
  return {
    vatRate: rate,
    subtotal: Number(subtotal.toFixed(2)),
    discount: 0,
    vat: Number(vat.toFixed(2)),
    total: Number(total.toFixed(2)),
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

export function missingContainerNumber(rows: Array<Record<string, unknown>>) {
  return rows.some((row) => {
    const started = Boolean(text(row.sealNo) || asNumber(row.netWeightKg) || asNumber(row.grossWeightKg))
    return started && !text(row.containerNo)
  })
}

/** Copy quotation_revision_containers + pricing lines onto a new service order. */
export function serviceOrderContainersFromQuotation(
  quotation: Record<string, unknown>,
  job: { id?: unknown, jobNo?: unknown },
): {
  requirements: Array<Record<string, unknown>>
  actuals: Array<Record<string, unknown>>
  payments: Array<Record<string, unknown>>
} {
  const requirements: Array<Record<string, unknown>> = jobContainerRequirements({}, { quotation }).map((row, index) => ({
    ...row,
    id: newLineId('cr'),
    jobNo: text(job.jobNo),
    serviceOrderId: text(job.id),
    sequence: index + 1,
  }))
  const payments: Array<Record<string, unknown>> = jobContainerPaymentRows({}, { quotation }).map(row => ({
    ...row,
    id: newLineId('cp'),
  }))
  return { requirements, actuals: [], payments }
}

export function firstOpenRequirement(requirements: Array<Record<string, unknown>>) {
  const withProgress = requirements
  return withProgress.find(row => asNumber(row.remaining) > 0) || withProgress[0] || null
}

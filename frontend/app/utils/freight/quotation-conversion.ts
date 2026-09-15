type DataRecord = Record<string, unknown>

function cloneRows(value: unknown): DataRecord[] {
  if (!Array.isArray(value)) return []
  return value.map(row => ({ ...(row as DataRecord) }))
}

function roleIncludes(row: DataRecord, values: string[]) {
  const role = String(row.placeRole || '').trim().toLowerCase()
  return values.some(value => role.includes(value))
}

function rowValue(rows: DataRecord[], roles: string[], key: 'place' | 'plannedActual') {
  const row = rows.find(item => roleIncludes(item, roles))
  return String(row?.[key] || '').trim()
}

/** Operational route and file values captured when a quotation becomes a service order. */
export function quotationOperationalFields(quotation: DataRecord) {
  const places = cloneRows(quotation.places)
  const attachments = cloneRows(quotation.attachments)
  const pickup = String(quotation.pickup || rowValue(places, ['pickup', 'origin'], 'place')).trim()
  const port = String(quotation.port || rowValue(places, ['port of loading', 'port'], 'place')).trim()
  const border = String(quotation.border || rowValue(places, ['border', 'transit'], 'place')).trim()
  const destination = String(
    quotation.destination
    || quotation.delivery
    || quotation.deliveryLocation
    || rowValue(places, ['destination', 'delivery'], 'place'),
  ).trim()

  return {
    places,
    attachments,
    pickup,
    origin: String(quotation.origin || pickup).trim(),
    port,
    border,
    destination,
    deliveryLocation: String(quotation.deliveryLocation || destination).trim(),
    shipmentDate: String(quotation.shipmentDate || rowValue(places, ['pickup', 'origin'], 'plannedActual')).slice(0, 10),
    etaPort: String(quotation.etaPort || rowValue(places, ['port of loading', 'port'], 'plannedActual')).slice(0, 10),
    etaBorder: String(quotation.etaBorder || rowValue(places, ['border', 'transit'], 'plannedActual')).slice(0, 10),
    deliveryDate: String(quotation.deliveryDate || rowValue(places, ['destination', 'delivery'], 'plannedActual')).slice(0, 10),
    transportMode: quotation.transportMode || quotation.transportBy || '',
  }
}

/** Fill conversion omissions on existing mock jobs without replacing operational edits. */
export function backfillConvertedJobOperationalFields(job: DataRecord, quotation: DataRecord) {
  const source = quotationOperationalFields(quotation)
  const next = { ...job }
  for (const [key, value] of Object.entries(source)) {
    const current = next[key]
    const missing = Array.isArray(current) ? current.length === 0 : !String(current || '').trim()
    if (missing && (Array.isArray(value) ? value.length > 0 : Boolean(String(value || '').trim()))) {
      next[key] = value
    }
  }
  return next
}

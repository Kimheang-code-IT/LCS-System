import {
  JOB_CORE_WORKSPACE_SECTIONS,
  JOB_DEFAULT_COMPONENT_SECTIONS,
  jobWorkspaceSectionIcon,
} from '~/utils/freight/job-component-tabs'

export const JOB_WORKSPACE_SECTIONS = JOB_CORE_WORKSPACE_SECTIONS

export type JobWorkspaceSection = string

export const JOB_WORKSPACE_SECTION_META: Record<string, { icon: string }> = Object.fromEntries(
  [...JOB_WORKSPACE_SECTIONS, ...JOB_DEFAULT_COMPONENT_SECTIONS].map(id => [id, { icon: jobWorkspaceSectionIcon(id) }]),
)

export const JOB_OVERVIEW_SECTIONS = new Set([
  'Job Information',
  'Dates',
  'Reference',
  'Remarks',
])

export function isJobWorkspaceSection(value: unknown, extraIds: readonly string[] = []): value is JobWorkspaceSection {
  if (typeof value !== 'string') return false
  const allowed = extraIds.length ? extraIds : JOB_WORKSPACE_SECTIONS
  return allowed.includes(value) || (JOB_WORKSPACE_SECTIONS as readonly string[]).includes(value)
}

export function parseJobWorkspaceSection(value: unknown, extraIds: readonly string[] = []): JobWorkspaceSection {
  const raw = typeof value === 'string' ? value.trim() : ''
  const aliases: Record<string, string> = {
    places: 'route',
    booking: 'route',
    tracking: 'route',
    'container-requirements': 'containers',
    'actual-containers': 'containers',
    containers: 'containers',
    components: 'invoice',
    tasks: 'invoice',
    'packing list': 'packing-list',
    packinglist: 'packing-list',
    'shipment-registration-number': 'shipment-registration',
    registration: 'shipment-registration',
    'bill-of-lading': 'bill',
    bl: 'bill',
    'service-charges': 'containers',
    charges: 'containers',
    'financial-documents': 'finance',
    finance: 'finance',
    profit: 'finance',
    attachments: 'files',
    documents: 'files',
    files: 'files',
    audit: 'overview',
  }
  const mapped = aliases[raw] || raw
  if (isJobWorkspaceSection(mapped, extraIds)) return mapped
  return 'overview'
}

export function jobWorkspacePath(jobId: string, section: JobWorkspaceSection = 'overview') {
  const path = `/service-orders/${jobId}`
  if (!jobId) return '/service-orders'
  if (section === 'overview') return path
  return { path, query: { section } }
}

/** Service order created from this quotation, if any. */
export function jobForQuotation(
  jobs: Array<Record<string, unknown>>,
  quotation: Record<string, unknown>,
) {
  const quotationNo = String(quotation.quotationNo || '').trim()
  const convertedJobNo = String(quotation.convertedJobNo || '').trim()
  return jobs.find(job =>
    (convertedJobNo && String(job.jobNo || '') === convertedJobNo)
    || (quotationNo && String(job.quotationNo || '') === quotationNo),
  ) || null
}

export function workspaceSectionForPath(path: string): JobWorkspaceSection {
  if (path.includes('/operations/shipments') || path.includes('/operations/deliveries')) return 'route'
  if (path.includes('/operations/documents')) return 'files'
  if (path.includes('/operations/customs')) return 'customs'
  if (path.includes('/finance/job-charges') || path.includes('/finance/supplier-costs')) return 'containers'
  if (path.includes('/finance/')) return 'finance'
  return 'overview'
}

const JOB_ROUTE_STOPS = [
  { placeRole: 'Pickup', placeKeys: ['pickup', 'origin'], dateKey: 'shipmentDate' },
  { placeRole: 'Port of Loading', placeKeys: ['port'], dateKey: 'etaPort' },
  { placeRole: 'Transit / Border', placeKeys: ['border'], dateKey: 'etaBorder' },
  { placeRole: 'Destination', placeKeys: ['destination'], dateKey: 'deliveryDate' },
] as const

function routePlaceRow(row: Record<string, unknown>, index: number): Record<string, unknown> {
  return {
    sequence: Number(row.sequence || index + 1) || index + 1,
    placeRole: String(row.placeRole || 'Pickup').trim() || 'Pickup',
    place: String(row.place || '').trim(),
    plannedActual: String(row.plannedActual || '').slice(0, 10),
    notes: String(row.notes || '').trim(),
  }
}

export function defaultJobRoutePlaces(): Array<Record<string, unknown>> {
  return JOB_ROUTE_STOPS.map((stop, index) => routePlaceRow({ placeRole: stop.placeRole }, index))
}

/** Route tab lines. Stored on `job.places`; falls back to header pickup/port/border/destination. */
export function jobRoutePlaces(job: Record<string, unknown>): Array<Record<string, unknown>> {
  const stored = Array.isArray(job.places) ? job.places : []
  if (stored.length) return stored.map((row, index) => routePlaceRow(row as Record<string, unknown>, index))
  return JOB_ROUTE_STOPS.map((stop, index) => routePlaceRow({
    placeRole: stop.placeRole,
    place: stop.placeKeys.map(key => String(job[key] ?? '').trim()).find(Boolean) || '',
    plannedActual: job[stop.dateKey],
  }, index))
}

export function jobFieldsFromPlaces(places: Array<Record<string, unknown>>) {
  const rows = places.map((row, index) => routePlaceRow(row, index))
  const patch: Record<string, unknown> = { places: rows }
  for (const stop of JOB_ROUTE_STOPS) {
    const row = rows.find(item => String(item.placeRole) === stop.placeRole)
    if (!row) continue
    patch[stop.placeKeys[0]] = row.place
    patch[stop.dateKey] = row.plannedActual
  }
  return patch
}

export function displayText(value: unknown) {
  if (Array.isArray(value)) return value.map(item => String(item ?? '').trim()).filter(Boolean).join(', ') || '—'
  const text = String(value ?? '').trim()
  return text || '—'
}

export function isMoneyKey(key: string) {
  return /amount|total|vat|received|outstanding|paid|revenue|profit|cost|price|buying|selling|fee|subtotal/i.test(key)
    && !/date|status|type|note|method|side/i.test(key)
}

export function isNumericKey(key: string) {
  return /^(quantity|qty|daysOutstanding|margin|exchangeRate|userCount|permissionCount)$/i.test(key)
}

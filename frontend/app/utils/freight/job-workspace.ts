import { JOB_CORE_WORKSPACE_SECTIONS } from '~/utils/freight/job-component-tabs'

export const JOB_WORKSPACE_SECTIONS = JOB_CORE_WORKSPACE_SECTIONS

export type JobWorkspaceSection = string

/**
 * Leading overview group. Its heading is redundant — the tab is already titled
 * "Overview" — so the overview form renders the fields without a label.
 */
export const JOB_OVERVIEW_LEAD_SECTION = 'Job Information'

export const JOB_OVERVIEW_SECTIONS = new Set([
  JOB_OVERVIEW_LEAD_SECTION,
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
    'service-charges': 'charges',
    charges: 'charges',
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

function routePlaceRow(row: Record<string, unknown>, index: number): Record<string, unknown> {
  return {
    id: row.id !== null && row.id !== undefined ? String(row.id) : '',
    sequence: Number(row.sequence ?? row.sequenceNo ?? index + 1) || index + 1,
    // The reference id is what the API stores; the text snapshot beside it keeps
    // a historical stop readable when the role is deactivated.
    placeRoleId: row.placeRoleId !== null && row.placeRoleId !== undefined ? String(row.placeRoleId) : '',
    placeRole: String(row.placeRole || '').trim(),
    place: String(row.place || '').trim(),
    // `plannedActual` was the single date column before Planned/Actual split.
    planned: String(row.planned ?? row.plannedAt ?? row.plannedActual ?? '').trim(),
    actual: String(row.actual ?? row.actualAt ?? '').trim(),
    notes: String(row.notes || '').trim(),
  }
}

/**
 * Route tab lines, as stored on the order. The backend returns them from
 * `service_order_places` (falling back to the embedded JSON for an older order),
 * so this is a normalisation only — there is no hardcoded stop list any more.
 */
export function jobRoutePlaces(job: Record<string, unknown>): Array<Record<string, unknown>> {
  const stored = Array.isArray(job.places) ? job.places : []
  return stored.map((row, index) => routePlaceRow(row as Record<string, unknown>, index))
}

/**
 * The route table writes back only its own rows. Header place text is no longer
 * mirrored from role names: roles are configuration, so matching a hardcoded
 * "Pickup" string would silently stop working when an administrator renames it.
 */
export function jobFieldsFromPlaces(places: Array<Record<string, unknown>>) {
  return { places: places.map((row, index) => routePlaceRow(row, index)) }
}

export function isMoneyKey(key: string) {
  return /amount|total|vat|received|outstanding|paid|revenue|profit|cost|price|buying|selling|fee|subtotal/i.test(key)
    && !/date|status|type|note|method|side/i.test(key)
}

export function isNumericKey(key: string) {
  return /^(quantity|qty|daysOutstanding|margin|exchangeRate|userCount|permissionCount)$/i.test(key)
}

/**
 * Filters a report page collects before it generates anything.
 *
 * Kept out of the component so the request body is testable: a report auto-loads
 * when opened and re-runs these filters on Generate or Rebuild.
 */
export type ReportFilterValues = {
  dateFrom: string
  dateTo: string
  fiscalYear: string
  accountFrom: string
  accountTo: string
  accountCode: string
  party: string
  voucherType: string
  voucherNo: string
  currency: string
}

export const EMPTY_REPORT_FILTERS: ReportFilterValues = {
  dateFrom: '',
  dateTo: '',
  fiscalYear: '',
  accountFrom: '',
  accountTo: '',
  accountCode: '',
  party: '',
  voucherType: '',
  voucherNo: '',
  currency: '',
}

/** Reports backed by the on-demand generation endpoints (server-paginated). */
export const GENERATED_REPORT_SLUGS = ['trial-balance', 'general-ledger'] as const

export function isGeneratedReport(slug: string) {
  return (GENERATED_REPORT_SLUGS as readonly string[]).includes(slug)
}

export function hasReportFilters(filters: ReportFilterValues) {
  return Object.values(filters).some(value => String(value ?? '').trim() !== '')
}

export function reportGenerateBody(
  slug: string,
  filters: ReportFilterValues,
  page: number,
  pageSize: number,
): Record<string, unknown> | null {
  const body = reportFilterBody(slug, filters)
  return body ? { ...body, page, pageSize } : null
}

/**
 * The body of a full-result export: the same filters as Generate without the
 * page, plus the optional column selection the export dialog sends.
 */
export function reportExportBody(
  slug: string,
  filters: ReportFilterValues,
  fields: string[] = [],
): Record<string, unknown> | null {
  const body = reportFilterBody(slug, filters)
  if (!body) return null
  return fields.length ? { ...body, fields } : body
}

function reportFilterBody(slug: string, filters: ReportFilterValues): Record<string, unknown> | null {
  if (!isGeneratedReport(slug)) return null
  const body: Record<string, unknown> = {}
  const text = (value: string) => String(value ?? '').trim()

  if (text(filters.dateFrom)) body.fromDate = text(filters.dateFrom)
  if (text(filters.dateTo)) body.toDate = text(filters.dateTo)
  if (text(filters.fiscalYear)) body.fiscalYear = Number(text(filters.fiscalYear))

  if (slug === 'trial-balance') {
    if (text(filters.accountFrom)) body.accountFrom = text(filters.accountFrom)
    if (text(filters.accountTo)) body.accountTo = text(filters.accountTo)
  }
  else {
    if (text(filters.accountCode)) body.accountCode = text(filters.accountCode)
    if (text(filters.party)) body.party = text(filters.party)
    if (text(filters.voucherType)) body.voucherType = text(filters.voucherType)
    if (text(filters.voucherNo)) body.voucherNo = text(filters.voucherNo)
    if (text(filters.currency)) body.currency = text(filters.currency).toUpperCase()
  }
  return body
}

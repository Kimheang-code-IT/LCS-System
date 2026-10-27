export type ExportScope = 'all_matching' | 'current_page' | 'selected'

export type ExportFormat = 'xlsx' | 'csv'

/** Filters applied at the database query level by the backend export API. */
export interface ExportFilters {
  dateFrom?: string
  dateTo?: string
  updatedBy?: string
  status?: string
}

export interface ExportFieldOption {
  label: string
  value: string
}

export interface ExportRequest {
  startDate?: string
  endDate?: string
  scope: ExportScope
  fieldCodes: string[]
  format?: ExportFormat
  filters?: ExportFilters
}

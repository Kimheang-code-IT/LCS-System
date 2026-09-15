export interface PersonSummary {
  id: string
  name: string
  email?: string
  avatarUrl?: string
}

export interface OrganizationSummary {
  id: string
  name: string
  code?: string
}

export interface ApiMeta {
  page: number
  limit: number
  total: number
  totalPages?: number
  cursor?: string | null
  nextCursor?: string | null
}

export interface ApiErrorItem {
  code: string
  message: string
  field?: string
}

export interface ApiResponse<T> {
  data: T
  meta?: ApiMeta
  errors?: ApiErrorItem[]
}

export interface GroupCountSummary {
  total: number
  unassigned: number
  groups: Record<string, number>
}

export interface ListQuery {
  q?: string
  page?: number
  limit?: number
  sort?: string
  view?: EntityView
  stage?: string
  status?: string
  startDate?: string
  endDate?: string
  [key: string]: string | number | boolean | undefined
}

export interface WorkflowStage {
  id: string
  code: string
  labelKey: string
  /** Literal configured label; preferred over labelKey for user-defined stages. */
  label?: string
  order: number
  color?: string
}

export interface EntityComment {
  id: string
  entityType: string
  entityId: string
  body: string
  author: PersonSummary
  createdAt: string
  editedAt?: string
}

export type EntityView = 'table' | 'kanban' | 'hierarchy' | 'timeline'

export interface EntityRecordNeighbors {
  previousId: string | null
  nextId: string | null
}

export interface EntityFavoriteState {
  isFavorite: boolean
}

export interface ActivityEvent {
  id: string
  entityType: string
  entityId: string
  action: string
  actor?: PersonSummary
  summary: string
  occurredAt: string
  correlationId?: string
  metadata?: Record<string, unknown>
}

export interface AttachmentMeta {
  id: string
  name: string
  mimeType: string
  sizeBytes: number
  url?: string
  uploadedBy?: PersonSummary
  uploadedAt: string
  storageSource?: 'local' | 'google_drive'
}

export type FieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'date'
  | 'datetime'
  | 'select'
  | 'multiselect'
  | 'boolean'
  | 'organization'
  | 'officer'
  | 'relation'
  | 'file'
  | 'url'
  | 'permission-matrix'
  | 'secret'
  | 'color'
  | 'image'
  | 'csv-list'
  | 'telegram-destinations'
  | 'notification-rules'
  | 'connection-status'
  | 'alert'
  | 'icon'
  | 'assigned-attributes'
  | 'workflow-builder'
  | 'numbering-preview'
  | 'validation-builder'
  | 'options-builder'
  | 'visibility-builder'
  | 'line-table'
  | 'related-records'
  | 'dynamic-table'
  | 'table-columns-builder'

export interface FieldOption {
  label: string
  value: string
  labelKey?: string
  /** Optional API-safe option context such as hierarchy depth and unformatted name. */
  meta?: Record<string, unknown>
}

export interface ConnectionStatusFieldValue {
  status: string
  message?: string
  lastTestedAt?: string
  details?: Array<{ label: string, value: string }>
}

export interface DocumentFieldSchema {
  key: string
  /** i18n key for the label. Prefer `label` for dynamic/config-driven fields. */
  labelKey: string
  /** Literal label (used when the text is not an i18n key, e.g. attribute catalog). */
  label?: string
  type: FieldType
  required?: boolean
  readOnly?: boolean
  colSpan?: 1 | 2
  options?: FieldOption[]
  /** Bounded API endpoint returning active `{ label, value }` options. */
  optionsEndpoint?: string
  /** Help text shown below the input (ERPNext-style field description). */
  helpKey?: string
  /** Literal help text for dynamic fields. */
  help?: string
  /** Hint shown via info icon (especially useful for checkboxes). Falls back to helpKey. */
  hintKey?: string
  placeholderKey?: string
  /** Literal placeholder for dynamic fields. */
  placeholder?: string
  /** Textarea row count (defaults to 4). */
  rows?: number
  /** Alert color when type is `alert`. */
  alertColor?: 'error' | 'warning' | 'info' | 'success' | 'neutral'
  /** Extra context for specialized field renderers (e.g. dataType, catalog). */
  meta?: Record<string, unknown>
}

export interface DocumentSectionSchema {
  id: string
  titleKey?: string
  /** Literal section title for dynamic sections. */
  title?: string
  descriptionKey?: string
  description?: string
  fields: DocumentFieldSchema[]
}

export interface DocumentTabSchema {
  id: string
  labelKey: string
  /** Literal tab label (used when text is not an i18n key). */
  label?: string
  sections: DocumentSectionSchema[]
}

export interface TableColumnDef {
  key: string
  labelKey: string
  sortable?: boolean
  width?: string
  priority?: 'high' | 'medium' | 'low'
  /** How the cell should render. Defaults are inferred from the key when omitted. */
  cell?: 'text' | 'badge' | 'datetime' | 'person'
}

export interface FilterDef {
  key: string
  labelKey: string
  type: 'select' | 'multiselect' | 'boolean' | 'date' | 'daterange'
  options?: FieldOption[]
  /** Custom start query key for daterange type (defaults to 'startDate'). */
  startKey?: string
  /** Custom end query key for daterange type (defaults to 'endDate'). */
  endKey?: string
}

export type EntityStatus = 'draft' | 'active' | 'archived' | 'deleted' | 'disabled' | 'pending' | 'completed' | 'failed'

export interface BaseEntity {
  id: string
  title?: string
  name?: string
  code?: string
  status: string
  stage?: string
  createdAt: string
  updatedAt: string
  createdBy?: PersonSummary
  updatedBy?: PersonSummary
  owner?: PersonSummary
  assignee?: PersonSummary
  organization?: OrganizationSummary
  tags?: string[]
  attachmentCount?: number
  commentCount?: number
}

export interface PersonSummary {
  id: string
  name: string
  email?: string
  avatarUrl?: string
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

export interface EntityComment {
  id: string
  entityType: string
  entityId: string
  body: string
  author: PersonSummary
  createdAt: string
  editedAt?: string
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
  | 'language-toggles'
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
  /**
   * Financial document types this field applies to (from `FreightField.documentTypes`).
   * Empty/absent means every type; the form drops the field for the other types.
   */
  documentTypes?: readonly string[]
  /**
   * Show the field only while two record fields differ, e.g. the exchange rate
   * while the document currency is not the company's base currency. Absent means
   * always shown, and the rule is not evaluated when no record is in hand.
   */
  visibleWhen?: { differs: readonly [string, string] }
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
  /**
   * Financial document types this tab applies to (`FreightTab`/recipe metadata).
   * Empty/absent means every type, so a tab only disappears when it declares one.
   */
  documentTypes?: readonly string[]
  /** Record statuses this tab applies to, matched case-insensitively. */
  statuses?: readonly string[]
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
  tags?: string[]
  attachmentCount?: number
  commentCount?: number
}

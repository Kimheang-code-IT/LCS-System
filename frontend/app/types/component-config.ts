/** Component configuration: reusable attributes, groups of attributes, and tabs of groups. */

export type ComponentDataType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'integer'
  | 'decimal'
  | 'money'
  | 'currency'
  | 'date'
  | 'datetime'
  | 'select'
  | 'multi_select'
  | 'checkbox'
  | 'boolean'
  | 'reference'

export type ComponentReferenceType =
  | 'business_party'
  | 'transport_asset'
  | 'transport_type'
  | 'container'
  | 'fee_type'
  | 'user'

/** Legacy group-level render mode, still the fallback for an unconfigured tab assignment. */
export type ComponentRenderMode = 'table' | 'form'

/** How a component group renders within one tab. */
export type ComponentDisplayMode = 'form_only' | 'table_only' | 'form_and_table'
export type ComponentDataCardinality = 'single' | 'multiple'
export type ComponentFormColumns = 1 | 2 | 3 | 4

export const COMPONENT_DISPLAY_MODES: ComponentDisplayMode[] = [
  'form_only',
  'table_only',
  'form_and_table',
]

export interface ComponentAttribute {
  id: string
  code: string
  label: string
  labelKm?: string | null
  dataType: ComponentDataType
  inputType?: string | null
  referenceType?: ComponentReferenceType | null
  isRequired: boolean
  defaultValue?: string | null
  placeholder?: string | null
  width?: string | null
  options?: Array<string | { label: string, value: string }>
  validationRules?: Record<string, unknown>
  displayOrder?: number
  status: string
  createdAt?: string | null
  updatedAt?: string | null
}

export interface ComponentAttributeInput {
  code?: string
  label?: string
  labelKm?: string
  dataType?: ComponentDataType
  inputType?: string
  referenceType?: ComponentReferenceType | null
  isRequired?: boolean
  defaultValue?: string
  placeholder?: string
  width?: string
  options?: Array<string | { label: string, value: string }>
  validationRules?: Record<string, unknown>
  status?: string
}

export interface ComponentGroupAttribute {
  id: string
  groupId: string
  attributeId: string
  code: string
  label: string
  labelKm?: string | null
  dataType: ComponentDataType
  inputType?: string | null
  referenceType?: ComponentReferenceType | null
  isRequired: boolean
  width?: string | null
  options?: Array<string | { label: string, value: string }>
  defaultValue?: string | null
  placeholder?: string | null
  displayOrder: number
  isVisible?: boolean
  status: string
}

export interface ComponentGroup {
  id: string
  code: string
  name: string
  nameKm?: string | null
  description?: string | null
  renderMode: ComponentRenderMode
  displayOrder: number
  isActive: boolean
  isArchived: boolean
  attributeCount?: number
  createdAt?: string | null
  updatedAt?: string | null
}

export interface ComponentGroupInput {
  code?: string
  name?: string
  nameKm?: string
  description?: string
  renderMode?: ComponentRenderMode
  displayOrder?: number
  isActive?: boolean
  isArchived?: boolean
}

export interface ComponentTab {
  id: string
  code: string
  name: string
  description?: string | null
  tradeDirectionId?: string | null
  displayOrder: number
  isActive: boolean
  isArchived: boolean
  groupCount?: number
  createdAt?: string | null
  updatedAt?: string | null
}

export interface ComponentTabInput {
  code?: string
  name?: string
  description?: string
  tradeDirectionId?: string | null
  displayOrder?: number
  isActive?: boolean
  isArchived?: boolean
}

/** Effective layout of one group assignment on a tab. */
export interface ComponentGroupLayout {
  displayMode: ComponentDisplayMode
  dataCardinality: ComponentDataCardinality
  formColumns: ComponentFormColumns
  showGroupTitle: boolean
  editable: boolean
  collapsible: boolean
  defaultExpanded: boolean
}

export type ComponentGroupLayoutInput = Partial<Omit<ComponentGroupLayout, 'formColumns'> & {
  formColumns: number
  displayOrder: number
  status: string
}>

export interface ComponentTabGroupLink extends ComponentGroup, ComponentGroupLayout {
  tabGroupId: string
  displayOrder: number
}

export interface ComponentGroupRow {
  id?: string
  groupId: string
  rowNo?: number
  values: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
}

export interface ComponentTabAttribute {
  id: string
  code: string
  label: string
  labelKm?: string | null
  fieldType: ComponentDataType
  inputType?: string | null
  referenceType?: ComponentReferenceType | null
  isRequired: boolean
  /** FALSE hides the attribute in every tab that uses this group; saved values are kept. */
  isVisible?: boolean
  defaultValue?: string | null
  placeholder?: string | null
  width?: string | null
  options?: Array<string | { label: string, value: string }>
  validationRules?: Record<string, unknown>
  sortOrder: number
}

export interface ComponentTabGroup extends ComponentGroupLayout {
  id: string
  /** The tab/group assignment this layout belongs to; namespaced saves use it. */
  tabGroupId?: string
  code: string
  name: string
  nameKm?: string | null
  renderMode: ComponentRenderMode
  displayOrder: number
  attributes: ComponentTabAttribute[]
  rows: ComponentGroupRow[]
}

export interface ComponentTabRuntime {
  id: string
  code: string
  name: string
  tradeDirectionId?: string | null
  displayOrder: number
  groups: ComponentTabGroup[]
}

export interface ComponentTabsBootstrap {
  serviceOrderId: string
  jobNo: string
  tradeDirectionId?: string | null
  tabs: ComponentTabRuntime[]
  references: Record<string, Record<string, string>>
  /** Published configuration the order was captured under, when one exists. */
  configVersionId?: string | null
  configVersion?: ConfigurationVersion | null
}

/**
 * A published snapshot of the Service Order configuration. Editing a tab no
 * longer changes how an existing order reads, because the order stays pinned to
 * the version it was created under.
 */
export interface ConfigurationVersion {
  id: string
  versionNo: number
  scope?: string
  origin?: 'PUBLISH' | 'ROLLBACK'
  status: 'DRAFT' | 'PUBLISHED' | 'RETIRED'
  changeNote?: string | null
  createdBy?: string | null
  publishedAt?: string | null
  publishedByUserId?: string | null
  publishedBy?: string | null
  activatedAt?: string | null
  activatedByUserId?: string | null
  activatedBy?: string | null
  sourceVersionId?: string | null
  sourceVersionNo?: number | null
  snapshotSchemaVersion?: number
  contentHash?: string | null
  tabCount: number
  groupCount?: number
  attributeCount?: number
  createdAt?: string | null
  updatedAt?: string | null
  configSnapshot?: { tabs?: ComponentTabRuntime[] } | null
  tradeDirections?: Record<string, string>
}

export interface ConfigurationVersionPreview {
  preview: { tabs?: ComponentTabRuntime[] }
  tabCount: number
  currentVersionNo: number | null
  unchanged: boolean
  tradeDirections?: Record<string, string>
}

export interface ConfigurationVersionListParams {
  page?: number
  pageSize?: number
  q?: string
  status?: string
  sortKey?: string
  sortDir?: 'asc' | 'desc'
}

export interface ConfigurationVersionPage {
  items: ConfigurationVersion[]
  meta: { page: number, page_size: number, total: number }
}

export interface ConfigurationVersionComparisonEntry {
  id?: string
  code?: string | null
  label?: string | null
  tab?: string | null
  group?: string | null
  path?: string
  field?: string
  before?: unknown
  after?: unknown
}

export interface ConfigurationVersionComparison {
  from: ConfigurationVersion
  to: ConfigurationVersion
  changes: {
    summary: Record<string, number>
    unchanged: boolean
    tabs: { added: ConfigurationVersionComparisonEntry[], removed: ConfigurationVersionComparisonEntry[], renamed: ConfigurationVersionComparisonEntry[] }
    groups: { added: ConfigurationVersionComparisonEntry[], removed: ConfigurationVersionComparisonEntry[], renamed: ConfigurationVersionComparisonEntry[] }
    attributes: {
      added: ConfigurationVersionComparisonEntry[]
      removed: ConfigurationVersionComparisonEntry[]
      renamed: ConfigurationVersionComparisonEntry[]
      changedFieldTypes: ConfigurationVersionComparisonEntry[]
      changedRequiredRules: ConfigurationVersionComparisonEntry[]
    }
    layouts: {
      changedDisplayModes: ConfigurationVersionComparisonEntry[]
      changedLayouts: ConfigurationVersionComparisonEntry[]
    }
    ordering: ConfigurationVersionComparisonEntry[]
  }
  tradeDirections?: Record<string, string>
}

export interface ConfigurationVersionActivationEvent {
  id: string
  occurredAt?: string | null
  eventType: string
  entityId: string
  action: string
  result: string
  reason?: string | null
  user: string
  before?: Record<string, unknown> | null
  after?: Record<string, unknown> | null
  metadata?: Record<string, unknown> | null
}

export const COMPONENT_DATA_TYPES: ComponentDataType[] = [
  'text',
  'textarea',
  'number',
  'integer',
  'decimal',
  'money',
  'currency',
  'date',
  'datetime',
  'select',
  'multi_select',
  'checkbox',
  'boolean',
  'reference',
]

/** Component configuration: reusable attributes, groups of attributes, and tabs of groups. */

export type ComponentDataType =
  | 'text'
  | 'textarea'
  | 'number'
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
  | 'place'
  | 'transport_asset'
  | 'transport_type'
  | 'container'
  | 'fee_type'
  | 'user'

export type ComponentRenderMode = 'table' | 'form'

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

export interface ComponentTabGroupLink extends ComponentGroup {
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
  defaultValue?: string | null
  placeholder?: string | null
  width?: string | null
  options?: Array<string | { label: string, value: string }>
  validationRules?: Record<string, unknown>
  sortOrder: number
}

export interface ComponentTabGroup {
  id: string
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
  status: 'DRAFT' | 'PUBLISHED' | 'RETIRED'
  changeNote?: string | null
  publishedAt?: string | null
  publishedByUserId?: string | null
  tabCount: number
  createdAt?: string | null
  updatedAt?: string | null
  configSnapshot?: { tabs?: ComponentTabRuntime[] } | null
}

export interface ConfigurationVersionPreview {
  preview: { tabs?: ComponentTabRuntime[] }
  tabCount: number
  currentVersionNo: number | null
  unchanged: boolean
}

export const COMPONENT_DATA_TYPES: ComponentDataType[] = [
  'text',
  'textarea',
  'number',
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

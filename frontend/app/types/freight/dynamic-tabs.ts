/** Configurable Service Order operational tabs (dynamic tables). */

export type DynamicFieldType =
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
  | 'reference'

export type DynamicReferenceType =
  | 'business_party'
  | 'place'
  | 'transport_asset'
  | 'transport_type'
  | 'container'
  | 'fee_type'
  | 'user'

export interface DynamicTabColumn {
  id: string
  tabId: string
  fieldKey: string
  label: string
  labelKm?: string | null
  fieldType: DynamicFieldType
  referenceType?: DynamicReferenceType | null
  isRequired: boolean
  isActive: boolean
  isArchived: boolean
  showInSummary: boolean
  width?: string | null
  sortOrder: number
  defaultValue?: string | null
  placeholder?: string | null
  validationRules?: Record<string, unknown>
  options?: Array<string | { label: string, value: string }>
}

export interface DynamicTabRow {
  id: string
  tabId: string
  tabCode: string
  rowNo: number
  values: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
}

export interface DynamicTab {
  id: string
  code: string
  name: string
  nameKm?: string | null
  icon?: string | null
  sortOrder: number
  isActive: boolean
  allowMultipleRows: boolean
  isArchived?: boolean
  columns: DynamicTabColumn[]
  rows?: DynamicTabRow[]
}

export interface DynamicTabsBootstrap {
  serviceOrderId: string
  jobNo: string
  tabs: DynamicTab[]
  references: Record<string, Record<string, string>>
}

export interface DynamicTabInput {
  code?: string
  name?: string
  nameKm?: string
  icon?: string
  description?: string
  sortOrder?: number
  isActive?: boolean
  allowMultipleRows?: boolean
  isArchived?: boolean
}

export interface DynamicColumnInput {
  fieldKey?: string
  label?: string
  labelKm?: string
  fieldType?: DynamicFieldType
  referenceType?: DynamicReferenceType | null
  isRequired?: boolean
  isActive?: boolean
  isArchived?: boolean
  showInSummary?: boolean
  width?: string
  sortOrder?: number
  defaultValue?: string
  placeholder?: string
  validationRules?: Record<string, unknown>
  options?: Array<string | { label: string, value: string }>
}

export const DYNAMIC_FIELD_TYPES: DynamicFieldType[] = [
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
  'reference',
]

export const DYNAMIC_REFERENCE_TYPES: DynamicReferenceType[] = [
  'business_party',
  'place',
  'transport_asset',
  'transport_type',
  'container',
  'fee_type',
  'user',
]

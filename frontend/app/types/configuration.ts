import type { BaseEntity } from './common'

/** Controlled attribute data types for dynamic record fields. */
export type AttributeDataType =
  | 'short_text'
  | 'long_text'
  | 'rich_text'
  | 'integer'
  | 'decimal'
  | 'currency'
  | 'boolean'
  | 'date'
  | 'time'
  | 'datetime'
  | 'email'
  | 'phone'
  | 'url'
  | 'select'
  | 'multi_select'
  | 'radio'
  | 'checkbox_group'
  | 'file'
  | 'image'
  | 'officer'
  | 'user'
  | 'record_reference'
  | 'table'

export type DynamicTableColumnType = 'text' | 'number' | 'date' | 'select'

export interface DynamicTableColumnDef {
  id: string
  key: string
  label: string
  labelKm?: string
  type: DynamicTableColumnType
  options?: string[]
  required?: boolean
  order: number
}

export type VisibilityOperator =
  | 'equals'
  | 'not_equals'
  | 'contains'
  | 'is_empty'
  | 'is_not_empty'
  | 'greater_than'
  | 'less_than'

export interface AttributeOption {
  id: string
  label: string
  value: string
  color?: string
  icon?: string
  active: boolean
  order: number
}

export interface ValidationRule {
  minLength?: number
  maxLength?: number
  pattern?: string
  min?: number
  max?: number
  precision?: number
  minDate?: string
  maxDate?: string
  allowFutureDate?: boolean
  allowPastDate?: boolean
  maxFileSizeMb?: number
  allowedExtensions?: string[]
  allowMultiple?: boolean
}

export interface VisibilityRule {
  fieldCode: string
  operator: VisibilityOperator
  value?: string | number | boolean | null
}

export interface RecordAttribute extends BaseEntity {
  label: string
  code: string
  description?: string
  helpText?: string
  dataType: AttributeDataType
  placeholder?: string
  defaultValue?: string | number | boolean | string[] | null
  required: boolean
  unique: boolean
  readOnly: boolean
  searchable: boolean
  filterable: boolean
  sortable: boolean
  showInList: boolean
  validation?: ValidationRule
  options?: AttributeOption[]
  visibility?: VisibilityRule | null
  /** Count of record types using this attribute (denormalized for lists). */
  usedByCount: number
}

export interface RecordTypeAttribute {
  attributeId: string
  attributeCode: string
  attributeLabel: string
  dataType: AttributeDataType
  required: boolean
  readOnly: boolean
  visible: boolean
  searchable: boolean
  filterable: boolean
  showInList: boolean
  /** Optional workflow stage where this field becomes applicable. Empty means all stages. */
  stageCode?: string
  section?: string
  columnWidth?: number
  order: number
}

export interface ConfigWorkflowStage {
  id: string
  name: string
  code: string
  color?: string
  isInitial: boolean
  isFinal: boolean
  order: number
}

export const ATTRIBUTE_DATA_TYPES: AttributeDataType[] = [
  'short_text',
  'long_text',
  'rich_text',
  'integer',
  'decimal',
  'currency',
  'boolean',
  'date',
  'time',
  'datetime',
  'email',
  'phone',
  'url',
  'select',
  'multi_select',
  'radio',
  'checkbox_group',
  'file',
  'image',
  'officer',
  'user',
  'record_reference',
  'table',
]

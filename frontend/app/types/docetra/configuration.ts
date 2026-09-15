import type { BaseEntity, EntityStatus } from './common'

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
  | 'organization'
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

export type CreateRecordAttributeInput = Omit<
  RecordAttribute,
  'id' | 'createdAt' | 'updatedAt' | 'usedByCount' | 'status'
> & { status?: EntityStatus | string }

export type UpdateRecordAttributeInput = Partial<CreateRecordAttributeInput>

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

export interface WorkflowTransition {
  id: string
  fromStageCode: string
  toStageCode: string
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

export interface RecordTypeFeatures {
  allowAttachments: boolean
  allowComments: boolean
  allowAssignment: boolean
  allowSharing: boolean
  allowRelatedRecords: boolean
  enableWorkflow: boolean
  enableDueDate: boolean
  enableHistory: boolean
  enableExport: boolean
}

export interface RecordTypeNumbering {
  prefix: string
  includeYear: boolean
  sequenceLength: number
  resetYearly: boolean
}

export interface RecordType extends BaseEntity {
  name: string
  code: string
  description?: string
  icon?: string
  color?: string
  features: RecordTypeFeatures
  numbering: RecordTypeNumbering
  attributes: RecordTypeAttribute[]
  stages: ConfigWorkflowStage[]
  transitions: WorkflowTransition[]
  attributeCount: number
  workflowEnabled: boolean
}

/** Permission-filtered, versionable schema used to render one record type. */
export interface ResolvedRecordTypeSchema {
  recordType: RecordType
  attributes: RecordAttribute[]
  version: string
}

export type CreateRecordTypeInput = Omit<
  RecordType,
  'id' | 'createdAt' | 'updatedAt' | 'attributeCount' | 'workflowEnabled' | 'status'
> & { status?: EntityStatus | string }

export type UpdateRecordTypeInput = Partial<CreateRecordTypeInput>

export interface RecordAttributeQuery {
  q?: string
  page?: number
  limit?: number
  sort?: string
  status?: string
  dataType?: AttributeDataType | string
}

export interface RecordTypeQuery {
  q?: string
  page?: number
  limit?: number
  sort?: string
  status?: string
  workflowEnabled?: boolean | string
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
  'organization',
  'officer',
  'user',
  'record_reference',
  'table',
]

export const OPTION_DATA_TYPES: AttributeDataType[] = [
  'select',
  'multi_select',
  'radio',
  'checkbox_group',
]

export const VISIBILITY_OPERATORS: VisibilityOperator[] = [
  'equals',
  'not_equals',
  'contains',
  'is_empty',
  'is_not_empty',
  'greater_than',
  'less_than',
]

export function defaultRecordTypeFeatures(): RecordTypeFeatures {
  return {
    allowAttachments: true,
    allowComments: true,
    allowAssignment: true,
    allowSharing: false,
    allowRelatedRecords: true,
    enableWorkflow: true,
    enableDueDate: true,
    enableHistory: true,
    enableExport: true,
  }
}

export function defaultRecordTypeNumbering(prefix = 'DOC'): RecordTypeNumbering {
  return {
    prefix,
    includeYear: true,
    sequenceLength: 6,
    resetYearly: true,
  }
}

export function previewRecordNumber(numbering: RecordTypeNumbering, seq = 1): string {
  const year = numbering.includeYear ? `-${new Date().getFullYear()}` : ''
  const padded = String(seq).padStart(Math.max(1, numbering.sequenceLength), '0')
  return `${numbering.prefix}${year}-${padded}`
}

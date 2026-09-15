export type PermissionScope = 'ORGANIZATION' | 'BRANCH' | 'OWN' | 'NONE'

export type QuotationRevisionStatus =
  | 'DRAFT'
  | 'SENT'
  | 'ACCEPTED'
  | 'CONVERTED'
  | 'REJECTED'
  | 'SUPERSEDED'
  | 'EXPIRED'
  | 'CANCELLED'

export type ServiceOrderStatus =
  | 'DRAFT'
  | 'OPEN'
  | 'IN_PROGRESS'
  | 'ON_HOLD'
  | 'COMPLETED'
  | 'CLOSED'
  | 'CANCELLED'

export type ServiceChargeStatus = 'DRAFT' | 'ISSUED'

export type FinancialDocumentStatus = 'DRAFT' | 'POSTED' | 'REVERSED' | 'CANCELLED'

export type JournalStatus = 'DRAFT' | 'POSTED' | 'REVERSED' | 'VOIDED'

export type ComponentStatus = 'PENDING' | 'COMPLETED'
export type ComponentInstanceMode = 'SINGLE' | 'REPEATABLE'
export type ComponentInstanceModeOverride = 'INHERIT' | ComponentInstanceMode

export type FinancialDocumentType =
  | 'CUSTOMER_INVOICE'
  | 'SUPPLIER_BILL'
  | 'CUSTOMER_RECEIPT'
  | 'SUPPLIER_PAYMENT'
  | 'OTHER_INCOME'
  | 'OTHER_EXPENSE'

export type LcsErrorCode =
  | 'AUTH_REQUIRED'
  | 'ACCESS_DENIED'
  | 'ORGANIZATION_CONTEXT_REQUIRED'
  | 'BRANCH_SCOPE_DENIED'
  | 'INVALID_STATE_TRANSITION'
  | 'REFERENCE_NOT_FOUND'
  | 'REFERENCE_OUT_OF_SCOPE'
  | 'DUPLICATE_NUMBER'
  | 'DUPLICATE_CONVERSION'
  | 'REQUIRED_VALUE_MISSING'
  | 'INVALID_ATTRIBUTE_TYPE'
  | 'PERIOD_CLOSED'
  | 'JOURNAL_UNBALANCED'
  | 'DOCUMENT_ALREADY_POSTED'
  | 'DOCUMENT_ALREADY_REVERSED'
  | 'ALLOCATION_EXCEEDS_BALANCE'
  | 'CURRENCY_MISMATCH'

export interface LcsApiErrorBody {
  code: LcsErrorCode | string
  message: string
  request_id: string
  field_errors?: Record<string, string>
}

export interface LcsPageMeta {
  page: number
  page_size: number
  total: number
}

export interface LcsPaged<T> {
  items: T[]
  meta: LcsPageMeta
}

export interface LcsOrganization {
  id: number
  organization_code: string
  legal_name: string
  display_name: string
  default_currency_code: string
  timezone: string
  status: string
}

export interface LcsBranch {
  id: number
  organization_id: number
  branch_code: string
  name: string
  is_head_office: boolean
  status: string
}

export interface LcsComponentValue {
  template_attribute_id: number
  code: string
  label: string
  data_type: 'text' | 'number' | 'date' | 'datetime' | 'boolean' | 'reference'
  required: boolean
  resolved_instance_mode: ComponentInstanceMode
  value_text?: string
  value_number?: number
  value_date?: string
  value_boolean?: boolean
}

export interface LcsServiceComponent {
  id: number
  service_order_id: number
  template_code: string
  template_version: string
  group_code: string
  status: ComponentStatus
  sequence_no: number
  required: boolean
  values: LcsComponentValue[]
}

export interface LcsActualContainer {
  id: number
  service_order_id: number
  container_requirement_id?: number
  container_type: string
  container_number: string
  seal_serial?: string
  net_weight_kg?: number
  gross_weight_kg?: number
  status: string
}

export interface LcsJournalLine {
  account_code: string
  account_name: string
  debit_amount: number
  credit_amount: number
  description: string
}

export interface LcsJournalEntry {
  id: number
  entry_no: string
  status: JournalStatus
  source_document_id?: number
  source_document_no?: string
  period_id: number
  debit_total: number
  credit_total: number
  lines: LcsJournalLine[]
}

export const SOURCE_PERMISSIONS = [
  'organization.read',
  'organization.update',
  'branch.read',
  'branch.manage',
  'user.read',
  'user.manage',
  'role.read',
  'role.manage',
  'quotation.read',
  'quotation.create',
  'quotation.update_draft',
  'quotation.send',
  'quotation.accept',
  'quotation.convert',
  'service_order.read',
  'service_order.create',
  'service_order.update',
  'service_order.complete',
  'service_charge.create',
  'service_charge.issue',
  'service_charge.convert_to_invoice',
  'financial_document.read',
  'financial_document.create',
  'financial_document.update_draft',
  'financial_document.post',
  'financial_document.reverse',
  'financial_document.allocate',
  'journal_entry.read',
  'journal_entry.create',
  'journal_entry.post',
  'accounting_period.read',
  'accounting_period.close',
  'chart_of_accounts.manage',
  'customs_credential.retrieve',
  'attachment.read',
  'attachment.upload',
  'attachment.delete',
  'audit_log.read',
  'report.read',
] as const

export type SourcePermission = typeof SOURCE_PERMISSIONS[number]

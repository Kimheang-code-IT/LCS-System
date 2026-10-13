export type QuotationRevisionStatus =
  | 'DRAFT'
  | 'SENT'
  | 'ACCEPTED'
  | 'CONVERTED'
  | 'REJECTED'
  | 'SUPERSEDED'
  | 'EXPIRED'
  | 'CANCELLED'

export type ServiceOrderStatus = 'ACTIVE' | 'INACTIVE' | 'FINISHED'

export type ServiceChargeStatus = 'DRAFT' | 'ISSUED'

export type FinancialDocumentStatus = 'DRAFT' | 'POSTED' | 'REVERSED' | 'CANCELLED'

export type ComponentInstanceMode = 'SINGLE' | 'REPEATABLE'
export type ComponentInstanceModeOverride = 'INHERIT' | ComponentInstanceMode

export type LcsErrorCode =
  | 'AUTH_REQUIRED'
  | 'ACCESS_DENIED'
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

export const SOURCE_PERMISSIONS = [
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
  'service_order_config.view',
  'service_order_config.create',
  'service_order_config.update',
  'service_order_config.delete',
  'service_charge.read',
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
  'archive.view',
  'archive.restore',
  'archive.hard_delete',
  'report.read',
  'report.export',
  'master.reference.view',
  'master.reference.manage',
] as const

export type SourcePermission = typeof SOURCE_PERMISSIONS[number]

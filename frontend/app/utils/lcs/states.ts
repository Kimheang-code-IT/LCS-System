import type { FinancialDocumentStatus, QuotationRevisionStatus, ServiceChargeStatus, ServiceOrderStatus } from '~/types/lcs/domain'

const QUOTATION_LABEL: Record<string, QuotationRevisionStatus> = {
  Draft: 'DRAFT',
  DRAFT: 'DRAFT',
  Sent: 'SENT',
  SENT: 'SENT',
  Accepted: 'ACCEPTED',
  ACCEPTED: 'ACCEPTED',
  Converted: 'CONVERTED',
  CONVERTED: 'CONVERTED',
  Rejected: 'REJECTED',
  REJECTED: 'REJECTED',
  Superseded: 'SUPERSEDED',
  SUPERSEDED: 'SUPERSEDED',
  Expired: 'EXPIRED',
  EXPIRED: 'EXPIRED',
  Cancelled: 'CANCELLED',
  CANCELLED: 'CANCELLED',
}

const CHARGE_STATUS: Record<string, ServiceChargeStatus> = {
  Draft: 'DRAFT',
  DRAFT: 'DRAFT',
  Issued: 'ISSUED',
  ISSUED: 'ISSUED',
}

const FINANCE_STATUS: Record<string, FinancialDocumentStatus> = {
  Draft: 'DRAFT',
  Approved: 'DRAFT',
  DRAFT: 'DRAFT',
  Posted: 'POSTED',
  Sent: 'POSTED',
  Partial: 'POSTED',
  Paid: 'POSTED',
  POSTED: 'POSTED',
  Reversed: 'REVERSED',
  REVERSED: 'REVERSED',
  Cancelled: 'CANCELLED',
  CANCELLED: 'CANCELLED',
}

export function quotationDomainStatus(value: unknown): QuotationRevisionStatus {
  return QUOTATION_LABEL[String(value || '')] || 'DRAFT'
}

export function jobDomainStatus(record: Record<string, unknown>): ServiceOrderStatus {
  const value = String(record.status || record.workflowStatus || '').trim().toLowerCase()
  return value === 'inactive' || value === 'cancelled' || value === 'canceled' || value === 'closed'
    ? 'INACTIVE'
    : 'ACTIVE'
}

export function chargeDomainStatus(value: unknown): ServiceChargeStatus {
  return CHARGE_STATUS[String(value || '')] || 'DRAFT'
}

export function financeDomainStatus(value: unknown): FinancialDocumentStatus {
  return FINANCE_STATUS[String(value || '')] || 'DRAFT'
}

export function isQuotationImmutable(status: unknown) {
  const value = quotationDomainStatus(status)
  return value !== 'DRAFT'
}

export function canConvertQuotation(status: unknown) {
  return quotationDomainStatus(status) === 'ACCEPTED'
}

export function isFinancePosted(status: unknown) {
  const value = financeDomainStatus(status)
  return value === 'POSTED' || value === 'REVERSED'
}

export function isChargeIssued(status: unknown) {
  return chargeDomainStatus(status) === 'ISSUED'
}

export function isRecordReadOnly(collection: string, record: Record<string, unknown> | null | undefined) {
  if (!record) return false
  if (collection === 'quotations') return isQuotationImmutable(record.status)
  if (collection === 'debitNotes' || collection === 'journals') return isFinancePosted(record.status) || ['VOIDED', 'REVERSED'].includes(String(record.status || '').toUpperCase())
  if (collection === 'jobCharges') return isChargeIssued(record.status)
  return false
}

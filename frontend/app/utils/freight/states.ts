import type { FinancialDocumentStatus, QuotationRevisionStatus, ServiceChargeStatus, ServiceOrderStatus } from '~/types/domain'

const QUOTATION_LABEL: Record<string, QuotationRevisionStatus> = {
  Draft: 'DRAFT',
  DRAFT: 'DRAFT',
  Submitted: 'SUBMITTED',
  SUBMITTED: 'SUBMITTED',
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
  if (['finished', 'completed', 'complete'].includes(value)) return 'FINISHED'
  return value === 'inactive' || value === 'cancelled' || value === 'canceled' || value === 'closed'
    ? 'INACTIVE'
    : 'ACTIVE'
}

export function chargeDomainStatus(value: unknown): ServiceChargeStatus {
  return CHARGE_STATUS[String(value || '')] || 'DRAFT'
}

/**
 * Service Order display label. The stored lifecycle keeps `ACTIVE` (the backend
 * and reports are authoritative); the operator-facing label for a working order
 * is "Draft", matching how a quotation is presented before it is finished.
 */
export function serviceOrderStatusLabel(value: unknown): string {
  const raw = String(value ?? '').trim()
  return raw.toUpperCase() === 'ACTIVE' ? 'Draft' : raw
}

export function financeDomainStatus(value: unknown): FinancialDocumentStatus {
  return FINANCE_STATUS[String(value || '')] || 'DRAFT'
}

/**
 * A quotation is a reusable CRUD reference: it stays editable whatever status a
 * legacy workflow wrote into it. The vocabulary (Sent / Accepted / …) remains
 * display-only for historical rows.
 */
export function isQuotationImmutable(_status: unknown) {
  return false
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

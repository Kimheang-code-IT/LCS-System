/** Document Types master-data vocabularies (display values, never database keys). */
import type { FreightRecord } from '~/types/record'

export const DOCUMENT_TYPE_CATEGORIES = ['FINANCE', 'OPERATIONS', 'CUSTOMS', 'SUPPORTING'] as const

export const DOCUMENT_TYPE_MODULES = [
  'financial_documents',
  'service_order_finance',
  'posting_rules',
  'operations_documents',
  'attachments',
] as const

/** Canonical accounting behaviours; a custom type must reference one of these. */
export const DOCUMENT_TYPE_BEHAVIORS = [
  'CUSTOMER_INVOICE',
  'CREDIT_NOTE',
  'SUPPLIER_BILL',
  'SUPPLIER_CREDIT_NOTE',
  'CUSTOMER_RECEIPT',
  'SUPPLIER_PAYMENT',
  'OTHER_INCOME',
  'OTHER_EXPENSE',
  'TRANSFER',
  'ADJUSTMENT',
] as const

/** Types an operator may create from the Service Order Finance tab. */
export const FINANCE_ENTRY_BEHAVIORS = new Set<string>([
  'CUSTOMER_INVOICE',
  'CUSTOMER_RECEIPT',
  'SUPPLIER_BILL',
  'SUPPLIER_PAYMENT',
  'OTHER_INCOME',
  'OTHER_EXPENSE',
])

/** Accounting behaviours that add to revenue / cost in the Service Order summary. */
export const INCOME_BEHAVIORS = new Set<string>(['CUSTOMER_INVOICE', 'OTHER_INCOME'])
export const EXPENSE_BEHAVIORS = new Set<string>(['SUPPLIER_BILL', 'OTHER_EXPENSE'])
/** Approved credit adjustments reduce the matching side of the summary. */
export const INCOME_CREDIT_BEHAVIORS = new Set<string>(['CREDIT_NOTE'])
export const EXPENSE_CREDIT_BEHAVIORS = new Set<string>(['SUPPLIER_CREDIT_NOTE'])

/**
 * Reversed/cancelled documents stay auditable but no longer contribute to a
 * summary; settlements are excluded because they move cash, not margin.
 */
export const EXCLUDED_FINANCE_SUMMARY_STATUSES = new Set<string>(['REVERSED', 'CANCELLED'])

export function documentTypeCategoryLabel(category: string) {
  return `freight.documentTypes.categories.${String(category).toLowerCase()}`
}

export function documentTypeBehaviorLabel(behavior: string) {
  return `freight.documentTypes.behaviors.${String(behavior).toLowerCase()}`
}

export function documentTypeModuleLabel(module: string) {
  return `freight.documentTypes.modules.${module}`
}

/** Finance types a financial document may carry (category + availability). */
export function financeDocumentTypeFilter(_record: unknown, rows: FreightRecord[]) {
  return rows.filter((row) => {
    if (String(row.category || '').toUpperCase() !== 'FINANCE') return false
    const available = Array.isArray(row.availableIn) ? row.availableIn as string[] : []
    return available.includes('financial_documents')
  })
}

/** Types a posting rule may address: canonical behaviours with a posting area. */
export function postingRuleDocumentTypeFilter(_record: unknown, rows: FreightRecord[]) {
  return rows.filter((row) => {
    const code = String(row.code || '').toUpperCase()
    if (!DOCUMENT_TYPE_BEHAVIORS.includes(code as never)) return false
    const available = Array.isArray(row.availableIn) ? row.availableIn as string[] : []
    return available.includes('posting_rules')
  })
}

import type { FreightRecord } from '~/types/freight/record'

export type RemoteEndpoint = {
  path: string
  query?: Record<string, string | number>
  itemPath?: (id: string) => string
  /** Collection has a bulk DELETE accepting `{ ids }`. */
  bulkDelete?: boolean
  /** Create and update both use POST to the collection path (upsert). */
  upsertViaPost?: boolean
  /** Read-only projection (receivables/payables/profitability). */
  readOnly?: boolean
}

const reference = (collection: string): RemoteEndpoint => ({
  path: `/api/v1/${collection}`,
  itemPath: id => `/api/v1/${collection}/${id}`,
  bulkDelete: true,
})

const financial = (documentType: string): RemoteEndpoint => ({
  path: '/api/v1/financial-documents',
  query: { document_type: documentType },
  itemPath: id => `/api/v1/financial-documents/${id}`,
  bulkDelete: true,
  upsertViaPost: true,
})

/** Collections the frontend store reads/writes, mapped to backend endpoints. */
export const REMOTE_ENDPOINTS: Record<string, RemoteEndpoint> = {
  quotations: {
    path: '/api/v1/quotations',
    itemPath: id => `/api/v1/quotations/${id}`,
    bulkDelete: true,
    upsertViaPost: true,
  },
  jobs: {
    path: '/api/v1/service-orders',
    itemPath: id => `/api/v1/service-orders/${id}`,
    bulkDelete: true,
  },
  jobCharges: {
    path: '/api/v1/service-charges',
    itemPath: id => `/api/v1/service-charges/${id}`,
    bulkDelete: true,
    upsertViaPost: true,
  },
  debitNotes: financial('CUSTOMER_INVOICE'),
  customerPayments: financial('CUSTOMER_RECEIPT'),
  supplierCosts: financial('SUPPLIER_BILL'),
  supplierPayments: financial('SUPPLIER_PAYMENT'),
  journals: {
    path: '/api/v1/journal-entries',
    itemPath: id => `/api/v1/journal-entries/${id}`,
  },
  auditLogs: { path: '/api/v1/audit-events', readOnly: true },
  receivables: { path: '/api/v1/receivables', readOnly: true },
  payables: { path: '/api/v1/payables', readOnly: true },
  profitability: { path: '/api/v1/profitability', readOnly: true },

  organizations: reference('organizations'),
  branches: reference('branches'),
  users: reference('users'),
  roles: reference('roles'),
  businessParties: reference('businessParties'),
  places: reference('places'),
  tradeDirections: reference('tradeDirections'),
  containerTypes: reference('containerTypes'),
  transportTypes: reference('transportTypes'),
  transportAssets: reference('transportAssets'),
  feeTypes: reference('feeTypes'),
  componentGroups: reference('componentGroups'),
  componentTemplates: reference('componentTemplates'),
  tradeDirectionComponents: reference('tradeDirectionComponents'),
  postingRules: reference('postingRules'),
  chartOfAccounts: reference('chartOfAccounts'),
  financialAccounts: reference('financialAccounts'),
  accountingPeriods: {
    path: '/api/v1/accounting-periods',
    itemPath: id => `/api/v1/accounting-periods/${id}`,
    readOnly: false,
  },
  documentSequences: { path: '/api/v1/document-sequences', upsertViaPost: true },

  companies: reference('companies'),
  shipments: reference('shipments'),
  customs: reference('customs'),
  documents: reference('documents'),
  deliveries: reference('deliveries'),
  cashAccounts: { path: '/api/v1/financial-accounts', readOnly: true },
}

/** Collections derived from the service-order payload (embedded in `data`). */
export const JOB_DERIVED_COLLECTIONS = ['containerRequirements', 'actualContainers', 'serviceComponents']

export function endpointFor(collection: string): RemoteEndpoint | null {
  return REMOTE_ENDPOINTS[collection] || null
}

export function normalizeItems(data: unknown): FreightRecord[] {
  if (Array.isArray(data)) return data as FreightRecord[]
  if (data && typeof data === 'object') {
    const items = (data as { items?: unknown }).items
    if (Array.isArray(items)) return items as FreightRecord[]
  }
  return []
}

/** Drop client-only meta keys before sending a record to the API. */
export function stripRecord(record: Record<string, unknown>): Record<string, unknown> {
  const output: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(record)) {
    if (key.startsWith('_')) continue
    output[key] = value
  }
  return output
}

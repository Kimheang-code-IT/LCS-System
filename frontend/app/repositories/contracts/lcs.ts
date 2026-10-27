import type { FreightRecord } from '~/types/record'
import type { LcsPaged } from '~/types/domain'

export type LcsListQuery = {
  q?: string
  page?: number
  page_size?: number
  status?: string
}

export type CreateRecordInput = Record<string, unknown>

export interface QuotationRepository {
  list: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
  get: (id: string) => Promise<FreightRecord>
  create: (input: CreateRecordInput) => Promise<FreightRecord>
  saveDraft: (record: FreightRecord) => Promise<FreightRecord>
  send: (revisionId: string, idempotencyKey: string) => Promise<FreightRecord>
  accept: (revisionId: string, idempotencyKey: string) => Promise<FreightRecord>
  reject: (revisionId: string, reason: string, idempotencyKey: string) => Promise<FreightRecord>
  cancel: (revisionId: string, reason: string, idempotencyKey: string) => Promise<FreightRecord>
  createRevision: (quotationId: string) => Promise<FreightRecord>
  createFromServiceOrder: (serviceOrderId: string) => Promise<FreightRecord>
  listRevisions: (quotationId: string) => Promise<FreightRecord[]>
  submit: (revisionId: string, idempotencyKey: string) => Promise<FreightRecord>
  convert: (revisionId: string, idempotencyKey: string) => Promise<FreightRecord>
}

export interface JobRepository {
  list: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
  get: (id: string) => Promise<FreightRecord>
  save: (record: FreightRecord) => Promise<FreightRecord>
  /** Create a container, or update the prepared row when `payload.id` is sent. */
  addActualContainer: (serviceOrderId: string, payload: Record<string, unknown>) => Promise<FreightRecord>
  deleteActualContainers: (serviceOrderId: string, ids: string[]) => Promise<{ removed: number }>
  finish: (id: string, idempotencyKey: string) => Promise<FreightRecord>
}

export interface ServiceChargeRepository {
  list: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
  get: (id: string) => Promise<FreightRecord>
  create: (input: CreateRecordInput) => Promise<FreightRecord>
  saveDraft: (record: FreightRecord) => Promise<FreightRecord>
  issue: (chargeId: string, idempotencyKey: string) => Promise<FreightRecord>
  createFinanceInvoice: (chargeId: string, idempotencyKey: string) => Promise<FreightRecord>
  /** Bulk delete. The backend only removes charges still in DRAFT. */
  delete: (ids: string[]) => Promise<{ removed: number }>
  listForOrder: (orderId: string) => Promise<FreightRecord[]>
  createForOrder: (orderId: string, input: CreateRecordInput) => Promise<FreightRecord>
  getOrderInvoice: (orderId: string) => Promise<FreightRecord | null>
  createOrderInvoice: (orderId: string, idempotencyKey: string) => Promise<FreightRecord>
}

export interface FinanceRepository {
  listDocuments: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
  getDocument: (id: string) => Promise<FreightRecord>
  createDocument: (input: CreateRecordInput) => Promise<FreightRecord>
  saveDraft: (record: FreightRecord) => Promise<FreightRecord>
  post: (documentId: string, idempotencyKey: string) => Promise<FreightRecord>
  reverse: (documentId: string, reason: string, idempotencyKey: string) => Promise<FreightRecord>
  allocate: (paymentId: string, targetDocumentId: string, amount: number, idempotencyKey: string) => Promise<FreightRecord>
  listJournals: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
  getJournal: (id: string) => Promise<FreightRecord>
  createJournal: (input: CreateRecordInput) => Promise<FreightRecord>
  saveJournal: (record: FreightRecord) => Promise<FreightRecord>
  postJournal: (journalId: string, idempotencyKey: string) => Promise<FreightRecord>
  listPeriods: () => Promise<FreightRecord[]>
  closePeriod: (periodId: string, idempotencyKey: string) => Promise<FreightRecord>
}

export interface AuditRepository {
  list: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
}

export interface UserAdminRepository {
  /**
   * Set another account's password. The request sends either a password the
   * administrator typed or one this module generated; the server hashes it and
   * never returns it.
   *
   * ``mustChangePassword`` defaults to true on the server, so a temporary
   * password cannot be kept in use.
   */
  setPassword: (
    userId: string,
    password: string,
    options?: { mustChangePassword?: boolean },
  ) => Promise<FreightRecord>
}

export interface AttachmentRepository {
  listForRecord: (module: string, recordNo: string) => Promise<FreightRecord[]>
  presign: (fileName: string) => Promise<{ upload_url: string, file_name: string }>
  upload: (file: File, context?: { module: string, recordNo: string, note?: string }) => Promise<FreightRecord>
  updateNote: (id: string, note: string) => Promise<FreightRecord>
  remove: (ids: string[]) => Promise<number>
}

export interface UiSchemaRepository {
  getPageSchema: (page: string) => Promise<FreightRecord | null>
}

export type DashboardSummary = {
  generatedAt: string
  summary: {
    openOrders: number
    inProgressOrders: number
    onHoldOrders: number
    awaitingClosure: number
    receivables: number
    overdueReceivableCount: number
    payables: number
    cashBankBalance: number
    revenue: number
    expense: number
  }
  charts: {
    revenueExpense: Array<{ period: string, revenue: number, expense: number }>
    ordersByStatus: Array<{ status: string, count: number }>
    receivablesAging: Array<{ key: string, amount: number }>
    payablesAging: Array<{ key: string, amount: number }>
  }
  options: {
    customers: string[]
  }
}

export interface ReportsRepository {
  dashboard: (granularity?: 'day' | 'month' | 'year') => Promise<DashboardSummary>
  receivables: () => Promise<FreightRecord[]>
  payables: () => Promise<FreightRecord[]>
  profitability: () => Promise<FreightRecord[]>
  ledgerLines: () => Promise<FreightRecord[]>
}

export type { CreateRecordInput as LcsCreateRecordInput }

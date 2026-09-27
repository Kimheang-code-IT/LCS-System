import type { FreightRecord } from '~/types/freight/record'
import type { LcsPaged } from '~/types/lcs/domain'
import type { ComponentInstanceMode } from '~/utils/freight/component-instance-mode'

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
  createRevision: (quotationId: string) => Promise<FreightRecord>
  submit: (revisionId: string, idempotencyKey: string) => Promise<FreightRecord>
  convert: (revisionId: string, idempotencyKey: string) => Promise<FreightRecord>
}

export interface JobRepository {
  list: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
  get: (id: string) => Promise<FreightRecord>
  save: (record: FreightRecord) => Promise<FreightRecord>
  addActualContainer: (serviceOrderId: string, payload: Record<string, unknown>) => Promise<FreightRecord>
}

export type EnsureServiceComponentPayload = {
  jobNo: string
  serviceOrderId?: string
  groupCode: string
  templateCode: string
  templateVersion?: string
  latestTemplateVersion?: string
  required?: boolean
  repeatable?: boolean
  instanceMode?: ComponentInstanceMode
  maximumInstances?: number
  values?: unknown[]
  forceNew?: boolean
}

export interface ComponentRepository {
  listForJob: (jobNo: string) => Promise<FreightRecord[]>
  complete: (componentId: string, idempotencyKey: string) => Promise<FreightRecord>
  saveValues: (componentId: string, values: unknown[]) => Promise<FreightRecord>
  remove: (componentId: string, idempotencyKey: string) => Promise<FreightRecord>
  ensureForJob: (jobNo: string, payload: EnsureServiceComponentPayload) => Promise<FreightRecord>
}

export interface ServiceChargeRepository {
  list: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
  get: (id: string) => Promise<FreightRecord>
  create: (input: CreateRecordInput) => Promise<FreightRecord>
  saveDraft: (record: FreightRecord) => Promise<FreightRecord>
  issue: (chargeId: string, idempotencyKey: string) => Promise<FreightRecord>
  createFinanceInvoice: (chargeId: string, idempotencyKey: string) => Promise<FreightRecord>
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
  listPeriods: () => Promise<FreightRecord[]>
  closePeriod: (periodId: string, idempotencyKey: string) => Promise<FreightRecord>
}

export interface AuditRepository {
  list: (query?: LcsListQuery) => Promise<LcsPaged<FreightRecord>>
}

export interface AttachmentRepository {
  listForRecord: (module: string, recordNo: string) => Promise<FreightRecord[]>
  presign: (fileName: string) => Promise<{ upload_url: string, file_name: string }>
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
    revenueExpense: Array<{ month: string, revenue: number, expense: number }>
    ordersByStatus: Array<{ status: string, count: number }>
    receivablesAging: Array<{ key: string, amount: number }>
    payablesAging: Array<{ key: string, amount: number }>
  }
  options: {
    customers: string[]
  }
}

export interface ReportsRepository {
  dashboard: () => Promise<DashboardSummary>
  receivables: () => Promise<FreightRecord[]>
  payables: () => Promise<FreightRecord[]>
  profitability: () => Promise<FreightRecord[]>
}

export type { CreateRecordInput as LcsCreateRecordInput }

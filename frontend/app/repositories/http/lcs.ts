import type {
  AttachmentRepository,
  AuditRepository,
  ComponentRepository,
  FinanceRepository,
  JobRepository,
  QuotationRepository,
  ServiceChargeRepository,
  UiSchemaRepository,
} from '~/repositories/contracts/lcs'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { unwrapApiData } from '~/repositories/http/response'
import type { ApiResponse } from '~/types/docetra/common'
import type { FreightRecord } from '~/types/freight/record'
import type { LcsPaged } from '~/types/lcs/domain'
import { stripOfficialNumberFields } from '~/utils/lcs/sequences'

function withIdempotency(key: string) {
  return { headers: { 'Idempotency-Key': key } }
}

function asPaged(data: FreightRecord[] | LcsPaged<FreightRecord>): LcsPaged<FreightRecord> {
  if (Array.isArray(data)) {
    return { items: data, meta: { page: 1, page_size: data.length, total: data.length } }
  }
  return data
}

export function createHttpQuotationRepository(): QuotationRepository {
  const api = useApi()
  return {
    list: async query => asPaged(unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.QUOTATIONS, { query }))),
    get: async id => unwrapApiData(await api.get<ApiResponse<FreightRecord>>(`${ApiV1Endpoints.QUOTATIONS}/${id}`)),
    create: async input =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.QUOTATIONS, stripOfficialNumberFields(input, 'quotations'))),
    saveDraft: async record => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.QUOTATIONS, record)),
    send: async (revisionId, key) => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.QUOTATION_SEND(revisionId), {}, withIdempotency(key))),
    accept: async (revisionId, key) => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.QUOTATION_ACCEPT(revisionId), {}, withIdempotency(key))),
    createRevision: async quotationId => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.QUOTATION_REVISIONS(quotationId), {})),
    submit: async (revisionId, key) => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.QUOTATION_SUBMIT(revisionId), {}, withIdempotency(key))),
    convert: async (revisionId, key) => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.QUOTATION_CONVERT(revisionId), {}, withIdempotency(key))),
  }
}

export function createHttpJobRepository(): JobRepository {
  const api = useApi()
  return {
    list: async query => asPaged(unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.SERVICE_ORDERS, { query }))),
    get: async id => unwrapApiData(await api.get<ApiResponse<FreightRecord>>(ApiV1Endpoints.SERVICE_ORDER(id))),
    save: async record => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.SERVICE_ORDER(record.id), record)),
    addActualContainer: async (serviceOrderId, payload) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.SERVICE_ORDER_CONTAINERS(serviceOrderId), payload)),
  }
}

export function createHttpComponentRepository(): ComponentRepository {
  const api = useApi()
  return {
    listForJob: async (jobNo) => {
      const data = unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.SERVICE_ORDER_COMPONENTS(jobNo)))
      return Array.isArray(data) ? data : []
    },
    complete: async (componentId, key) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.COMPONENT_COMPLETE(componentId), {}, withIdempotency(key))),
    saveValues: async (componentId, values) =>
      unwrapApiData(await api.put<ApiResponse<FreightRecord>>(ApiV1Endpoints.COMPONENT_VALUES(componentId), { values })),
    remove: async (componentId, key) =>
      unwrapApiData(await api.delete<ApiResponse<FreightRecord>>(ApiV1Endpoints.COMPONENT(componentId), withIdempotency(key))),
    ensureForJob: async (jobNo, payload) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.SERVICE_ORDER_COMPONENTS(jobNo), payload)),
  }
}

export function createHttpServiceChargeRepository(): ServiceChargeRepository {
  const api = useApi()
  return {
    list: async query => asPaged(unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.SERVICE_CHARGES, { query }))),
    get: async id => unwrapApiData(await api.get<ApiResponse<FreightRecord>>(`${ApiV1Endpoints.SERVICE_CHARGES}/${id}`)),
    create: async input =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.SERVICE_CHARGES, stripOfficialNumberFields(input, 'jobCharges'))),
    saveDraft: async record =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.SERVICE_ORDER_CHARGES(String(record.jobNo || record.id)), record)),
    issue: async (chargeId, key) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.CHARGE_ISSUE(chargeId), {}, withIdempotency(key))),
    createFinanceInvoice: async (chargeId, key) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.CHARGE_CREATE_INVOICE(chargeId), {}, withIdempotency(key))),
  }
}

export function createHttpFinanceRepository(): FinanceRepository {
  const api = useApi()
  return {
    listDocuments: async query => asPaged(unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.FINANCIAL_DOCUMENTS, { query }))),
    getDocument: async id => unwrapApiData(await api.get<ApiResponse<FreightRecord>>(`${ApiV1Endpoints.FINANCIAL_DOCUMENTS}/${id}`)),
    createDocument: async input =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.FINANCIAL_DOCUMENTS, stripOfficialNumberFields(input, 'debitNotes'))),
    saveDraft: async record => unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.FINANCIAL_DOCUMENTS, record)),
    post: async (documentId, key) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.FINANCIAL_POST(documentId), {}, withIdempotency(key))),
    reverse: async (documentId, reason, key) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.FINANCIAL_REVERSE(documentId), { reason }, withIdempotency(key))),
    allocate: async (paymentId, targetDocumentId, amount, key) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.FINANCIAL_ALLOCATE(paymentId), { target_document_id: targetDocumentId, amount }, withIdempotency(key))),
    listJournals: async query => asPaged(unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.JOURNALS, { query }))),
    getJournal: async id => unwrapApiData(await api.get<ApiResponse<FreightRecord>>(`${ApiV1Endpoints.JOURNALS}/${id}`)),
    createJournal: async input =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.JOURNALS, stripOfficialNumberFields(input, 'journals'))),
    saveJournal: async record =>
      unwrapApiData(await api.put<ApiResponse<FreightRecord>>(`${ApiV1Endpoints.JOURNALS}/${record.id}`, record)),
    listPeriods: async () => unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>('/api/v1/accounting-periods')),
    closePeriod: async (periodId, key) =>
      unwrapApiData(await api.post<ApiResponse<FreightRecord>>(ApiV1Endpoints.PERIOD_CLOSE(periodId), {}, withIdempotency(key))),
  }
}

export function createHttpAuditRepository(): AuditRepository {
  const api = useApi()
  return {
    list: async query => asPaged(unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.AUDIT_EVENTS, { query }))),
  }
}

export function createHttpAttachmentRepository(): AttachmentRepository {
  const api = useApi()
  return {
    listForRecord: async (module, recordNo) =>
      unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.ATTACHMENTS, { query: { module, record_no: recordNo } })),
    presign: async fileName =>
      unwrapApiData(await api.post<ApiResponse<{ upload_url: string, file_name: string }>>(ApiV1Endpoints.ATTACHMENTS_PRESIGN, { file_name: fileName })),
  }
}

export function createHttpUiSchemaRepository(): UiSchemaRepository {
  const api = useApi()
  return {
    getPageSchema: async (page) => {
      try {
        return unwrapApiData(await api.get<ApiResponse<FreightRecord>>(ApiV1Endpoints.UI_SCHEMA(page)))
      }
      catch {
        return null
      }
    },
  }
}

export function createHttpReportsRepository(): import('~/repositories/contracts/lcs').ReportsRepository {
  const api = useApi()
  return {
    dashboard: async () => unwrapApiData(await api.get<ApiResponse<import('~/repositories/contracts/lcs').DashboardSummary>>(ApiV1Endpoints.REPORTS_DASHBOARD)),
    receivables: async () => unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.REPORTS_RECEIVABLES)),
    payables: async () => unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.REPORTS_PAYABLES)),
    profitability: async () => unwrapApiData(await api.get<ApiResponse<FreightRecord[]>>(ApiV1Endpoints.REPORTS_PROFITABILITY)),
  }
}

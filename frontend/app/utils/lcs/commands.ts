import type { FreightRecord } from '~/types/freight/record'
import type { LcsSession } from '~/types/lcs/session'
import type { SourcePermission } from '~/types/lcs/domain'
import { domainError } from '~/utils/lcs/errors'
import {
  canConvertQuotation,
  chargeDomainStatus,
  financeDomainStatus,
  isChargeIssued,
  isFinancePosted,
  isQuotationImmutable,
  quotationDomainStatus,
} from '~/utils/lcs/states'
import { assertPermission, assertRecordAccess, stampTenant } from '~/utils/lcs/scope'
import { serviceOrderContainersFromQuotation } from '~/utils/freight/job-containers'
import { quotationOperationalFields } from '~/utils/freight/quotation-conversion'
import { missingRequiredValues } from '~/utils/freight/job-task-fields'
import {
  normalizeComponentInstanceMode,
  resolveComponentInstanceMode,
  type ComponentInstanceMode,
} from '~/utils/freight/component-instance-mode'

export type LcsCollections = Record<string, FreightRecord[]>

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function newId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

function rows(db: LcsCollections, collection: string) {
  return db[collection] || []
}

function replace(db: LcsCollections, collection: string, record: FreightRecord) {
  const list = [...rows(db, collection)]
  const index = list.findIndex(row => row.id === record.id)
  const next: FreightRecord = { ...record, updatedAt: new Date().toISOString() }
  if (index >= 0) list[index] = next
  else list.unshift({ ...next, createdAt: next.createdAt || new Date().toISOString() })
  db[collection] = list
  return next
}

function findById(db: LcsCollections, collection: string, id: string) {
  return rows(db, collection).find(row => row.id === id) || null
}

function rememberIdempotent(
  db: LcsCollections,
  key: string,
  command: string,
  entityId: string,
  result: FreightRecord,
) {
  const list = rows(db, 'idempotency')
  const existing = list.find(row => row.id === key)
  if (existing) return existing.result as FreightRecord
  db.idempotency = [
    { id: key, command, entityId, result: clone(result), createdAt: new Date().toISOString() },
    ...list,
  ]
  return result
}

function existingIdempotent(db: LcsCollections, key: string) {
  const hit = rows(db, 'idempotency').find(row => row.id === key)
  return hit ? hit.result as FreightRecord : null
}

function audit(db: LcsCollections, session: LcsSession, action: string, module: string, recordNo: string, remark = '') {
  replace(db, 'auditLogs', stampTenant({
    id: newId('log'),
    occurredAt: new Date().toISOString().slice(0, 19),
    user: session.userName,
    action,
    module,
    recordNo,
    remark,
  } as FreightRecord, session))
}

function periodForDate(db: LcsCollections, session: LcsSession, dateValue: unknown) {
  const day = String(dateValue || '').slice(0, 10)
  return rows(db, 'accountingPeriods').find((period) => {
    if (Number(period.organizationId) !== session.organizationId) return false
    const start = String(period.startDate || '')
    const end = String(period.endDate || '')
    return Boolean(day) && day >= start && day <= end
  }) || null
}

function assertPeriodOpen(period: FreightRecord | null) {
  if (!period) {
    throw domainError('PERIOD_CLOSED', 'No open accounting period covers this document date.')
  }
  if (String(period.status) === 'CLOSED') {
    throw domainError('PERIOD_CLOSED', 'The accounting period is closed.')
  }
}

function journalLinesForInvoice(total: number, documentNo: string) {
  const amount = Number(total.toFixed(2))
  return [
    { account_code: '1100', account_name: 'Accounts Receivable', debit_amount: amount, credit_amount: 0, description: documentNo },
    { account_code: '4000', account_name: 'Freight Revenue', debit_amount: 0, credit_amount: amount, description: documentNo },
  ]
}

function assertBalanced(lines: Array<{ debit_amount: number, credit_amount: number }>) {
  const debit = lines.reduce((sum, line) => sum + Number(line.debit_amount || 0), 0)
  const credit = lines.reduce((sum, line) => sum + Number(line.credit_amount || 0), 0)
  if (Number(debit.toFixed(2)) !== Number(credit.toFixed(2))) {
    throw domainError('JOURNAL_UNBALANCED', 'Journal debit and credit totals must match.')
  }
  return { debit, credit }
}

export function assertMutableRecord(collection: string, existing: FreightRecord | null, next?: FreightRecord) {
  if (!existing) return
  if (collection === 'quotations' && isQuotationImmutable(existing.status) && next) {
    const allowed = ['status', 'updatedAt', 'convertedJobNo', 'supersededBy']
    const changed = Object.keys(next).filter((key) => {
      if (allowed.includes(key) || key === 'id') return false
      return JSON.stringify(existing[key]) !== JSON.stringify(next[key])
    })
    const statusChange = quotationDomainStatus(next.status)
    if (changed.length && statusChange === quotationDomainStatus(existing.status)) {
      throw domainError('INVALID_STATE_TRANSITION', 'Sent and later quotation revisions are read-only. Create a new revision to change terms.')
    }
  }
  if (collection === 'debitNotes' && isFinancePosted(existing.status)) {
    throw domainError('DOCUMENT_ALREADY_POSTED', 'Posted financial documents are read-only. Use reversal to correct them.')
  }
  if (collection === 'journals' && ['POSTED', 'REVERSED', 'VOIDED'].includes(String(existing.status))) {
    throw domainError('DOCUMENT_ALREADY_POSTED', 'Posted journals are read-only.')
  }
  if (collection === 'jobCharges' && isChargeIssued(existing.status) && next && chargeDomainStatus(next.status) === 'ISSUED') {
    const locked = ['amount', 'unitPrice', 'quantity', 'chargeType', 'currency']
    if (locked.some(key => JSON.stringify(existing[key]) !== JSON.stringify(next[key]))) {
      throw domainError('INVALID_STATE_TRANSITION', 'Issued service charges cannot change commercial amounts.')
    }
  }
}

export function sendQuotationRevision(
  db: LcsCollections,
  session: LcsSession,
  revisionId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'quotation.send')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const quotation = findById(db, 'quotations', revisionId)
  assertRecordAccess(quotation, session)
  const status = quotationDomainStatus(quotation!.status)
  if (status !== 'DRAFT') {
    throw domainError('INVALID_STATE_TRANSITION', 'Only draft quotations can be sent.')
  }
  const saved = replace(db, 'quotations', { ...quotation!, status: 'Sent' })
  audit(db, session, 'Sent quotation', 'Quotations', String(saved.quotationNo || saved.id))
  return rememberIdempotent(db, idempotencyKey, 'quotation.send', revisionId, saved)
}

export function acceptQuotationRevision(
  db: LcsCollections,
  session: LcsSession,
  revisionId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'quotation.accept')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const quotation = findById(db, 'quotations', revisionId)
  assertRecordAccess(quotation, session)
  if (quotationDomainStatus(quotation!.status) !== 'SENT') {
    throw domainError('INVALID_STATE_TRANSITION', 'Only sent quotations can be accepted.')
  }
  const saved = replace(db, 'quotations', { ...quotation!, status: 'Accepted' })
  audit(db, session, 'Accepted quotation', 'Quotations', String(saved.quotationNo || saved.id))
  return rememberIdempotent(db, idempotencyKey, 'quotation.accept', revisionId, saved)
}

export function createQuotationRevision(
  db: LcsCollections,
  session: LcsSession,
  quotationId: string,
) {
  assertPermission(session, 'quotation.create')
  const source = findById(db, 'quotations', quotationId)
  assertRecordAccess(source, session)
  if (quotationDomainStatus(source!.status) !== 'SENT') {
    throw domainError('INVALID_STATE_TRANSITION', 'Create revision is only available for sent quotations.')
  }
  const revisionNo = Number(source!.revisionNo || 1) + 1
  replace(db, 'quotations', { ...source!, status: 'Superseded', supersededBy: undefined })
  const copy = clone(source!)
  const created = replace(db, 'quotations', stampTenant({
    ...copy,
    id: newId('qt'),
    quotationNo: `${String(source!.quotationNo)}-R${revisionNo}`,
    status: 'Draft',
    revisionNo,
    quotationId: source!.quotationId || source!.id,
    supersededFrom: source!.id,
  } as FreightRecord, session, recordBranchFallback(source!)))
  replace(db, 'quotations', { ...findById(db, 'quotations', source!.id)!, supersededBy: created.id })
  audit(db, session, 'Created quotation revision', 'Quotations', String(created.quotationNo))
  return created
}

function recordBranchFallback(record: FreightRecord) {
  return Number(record.branchId || 0) || undefined
}

export function submitQuotationRevision(
  db: LcsCollections,
  session: LcsSession,
  revisionId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'quotation.convert')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const quotation = findById(db, 'quotations', revisionId)
  assertRecordAccess(quotation, session)
  if (quotationDomainStatus(quotation!.status) !== 'DRAFT') {
    throw domainError('INVALID_STATE_TRANSITION', 'Only draft quotations can be submitted.')
  }
  replace(db, 'quotations', { ...quotation!, status: 'Accepted' })
  const job = convertQuotationRevision(db, session, revisionId, `${idempotencyKey}:convert`)
  audit(db, session, 'Submitted quotation', 'Quotations', String(quotation!.quotationNo || quotation!.id), String(job.jobNo || job.id))
  return rememberIdempotent(db, idempotencyKey, 'quotation.submit', revisionId, job)
}

export function convertQuotationRevision(
  db: LcsCollections,
  session: LcsSession,
  revisionId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'quotation.convert')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const quotation = findById(db, 'quotations', revisionId)
  assertRecordAccess(quotation, session)
  if (quotationDomainStatus(quotation!.status) === 'CONVERTED') {
    throw domainError('DUPLICATE_CONVERSION', 'This quotation revision has already been converted.')
  }
  if (!canConvertQuotation(quotation!.status)) {
    throw domainError('INVALID_STATE_TRANSITION', 'Only an accepted quotation revision can be converted to a job.')
  }
  const existingJob = rows(db, 'jobs').find(job =>
    String(job.quotationNo || '') === String(quotation!.quotationNo || '')
    && Number(job.organizationId) === session.organizationId,
  )
  if (existingJob) {
    throw domainError('DUPLICATE_CONVERSION', 'This quotation revision has already been converted.')
  }
  const direction = String(quotation!.direction || 'Import') === 'Export' ? 'EX' : 'IM'
  const branch = recordBranchFallback(quotation!)
  const operationalFields = quotationOperationalFields(quotation!)
  const created = replace(db, 'jobs', stampTenant({
    id: newId('job'),
    jobNo: `LCS-${direction}-${Date.now().toString().slice(-6)}`,
    date: new Date().toISOString().slice(0, 10),
    customer: quotation!.customer,
    direction: quotation!.direction,
    quotationNo: quotation!.quotationNo,
    ...operationalFields,
    currency: quotation!.currency || 'USD',
    branchName: quotation!.branchName,
    status: 'Job Created',
    workflowStatus: 'OPEN',
    contact: quotation!.attention,
    description: quotation!.description,
    remarks: quotation!.notes,
    sourceQuotationId: quotation!.id,
    templateVersion: '2026.08',
    amount: quotation!.total || quotation!.amount,
  } as FreightRecord, session, branch))
  const copied = serviceOrderContainersFromQuotation(quotation!, created)
  for (const row of copied.requirements) {
    replace(db, 'containerRequirements', stampTenant({
      ...row,
      id: String(row.id || ''),
      jobNo: created.jobNo,
      serviceOrderId: created.id,
    } as unknown as FreightRecord, session, branch))
  }
  const job = replace(db, 'jobs', {
    ...created,
    containerType: copied.requirements[0] ? String(copied.requirements[0].containerType) : created.containerType,
    containerRequirements: copied.requirements,
    actualContainers: copied.actuals,
    containerPayments: copied.payments,
  })
  replace(db, 'quotations', { ...quotation!, status: 'Converted', convertedJobNo: job.jobNo })
  audit(db, session, 'Converted quotation to job', 'Quotations', String(quotation!.quotationNo), String(job.jobNo))
  return rememberIdempotent(db, idempotencyKey, 'quotation.convert', revisionId, job)
}

export function issueServiceCharge(
  db: LcsCollections,
  session: LcsSession,
  chargeId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'service_charge.issue')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const charge = findById(db, 'jobCharges', chargeId)
  assertRecordAccess(charge, session)
  if (chargeDomainStatus(charge!.status) !== 'DRAFT') {
    throw domainError('INVALID_STATE_TRANSITION', 'Only draft service charges can be issued.')
  }
  const saved = replace(db, 'jobCharges', {
    ...charge!,
    status: 'Issued',
    journalId: '',
    posted: false,
  })
  audit(db, session, 'Issued service charge', 'Service Charges', String(saved.id), 'Issuing this service charge does not post accounting.')
  return rememberIdempotent(db, idempotencyKey, 'charge.issue', chargeId, saved)
}

export function createFinanceInvoiceFromCharge(
  db: LcsCollections,
  session: LcsSession,
  chargeId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'service_charge.convert_to_invoice')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const charge = findById(db, 'jobCharges', chargeId)
  assertRecordAccess(charge, session)
  if (!isChargeIssued(charge!.status)) {
    throw domainError('INVALID_STATE_TRANSITION', 'Convert a service charge only after it is issued.')
  }
  if (charge!.financialDocumentId) {
    const existing = findById(db, 'debitNotes', String(charge!.financialDocumentId))
    if (existing) return existing
  }
  const amount = Number(charge!.amount || 0)
  const vatRate = 10
  const vat = Number((amount * vatRate / 100).toFixed(2))
  const invoice = replace(db, 'debitNotes', stampTenant({
    id: newId('dn'),
    debitNoteNo: `DN-${Date.now().toString().slice(-6)}`,
    date: new Date().toISOString().slice(0, 10),
    customer: charge!.customer || '',
    jobNo: charge!.jobNo,
    amount,
    vatRate,
    vat,
    total: Number((amount + vat).toFixed(2)),
    status: 'Draft',
    documentType: 'CUSTOMER_INVOICE',
    sourceChargeId: charge!.id,
    journalId: '',
    periodId: periodForDate(db, session, new Date().toISOString())?.id || 'per-002',
  } as FreightRecord, session, recordBranchFallback(charge!)))
  replace(db, 'jobCharges', { ...charge!, financialDocumentId: invoice.id, invoiceNo: invoice.debitNoteNo })
  audit(db, session, 'Created draft customer invoice', 'Finance', String(invoice.debitNoteNo), 'Conversion creates a draft invoice only.')
  return rememberIdempotent(db, idempotencyKey, 'charge.create-invoice', chargeId, invoice)
}

export function postFinancialDocument(
  db: LcsCollections,
  session: LcsSession,
  documentId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'financial_document.post')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const document = findById(db, 'debitNotes', documentId)
  assertRecordAccess(document, session)
  if (financeDomainStatus(document!.status) !== 'DRAFT') {
    throw domainError('DOCUMENT_ALREADY_POSTED', 'Only draft financial documents can be posted.')
  }
  const period = findById(db, 'accountingPeriods', String(document!.periodId || '')) || periodForDate(db, session, document!.date)
  assertPeriodOpen(period)
  const total = Number(document!.total || document!.amount || 0)
  const lines = journalLinesForInvoice(total, String(document!.debitNoteNo))
  const totals = assertBalanced(lines)
  const journal = replace(db, 'journals', stampTenant({
    id: newId('je'),
    entryNo: `JE-${Date.now().toString().slice(-6)}`,
    status: 'POSTED',
    sourceDocumentId: document!.id,
    sourceDocumentNo: document!.debitNoteNo,
    periodId: period!.id,
    debitTotal: totals.debit,
    creditTotal: totals.credit,
    lines,
  } as FreightRecord, session, recordBranchFallback(document!)))
  const saved = replace(db, 'debitNotes', {
    ...document!,
    status: 'Posted',
    journalId: journal.id,
    postedAt: new Date().toISOString(),
  })
  const sourceChargeId = String(saved.sourceChargeId || '')
  if (sourceChargeId) {
    const charge = findById(db, 'jobCharges', sourceChargeId)
    if (charge) {
      replace(db, 'jobCharges', {
        ...charge,
        financialDocumentId: charge.financialDocumentId || saved.id,
        invoiceNo: charge.invoiceNo || saved.debitNoteNo,
        journalId: journal.id,
      })
    }
  }
  audit(db, session, 'Posted financial document', 'Finance', String(saved.debitNoteNo), String(journal.entryNo))
  return rememberIdempotent(db, idempotencyKey, 'finance.post', documentId, saved)
}

export function reverseFinancialDocument(
  db: LcsCollections,
  session: LcsSession,
  documentId: string,
  reason: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'financial_document.reverse')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  if (!String(reason || '').trim()) {
    throw domainError('REQUIRED_VALUE_MISSING', 'A reversal reason is required.', {
      field_errors: { reason: 'Required' },
    })
  }
  const document = findById(db, 'debitNotes', documentId)
  assertRecordAccess(document, session)
  if (financeDomainStatus(document!.status) !== 'POSTED') {
    throw domainError('INVALID_STATE_TRANSITION', 'Only posted financial documents can be reversed.')
  }
  const period = findById(db, 'accountingPeriods', String(document!.periodId || ''))
  assertPeriodOpen(period)
  const original = findById(db, 'journals', String(document!.journalId || ''))
  const sourceLines = (original?.lines as Array<{ debit_amount: number, credit_amount: number, account_code: string, account_name: string, description: string }>) || []
  const lines = sourceLines.map(line => ({
    ...line,
    debit_amount: line.credit_amount,
    credit_amount: line.debit_amount,
    description: `Reversal of ${document!.debitNoteNo}`,
  }))
  assertBalanced(lines)
  replace(db, 'journals', stampTenant({
    id: newId('je'),
    entryNo: `JE-R-${Date.now().toString().slice(-6)}`,
    status: 'REVERSED',
    sourceDocumentId: document!.id,
    sourceDocumentNo: document!.debitNoteNo,
    periodId: period!.id,
    debitTotal: Number(document!.total || 0),
    creditTotal: Number(document!.total || 0),
    lines,
  } as FreightRecord, session, recordBranchFallback(document!)))
  const saved = replace(db, 'debitNotes', {
    ...document!,
    status: 'Reversed',
    reversalReason: reason,
  })
  audit(db, session, 'Reversed financial document', 'Finance', String(saved.debitNoteNo), reason)
  return rememberIdempotent(db, idempotencyKey, 'finance.reverse', documentId, saved)
}

export function allocatePayment(
  db: LcsCollections,
  session: LcsSession,
  paymentId: string,
  targetDocumentId: string,
  amount: number,
  idempotencyKey: string,
) {
  assertPermission(session, 'financial_document.allocate')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const payment = findById(db, 'customerPayments', paymentId)
  assertRecordAccess(payment, session)
  const target = findById(db, 'debitNotes', targetDocumentId)
  assertRecordAccess(target, session)
  if (financeDomainStatus(target!.status) !== 'POSTED') {
    throw domainError('INVALID_STATE_TRANSITION', 'Payments can only be allocated to posted invoices.')
  }
  if (String(payment!.currency || 'USD') !== String(target!.currency || 'USD')) {
    throw domainError('CURRENCY_MISMATCH', 'Payment and invoice currencies must match.')
  }
  const unallocated = Number(payment!.unallocatedAmount ?? Number(payment!.received || 0) - Number(payment!.allocatedAmount || 0))
  const outstanding = Number(target!.total || target!.amount || 0) - Number(target!.allocatedAmount || 0)
  if (amount <= 0 || amount > unallocated + 0.001 || amount > outstanding + 0.001) {
    throw domainError('ALLOCATION_EXCEEDS_BALANCE', 'Allocation cannot exceed remaining payment or invoice outstanding.')
  }
  const allocation = replace(db, 'allocations', stampTenant({
    id: newId('al'),
    paymentId,
    targetDocumentId,
    amount,
    currency: payment!.currency || 'USD',
  } as FreightRecord, session, recordBranchFallback(payment!)))
  replace(db, 'customerPayments', {
    ...payment!,
    allocatedAmount: Number((Number(payment!.allocatedAmount || 0) + amount).toFixed(2)),
    unallocatedAmount: Number((unallocated - amount).toFixed(2)),
  })
  replace(db, 'debitNotes', {
    ...target!,
    allocatedAmount: Number((Number(target!.allocatedAmount || 0) + amount).toFixed(2)),
  })
  audit(db, session, 'Allocated payment', 'Finance', String(payment!.paymentNo), `${amount} → ${target!.debitNoteNo}`)
  return rememberIdempotent(db, idempotencyKey, 'finance.allocate', paymentId, allocation)
}

export function completeServiceComponent(
  db: LcsCollections,
  session: LcsSession,
  componentId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'service_order.update')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const component = findById(db, 'serviceComponents', componentId)
  assertRecordAccess(component, session)
  const values = Array.isArray(component!.values) ? component!.values as Array<Record<string, unknown>> : []
  const missing = missingRequiredValues(values)
  if (missing.length) {
    throw domainError('REQUIRED_VALUE_MISSING', 'Required component values must be completed before completion.', {
      field_errors: Object.fromEntries(missing.map(value => [String(value.code), 'Required'])),
    })
  }
  const saved = replace(db, 'serviceComponents', {
    ...component!,
    status: 'COMPLETED',
    templateVersion: component!.templateVersion,
  })
  audit(db, session, 'Completed service component', 'Jobs', String(saved.templateCode), String(saved.templateVersion))
  return rememberIdempotent(db, idempotencyKey, 'component.complete', componentId, saved)
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

export function ensureServiceComponent(
  db: LcsCollections,
  session: LcsSession,
  payload: EnsureServiceComponentPayload,
) {
  assertPermission(session, 'service_order.update')
  const jobNo = String(payload.jobNo || '').trim()
  const job = rows(db, 'jobs').find(row =>
    String(row.jobNo || '') === jobNo
    || String(row.id || '') === String(payload.serviceOrderId || ''),
  )
  assertRecordAccess(job, session)
  const groupCode = String(payload.groupCode || '').trim().toUpperCase()
  const existing = rows(db, 'serviceComponents').filter(row =>
    String(row.jobNo || '') === jobNo && String(row.groupCode || '').toUpperCase() === groupCode,
  )
  const template = rows(db, 'componentTemplates').find(row =>
    String(row.code || '').toUpperCase() === String(payload.templateCode || '').toUpperCase()
    || String(row.name || '').toUpperCase() === String(payload.templateCode || '').toUpperCase(),
  )
  const assignment = rows(db, 'tradeDirectionComponents').find(row =>
    String(row.tradeDirection || '').toUpperCase() === String(job!.direction || '').toUpperCase()
    && (String(row.componentTemplate || '').toUpperCase() === String(template?.name || payload.templateCode).toUpperCase()
      || String(row.componentGroup || '').toUpperCase().replace(/\s+/g, '_') === groupCode),
  )
  const instanceMode = template || assignment
    ? resolveComponentInstanceMode(assignment, template)
    : normalizeComponentInstanceMode(payload.instanceMode, payload.repeatable)
  if (instanceMode === 'SINGLE' && existing.length) return existing[0] as FreightRecord

  const configuredMaximum = Number(assignment?.maximumInstances ?? template?.maximumInstances ?? payload.maximumInstances)
  if (Number.isFinite(configuredMaximum) && configuredMaximum > 0 && existing.length >= configuredMaximum) {
    throw domainError('INVALID_STATE_TRANSITION', `Maximum ${configuredMaximum} component records allowed.`)
  }

  const created = stampTenant({
    id: newId('cmp'),
    jobNo,
    serviceOrderId: payload.serviceOrderId || String(job!.id || ''),
    templateCode: payload.templateCode,
    templateVersion: payload.templateVersion || '',
    latestTemplateVersion: payload.latestTemplateVersion || payload.templateVersion || '',
    groupCode,
    status: 'PENDING',
    required: payload.required !== false,
    resolvedInstanceMode: instanceMode,
    sequenceNo: Math.max(0, ...existing.map(row => Number(row.sequenceNo || 0))) + 1,
    values: Array.isArray(payload.values) ? payload.values : [],
  } as FreightRecord, session)
  const saved = replace(db, 'serviceComponents', created)
  audit(db, session, 'Created service component', 'Jobs', String(saved.templateCode), jobNo)
  return saved
}

export function saveServiceComponentValues(
  db: LcsCollections,
  session: LcsSession,
  componentId: string,
  values: unknown[],
) {
  assertPermission(session, 'service_order.update')
  const component = findById(db, 'serviceComponents', componentId)
  assertRecordAccess(component, session)
  if (String(component!.status || '').toUpperCase() === 'COMPLETED') {
    throw domainError('INVALID_STATE_TRANSITION', 'Completed component records cannot be edited.')
  }
  const saved = replace(db, 'serviceComponents', { ...component!, values })
  audit(db, session, 'Updated service component', 'Jobs', String(saved.templateCode), String(saved.jobNo))
  return saved
}

export function removeServiceComponent(
  db: LcsCollections,
  session: LcsSession,
  componentId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'service_order.update')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const component = findById(db, 'serviceComponents', componentId)
  assertRecordAccess(component, session)
  if (String(component!.status || '').toUpperCase() === 'COMPLETED') {
    throw domainError('INVALID_STATE_TRANSITION', 'Completed component records cannot be deleted.')
  }
  db.serviceComponents = rows(db, 'serviceComponents').filter(row => row.id !== componentId)
  audit(db, session, 'Deleted service component', 'Jobs', String(component!.templateCode), String(component!.jobNo))
  return rememberIdempotent(db, idempotencyKey, 'component.remove', componentId, component!)
}

export function addActualContainer(
  db: LcsCollections,
  session: LcsSession,
  serviceOrderId: string,
  payload: Record<string, unknown>,
) {
  assertPermission(session, 'service_order.update')
  const job = findById(db, 'jobs', serviceOrderId)
  assertRecordAccess(job, session)
  const gross = Number(payload.grossWeightKg || 0)
  const net = Number(payload.netWeightKg || 0)
  if (gross && net && gross < net) {
    throw domainError('INVALID_ATTRIBUTE_TYPE', 'Gross weight cannot be less than net weight.', {
      field_errors: { grossWeightKg: 'Must be greater than or equal to net weight' },
    })
  }
  const saved = replace(db, 'actualContainers', stampTenant({
    id: newId('ac'),
    jobNo: job!.jobNo,
    serviceOrderId,
    containerType: payload.containerType || job!.containerType,
    containerNo: payload.containerNo,
    sealNo: payload.sealNo,
    netWeightKg: net || undefined,
    grossWeightKg: gross || undefined,
    status: payload.status || 'Loaded',
    containerRequirementId: payload.containerRequirementId,
  } as FreightRecord, session, recordBranchFallback(job!)))
  audit(db, session, 'Added actual container', 'Jobs', String(job!.jobNo), String(saved.containerNo))
  return saved
}

export function closeAccountingPeriod(
  db: LcsCollections,
  session: LcsSession,
  periodId: string,
  idempotencyKey: string,
) {
  assertPermission(session, 'accounting_period.close')
  const cached = existingIdempotent(db, idempotencyKey)
  if (cached) return cached
  const period = findById(db, 'accountingPeriods', periodId)
  assertRecordAccess(period, session)
  const saved = replace(db, 'accountingPeriods', { ...period!, status: 'CLOSED', closedBy: session.userName, closedAt: new Date().toISOString() })
  audit(db, session, 'Closed accounting period', 'Finance', String(saved.code))
  return rememberIdempotent(db, idempotencyKey, 'period.close', periodId, saved)
}

export function canPostDocument(db: LcsCollections, session: LcsSession, document: FreightRecord) {
  if (financeDomainStatus(document.status) !== 'DRAFT') return false
  const period = findById(db, 'accountingPeriods', String(document.periodId || '')) || periodForDate(db, session, document.date)
  return Boolean(period && String(period.status) !== 'CLOSED')
}

export function assertCanSave(
  db: LcsCollections,
  session: LcsSession,
  collection: string,
  record: FreightRecord,
  permission: SourcePermission,
) {
  assertPermission(session, permission)
  const existing = record.id ? findById(db, collection, record.id) : null
  if (existing) assertRecordAccess(existing, session)
  assertMutableRecord(collection, existing, record)
}

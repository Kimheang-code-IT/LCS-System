import { describe, expect, it } from 'vitest'
import { createLcsFreightSeed } from './fixtures/lcs-seed'
import type { FreightRecord } from '../app/types/freight/record'
import type { LcsSession } from '../app/types/lcs/session'
import {
  allocatePayment,
  completeServiceComponent,
  convertQuotationRevision,
  createFinanceInvoiceFromCharge,
  ensureServiceComponent,
  issueServiceCharge,
  postFinancialDocument,
  sendQuotationRevision,
  submitQuotationRevision,
} from '../app/utils/lcs/commands'
import { isLcsDomainError } from '../app/utils/lcs/errors'
import { filterScopedRecords } from '../app/utils/lcs/scope'
import { canConvertQuotation, isQuotationImmutable } from '../app/utils/lcs/states'
import { SOURCE_PERMISSIONS } from '../app/types/lcs/domain'

function adminSession(overrides: Partial<LcsSession> = {}): LcsSession {
  return {
    userId: 1,
    userName: 'System Administrator',
    organizationId: 1,
    branchId: 'all',
    assignedBranchIds: [1, 2],
    permissionScope: 'ORGANIZATION',
    sourcePermissions: [...SOURCE_PERMISSIONS],
    ...overrides,
  }
}

function db() {
  const seed = createLcsFreightSeed()
  seed.idempotency = []
  return seed
}

describe('quotation states', () => {
  it('treats SENT revisions as immutable and only ACCEPTED as convertible', () => {
    expect(isQuotationImmutable('Sent')).toBe(true)
    expect(isQuotationImmutable('Draft')).toBe(false)
    expect(canConvertQuotation('Sent')).toBe(false)
    expect(canConvertQuotation('Accepted')).toBe(true)
    expect(canConvertQuotation('Rejected')).toBe(false)
  })

  it('submits a saved draft quotation into a service order', () => {
    const data = db()
    data.quotations.push({
      id: 'qt-submit',
      quotationNo: 'QT-TEST-SUBMIT',
      status: 'Draft',
      organizationId: 1,
      branchId: 1,
      direction: 'Import',
      customer: 'Manhattan SEZ Co., Ltd.',
      revisionNo: 1,
      currency: 'USD',
      total: 1850,
      containerRequirements: [{ id: 'qrc-submit', containerType: '40HC', quantity: 1, description: 'Submit test' }],
      pricingLines: [{ feeType: 'Trucking Fee', description: 'Freight', quantity: 1, unitPrice: 1850, taxPercent: 0 }],
    })
    const job = submitQuotationRevision(data, adminSession(), 'qt-submit', 'idem-submit-1')
    expect(String(job.jobNo)).toMatch(/^LCS-/)
    expect(data.quotations.find(row => row.id === 'qt-submit')?.status).toBe('Converted')
    expect(submitQuotationRevision(data, adminSession(), 'qt-submit', 'idem-submit-1').id).toBe(job.id)
  })

  it('sends a draft quotation and converts an accepted revision once', () => {
    const data = db()
    const sent = sendQuotationRevision(data, adminSession(), 'qt-003', 'idem-send-1')
    expect(sent.status).toBe('Sent')
    expect(sendQuotationRevision(data, adminSession(), 'qt-003', 'idem-send-1').id).toBe(sent.id)

    data.quotations.push({
      id: 'qt-acc',
      quotationNo: 'QT-TEST-ACCEPT',
      status: 'Accepted',
      organizationId: 1,
      branchId: 1,
      direction: 'Import',
      customer: 'Manhattan SEZ Co., Ltd.',
      revisionNo: 1,
      currency: 'USD',
      total: 1100,
      places: [
        { placeRole: 'Pickup', place: 'Cat Lai', plannedActual: '2026-08-30', notes: 'Collect cargo' },
        { placeRole: 'Transit / Border', place: 'Moc Bai / Bavet', plannedActual: '2026-08-31' },
        { placeRole: 'Delivery', place: 'Manhattan SEZ', plannedActual: '2026-09-01' },
      ],
      attachments: [{ fileName: 'quotation-support.pdf', uploadedBy: 'Sales User' }],
      containerRequirements: [{ id: 'qrc-acc', containerType: '40HC', quantity: 1, description: 'Test box' }],
      pricingLines: [{ feeType: 'Trucking Fee', description: 'Freight', quantity: 1, unitPrice: 1000, taxPercent: 10 }],
    })
    const job = convertQuotationRevision(data, adminSession(), 'qt-acc', 'idem-convert-1')
    expect(String(job.jobNo)).toMatch(/^LCS-/)
    expect(job.containerRequirements).toEqual(expect.arrayContaining([
      expect.objectContaining({ containerType: '40HC', quantity: 1, sourceQuotationContainerId: 'qrc-acc' }),
    ]))
    expect(data.containerRequirements?.some(row => String(row.jobNo) === String(job.jobNo))).toBe(true)
    expect(job.containerPayments).toEqual(expect.arrayContaining([
      expect.objectContaining({ feeType: 'Trucking Fee', lineTotal: 1100 }),
    ]))
    expect(job.places).toEqual(expect.arrayContaining([
      expect.objectContaining({ placeRole: 'Delivery', place: 'Manhattan SEZ' }),
    ]))
    expect(job.destination).toBe('Manhattan SEZ')
    expect(job.etaBorder).toBe('2026-08-31')
    expect(job.attachments).toEqual([
      expect.objectContaining({ fileName: 'quotation-support.pdf', uploadedBy: 'Sales User' }),
    ])
    expect(job.attachments).not.toBe(data.quotations.find(row => row.id === 'qt-acc')?.attachments)
    expect(data.quotations.find(row => row.id === 'qt-acc')?.status).toBe('Converted')

    try {
      convertQuotationRevision(data, adminSession(), 'qt-acc', 'idem-convert-2')
      expect.unreachable()
    }
    catch (error) {
      expect(isLcsDomainError(error) && error.code).toBe('DUPLICATE_CONVERSION')
    }
  })

  it('rejects conversion of a sent quotation', () => {
    const data = db()
    try {
      convertQuotationRevision(data, adminSession(), 'qt-002', 'idem-bad-convert')
      expect.unreachable()
    }
    catch (error) {
      expect(isLcsDomainError(error) && error.code).toBe('INVALID_STATE_TRANSITION')
    }
  })
})

describe('organization and branch isolation', () => {
  it('hides other-organization jobs from LCS users', () => {
    const data = db()
    const lcs = adminSession()
    const visible = filterScopedRecords(data.jobs, lcs)
    expect(visible.some(row => row.id === 'job-008')).toBe(false)
    expect(visible.some(row => row.id === 'job-001')).toBe(true)
  })

  it('limits Bavet operators to the Bavet branch', () => {
    const data = db()
    const ops = adminSession({
      userId: 3,
      permissionScope: 'BRANCH',
      branchId: 1,
      assignedBranchIds: [1],
      sourcePermissions: ['service_order.read'],
    })
    const visible = filterScopedRecords(data.jobs, ops)
    expect(visible.some(row => row.id === 'job-003')).toBe(false)
    expect(visible.some(row => row.id === 'job-001')).toBe(true)
  })
})

describe('service charges and finance', () => {
  it('issues a charge without creating a journal', () => {
    const data = db()
    const issued = issueServiceCharge(data, adminSession(), 'jc-002', 'idem-issue-1')
    expect(issued.status).toBe('Issued')
    expect(issued.journalId).toBe('')
    expect(data.journals.filter(row => row.sourceDocumentId === 'jc-002')).toHaveLength(0)
  })

  it('converts an issued charge to a draft invoice only', () => {
    const data = db()
    const invoice = createFinanceInvoiceFromCharge(data, adminSession(), 'jc-003', 'idem-inv-1')
    const repeated = createFinanceInvoiceFromCharge(data, adminSession(), 'jc-003', 'idem-inv-2')
    const charge = data.jobCharges.find(row => row.id === 'jc-003')
    expect(invoice.status).toBe('Draft')
    expect(invoice.documentType).toBe('CUSTOMER_INVOICE')
    expect(invoice.journalId).toBe('')
    expect(invoice.sourceChargeId).toBe('jc-003')
    expect(charge?.financialDocumentId).toBe(invoice.id)
    expect(charge?.invoiceNo).toBe(invoice.debitNoteNo)
    expect(repeated.id).toBe(invoice.id)
    expect(data.debitNotes.filter(row => row.sourceChargeId === 'jc-003')).toHaveLength(1)
  })

  it('copies the posted journal onto the source service charge', () => {
    const data = db()
    const posted = postFinancialDocument(data, adminSession(), 'dn-002', 'idem-post-charge')
    const charge = data.jobCharges.find(row => row.id === 'jc-003')
    expect(posted.status).toBe('Posted')
    expect(charge?.journalId).toBe(posted.journalId)
    expect(charge?.financialDocumentId).toBe('dn-002')
  })

  it('blocks posting into a closed period', () => {
    const data = db()
    try {
      postFinancialDocument(data, adminSession(), 'dn-004', 'idem-post-closed')
      expect.unreachable()
    }
    catch (error) {
      expect(isLcsDomainError(error) && error.code).toBe('PERIOD_CLOSED')
    }
  })

  it('refuses allocation beyond remaining payment', () => {
    const data = db()
    try {
      allocatePayment(data, adminSession(), 'cp-001', 'dn-001', 99999, 'idem-alloc-1')
      expect.unreachable()
    }
    catch (error) {
      expect(isLcsDomainError(error) && error.code).toBe('ALLOCATION_EXCEEDS_BALANCE')
    }
  })
})

describe('dynamic components', () => {
  it('keeps the captured template version and blocks incomplete required values', () => {
    const data = db()
    const pending = data.serviceComponents.find(row => row.id === 'cmp-002') as FreightRecord
    expect(pending.templateVersion).toBe('2026.06')
    expect(pending.latestTemplateVersion).toBe('2026.08')
    try {
      completeServiceComponent(data, adminSession(), 'cmp-002', 'idem-cmp-1')
      expect.unreachable()
    }
    catch (error) {
      expect(isLcsDomainError(error) && error.code).toBe('REQUIRED_VALUE_MISSING')
    }
    const completed = data.serviceComponents.find(row => row.id === 'cmp-001') as FreightRecord
    expect(completed.templateVersion).toBe('2026.04')
  })

  it('creates repeatable component records when the template instance mode is REPEATABLE', () => {
    const data = db()
    const created = ensureServiceComponent(data, adminSession(), {
      jobNo: 'LCS-EX-260820',
      groupCode: 'PACKING_LIST',
      templateCode: 'PACKING_LIST',
      templateVersion: '2026.08',
      values: [{ code: 'packing_list_no', label: 'Packing List No.', dataType: 'text', required: true }],
    })
    expect(created.groupCode).toBe('PACKING_LIST')
    expect(created.status).toBe('PENDING')
    const again = ensureServiceComponent(data, adminSession(), {
      jobNo: 'LCS-EX-260820',
      groupCode: 'PACKING_LIST',
      templateCode: 'PACKING_LIST',
    })
    expect(again.id).not.toBe(created.id)
    expect(again.sequenceNo).toBeGreaterThan(Number(created.sequenceNo || 0))
  })
})

describe('navigation workspace modules', () => {
  it('resolves every sidebar page path to a freight module', async () => {
    const { getFreightModule } = await import('../app/config/freight-modules')
    const paths = [
      '/quotations',
      '/service-orders',
      '/service-charges',
      '/finance/documents',
      '/finance/chart-of-accounts',
      '/finance/financial-accounts',
      '/finance/journals',
      '/finance/accounting-periods',
      '/reports',
      '/master-data/business-parties',
      '/master-data/places',
      '/master-data/trade-directions',
      '/master-data/container-types',
      '/master-data/transport-types',
      '/master-data/transport-assets',
      '/master-data/fee-types',
      '/configuration/component-templates',
      '/administration/organizations',
      '/administration/branches',
      '/administration/users',
      '/administration/roles',
      '/administration/audit-logs',
    ]
    for (const path of paths) {
      expect(getFreightModule(path)?.path, path).toBe(path)
      expect(getFreightModule(`${path}/sample-id`)?.path, `${path}/id`).toBe(path)
    }
  })
})

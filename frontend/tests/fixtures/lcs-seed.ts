import type { FreightRecord } from '~/types/freight/record'
import { createFreightSeed } from './freight-seed'
import {
  BRANCH_BAVET_ID,
  BRANCH_DEMO_ID,
  BRANCH_PP_ID,
  DEMO_ORG_ID,
  LCS_ORG_ID,
} from './lcs-tenant'
import { permissionRowsToFlatKeys, seedRolePermissionRows } from '~/utils/role/permissions'
import { jobRoutePlaces } from '~/utils/freight/job-workspace'
import { jobFileAttachments } from '~/utils/freight/attachments'

const JOB_WORKFLOW_BY_STATUS: Record<string, string> = {
  'Job Created': 'OPEN',
  'Documents Received': 'OPEN',
  'Transport Registered': 'IN_PROGRESS',
  'Customs Processing': 'IN_PROGRESS',
  'Customs Cleared': 'IN_PROGRESS',
  'In Transit': 'IN_PROGRESS',
  'Arrived Factory': 'IN_PROGRESS',
  Delivered: 'COMPLETED',
  'Financial Completed': 'COMPLETED',
  Closed: 'CLOSED',
  'On Hold': 'ON_HOLD',
  Cancelled: 'CANCELLED',
  Draft: 'DRAFT',
}

function stamp<T extends FreightRecord>(row: T, organizationId: number, branchId: number, extra: Record<string, unknown> = {}): T {
  return { organizationId, branchId, createdByUserId: 1, ...row, ...extra }
}

function stampAll(rows: FreightRecord[] | undefined, organizationId: number, branchId: number) {
  return (rows || []).map(row => stamp(row, organizationId, branchId))
}

function id(prefix: string, n: number) {
  return `${prefix}-${String(n).padStart(3, '0')}`
}

/** Operational seed plus org/branch, workflow, finance, and template fixtures. */
export function createLcsFreightSeed(): Record<string, FreightRecord[]> {
  const base = createFreightSeed()

  const quotations = stampAll(base.quotations, LCS_ORG_ID, BRANCH_BAVET_ID).map((row) => {
    const extra: Record<string, unknown> = {
      revisionNo: 1,
      quotationId: row.id,
      containerRequirements: [
        { containerType: Number(row.selling40 || 0) > 0 ? '40HC' : '20GP', quantity: 1, description: 'Quoted container requirement' },
      ],
      pricingLines: [
        { feeType: 'INLAND_TRANSPORT', containerType: Number(row.selling40 || 0) > 0 ? '40HC' : '20GP', description: 'Cross-border freight service', quantity: 1, unit: 'Container', unitPrice: Number(row.selling40 || row.selling20 || row.amount || 0), discount: 0, tax: 0, total: Number(row.selling40 || row.selling20 || row.amount || 0) },
      ],
    }
    if (row.id === 'qt-001') extra.status = 'Converted'
    if (row.id === 'qt-002') extra.status = 'Sent'
    if (row.id === 'qt-003') extra.status = 'Draft'
    return { ...row, ...extra }
  })

  quotations.push(stamp({
    id: id('qt', 4),
    quotationNo: 'QT-2026-0808',
    date: '2026-08-08',
    customer: 'QiLu Cambodia Co., Ltd.',
    attention: 'Mr. Vannak',
    phone: '+855 12 889 221',
    email: 'vannak@qilu.com.kh',
    direction: 'Import',
    pickup: 'CATLAI',
    border: 'MOC BAI / BAVET',
    delivery: 'QILU',
    transportBy: 'Truck',
    route: 'CATLAI → MOC BAI / BAVET → QILU',
    validUntil: '2026-09-01',
    currency: 'USD',
    amount: 2100,
    status: 'Converted',
    convertedJobNo: 'LCS-IM-260818',
    revisionNo: 1,
    quotationId: id('qt', 4),
    buying20: 900,
    selling20: 1200,
    totalBuying: 900,
    totalSelling: 1200,
    profit: 300,
    margin: 25,
  } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID))

  quotations.push(stamp({
    id: id('qt', 5),
    quotationNo: 'QT-2026-0807',
    date: '2026-08-07',
    customer: 'Tai Seng Manufacturing',
    attention: 'Mr. Dara',
    direction: 'Export',
    pickup: 'TAI SENG',
    border: 'BAVET / MOC BAI',
    delivery: 'CAT LAI',
    transportBy: 'Truck',
    validUntil: '2026-08-20',
    currency: 'USD',
    amount: 1600,
    status: 'Rejected',
    revisionNo: 1,
    quotationId: id('qt', 5),
  } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID))

  quotations.push(stamp({
    id: id('qt', 7),
    quotationNo: 'QT-2026-0814',
    date: '2026-08-14',
    customer: 'Manhattan SEZ Co., Ltd.',
    attention: 'Ms. Lina',
    phone: '+855 12 345 678',
    email: 'dara@manhattan.com.kh',
    direction: 'Import',
    pickup: 'CATLAI',
    border: 'MOC BAI / BAVET',
    delivery: 'MANHATTAN',
    transportBy: 'Truck',
    validUntil: '2026-09-20',
    currency: 'USD',
    amount: 2400,
    status: 'Accepted',
    revisionNo: 1,
    quotationId: id('qt', 7),
    buying20: 900,
    selling20: 1200,
    totalBuying: 900,
    totalSelling: 1200,
    profit: 300,
    margin: 25,
  } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID))

  quotations.push(stamp({
    id: id('qt', 6),
    quotationNo: 'QT-DEMO-0101',
    date: '2026-08-10',
    customer: 'Demo Customer Ltd.',
    direction: 'Import',
    status: 'Draft',
    amount: 500,
    currency: 'USD',
    revisionNo: 1,
    quotationId: id('qt', 6),
  } as FreightRecord, DEMO_ORG_ID, BRANCH_DEMO_ID))

  for (const quotation of quotations) {
    const amount = Number(quotation.total || quotation.amount || 0)
    quotation.branchName = Number(quotation.branchId) === BRANCH_PP_ID ? 'Phnom Penh' : Number(quotation.branchId) === BRANCH_DEMO_ID ? 'Demo HQ' : 'Bavet'
    quotation.subtotal = amount
    quotation.discount = Number(quotation.discount || 0)
    quotation.tax = Number(quotation.tax || 0)
    quotation.total = amount - Number(quotation.discount || 0) + Number(quotation.tax || 0)
    quotation.createdBy = quotation.createdBy || 'Dara C.'
    quotation.createdAt = quotation.createdAt || `${String(quotation.date || '2026-08-01')}T08:30:00`
    quotation.places = Array.isArray(quotation.places) ? quotation.places : [
      { sequence: 1, placeRole: 'Pickup', place: quotation.pickup, freeTextLocation: '', notes: '' },
      { sequence: 2, placeRole: 'Transit / Border', place: quotation.border, freeTextLocation: '', notes: '' },
      { sequence: 3, placeRole: 'Delivery', place: quotation.delivery, freeTextLocation: '', notes: '' },
    ]
    if (!Array.isArray(quotation.containerRequirements)) quotation.containerRequirements = [{ containerType: String(quotation.containerType || '40HC'), quantity: 1, description: 'Standard container requirement' }]
    if (!Array.isArray(quotation.pricingLines)) quotation.pricingLines = [{ lineNo: 1, feeType: 'INLAND_TRANSPORT', containerRequirement: String(quotation.containerType || '40HC'), description: 'Freight service', quantity: 1, unit: 'Container', unitPrice: amount, discountPercent: 0, taxPercent: 0, subtotal: amount, discountAmount: 0, taxAmount: 0, lineTotal: amount }]
    quotation.attachments = Array.isArray(quotation.attachments) ? quotation.attachments : []
    quotation.revisionHistory = [{ revisionNo: quotation.revisionNo || 1, status: quotation.status, quotationDate: quotation.date, validUntil: quotation.validUntil, currency: quotation.currency, total: quotation.total, sentAt: quotation.sentAt || '', acceptedAt: quotation.acceptedAt || '', createdBy: quotation.createdBy, createdAt: quotation.createdAt }]
  }

  const jobs = stampAll(base.jobs, LCS_ORG_ID, BRANCH_BAVET_ID).map((row) => {
    const workflowStatus = JOB_WORKFLOW_BY_STATUS[String(row.status)] || 'OPEN'
    const extra: Record<string, unknown> = { workflowStatus, templateVersion: '2026.04', branchName: Number(row.branchId) === BRANCH_PP_ID ? 'Phnom Penh' : 'Bavet', currency: row.currency || 'USD', createdBy: row.assignedStaff || 'Operations', createdAt: `${String(row.date || '2026-08-01')}T08:00:00`, updatedAt: '2026-08-20T10:00:00' }
    extra.places = jobRoutePlaces(row)
    extra.attachments = jobFileAttachments(row, (base.documents || []).filter(item => String(item.jobNo || '') === String(row.jobNo || '')))
    if (row.id === 'job-003') extra.branchId = BRANCH_PP_ID
    if (row.id === 'job-006') extra.workflowStatus = 'CLOSED'
    if (row.id === 'job-001') {
      extra.vatRate = 10
      extra.containerPayments = [
        { feeType: 'Trucking Fee', containerNo: 'MSCU 482190-7', quantity: 1, unit: 'Trip', description: 'Inland trucking', unitPrice: 1250, discountAmount: 0, taxRate: 10 },
        { feeType: 'Customs Clearance Fee', containerNo: 'MSCU 482190-7', quantity: 1, unit: 'Job', description: 'Customs clearance', unitPrice: 120, discountAmount: 0, taxRate: 10 },
      ]
    }
    return { ...row, ...extra }
  })

  jobs.push(stamp({
    id: id('job', 7),
    jobNo: 'LCS-IM-260815',
    date: '2026-08-15',
    customer: 'Royal Group Manufacturing',
    factory: 'Royal Factory',
    zone: 'Phnom Penh SEZ',
    direction: 'Import',
    serviceType: 'Trucking',
    status: 'On Hold',
    workflowStatus: 'ON_HOLD',
    assignedStaff: 'Lina K.',
    quotationNo: '',
    soNo: 'SO-2608-171',
    containerType: '40GP',
    origin: 'Cai Mep',
    destination: 'PPSEZ',
    operationalRemark: 'Waiting customer documents.',
  } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID))

  jobs.push(stamp({
    id: id('job', 8),
    jobNo: 'DEMO-IM-0101',
    date: '2026-08-12',
    customer: 'Demo Customer Ltd.',
    direction: 'Import',
    status: 'Job Created',
    workflowStatus: 'OPEN',
    soNo: 'SO-DEMO-001',
  } as FreightRecord, DEMO_ORG_ID, BRANCH_DEMO_ID))

  const containerRequirements: FreightRecord[] = [
    stamp({
      id: id('cr', 1),
      jobNo: 'LCS-IM-260821',
      serviceOrderId: 'job-001',
      containerType: '40HC',
      quantity: 1,
      description: 'From quotation QT-2026-0812',
      sourceQuotationContainerId: 'qrc-qt-001',
      status: 'Required',
    } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    stamp({
      id: id('cr', 2),
      jobNo: 'LCS-EX-260817',
      serviceOrderId: 'job-005',
      containerType: '40HC',
      quantity: 1,
      description: '',
      status: 'Required',
    } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
  ]
  const actualContainers: FreightRecord[] = [
    stamp({
      id: id('ac', 1),
      jobNo: 'LCS-IM-260821',
      serviceOrderId: 'job-001',
      containerRequirementId: 'cr-001',
      containerType: '40HC',
      containerNo: 'MSCU 482190-7',
      sealNo: 'SL-9912',
      netWeightKg: 18200,
      grossWeightKg: 21800,
      status: 'Loaded',
    } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    stamp({
      id: id('ac', 2),
      jobNo: 'LCS-EX-260820',
      serviceOrderId: 'job-002',
      containerRequirementId: 'cr-job-002',
      containerType: '20GP',
      containerNo: 'TGHU 771923-4',
      sealNo: 'SL-7741',
      netWeightKg: 12450,
      grossWeightKg: 15200,
      status: 'In Transit',
    } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    stamp({
      id: id('ac', 3),
      jobNo: 'LCS-IM-260819',
      serviceOrderId: 'job-003',
      containerRequirementId: 'cr-job-003',
      containerType: '40GP',
      containerNo: 'OOLU 204187-1',
      sealNo: 'SL-4410',
      netWeightKg: 19800,
      grossWeightKg: 22400,
      status: 'Delivered',
    } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
    stamp({
      id: id('ac', 4),
      jobNo: 'LCS-IM-260818',
      serviceOrderId: 'job-004',
      containerRequirementId: 'cr-job-004',
      containerType: '40HC',
      containerNo: 'CSLU 551882-1',
      sealNo: 'SL-2281',
      netWeightKg: 17600,
      grossWeightKg: 21100,
      status: 'Loaded',
    } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    stamp({
      id: id('ac', 5),
      jobNo: 'LCS-IM-260816',
      serviceOrderId: 'job-006',
      containerRequirementId: 'cr-job-006',
      containerType: '20GP',
      containerNo: 'MSCU 771100-2',
      sealNo: 'SL-1102',
      netWeightKg: 9850,
      grossWeightKg: 11800,
      status: 'Returned',
    } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
  ]

  for (const job of jobs) {
    const reqs = containerRequirements.filter(row => String(row.jobNo) === String(job.jobNo))
    const acts = actualContainers.filter(row => String(row.jobNo) === String(job.jobNo))
    if (reqs.length) job.containerRequirements = reqs
    else {
      const row = {
        id: `cr-${job.id}`,
        containerType: String(job.containerType || '40HC'),
        quantity: 1,
        description: String(job.quotationNo || '').trim() ? `From quotation ${job.quotationNo}` : '',
      }
      job.containerRequirements = [row]
      containerRequirements.push(stamp({
        ...row,
        jobNo: job.jobNo,
        serviceOrderId: job.id,
        status: 'Required',
      } as FreightRecord, Number(job.organizationId) || LCS_ORG_ID, Number(job.branchId) || BRANCH_BAVET_ID))
    }
    if (acts.length) job.actualContainers = acts
    else if (String(job.containerNo || '').trim()) {
      const requirementId = String((job.containerRequirements as Array<Record<string, unknown>>)[0]?.id || '')
      const row = {
        id: `ac-${job.id}`,
        containerRequirementId: requirementId,
        containerType: job.containerType,
        containerNo: job.containerNo,
        sealNo: job.sealNo,
        status: 'Loaded',
        netWeightKg: 0,
        grossWeightKg: 0,
      }
      job.actualContainers = [row]
      actualContainers.push(stamp({
        ...row,
        jobNo: job.jobNo,
        serviceOrderId: job.id,
      } as FreightRecord, Number(job.organizationId) || LCS_ORG_ID, Number(job.branchId) || BRANCH_BAVET_ID))
    }
    else job.actualContainers = Array.isArray(job.actualContainers) ? job.actualContainers : []
  }

  const jobCharges = stampAll(base.jobCharges, LCS_ORG_ID, BRANCH_BAVET_ID).map((row) => {
    const status = row.id === 'jc-002' ? 'Draft' : 'Issued'
    const job = jobs.find(item => String(item.jobNo) === String(row.jobNo))
    const subtotal = Number(row.amount || 0)
    const tax = Number(row.tax || 0)
    return {
      ...row,
      status,
      chargeNo: `SC-2026-${String(row.id).replace(/\D/g, '').padStart(4, '0')}`,
      documentDate: '2026-08-20',
      documentType: 'SERVICE_NOTE',
      customer: job?.customer || '',
      branchName: Number(row.branchId) === BRANCH_PP_ID ? 'Phnom Penh' : 'Bavet',
      subtotal,
      discount: 0,
      tax,
      total: subtotal + tax,
      remarks: '',
      feeLines: [{ feeType: row.chargeType, description: row.description, containerNo: job?.containerNo || '', quantity: row.quantity, unitAmount: row.unitPrice, discount: 0, taxAmount: tax, amount: subtotal + tax }],
      createdBy: row.staff || 'Finance',
      createdAt: '2026-08-20T09:00:00',
      journalId: row.id === 'jc-001' ? 'je-001' : '',
      financialDocumentId: row.id === 'jc-001' ? 'dn-001' : row.id === 'jc-003' ? 'dn-002' : '',
      posted: false,
    }
  })

  const debitNotes = stampAll(base.debitNotes, LCS_ORG_ID, BRANCH_BAVET_ID).map((row) => {
    const extra: Record<string, unknown> = {
      documentType: 'CUSTOMER_INVOICE',
      periodId: 'per-002',
      journalId: '',
      allocatedAmount: 0,
    }
    if (row.id === 'dn-001') {
      extra.status = 'Posted'
      extra.journalId = 'je-001'
      extra.sourceChargeId = 'jc-001'
      extra.postedAt = '2026-08-20T11:40:00'
    }
    if (row.id === 'dn-002') {
      extra.status = 'Draft'
      extra.sourceChargeId = 'jc-003'
    }
    if (row.id === 'dn-003') {
      extra.status = 'Posted'
      extra.journalId = 'je-002'
      extra.branchId = BRANCH_PP_ID
    }
    return { ...row, ...extra }
  })

  debitNotes.push(stamp({
    id: id('dn', 4),
    debitNoteNo: 'DN-2607-012',
    date: '2026-07-15',
    customer: 'Manhattan SEZ Co., Ltd.',
    jobNo: 'LCS-IM-260816',
    amount: 400,
    vatRate: 10,
    vat: 40,
    total: 440,
    status: 'Draft',
    documentType: 'CUSTOMER_INVOICE',
    periodId: 'per-001',
    direction: 'Import',
  } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID))

  const customerPayments = stampAll(base.customerPayments, LCS_ORG_ID, BRANCH_BAVET_ID).map((row) => {
    const extra: Record<string, unknown> = { allocatedAmount: 0, unallocatedAmount: Number(row.received || 0) }
    if (row.id === 'cp-002') {
      extra.allocatedAmount = 500
      extra.unallocatedAmount = 0
      extra.journalId = 'je-004'
      extra.allocations = [{ targetDocumentNo: 'DN-2608-040', targetOutstanding: 1226.5, amount: 500, currency: 'USD', exchangeRate: 1 }]
    }
    if (row.id === 'cp-003') {
      extra.allocatedAmount = 1375
      extra.unallocatedAmount = 0
      extra.branchId = BRANCH_PP_ID
      extra.journalId = 'je-003'
      extra.allocations = [{ targetDocumentNo: 'DN-2608-039', targetOutstanding: 1375, amount: 1375, currency: 'USD', exchangeRate: 1 }]
    }
    if (row.id === 'cp-001') {
      extra.received = 200
      extra.outstanding = 1422.5
      extra.allocatedAmount = 0
      extra.unallocatedAmount = 200
      extra.status = 'Partial'
      extra.journalId = 'je-008'
      extra.allocations = []
    }
    return { ...row, ...extra }
  })

  const supplierCosts: FreightRecord[] = stampAll(base.supplierCosts, LCS_ORG_ID, BRANCH_BAVET_ID).map((row): FreightRecord => {
    if (row.id === 'sc-003') return { ...row, branchId: BRANCH_PP_ID, postingStatus: 'Posted' }
    return { ...row, postingStatus: row.status === 'Paid' ? 'Posted' : 'Draft' }
  })

  const financialDocuments: FreightRecord[] = [
    ...debitNotes.map(row => ({
      ...row,
      documentType: row.documentType || 'CUSTOMER_INVOICE',
      currency: row.currency || 'USD',
      branchName: Number(row.branchId) === BRANCH_PP_ID ? 'Phnom Penh' : 'Bavet',
      postingDate: row.postedAt ? String(row.postedAt).slice(0, 10) : row.date,
      createdBy: row.createdBy || 'Finance',
      postedBy: row.status === 'Posted' ? 'Finance Manager' : '',
      referenceNo: row.referenceNo || row.invoiceNo || '',
      lines: Array.isArray(row.lines) ? row.lines : [{ lineNo: 1, description: `Customer invoice ${row.debitNoteNo}`, feeType: 'FREIGHT_SERVICE', serviceOrder: row.jobNo, containerNo: row.containerNo, accountCode: '4010', quantity: 1, unit: 'Service', unitAmount: Number(row.amount || 0), discount: 0, taxRate: Number(row.vatRate || 0), taxAmount: Number(row.vat || 0), amount: Number(row.total || row.amount || 0) }],
    })),
    ...customerPayments.map(row => ({
      ...row,
      debitNoteNo: row.paymentNo,
      documentType: 'CUSTOMER_RECEIPT',
      total: Number(row.received || 0),
      amount: Number(row.received || 0),
      status: Number(row.received || 0) > 0 ? 'Posted' : 'Draft',
      financialAccount: String(row.paymentMethod || ''),
      branchName: Number(row.branchId) === BRANCH_PP_ID ? 'Phnom Penh' : 'Bavet', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-20T11:00:00',
      lines: [{ lineNo: 1, description: `Customer receipt ${row.paymentNo}`, feeType: '', serviceOrder: row.jobNo, containerNo: row.containerNo, accountCode: '1020', quantity: 1, unit: 'Receipt', unitAmount: Number(row.received || 0), discount: 0, taxRate: 0, taxAmount: 0, amount: Number(row.received || 0) }],
    })),
    ...supplierCosts.map(row => ({
      ...row,
      debitNoteNo: row.invoiceNo,
      documentType: 'SUPPLIER_BILL',
      customer: row.supplier,
      date: row.date || '2026-08-20',
      total: Number(row.amount || 0),
      status: row.postingStatus === 'Posted' ? 'Posted' : 'Draft',
      branchName: Number(row.branchId) === BRANCH_PP_ID ? 'Phnom Penh' : 'Bavet', createdBy: 'Finance',
      lines: [{ lineNo: 1, description: row.description || row.chargeType, feeType: row.chargeType, serviceOrder: row.jobNo, containerNo: row.containerNo || '', accountCode: '5010', quantity: Number(row.quantity || 1), unit: 'Service', unitAmount: Number(row.unitCost || row.amount || 0), discount: 0, taxRate: 0, taxAmount: 0, amount: Number(row.amount || 0) }],
    })),
    ...stampAll(base.supplierPayments, LCS_ORG_ID, BRANCH_BAVET_ID).map(row => ({
      ...row,
      debitNoteNo: row.paymentNo,
      documentType: 'SUPPLIER_PAYMENT',
      customer: row.supplier,
      total: Number(row.amount || 0),
      status: 'Posted',
      financialAccount: String(row.paymentMethod || ''),
      branchName: Number(row.branchId) === BRANCH_PP_ID ? 'Phnom Penh' : 'Bavet', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-20T11:00:00',
      lines: [{ lineNo: 1, description: `Supplier payment ${row.paymentNo}`, feeType: '', serviceOrder: row.jobNo, containerNo: '', accountCode: '1020', quantity: 1, unit: 'Payment', unitAmount: Number(row.amount || 0), discount: 0, taxRate: 0, taxAmount: 0, amount: Number(row.amount || 0) }],
    })),
  ]

  return {
    ...base,
    companies: stampAll(base.companies, LCS_ORG_ID, BRANCH_BAVET_ID),
    suppliers: stampAll(base.suppliers, LCS_ORG_ID, BRANCH_BAVET_ID),
    quotations,
    jobs,
    shipments: stampAll(base.shipments, LCS_ORG_ID, BRANCH_BAVET_ID),
    customs: stampAll(base.customs, LCS_ORG_ID, BRANCH_BAVET_ID).map(row =>
      row.id === 'cu-003' ? { ...row, branchId: BRANCH_PP_ID } : row,
    ),
    documents: stampAll(base.documents, LCS_ORG_ID, BRANCH_BAVET_ID),
    deliveries: stampAll(base.deliveries, LCS_ORG_ID, BRANCH_BAVET_ID).map(row =>
      row.id === 'dl-002' ? { ...row, branchId: BRANCH_PP_ID } : row,
    ),
    debitNotes: financialDocuments,
    customerPayments,
    jobCharges,
    supplierCosts,
    supplierPayments: stampAll(base.supplierPayments, LCS_ORG_ID, BRANCH_BAVET_ID).map(row => {
      const extra: Record<string, unknown> = {}
      if (row.id === 'sp-001') extra.journalId = 'je-005'
      if (row.id === 'sp-002') extra.journalId = 'je-006'
      if (row.id === 'sp-003') extra.journalId = 'je-007'
      return { ...row, ...extra }
    }),
    users: stampAll(base.users, LCS_ORG_ID, BRANCH_BAVET_ID).map((row, index) => ({
      ...row,
      userCode: `USR-${String(index + 1).padStart(3, '0')}`,
      displayName: row.name,
      locale: 'en', timezone: 'Asia/Phnom_Penh', defaultBranch: index === 2 ? 'Phnom Penh' : 'Bavet', lastLogin: `2026-08-${String(20 - index).padStart(2, '0')}T09:30:00`,
      organization: 'LCS Freight', branch: index === 2 ? 'All branches' : 'Bavet', telegram: index === 0 ? '@lcs.admin' : '',
      roleAssignments: [{ role: row.role, organization: 'LCS Freight', branch: index === 2 ? 'All branches' : 'Bavet', effectiveDate: '2026-01-01', expiryDate: '', assignedBy: 'System Administrator' }],
      branchAssignments: [{ organization: 'LCS Freight', branch: index === 2 ? 'Phnom Penh' : 'Bavet', isDefault: 'Yes', startDate: '2026-01-01', expiryDate: '' }],
      sessions: [{ startedAt: '2026-08-20 08:30', lastSeenAt: '2026-08-20 11:45', ipAddress: '10.0.0.24', device: 'Chrome on Windows', status: 'Active' }],
      auditHistory: [{ occurredAt: '2026-08-20 08:30', action: 'Signed in', result: 'SUCCESS', requestId: `req-user-${index + 1}` }],
    })),
    roles: stampAll(base.roles, LCS_ORG_ID, BRANCH_BAVET_ID).map((row, index) => {
      const mode = index === 0 ? 'all' : index === 1 ? 'operations' : index === 2 ? 'finance' : 'customs'
      const permissionRows = seedRolePermissionRows(mode)
      return {
        ...row,
        code: `ROLE_${String(row.name || `ROLE_${index + 1}`).toUpperCase().replace(/\W+/g, '_')}`,
        systemRole: index < 2 ? 'Yes' : 'No',
        permissionRows,
        permissionCount: permissionRowsToFlatKeys(permissionRows).length,
      }
    }),
    auditLogs: [
      ...stampAll(base.auditLogs, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('log', 4),
        occurredAt: '2026-08-20 11:41',
        user: 'Dara C.',
        action: 'Posted financial document',
        eventType: 'FINANCE_POSTED', entityType: 'Financial Document', entity: 'DN-2608-041', organizationName: 'LCS Freight', branchName: 'Bavet', result: 'SUCCESS', reason: '', requestId: 'req-fin-0041', correlationId: 'corr-fin-0041', beforeData: '{"status":"DRAFT"}', afterData: '{"status":"POSTED"}', metadata: '{"journal":"JE-2026-0041"}',
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    zones: stampAll(base.zones, LCS_ORG_ID, BRANCH_BAVET_ID),
    locations: stampAll(base.locations, LCS_ORG_ID, BRANCH_BAVET_ID),
    equipmentTypes: stampAll(base.equipmentTypes, LCS_ORG_ID, BRANCH_BAVET_ID),
    directions: stampAll(base.directions, LCS_ORG_ID, BRANCH_BAVET_ID),
    chargeTypes: stampAll(base.chargeTypes, LCS_ORG_ID, BRANCH_BAVET_ID),
    currencies: stampAll(base.currencies, LCS_ORG_ID, BRANCH_BAVET_ID),
    organizations: [
      { id: 'org-001', organizationId: LCS_ORG_ID, branchId: BRANCH_BAVET_ID, organizationCode: 'LCS', legalName: 'LCS XING YUN LOGISTICS CO., LTD.', legalNameKh: 'អិលស៊ីអេស ស៊ីង យ៊ុន ឡូជីស្ទីក ឯ.ក', displayName: 'LCS XINGYUN', taxIdentifier: 'K002-902601366', address: 'Address: National Road No. 1, Toul Ampil Village, Sangkat Chrok Mtes, Bavet City, Svay Rieng Province', addressKh: 'អាសយដ្ឋាន៖ ផ្លូវជាតិលេខ១ ភូមិទួលអំពិល សង្កាត់ច្រកម្ទេស ក្រុងបាវិត ខេត្តស្វាយរៀង', phone: '(+855) 97 78 70 445', email: 'chenzhenzhu5@gmail.com / Hengvanra67@gmail.com', country: 'Cambodia', defaultCurrency: 'USD', timezone: 'Asia/Phnom_Penh', status: 'Active' },
      { id: 'org-002', organizationId: DEMO_ORG_ID, branchId: BRANCH_DEMO_ID, organizationCode: 'DEMO', legalName: 'Demo Logistics Ltd.', displayName: 'Demo Logistics', taxIdentifier: 'K001-DEMO', country: 'Cambodia', defaultCurrency: 'USD', timezone: 'Asia/Phnom_Penh', status: 'Active' },
    ],
    branches: [
      stamp({ id: 'br-001', branchCode: 'BAV', name: 'Bavet', place: 'Bavet', address: 'National Road 1, Bavet', phone: '+855 44 555 101', email: 'bavet@lcs.local', headOffice: 'No', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'br-002', branchCode: 'PNH', name: 'Phnom Penh', place: 'Phnom Penh', address: 'Phnom Penh, Cambodia', phone: '+855 23 555 102', email: 'pnh@lcs.local', headOffice: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({ id: 'br-003', branchCode: 'HQ', name: 'Demo HQ', place: 'Phnom Penh', address: 'Demo address', headOffice: 'Yes', status: 'Active' } as FreightRecord, DEMO_ORG_ID, BRANCH_DEMO_ID),
    ],
    businessParties: [
      ...stampAll(base.companies, LCS_ORG_ID, BRANCH_BAVET_ID).map(row => ({ ...row, partyCode: row.code, legalName: row.name, displayName: row.factoryName || row.name, roles: ['Customer'], country: 'Cambodia', taxIdentifier: row.patentNo, contactPerson: row.contact })),
      ...stampAll(base.suppliers, LCS_ORG_ID, BRANCH_BAVET_ID).map(row => ({ ...row, partyCode: row.code, legalName: row.name, displayName: row.name, roles: ['Supplier', ...(String(row.serviceType || '').includes('Trucking') ? ['Carrier', 'Transport Operator'] : [])], country: String(row.address || '').includes('Vietnam') || String(row.email || '').endsWith('.vn') ? 'Vietnam' : 'Cambodia', taxIdentifier: row.taxNo, contactPerson: row.contact })),
    ],
    places: stampAll(base.locations, LCS_ORG_ID, BRANCH_BAVET_ID).map(row => ({ ...row, category: row.category === 'Border' ? 'Border Checkpoint' : row.category })),
    tradeDirections: [
      stamp({ id: 'td-001', code: 'IMPORT', name: 'Import', description: 'Goods enter Cambodia', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'td-002', code: 'EXPORT', name: 'Export', description: 'Goods leave Cambodia', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'td-003', code: 'TRANSIT', name: 'Transit', description: 'Goods pass through the country', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'td-004', code: 'RE_EXPORT', name: 'Re-export', description: 'Previously imported goods leave the country', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    containerTypes: [
      ['20DV', '20-foot Dry Van', '22G1', '20FT', 'Dry', 20],
      ['40DV', '40-foot Dry Van', '42G1', '40FT', 'Dry', 40],
      ['40HC', '40-foot High Cube', '45G1', '40FT', 'High Cube', 40],
      ['40RF', '40-foot Reefer', '45R1', '40FT', 'Reefer', 40],
    ].map((row, index) => stamp({ id: `ct-${index + 1}`, code: row[0], name: row[1], isoCode: row[2], size: row[3], kind: row[4], lengthFeet: row[5], widthMeters: 2.44, heightMeters: String(row[4]).includes('High') ? 2.90 : 2.59, maxGrossWeightKg: 30480, description: `${row[1]} ISO container`, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID)),
    transportTypes: ['Truck', 'Vessel', 'Air', 'Rail', 'Multimodal'].map((name, index) => stamp({ id: `tt-${index + 1}`, code: name.toUpperCase(), name, description: `${name} transport`, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID)),
    transportAssets: [
      stamp({ id: 'ta-001', assetCode: 'TRK-001', transportType: 'Truck', identity: '3C-9088', identityType: 'License Plate', ownerParty: 'NTL Transport', operatorParty: 'NTL Transport', registrationCountry: 'Cambodia', description: '40T tractor head', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'ta-002', assetCode: 'TRK-002', transportType: 'Truck', identity: '3A-5512', identityType: 'License Plate', ownerParty: 'Golden Logistics', operatorParty: 'Golden Logistics', registrationCountry: 'Cambodia', description: '25T rigid truck', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'ta-003', assetCode: 'TRK-003', transportType: 'Truck', identity: '3B-7721', identityType: 'License Plate', ownerParty: 'Vanxuan Transport', operatorParty: 'Vanxuan Transport', registrationCountry: 'Vietnam', description: 'Cross-border tractor', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
    ],
    feeTypes: stampAll(base.chargeTypes, LCS_ORG_ID, BRANCH_BAVET_ID).map(row => ({ ...row, description: row.description || `${row.name} fee` })),
    componentGroups: [
      stamp({ id: 'cg-001', code: 'INVOICE', name: 'Invoice', description: 'Commercial invoice fields for the service order', displayOrder: 10, showOnJobWorkspace: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'cg-002', code: 'PACKING_LIST', name: 'Packing List', description: 'Packing list fields for the service order', displayOrder: 20, showOnJobWorkspace: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'cg-003', code: 'SHIPMENT_REGISTRATION', name: 'Shipment Registration Number', description: 'Shipment registration number and office', displayOrder: 30, showOnJobWorkspace: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'cg-004', code: 'BILL', name: 'Bill', description: 'Bill of lading / transport bill fields', displayOrder: 40, showOnJobWorkspace: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'cg-005', code: 'CUSTOMS', name: 'Customs', description: 'Customs declaration and clearance work', displayOrder: 50, showOnJobWorkspace: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'cg-006', code: 'TRANSPORT', name: 'Transport', description: 'Truck dispatch and border crossing execution', displayOrder: 60, showOnJobWorkspace: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    componentTemplates: [
      stamp({ id: 'tpl-001', code: 'COMMERCIAL_INVOICE', name: 'Commercial Invoice', group: 'INVOICE', version: '2026.08', direction: 'Import', required: 'Yes', repeatable: 'Yes', instanceMode: 'REPEATABLE', minimumInstances: 1, status: 'Active', attributes: [{ code: 'invoice_no', label: 'Invoice No.', dataType: 'Text', inputType: 'Text', required: 'Yes', displayOrder: 10, showInSummary: 'Yes', validation: '' }, { code: 'invoice_date', label: 'Invoice Date', dataType: 'Date', inputType: 'Date', required: 'Yes', displayOrder: 20, showInSummary: 'Yes', validation: '' }, { code: 'seller', label: 'Seller', dataType: 'Text', inputType: 'Text', required: 'No', displayOrder: 30, validation: '' }, { code: 'invoice_amount', label: 'Invoice Amount', dataType: 'Number', inputType: 'Currency', required: 'No', displayOrder: 40, validation: 'Minimum 0' }] } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tpl-002', code: 'PACKING_LIST', name: 'Packing List', group: 'PACKING_LIST', version: '2026.08', direction: 'Import', required: 'Yes', repeatable: 'Yes', instanceMode: 'REPEATABLE', minimumInstances: 1, status: 'Active', attributes: [{ code: 'packing_list_no', label: 'Packing List No.', dataType: 'Text', inputType: 'Text', required: 'Yes', displayOrder: 10, showInSummary: 'Yes', validation: '' }, { code: 'packages', label: 'Packages', dataType: 'Number', inputType: 'Number', required: 'No', displayOrder: 20, showInSummary: 'Yes', validation: '' }, { code: 'gross_weight', label: 'Gross Weight (kg)', dataType: 'Number', inputType: 'Number', required: 'No', displayOrder: 30, validation: '' }, { code: 'net_weight', label: 'Net Weight (kg)', dataType: 'Number', inputType: 'Number', required: 'No', displayOrder: 40, validation: '' }, { code: 'package_lines', label: 'Package Lines', dataType: 'Table', inputType: 'Table', required: 'No', displayOrder: 50, helpText: 'Add one row per package line on the packing list.', tableColumns: [{ key: 'description', label: 'Description', type: 'text', order: 1 }, { key: 'quantity', label: 'Qty', type: 'number', order: 2 }, { key: 'weight_kg', label: 'Weight (kg)', type: 'number', order: 3 }] }] } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tpl-003', code: 'SHIPMENT_REGISTRATION', name: 'Shipment Registration', group: 'SHIPMENT_REGISTRATION', version: '2026.08', direction: 'Import', required: 'Yes', repeatable: 'Yes', instanceMode: 'REPEATABLE', minimumInstances: 1, status: 'Active', attributes: [{ code: 'registration_no', label: 'Registration No.', dataType: 'Text', inputType: 'Text', required: 'Yes', displayOrder: 10, showInSummary: 'Yes', validation: '' }, { code: 'registered_at', label: 'Registered At', dataType: 'Date', inputType: 'Date', required: 'No', displayOrder: 20, showInSummary: 'Yes', validation: '' }, { code: 'issuing_office', label: 'Issuing Office', dataType: 'Text', inputType: 'Text', required: 'No', displayOrder: 30, validation: '' }] } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tpl-004', code: 'TRANSPORT_BILL', name: 'Bill', group: 'BILL', version: '2026.08', direction: 'Import', required: 'Yes', repeatable: 'Yes', instanceMode: 'REPEATABLE', minimumInstances: 1, status: 'Active', attributes: [{ code: 'bill_no', label: 'Bill / B/L No.', dataType: 'Text', inputType: 'Text', required: 'Yes', displayOrder: 10, showInSummary: 'Yes', validation: '' }, { code: 'bill_date', label: 'Bill Date', dataType: 'Date', inputType: 'Date', required: 'No', displayOrder: 20, showInSummary: 'Yes', validation: '' }, { code: 'carrier', label: 'Carrier', dataType: 'Text', inputType: 'Text', required: 'No', displayOrder: 30, validation: '' }] } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tpl-005', code: 'CUSTOMS_CLEARANCE', name: 'Customs Clearance', group: 'CUSTOMS', version: '2026.08', direction: 'Import', required: 'Yes', repeatable: 'Yes', instanceMode: 'REPEATABLE', minimumInstances: 1, status: 'Active', attributes: [{ code: 'declaration_no', label: 'Declaration No.', dataType: 'Text', inputType: 'Text', required: 'Yes', displayOrder: 10, showInSummary: 'Yes', validation: 'Unique within organization' }, { code: 'cleared_at', label: 'Cleared At', dataType: 'Date', inputType: 'Date', required: 'Yes', displayOrder: 20, showInSummary: 'Yes', validation: '' }, { code: 'customs_fee', label: 'Customs Fee', dataType: 'Number', inputType: 'Currency', required: 'No', displayOrder: 30, validation: 'Minimum 0' }] } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tpl-006', code: 'TRUCK_DISPATCH', name: 'Truck Dispatch', group: 'TRANSPORT', version: '2026.08', direction: 'Import', required: 'Yes', repeatable: 'Yes', instanceMode: 'REPEATABLE', minimumInstances: 1, status: 'Active', attributes: [{ code: 'truck_plate', label: 'Truck Plate', dataType: 'Text', inputType: 'Text', required: 'Yes', displayOrder: 10, showInSummary: 'Yes', validation: '' }, { code: 'driver_name', label: 'Driver Name', dataType: 'Text', inputType: 'Text', required: 'No', displayOrder: 20, showInSummary: 'Yes', validation: '' }, { code: 'driver_phone', label: 'Driver Phone', dataType: 'Text', inputType: 'Text', required: 'No', displayOrder: 30, validation: '' }, { code: 'border_eta', label: 'Border ETA', dataType: 'Date', inputType: 'Date', required: 'No', displayOrder: 40, validation: '' }, { code: 'factory_eta', label: 'Factory ETA', dataType: 'Date', inputType: 'Date', required: 'No', displayOrder: 50, validation: '' }] } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ].map(row => ({
      ...row,
      instanceMode: row.instanceMode || 'SINGLE',
      minimumInstances: row.minimumInstances ?? (row.required === 'Yes' ? 1 : 0),
      description: row.description || `${row.name} component template`,
      attributeCount: Array.isArray(row.attributes) ? row.attributes.length : 0,
      attributes: (Array.isArray(row.attributes) ? row.attributes as Array<Record<string, unknown>> : []).map((attribute) => {
        const helpByCode: Record<string, string> = {
          invoice_no: 'Commercial invoice number for this shipment.',
          invoice_date: 'Date printed on the commercial invoice.',
          seller: 'Seller or shipper named on the invoice.',
          invoice_amount: 'Invoice amount. Must be zero or greater.',
          packing_list_no: 'Packing list number matching this cargo.',
          packages: 'Number of packages on the packing list.',
          gross_weight: 'Gross weight in kilograms.',
          net_weight: 'Net weight in kilograms.',
          registration_no: 'Official shipment registration number.',
          registered_at: 'Date the shipment was registered.',
          issuing_office: 'Office that issued the registration number.',
          bill_no: 'Bill of lading or transport bill number.',
          bill_date: 'Date the bill was issued.',
          carrier: 'Carrier named on the bill.',
          declaration_no: 'Customs declaration number for this clearance.',
          cleared_at: 'Date customs clearance was granted.',
          customs_fee: 'Customs fee amount. Must be zero or greater.',
          truck_plate: 'License plate of the assigned truck.',
          driver_name: 'Driver assigned to this movement.',
          driver_phone: 'Driver contact number for dispatch updates.',
          border_eta: 'Expected arrival at the border checkpoint.',
          factory_eta: 'Expected arrival at the factory or delivery point.',
        }
        const code = String(attribute.code || '')
        return {
          ...attribute,
          helpText: attribute.helpText || helpByCode[code] || `Enter the ${attribute.label || attribute.code} for this document.`,
          repeatable: attribute.repeatable || 'No',
          referenceType: attribute.referenceType || (attribute.dataType === 'Reference' ? attribute.validation : ''),
          validationRules: attribute.validationRules || attribute.validation || '',
          status: attribute.status || 'Active',
        }
      }),
    })),
    tradeDirectionComponents: [
      stamp({ id: 'tdc-001', tradeDirection: 'Import', componentGroup: 'Invoice', componentTemplate: 'Commercial Invoice', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 10, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-002', tradeDirection: 'Import', componentGroup: 'Packing List', componentTemplate: 'Packing List', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 20, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-003', tradeDirection: 'Import', componentGroup: 'Shipment Registration Number', componentTemplate: 'Shipment Registration', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 30, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-004', tradeDirection: 'Import', componentGroup: 'Bill', componentTemplate: 'Bill', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 40, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-005', tradeDirection: 'Import', componentGroup: 'Customs', componentTemplate: 'Customs Clearance', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 50, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-006', tradeDirection: 'Export', componentGroup: 'Invoice', componentTemplate: 'Commercial Invoice', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 10, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-007', tradeDirection: 'Export', componentGroup: 'Packing List', componentTemplate: 'Packing List', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 20, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-008', tradeDirection: 'Export', componentGroup: 'Shipment Registration Number', componentTemplate: 'Shipment Registration', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 30, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-009', tradeDirection: 'Export', componentGroup: 'Bill', componentTemplate: 'Bill', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 40, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-010', tradeDirection: 'Export', componentGroup: 'Customs', componentTemplate: 'Customs Clearance', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 50, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-011', tradeDirection: 'Import', componentGroup: 'Transport', componentTemplate: 'Truck Dispatch', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 60, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'tdc-012', tradeDirection: 'Export', componentGroup: 'Transport', componentTemplate: 'Truck Dispatch', templateVersion: '2026.08', required: 'Yes', repeatable: 'No', displayOrder: 60, status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ].map(row => ({ ...row, instanceModeOverride: 'INHERIT' })),
    postingRules: [
      stamp({ id: 'pr-001', documentType: 'CUSTOMER_INVOICE', feeType: 'FREIGHT_SERVICE', debitAccount: '1100 · Accounts Receivable', creditAccount: '4010 · Service Revenue', taxAccount: '2020 · Output Tax', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-002', documentType: 'SUPPLIER_BILL', feeType: 'TRANSPORT', debitAccount: '5010 · Transport Expense', creditAccount: '2010 · Accounts Payable', taxAccount: '1210 · Input Tax', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-003', documentType: 'SUPPLIER_BILL', feeType: 'CUSTOMS_CLEARANCE', debitAccount: '5020 · Customs Expense', creditAccount: '2010 · Accounts Payable', taxAccount: '1210 · Input Tax', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-004', documentType: 'CUSTOMER_RECEIPT', feeType: 'BANK_TRANSFER', debitAccount: '1020 · Bank Account', creditAccount: '1100 · Accounts Receivable', taxAccount: '', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-005', documentType: 'CUSTOMER_RECEIPT', feeType: 'CASH', debitAccount: '1010 · Cash on Hand', creditAccount: '1100 · Accounts Receivable', taxAccount: '', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-006', documentType: 'SUPPLIER_PAYMENT', feeType: 'BANK_TRANSFER', debitAccount: '2010 · Accounts Payable', creditAccount: '1020 · Bank Account', taxAccount: '', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-007', documentType: 'SUPPLIER_PAYMENT', feeType: 'CASH', debitAccount: '2010 · Accounts Payable', creditAccount: '1010 · Cash on Hand', taxAccount: '', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-008', documentType: 'SERVICE_CHARGE', feeType: 'INLAND_TRANSPORT', debitAccount: '1100 · Accounts Receivable', creditAccount: '4010 · Service Revenue', taxAccount: '2020 · Output Tax', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'pr-009', documentType: 'SUPPLIER_BILL', feeType: 'VIETNAM_SERVICE', debitAccount: '5010 · Transport Expense', creditAccount: '2010 · Accounts Payable', taxAccount: '1210 · Input Tax', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    documentSequences: [
      ...['QUOTATION', 'SERVICE_ORDER', 'SERVICE_CHARGE', 'CUSTOMER_INVOICE', 'SUPPLIER_BILL', 'CUSTOMER_RECEIPT', 'SUPPLIER_PAYMENT', 'JOURNAL'].map((documentType, index) => stamp({
        id: `seq-${index + 1}`,
        documentType,
        year: 2026,
        prefix: ['Q', 'SO', 'SC', 'INV', 'BILL', 'REC', 'PAY', 'JE'][index],
        lastValue: 40 + index,
        paddingLength: 6,
        status: 'ACTIVE',
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID)),
    ],
    systemSettings: [
      stamp({ id: 'set-001', organizationName: 'LCS Freight', branchName: '', settingKey: 'default_currency', settingValue: 'USD', displayValue: 'USD', scope: 'Organization', sensitive: 'No', updatedBy: 'System Administrator', updatedAt: '2026-08-20T08:00:00' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'set-002', organizationName: 'LCS Freight', branchName: 'Bavet', settingKey: 'invoice_approval_limit', settingValue: '5000', displayValue: '5,000 USD', scope: 'Bavet', sensitive: 'No', updatedBy: 'Finance Manager', updatedAt: '2026-08-19T15:20:00' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'set-003', organizationName: 'LCS Freight', branchName: '', settingKey: 'smtp_password', settingValue: '••••••••', displayValue: '••••••••', scope: 'Organization', sensitive: 'Yes', updatedBy: 'System Administrator', updatedAt: '2026-08-18T10:10:00' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    chartOfAccounts: [
      ['1010', 'Cash on Hand', 'Asset', 'Debit'], ['1020', 'Bank Account', 'Asset', 'Debit'], ['1100', 'Accounts Receivable', 'Asset', 'Debit'], ['1210', 'Input Tax', 'Asset', 'Debit'], ['1200', 'Prepayments', 'Asset', 'Debit'], ['2010', 'Accounts Payable', 'Liability', 'Credit'], ['2020', 'Output Tax', 'Liability', 'Credit'], ['3010', 'Owner Equity', 'Equity', 'Credit'], ['4010', 'Service Revenue', 'Revenue', 'Credit'], ['4020', 'Other Income', 'Revenue', 'Credit'], ['5010', 'Transport Expense', 'Expense', 'Debit'], ['5020', 'Customs Expense', 'Expense', 'Debit'], ['5030', 'Office Expense', 'Expense', 'Debit'], ['5040', 'Bank Charges', 'Expense', 'Debit'],
    ].map((row, index) => stamp({ id: `coa-${index + 1}`, accountCode: row[0], accountName: row[1], accountType: row[2], normalBalance: row[3], parentCode: '', postable: 'Yes', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID)),
    financialAccounts: [
      stamp({ id: 'fa-001', accountName: 'ABA Bavet Operating', accountType: 'Bank', ledgerCode: '1020', currency: 'USD', bankName: 'ABA Bank', accountNumberMasked: '****1234', balance: 40900, branchName: 'Bavet', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'fa-002', accountName: 'Cash on Hand — Bavet', accountType: 'Cash', ledgerCode: '1010', currency: 'USD', bankName: '', accountNumberMasked: '', balance: 2700, branchName: 'Bavet', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'fa-003', accountName: 'LCS XING YUN LOGISTICS CO., LTD.', accountType: 'Bank', ledgerCode: '1020', currency: 'USD', bankName: 'ACLEDA Bank Plc', accountNumberMasked: '34050631801412', swiftCode: 'ACLBKHPP', balance: 1375, branchName: 'Phnom Penh', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({ id: 'fa-004', accountName: 'Canadia USD — Bavet', accountType: 'Bank', ledgerCode: '1020', currency: 'USD', bankName: 'Canadia Bank', accountNumberMasked: '****9012', balance: 8500, branchName: 'Bavet', status: 'Active' } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    containerRequirements,
    actualContainers,
    serviceComponents: [
      stamp({
        id: id('cmp', 1),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'CUSTOMS_CLEARANCE',
        templateVersion: '2026.04',
        latestTemplateVersion: '2026.08',
        groupCode: 'CUSTOMS',
        status: 'COMPLETED',
        required: true,
        sequenceNo: 5,
        values: [
          { code: 'declaration_no', label: 'Declaration No.', dataType: 'text', required: true, valueText: 'SAD-IM-008821', helpText: 'Customs declaration number for this clearance.' },
          { code: 'cleared_at', label: 'Cleared At', dataType: 'date', required: true, valueDate: '2026-08-20', helpText: 'Date customs clearance was granted.' },
          { code: 'customs_fee', label: 'Customs Fee', dataType: 'number', required: false, valueNumber: 120, helpText: 'Customs fee amount. Must be zero or greater.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 2),
        jobNo: 'LCS-EX-260820',
        serviceOrderId: 'job-002',
        templateCode: 'COMMERCIAL_INVOICE',
        templateVersion: '2026.06',
        latestTemplateVersion: '2026.08',
        groupCode: 'INVOICE',
        status: 'PENDING',
        required: true,
        sequenceNo: 1,
        values: [
          { code: 'invoice_no', label: 'Invoice No.', dataType: 'text', required: true, valueText: '', helpText: 'Commercial invoice number for this shipment.' },
          { code: 'invoice_date', label: 'Invoice Date', dataType: 'date', required: true, valueDate: '', helpText: 'Date printed on the commercial invoice.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 3),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'COMMERCIAL_INVOICE',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'INVOICE',
        status: 'PENDING',
        required: true,
        sequenceNo: 1,
        values: [
          { code: 'invoice_no', label: 'Invoice No.', dataType: 'text', required: true, valueText: 'INV-2608-118', helpText: 'Commercial invoice number for this shipment.' },
          { code: 'invoice_date', label: 'Invoice Date', dataType: 'date', required: true, valueDate: '2026-08-18', helpText: 'Date printed on the commercial invoice.' },
          { code: 'seller', label: 'Seller', dataType: 'text', required: false, valueText: 'Cat Lai Supplier', helpText: 'Seller or shipper named on the invoice.' },
          { code: 'invoice_amount', label: 'Invoice Amount', dataType: 'number', required: false, valueNumber: 18500, helpText: 'Invoice amount. Must be zero or greater.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 8),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'COMMERCIAL_INVOICE',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'INVOICE',
        status: 'PENDING',
        required: true,
        resolvedInstanceMode: 'REPEATABLE',
        sequenceNo: 2,
        values: [
          { code: 'invoice_no', label: 'Invoice No.', dataType: 'text', required: true, valueText: 'INV-2608-118-B', helpText: 'Commercial invoice number for this shipment.' },
          { code: 'invoice_date', label: 'Invoice Date', dataType: 'date', required: true, valueDate: '2026-08-19', helpText: 'Date printed on the commercial invoice.' },
          { code: 'seller', label: 'Seller', dataType: 'text', required: false, valueText: 'Second Supplier', helpText: 'Seller or shipper named on the invoice.' },
          { code: 'invoice_amount', label: 'Invoice Amount', dataType: 'number', required: false, valueNumber: 4200, helpText: 'Invoice amount. Must be zero or greater.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 4),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'PACKING_LIST',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'PACKING_LIST',
        status: 'PENDING',
        required: true,
        sequenceNo: 2,
        values: [
          { code: 'packing_list_no', label: 'Packing List No.', dataType: 'text', required: true, valueText: 'PL-2608-118', helpText: 'Packing list number matching this cargo.' },
          { code: 'packages', label: 'Packages', dataType: 'number', required: false, valueNumber: 18, helpText: 'Number of packages on the packing list.' },
          { code: 'gross_weight', label: 'Gross Weight (kg)', dataType: 'number', required: false, valueNumber: 21800, helpText: 'Gross weight in kilograms.' },
          { code: 'net_weight', label: 'Net Weight (kg)', dataType: 'number', required: false, valueNumber: 20150, helpText: 'Net weight in kilograms.' },
          { code: 'package_lines', label: 'Package Lines', dataType: 'table', inputType: 'table', required: false, helpText: 'Add one row per package line on the packing list.', tableColumns: [{ key: 'description', label: 'Description', type: 'text', order: 1 }, { key: 'quantity', label: 'Qty', type: 'number', order: 2 }, { key: 'weight_kg', label: 'Weight (kg)', type: 'number', order: 3 }], valueJson: [{ description: 'Cartons on pallet A', quantity: 10, weight_kg: 9800 }, { description: 'Cartons on pallet B', quantity: 8, weight_kg: 12000 }] },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 5),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'SHIPMENT_REGISTRATION',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'SHIPMENT_REGISTRATION',
        status: 'PENDING',
        required: true,
        sequenceNo: 3,
        values: [
          { code: 'registration_no', label: 'Registration No.', dataType: 'text', required: true, valueText: 'REG-8821', helpText: 'Official shipment registration number.' },
          { code: 'registered_at', label: 'Registered At', dataType: 'date', required: false, valueDate: '2026-08-20', helpText: 'Date the shipment was registered.' },
          { code: 'issuing_office', label: 'Issuing Office', dataType: 'text', required: false, valueText: 'Bavet', helpText: 'Office that issued the registration number.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 6),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'TRANSPORT_BILL',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'BILL',
        status: 'PENDING',
        required: true,
        sequenceNo: 4,
        values: [
          { code: 'bill_no', label: 'Bill / B/L No.', dataType: 'text', required: true, valueText: 'EGLV-8821907', helpText: 'Bill of lading or transport bill number.' },
          { code: 'bill_date', label: 'Bill Date', dataType: 'date', required: false, valueDate: '2026-08-19', helpText: 'Date the bill was issued.' },
          { code: 'carrier', label: 'Carrier', dataType: 'text', required: false, valueText: 'NTL Transport', helpText: 'Carrier named on the bill.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 7),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'TRUCK_DISPATCH',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'TRANSPORT',
        status: 'COMPLETED',
        required: true,
        sequenceNo: 6,
        values: [
          { code: 'truck_plate', label: 'Truck Plate', dataType: 'text', required: true, valueText: '3C-9088', helpText: 'License plate of the assigned truck.' },
          { code: 'driver_name', label: 'Driver Name', dataType: 'text', required: false, valueText: 'Vannak', helpText: 'Driver assigned to this movement.' },
          { code: 'driver_phone', label: 'Driver Phone', dataType: 'text', required: false, valueText: '+855 12 900 111', helpText: 'Driver contact number for dispatch updates.' },
          { code: 'border_eta', label: 'Border ETA', dataType: 'date', required: false, valueDate: '2026-08-20', helpText: 'Expected arrival at the border checkpoint.' },
          { code: 'factory_eta', label: 'Factory ETA', dataType: 'date', required: false, valueDate: '2026-08-21', helpText: 'Expected arrival at the factory or delivery point.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 9),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'PACKING_LIST',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'PACKING_LIST',
        status: 'PENDING',
        required: true,
        resolvedInstanceMode: 'REPEATABLE',
        sequenceNo: 7,
        values: [
          { code: 'packing_list_no', label: 'Packing List No.', dataType: 'text', required: true, valueText: 'PL-2608-119', helpText: 'Packing list number matching this cargo.' },
          { code: 'packages', label: 'Packages', dataType: 'number', required: false, valueNumber: 12, helpText: 'Number of packages on the packing list.' },
          { code: 'gross_weight', label: 'Gross Weight (kg)', dataType: 'number', required: false, valueNumber: 14200, helpText: 'Gross weight in kilograms.' },
          { code: 'net_weight', label: 'Net Weight (kg)', dataType: 'number', required: false, valueNumber: 13100, helpText: 'Net weight in kilograms.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 10),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'SHIPMENT_REGISTRATION',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'SHIPMENT_REGISTRATION',
        status: 'PENDING',
        required: true,
        resolvedInstanceMode: 'REPEATABLE',
        sequenceNo: 8,
        values: [
          { code: 'registration_no', label: 'Registration No.', dataType: 'text', required: true, valueText: 'REG-8822', helpText: 'Official shipment registration number.' },
          { code: 'registered_at', label: 'Registered At', dataType: 'date', required: false, valueDate: '2026-08-21', helpText: 'Date the shipment was registered.' },
          { code: 'issuing_office', label: 'Issuing Office', dataType: 'text', required: false, valueText: 'Phnom Penh', helpText: 'Office that issued the registration number.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 11),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'TRANSPORT_BILL',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'BILL',
        status: 'PENDING',
        required: true,
        resolvedInstanceMode: 'REPEATABLE',
        sequenceNo: 9,
        values: [
          { code: 'bill_no', label: 'Bill / B/L No.', dataType: 'text', required: true, valueText: 'EGLV-8821908', helpText: 'Bill of lading or transport bill number.' },
          { code: 'bill_date', label: 'Bill Date', dataType: 'date', required: false, valueDate: '2026-08-20', helpText: 'Date the bill was issued.' },
          { code: 'carrier', label: 'Carrier', dataType: 'text', required: false, valueText: 'Evergreen Line', helpText: 'Carrier named on the bill.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 12),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'CUSTOMS_CLEARANCE',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'CUSTOMS',
        status: 'PENDING',
        required: true,
        resolvedInstanceMode: 'REPEATABLE',
        sequenceNo: 10,
        values: [
          { code: 'declaration_no', label: 'Declaration No.', dataType: 'text', required: true, valueText: 'SAD-IM-008822', helpText: 'Customs declaration number for this clearance.' },
          { code: 'cleared_at', label: 'Cleared At', dataType: 'date', required: true, valueDate: '', helpText: 'Date customs clearance was granted.' },
          { code: 'customs_fee', label: 'Customs Fee', dataType: 'number', required: false, valueNumber: 0, helpText: 'Customs fee amount. Must be zero or greater.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: id('cmp', 13),
        jobNo: 'LCS-IM-260821',
        serviceOrderId: 'job-001',
        templateCode: 'TRUCK_DISPATCH',
        templateVersion: '2026.08',
        latestTemplateVersion: '2026.08',
        groupCode: 'TRANSPORT',
        status: 'PENDING',
        required: true,
        resolvedInstanceMode: 'REPEATABLE',
        sequenceNo: 11,
        values: [
          { code: 'truck_plate', label: 'Truck Plate', dataType: 'text', required: true, valueText: '2A-7711', helpText: 'License plate of the assigned truck.' },
          { code: 'driver_name', label: 'Driver Name', dataType: 'text', required: false, valueText: 'Sokha', helpText: 'Driver assigned to this movement.' },
          { code: 'driver_phone', label: 'Driver Phone', dataType: 'text', required: false, valueText: '+855 12 900 222', helpText: 'Driver contact number for dispatch updates.' },
          { code: 'border_eta', label: 'Border ETA', dataType: 'date', required: false, valueDate: '2026-08-22', helpText: 'Expected arrival at the border checkpoint.' },
          { code: 'factory_eta', label: 'Factory ETA', dataType: 'date', required: false, valueDate: '2026-08-23', helpText: 'Expected arrival at the factory or delivery point.' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    accountingPeriods: [
      stamp({
        id: 'per-001',
        code: '2026-07',
        name: 'July 2026',
        startDate: '2026-07-01',
        endDate: '2026-07-31',
        status: 'CLOSED',
        year: 2026, month: 7, postingCount: 48, closedBy: 'Finance Manager', closedAt: '2026-08-03T17:00:00',
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: 'per-002',
        code: '2026-08',
        name: 'August 2026',
        startDate: '2026-08-01',
        endDate: '2026-08-31',
        status: 'OPEN',
        year: 2026, month: 8, postingCount: 26, closedBy: '', closedAt: '',
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    journals: [
      stamp({
        id: 'je-open',
        entryNo: 'JE-2026-0001',
        entryType: 'MANUAL', entryDate: '2026-08-01', postingDate: '2026-08-01', periodName: 'August 2026', branchName: 'Bavet', description: 'Opening cash and bank balances', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-01T08:00:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentNo: 'OPEN-2026-08',
        periodId: 'per-002',
        debitTotal: 44500,
        creditTotal: 44500,
        lines: [
          { lineNo: 1, account_code: '1020', account_name: 'Bank Account', party: '', branch: 'Bavet', debit_amount: 42000, credit_amount: 0, currency: 'USD', description: 'Opening bank balance' },
          { lineNo: 2, account_code: '1010', account_name: 'Cash on Hand', party: '', branch: 'Bavet', debit_amount: 2500, credit_amount: 0, currency: 'USD', description: 'Opening cash balance' },
          { lineNo: 3, account_code: '3010', account_name: 'Owner Equity', party: '', branch: 'Bavet', debit_amount: 0, credit_amount: 44500, currency: 'USD', description: 'Opening equity offset' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: 'je-007',
        entryNo: 'JE-2026-0035',
        entryType: 'AUTOMATIC', entryDate: '2026-08-16', postingDate: '2026-08-16', periodName: 'August 2026', branchName: 'Bavet', description: 'Supplier payment SP-2608-019', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-16T14:10:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'sp-003',
        sourceDocumentNo: 'SP-2608-019',
        jobNo: 'LCS-IM-260816',
        periodId: 'per-002',
        debitTotal: 980,
        creditTotal: 980,
        lines: [
          { lineNo: 1, account_code: '2010', account_name: 'Accounts Payable', party: 'NTL Transport', branch: 'Bavet', serviceOrder: 'LCS-IM-260816', financialDocument: 'SP-2608-019', debit_amount: 980, credit_amount: 0, currency: 'USD', description: 'Supplier payment to NTL Transport' },
          { lineNo: 2, account_code: '1020', account_name: 'Bank Account', party: 'NTL Transport', branch: 'Bavet', serviceOrder: 'LCS-IM-260816', financialDocument: 'SP-2608-019', debit_amount: 0, credit_amount: 980, currency: 'USD', description: 'Bank transfer SP-2608-019' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: 'je-003',
        entryNo: 'JE-2026-0037',
        entryType: 'AUTOMATIC', entryDate: '2026-08-18', postingDate: '2026-08-18', periodName: 'August 2026', branchName: 'Phnom Penh', description: 'Customer receipt PAY-2608-026', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-18T16:05:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'cp-003',
        sourceDocumentNo: 'PAY-2608-026',
        jobNo: 'LCS-IM-260819',
        periodId: 'per-002',
        debitTotal: 1375,
        creditTotal: 1375,
        lines: [
          { lineNo: 1, account_code: '1020', account_name: 'Bank Account', party: 'Royal Group Manufacturing', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'PAY-2608-026', debit_amount: 1375, credit_amount: 0, currency: 'USD', description: 'Customer receipt PAY-2608-026' },
          { lineNo: 2, account_code: '1100', account_name: 'Accounts Receivable', party: 'Royal Group Manufacturing', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'DN-2608-039', debit_amount: 0, credit_amount: 1375, currency: 'USD', description: 'Allocation DN-2608-039' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({
        id: 'je-006',
        entryNo: 'JE-2026-0038',
        entryType: 'AUTOMATIC', entryDate: '2026-08-18', postingDate: '2026-08-18', periodName: 'August 2026', branchName: 'Phnom Penh', description: 'Supplier payment SP-2608-020', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-18T17:20:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'sp-002',
        sourceDocumentNo: 'SP-2608-020',
        jobNo: 'LCS-IM-260819',
        periodId: 'per-002',
        debitTotal: 300,
        creditTotal: 300,
        lines: [
          { lineNo: 1, account_code: '2010', account_name: 'Accounts Payable', party: 'Vanxuan Transport', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'SP-2608-020', debit_amount: 300, credit_amount: 0, currency: 'USD', description: 'Supplier payment Vanxuan Transport' },
          { lineNo: 2, account_code: '1010', account_name: 'Cash on Hand', party: 'Vanxuan Transport', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'SP-2608-020', debit_amount: 0, credit_amount: 300, currency: 'USD', description: 'Cash payment SP-2608-020' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({
        id: 'je-011',
        entryNo: 'JE-2026-0036',
        entryType: 'AUTOMATIC', entryDate: '2026-08-18', postingDate: '2026-08-18', periodName: 'August 2026', branchName: 'Phnom Penh', description: 'Supplier bill SUP-VX-8852', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-18T11:00:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentNo: 'SUP-VX-8852',
        jobNo: 'LCS-IM-260819',
        periodId: 'per-002',
        debitTotal: 610,
        creditTotal: 610,
        lines: [
          { lineNo: 1, account_code: '5010', account_name: 'Transport Expense', party: 'Vanxuan Transport', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'SUP-VX-8852', debit_amount: 610, credit_amount: 0, currency: 'USD', description: 'Vietnam port and border handling' },
          { lineNo: 2, account_code: '2010', account_name: 'Accounts Payable', party: 'Vanxuan Transport', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'SUP-VX-8852', debit_amount: 0, credit_amount: 610, currency: 'USD', description: 'Supplier bill SUP-VX-8852' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({
        id: 'je-002',
        entryNo: 'JE-2026-0039',
        entryType: 'AUTOMATIC', entryDate: '2026-08-18', postingDate: '2026-08-18', periodName: 'August 2026', branchName: 'Phnom Penh', description: 'Customer invoice DN-2608-039', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-18T15:30:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'dn-003',
        sourceDocumentNo: 'DN-2608-039',
        jobNo: 'LCS-IM-260819',
        periodId: 'per-002',
        debitTotal: 1375,
        creditTotal: 1375,
        lines: [
          { lineNo: 1, account_code: '1100', account_name: 'Accounts Receivable', party: 'Royal Group Manufacturing', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'DN-2608-039', debit_amount: 1375, credit_amount: 0, currency: 'USD', description: 'Customer invoice DN-2608-039' },
          { lineNo: 2, account_code: '4010', account_name: 'Service Revenue', party: 'Royal Group Manufacturing', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'DN-2608-039', debit_amount: 0, credit_amount: 1250, currency: 'USD', description: 'Freight service revenue' },
          { lineNo: 3, account_code: '2020', account_name: 'Output Tax', party: 'Royal Group Manufacturing', branch: 'Phnom Penh', serviceOrder: 'LCS-IM-260819', financialDocument: 'DN-2608-039', debit_amount: 0, credit_amount: 125, currency: 'USD', description: 'VAT 10%' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({
        id: 'je-005',
        entryNo: 'JE-2026-0040',
        entryType: 'AUTOMATIC', entryDate: '2026-08-19', postingDate: '2026-08-19', periodName: 'August 2026', branchName: 'Bavet', description: 'Supplier payment SP-2608-021', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-19T10:45:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'sp-001',
        sourceDocumentNo: 'SP-2608-021',
        jobNo: 'LCS-EX-260820',
        periodId: 'per-002',
        debitTotal: 320,
        creditTotal: 320,
        lines: [
          { lineNo: 1, account_code: '2010', account_name: 'Accounts Payable', party: 'Golden Logistics', branch: 'Bavet', serviceOrder: 'LCS-EX-260820', financialDocument: 'SP-2608-021', debit_amount: 320, credit_amount: 0, currency: 'USD', description: 'Supplier payment Golden Logistics' },
          { lineNo: 2, account_code: '1020', account_name: 'Bank Account', party: 'Golden Logistics', branch: 'Bavet', serviceOrder: 'LCS-EX-260820', financialDocument: 'SP-2608-021', debit_amount: 0, credit_amount: 320, currency: 'USD', description: 'Bank transfer SP-2608-021' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: 'je-004',
        entryNo: 'JE-2026-0042',
        entryType: 'AUTOMATIC', entryDate: '2026-08-19', postingDate: '2026-08-19', periodName: 'August 2026', branchName: 'Bavet', description: 'Customer receipt PAY-2608-027', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-19T15:10:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'cp-002',
        sourceDocumentNo: 'PAY-2608-027',
        jobNo: 'LCS-EX-260820',
        periodId: 'per-002',
        debitTotal: 500,
        creditTotal: 500,
        lines: [
          { lineNo: 1, account_code: '1010', account_name: 'Cash on Hand', party: 'Tai Seng Manufacturing', branch: 'Bavet', serviceOrder: 'LCS-EX-260820', financialDocument: 'PAY-2608-027', debit_amount: 500, credit_amount: 0, currency: 'USD', description: 'Cash receipt PAY-2608-027' },
          { lineNo: 2, account_code: '1100', account_name: 'Accounts Receivable', party: 'Tai Seng Manufacturing', branch: 'Bavet', serviceOrder: 'LCS-EX-260820', financialDocument: 'DN-2608-040', debit_amount: 0, credit_amount: 500, currency: 'USD', description: 'Partial allocation DN-2608-040' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: 'je-001',
        entryNo: 'JE-2026-0041',
        entryType: 'AUTOMATIC', entryDate: '2026-08-20', postingDate: '2026-08-20', periodName: 'August 2026', branchName: 'Bavet', description: 'Customer invoice DN-2608-041', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-20T11:40:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'dn-001',
        sourceDocumentNo: 'DN-2608-041',
        jobNo: 'LCS-IM-260821',
        periodId: 'per-002',
        debitTotal: 1622.5,
        creditTotal: 1622.5,
        lines: [
          { lineNo: 1, account_code: '1100', account_name: 'Accounts Receivable', party: 'Manhattan SEZ Co., Ltd.', branch: 'Bavet', serviceOrder: 'LCS-IM-260821', financialDocument: 'DN-2608-041', debit_amount: 1622.5, credit_amount: 0, currency: 'USD', description: 'Customer invoice DN-2608-041' },
          { lineNo: 2, account_code: '4010', account_name: 'Service Revenue', party: 'Manhattan SEZ Co., Ltd.', branch: 'Bavet', serviceOrder: 'LCS-IM-260821', financialDocument: 'DN-2608-041', debit_amount: 0, credit_amount: 1475, currency: 'USD', description: 'Freight service revenue' },
          { lineNo: 3, account_code: '2020', account_name: 'Output Tax', party: 'Manhattan SEZ Co., Ltd.', branch: 'Bavet', serviceOrder: 'LCS-IM-260821', financialDocument: 'DN-2608-041', debit_amount: 0, credit_amount: 147.5, currency: 'USD', description: 'VAT 10%' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: 'je-008',
        entryNo: 'JE-2026-0043',
        entryType: 'AUTOMATIC', entryDate: '2026-08-20', postingDate: '2026-08-20', periodName: 'August 2026', branchName: 'Bavet', description: 'Customer receipt partial PAY-2608-028', createdBy: 'Finance', postedBy: 'Finance Manager', postedAt: '2026-08-20T14:20:00', balanceDifference: 0,
        status: 'POSTED',
        sourceDocumentId: 'cp-001',
        sourceDocumentNo: 'PAY-2608-028',
        jobNo: 'LCS-IM-260821',
        periodId: 'per-002',
        debitTotal: 200,
        creditTotal: 200,
        lines: [
          { lineNo: 1, account_code: '1020', account_name: 'Bank Account', party: 'Manhattan SEZ Co., Ltd.', branch: 'Bavet', serviceOrder: 'LCS-IM-260821', financialDocument: 'PAY-2608-028', debit_amount: 200, credit_amount: 0, currency: 'USD', description: 'Partial bank receipt PAY-2608-028' },
          { lineNo: 2, account_code: '1100', account_name: 'Accounts Receivable', party: 'Manhattan SEZ Co., Ltd.', branch: 'Bavet', serviceOrder: 'LCS-IM-260821', financialDocument: 'DN-2608-041', debit_amount: 0, credit_amount: 200, currency: 'USD', description: 'Unallocated receipt on account' },
        ],
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    allocations: [
      stamp({
        id: id('al', 1),
        paymentId: 'cp-002',
        targetDocumentId: 'dn-002',
        amount: 500,
        currency: 'USD',
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    cashAccounts: [
      stamp({
        id: 'cash-001',
        name: 'ABA Bavet Operating',
        currency: 'USD',
        balance: 40900,
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({
        id: 'cash-002',
        name: 'ACLEDA Phnom Penh',
        currency: 'USD',
        balance: 1375,
      } as FreightRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({
        id: 'cash-003',
        name: 'Cash on Hand — Bavet',
        currency: 'USD',
        balance: 2700,
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
    uiSchemas: [
      stamp({
        id: 'ui-job-1',
        page: 'job-workspace',
        version: 3,
        note: 'Safe layout only. Cannot grant posting or bypass SENT/POSTED rules.',
      } as FreightRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
  }
}

export function jobWorkflowStatus(record: Record<string, unknown>) {
  return String(record.workflowStatus || JOB_WORKFLOW_BY_STATUS[String(record.status || '')] || 'OPEN')
}

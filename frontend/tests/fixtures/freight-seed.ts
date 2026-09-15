import { DEBIT_CHARGE_TYPES, JOB_CHECKLIST_TYPES, QUOTATION_CONDITIONS } from '~/config/freight-options'
import type { FreightRecord } from '~/types/freight/record'

export type { FreightRecord }

function id(prefix: string, n: number) {
  return `${prefix}-${String(n).padStart(3, '0')}`
}

function money(n: number) {
  return Number(n.toFixed(2))
}

function checklist(overrides: Record<string, string> = {}) {
  return JOB_CHECKLIST_TYPES.map(type => ({
    type,
    required: true,
    status: overrides[type] || 'Uploaded',
    remark: '',
  }))
}

function debitCharges(filled: Record<string, { cambodia?: number, vietnam?: number, cash?: number }>) {
  return DEBIT_CHARGE_TYPES.map(description => ({
    description,
    cambodia: filled[description]?.cambodia || 0,
    vietnam: filled[description]?.vietnam || 0,
    cash: filled[description]?.cash || 0,
    remark: '',
  }))
}

function quotationConditions() {
  return QUOTATION_CONDITIONS.map(condition => ({
    condition,
    description: condition,
    amount: '',
    unit: '',
    remark: 'Charged separately if required',
  }))
}

export function createFreightSeed(): Record<string, FreightRecord[]> {
  const companies: FreightRecord[] = [
    { id: id('co', 1), code: 'LCS-001', factoryName: 'Manhattan Factory', name: 'Manhattan SEZ Co., Ltd.', zone: 'Manhattan SEZ', patentNo: 'PAT-24018', contact: 'Sok Dara', phone: '+855 12 345 678', email: 'dara@manhattan.com.kh', address: 'Manhattan SEZ, Bavet, Svay Rieng', customsAccount: 'CA-MH-018', customsUsername: 'manhattan.ops', credentialReference: 'CRED-MH-018', patent: 'PAT-24018', direction: 'Import', containerType: '40HC', truckType: '8T', defaultZone: 'Manhattan SEZ', deliveryLocation: 'Manhattan Factory Gate 2', status: 'Active' },
    { id: id('co', 2), code: 'LCS-002', factoryName: 'Tai Seng Factory', name: 'Tai Seng Manufacturing', zone: 'Bavet SEZ', patentNo: 'PAT-24031', contact: 'Chan Sopheak', phone: '+855 16 778 899', email: 'sopheak@taiseng.com.kh', address: 'Tai Seng SEZ, Bavet', customsAccount: 'CA-TS-031', customsUsername: 'taiseng.ops', credentialReference: 'CRED-TS-031', patent: 'PAT-24031', direction: 'Export', containerType: '20GP', truckType: '5T', defaultZone: 'Bavet SEZ', deliveryLocation: 'Tai Seng Warehouse A', status: 'Active' },
    { id: id('co', 3), code: 'LCS-003', factoryName: 'Royal Factory', name: 'Royal Group Manufacturing', zone: 'Phnom Penh SEZ', patentNo: 'PAT-24052', contact: 'Kim Lina', phone: '+855 10 554 433', email: 'lina@royal.com.kh', address: 'PPSEZ, Khan Prek Pnov', customsAccount: 'CA-RG-052', customsUsername: 'royal.ops', credentialReference: 'CRED-RG-052', patent: 'PAT-24052', direction: 'Import', containerType: '40GP', truckType: '8T', defaultZone: 'Phnom Penh SEZ', deliveryLocation: 'Royal Factory Dock 1', status: 'Active' },
    { id: id('co', 4), code: 'LCS-004', factoryName: 'QiLu Plant', name: 'QiLu Cambodia Co., Ltd.', zone: 'Manhattan SEZ', patentNo: 'PAT-24067', contact: 'Ly Vannak', phone: '+855 12 889 221', email: 'vannak@qilu.com.kh', address: 'Manhattan SEZ, Bavet', customsAccount: 'CA-QL-067', customsUsername: 'qilu.ops', credentialReference: 'CRED-QL-067', patent: 'PAT-24067', direction: 'Import', containerType: '40HC', truckType: '8T', defaultZone: 'Manhattan SEZ', deliveryLocation: 'QiLu Plant Yard', status: 'Active' },
    { id: id('co', 5), code: 'LCS-005', factoryName: 'Dragon Well', name: 'Dragon Well Garment', zone: 'Tai Seng SEZ', patentNo: 'PAT-24088', contact: 'Pich Sreyneang', phone: '+855 15 332 110', email: 'sreyneang@dragonwell.com.kh', address: 'Tai Seng SEZ, Bavet', customsAccount: 'CA-DW-088', customsUsername: 'dragon.ops', credentialReference: 'CRED-DW-088', patent: 'PAT-24088', direction: 'Export', containerType: '40HC', truckType: '5T', defaultZone: 'Tai Seng SEZ', deliveryLocation: 'Dragon Well Loading Bay', status: 'Inactive' },
  ]

  const suppliers: FreightRecord[] = [
    { id: id('sup', 1), code: 'SUP-NTL', name: 'NTL Transport', contact: 'Mr. Narin', phone: '+855 12 111 222', email: 'narin@ntl.com.kh', address: 'Bavet, Svay Rieng', taxNo: 'VAT-NTL-01', currency: 'USD', paymentTerms: '15 days', serviceType: ['Trucking', 'Container Service'], bankName: 'ABA Bank', accountName: 'NTL Transport', accountNumber: '000 123 456', paymentCurrency: 'USD', bankTerms: '15 days', status: 'Active' },
    { id: id('sup', 2), code: 'SUP-GLD', name: 'Golden Logistics', contact: 'Ms. Leakhena', phone: '+855 16 333 444', email: 'leakhena@golden.com.kh', address: 'Phnom Penh', taxNo: 'VAT-GLD-02', currency: 'USD', paymentTerms: '30 days', serviceType: ['Customs', 'Cambodia Service'], bankName: 'ACLEDA', accountName: 'Golden Logistics', accountNumber: '000 222 333', paymentCurrency: 'USD', bankTerms: '30 days', status: 'Active' },
    { id: id('sup', 3), code: 'SUP-T1', name: 'TOP1 Service', contact: 'Mr. Huy', phone: '+84 90 111 222', email: 'huy@top1.vn', address: 'Moc Bai, Tay Ninh', taxNo: 'VAT-T1-03', currency: 'USD', paymentTerms: '15 days', serviceType: ['Vietnam Service', 'Customs'], bankName: 'Vietcombank', accountName: 'TOP1 Service', accountNumber: '007 889 221', paymentCurrency: 'USD', bankTerms: '15 days', status: 'Active' },
    { id: id('sup', 4), code: 'SUP-VX', name: 'Vanxuan Transport', contact: 'Mr. Tuan', phone: '+84 91 555 666', email: 'tuan@vanxuan.vn', address: 'Cat Lai, HCMC', taxNo: 'VAT-VX-04', currency: 'USD', paymentTerms: 'Cash', serviceType: ['Trucking', 'Vietnam Service'], bankName: 'Techcombank', accountName: 'Vanxuan Transport', accountNumber: '009 441 882', paymentCurrency: 'USD', bankTerms: 'Cash', status: 'Active' },
    { id: id('sup', 5), code: 'SUP-PAL', name: 'PAL Logistics', contact: 'Ms. Reatry', phone: '+855 10 777 888', email: 'reatry@pal.com.kh', address: 'Bavet', taxNo: 'VAT-PAL-05', currency: 'USD', paymentTerms: '7 days', serviceType: ['Trucking', 'Other'], bankName: 'Canadia Bank', accountName: 'PAL Logistics', accountNumber: '000 555 121', paymentCurrency: 'USD', bankTerms: '7 days', status: 'Active' },
  ]

  const quotations: FreightRecord[] = [
    { id: id('qt', 1), quotationNo: 'QT-2026-0812', date: '2026-08-12', customer: 'Manhattan SEZ Co., Ltd.', attention: 'Ms. Lina', phone: '+855 12 345 678', email: 'dara@manhattan.com.kh', direction: 'Import', pickup: 'CATLAI', border: 'MOC BAI / BAVET', delivery: 'MANHATTAN', transportBy: 'Truck', route: 'CATLAI → MOC BAI / BAVET → MANHATTAN', validUntil: '2026-09-15', currency: 'USD', amount: 2850, status: 'Accepted', buying20: 980, selling20: 1250, currency20: 'USD', buying40: 1480, selling40: 1850, currency40: 'USD', buying45: 1680, selling45: 2100, currency45: 'USD', otherCharges: [{ description: 'Customs Clearance Fee', quantity: 1, unit: 'Job', buyingRate: 80, sellingRate: 120, amount: 120, remark: '' }], conditions: quotationConditions(), totalBuying: 1560, totalSelling: 1970, profit: 410, margin: 20.8 },
    { id: id('qt', 2), quotationNo: 'QT-2026-0811', date: '2026-08-11', customer: 'Tai Seng Manufacturing', attention: 'Mr. Dara', phone: '+855 16 778 899', email: 'sopheak@taiseng.com.kh', direction: 'Export', pickup: 'TAI SENG', border: 'BAVET / MOC BAI', delivery: 'CAT LAI', transportBy: 'Truck', route: 'TAI SENG → BAVET / MOC BAI → CAT LAI', validUntil: '2026-09-10', currency: 'USD', amount: 3420, status: 'Sent', buying20: 1020, selling20: 1320, currency20: 'USD', buying40: 1550, selling40: 1980, currency40: 'USD', buying45: 1750, selling45: 2200, currency45: 'USD', otherCharges: [{ description: 'Fuel Surcharge', quantity: 1, unit: 'Trip', buyingRate: 40, sellingRate: 80, amount: 80, remark: '' }], conditions: quotationConditions(), totalBuying: 1590, totalSelling: 2060, profit: 470, margin: 22.8 },
    { id: id('qt', 3), quotationNo: 'QT-2026-0810', date: '2026-08-10', customer: 'Royal Group Manufacturing', attention: 'Ms. Sophea', phone: '+855 10 554 433', email: 'lina@royal.com.kh', direction: 'Import', pickup: 'CAI MEP', border: 'MOC BAI / BAVET', delivery: 'PPSEZ', transportBy: 'Truck', route: 'CAI MEP → MOC BAI / BAVET → PPSEZ', validUntil: '2026-09-05', currency: 'USD', amount: 1975, status: 'Draft', buying20: 890, selling20: 1150, currency20: 'USD', buying40: 1320, selling40: 1680, currency40: 'USD', buying45: 1500, selling45: 1900, currency45: 'USD', otherCharges: [], conditions: quotationConditions(), totalBuying: 1320, totalSelling: 1680, profit: 360, margin: 21.4 },
  ]

  const jobs: FreightRecord[] = [
    { id: id('job', 1), jobNo: 'LCS-IM-260821', date: '2026-08-20', customer: 'Manhattan SEZ Co., Ltd.', factory: 'Manhattan Factory', zone: 'Manhattan SEZ', contact: 'Sok Dara', direction: 'Import', serviceType: 'Trucking', status: 'In Transit', assignedStaff: 'Sokha V.', quotationNo: 'QT-2026-0812', soNo: 'SO-2608-118', invoiceNo: 'INV-2608-118', packingListNo: 'PL-2608-118', blNo: 'EGLV-8821907', patentNo: 'PAT-24018', transportMode: 'Road', containerNo: 'MSCU 482190-7', containerType: '40HC', sealNo: 'SL-9912', truckNo: '3C-9088', licensePlate: '3C-9088', carrier: 'NTL Transport', vessel: '', voyage: '', origin: 'Cat Lai', pickup: 'Cat Lai', port: 'Cat Lai', border: 'Moc Bai / Bavet', destination: 'Manhattan SEZ', deliveryLocation: 'Manhattan Factory Gate 2', shipmentDate: '2026-08-19', registeredDate: '2026-08-20', etaPort: '2026-08-20', etaBorder: '2026-08-20', etaFactory: '2026-08-21', actualArrival: '', deliveryDate: '', internalReference: 'INT-8821', transportReference: 'TR-260821', externalReference: 'REF-LCS-8821', referenceNo: 'REF-LCS-8821', customsStatus: 'Cleared', operationalRemark: 'Cross-border trucking in progress.', customsRemark: 'Cleared at Bavet.', deliveryRemark: '', internalNote: '', checklist: checklist({ POD: 'Missing' }), activity: [{ at: '2026-08-20 08:10', user: 'Sokha V.', action: 'Job created' }, { at: '2026-08-20 11:40', user: 'Dara C.', action: 'Customs cleared' }] },
    { id: id('job', 2), jobNo: 'LCS-EX-260820', date: '2026-08-19', customer: 'Tai Seng Manufacturing', factory: 'Tai Seng Factory', zone: 'Bavet SEZ', contact: 'Chan Sopheak', direction: 'Export', serviceType: 'Customs', status: 'Customs Processing', assignedStaff: 'Dara C.', quotationNo: 'QT-2026-0811', soNo: 'SO-2608-109', invoiceNo: 'INV-2608-109', packingListNo: 'PL-2608-109', blNo: 'OOLU-7719234', patentNo: 'PAT-24031', transportMode: 'Road', containerNo: 'TGHU 771923-4', containerType: '20GP', sealNo: 'SL-7741', truckNo: '3A-5512', licensePlate: '3A-5512', carrier: 'Golden Logistics', vessel: '', voyage: '', origin: 'Tai Seng', pickup: 'Tai Seng Factory', port: 'Cat Lai', border: 'Bavet / Moc Bai', destination: 'Cat Lai', deliveryLocation: 'Cat Lai Yard', shipmentDate: '2026-08-19', registeredDate: '2026-08-19', etaPort: '2026-08-22', etaBorder: '2026-08-21', etaFactory: '2026-08-22', actualArrival: '', deliveryDate: '', internalReference: 'INT-8734', transportReference: 'TR-260820', externalReference: 'REF-LCS-8734', referenceNo: 'REF-LCS-8734', customsStatus: 'Processing', operationalRemark: '', customsRemark: 'Waiting extra sheet.', deliveryRemark: '', internalNote: '', checklist: checklist({ 'Customs Declaration': 'Uploaded', 'Customs Fee Receipt': 'Missing', POD: 'Missing' }), activity: [{ at: '2026-08-19 09:00', user: 'Dara C.', action: 'Documents received' }] },
    { id: id('job', 3), jobNo: 'LCS-IM-260819', date: '2026-08-18', customer: 'Royal Group Manufacturing', factory: 'Royal Factory', zone: 'Phnom Penh SEZ', contact: 'Kim Lina', direction: 'Import', serviceType: 'Vietnam Service', status: 'Delivered', assignedStaff: 'Lina K.', quotationNo: 'QT-2026-0810', soNo: 'SO-2608-096', invoiceNo: 'INV-2608-096', packingListNo: 'PL-2608-096', blNo: 'MSCU-2041871', patentNo: 'PAT-24052', transportMode: 'Road', containerNo: 'OOLU 204187-1', containerType: '40GP', sealNo: 'SL-4410', truckNo: '3B-7721', licensePlate: '3B-7721', carrier: 'Vanxuan Transport', vessel: 'WAN HAI 325', voyage: 'V0325', origin: 'Cai Mep', pickup: 'Cai Mep', port: 'Cai Mep', border: 'Moc Bai / Bavet', destination: 'PPSEZ', deliveryLocation: 'Royal Factory Dock 1', shipmentDate: '2026-08-16', registeredDate: '2026-08-17', etaPort: '2026-08-17', etaBorder: '2026-08-18', etaFactory: '2026-08-18', actualArrival: '2026-08-18 15:10', deliveryDate: '2026-08-18', internalReference: 'INT-8690', transportReference: 'TR-260819', externalReference: 'REF-LCS-8690', referenceNo: 'REF-LCS-8690', customsStatus: 'Cleared', operationalRemark: '', customsRemark: '', deliveryRemark: 'POD signed.', internalNote: '', checklist: checklist(), activity: [{ at: '2026-08-18 15:10', user: 'Lina K.', action: 'Delivered at factory' }] },
    { id: id('job', 4), jobNo: 'LCS-IM-260818', date: '2026-08-20', customer: 'QiLu Cambodia Co., Ltd.', factory: 'QiLu Plant', zone: 'Manhattan SEZ', contact: 'Ly Vannak', direction: 'Import', serviceType: 'Trucking', status: 'Customs Cleared', assignedStaff: 'Sokha V.', quotationNo: '', soNo: 'SO-2608-141', invoiceNo: 'INV-2608-141', packingListNo: 'PL-2608-141', blNo: 'COSU-5518821', patentNo: 'PAT-24067', transportMode: 'Road', containerNo: 'CSLU 551882-1', containerType: '40HC', sealNo: 'SL-2281', truckNo: '3C-2210', licensePlate: '3C-2210', carrier: 'NTL Transport', vessel: '', voyage: '', origin: 'Cat Lai', pickup: 'Cat Lai', port: 'Cat Lai', border: 'Moc Bai / Bavet', destination: 'Manhattan SEZ', deliveryLocation: 'QiLu Plant Yard', shipmentDate: '2026-08-19', registeredDate: '2026-08-20', etaPort: '2026-08-20', etaBorder: '2026-08-20', etaFactory: '2026-08-21', actualArrival: '', deliveryDate: '', internalReference: 'INT-8911', transportReference: 'TR-260818', externalReference: 'REF-LCS-8911', referenceNo: 'REF-LCS-8911', customsStatus: 'Cleared', operationalRemark: 'Ready for delivery.', customsRemark: '', deliveryRemark: '', internalNote: '', checklist: checklist({ POD: 'Missing' }), activity: [{ at: '2026-08-20 16:20', user: 'Sokha V.', action: 'Customs cleared' }] },
    { id: id('job', 5), jobNo: 'LCS-EX-260817', date: '2026-08-17', customer: 'Dragon Well Garment', factory: 'Dragon Well', zone: 'Tai Seng SEZ', contact: 'Pich Sreyneang', direction: 'Export', serviceType: 'Container Service', status: 'Documents Received', assignedStaff: 'Lina K.', quotationNo: '', soNo: 'SO-2608-155', invoiceNo: 'INV-2608-155', packingListNo: 'PL-2608-155', blNo: '', patentNo: 'PAT-24088', transportMode: 'Road', containerNo: '', containerType: '40HC', sealNo: '', truckNo: '', licensePlate: '', carrier: 'PAL Logistics', vessel: '', voyage: '', origin: 'Tai Seng', pickup: 'Dragon Well Loading Bay', port: 'Cat Lai', border: 'Bavet / Moc Bai', destination: 'Cat Lai', deliveryLocation: 'Cat Lai Yard', shipmentDate: '', registeredDate: '', etaPort: '2026-08-24', etaBorder: '2026-08-23', etaFactory: '2026-08-24', actualArrival: '', deliveryDate: '', internalReference: 'INT-9002', transportReference: '', externalReference: 'REF-LCS-9002', referenceNo: 'REF-LCS-9002', customsStatus: 'Preparing', operationalRemark: 'Waiting B/L.', customsRemark: '', deliveryRemark: '', internalNote: '', checklist: checklist({ 'B/L': 'Missing', 'Transport Document': 'Missing', 'Customs Declaration': 'Missing', 'Customs Fee Receipt': 'Missing', POD: 'Missing' }), activity: [{ at: '2026-08-17 10:00', user: 'Lina K.', action: 'Documents received' }] },
    { id: id('job', 6), jobNo: 'LCS-IM-260816', date: '2026-08-16', customer: 'Manhattan SEZ Co., Ltd.', factory: 'Manhattan Factory', zone: 'Manhattan SEZ', contact: 'Sok Dara', direction: 'Import', serviceType: 'Trucking', status: 'Closed', assignedStaff: 'Dara C.', quotationNo: 'QT-2026-0812', soNo: 'SO-2608-080', invoiceNo: 'INV-2608-080', packingListNo: 'PL-2608-080', blNo: 'EGLV-7711002', patentNo: 'PAT-24018', transportMode: 'Road', containerNo: 'MSCU 771100-2', containerType: '20GP', sealNo: 'SL-1102', truckNo: '3C-1008', licensePlate: '3C-1008', carrier: 'NTL Transport', vessel: '', voyage: '', origin: 'Cat Lai', pickup: 'Cat Lai', port: 'Cat Lai', border: 'Moc Bai / Bavet', destination: 'Manhattan SEZ', deliveryLocation: 'Manhattan Factory Gate 2', shipmentDate: '2026-08-12', registeredDate: '2026-08-13', etaPort: '2026-08-13', etaBorder: '2026-08-14', etaFactory: '2026-08-14', actualArrival: '2026-08-14 11:20', deliveryDate: '2026-08-14', internalReference: 'INT-8080', transportReference: 'TR-260816', externalReference: 'REF-LCS-8080', referenceNo: 'REF-LCS-8080', customsStatus: 'Cleared', operationalRemark: '', customsRemark: '', deliveryRemark: 'Closed after POD and payment.', internalNote: '', checklist: checklist(), activity: [{ at: '2026-08-16 17:00', user: 'Dara C.', action: 'Job closed' }] },
  ]

  const shipments: FreightRecord[] = [
    { id: id('sh', 1), jobNo: 'LCS-IM-260821', customer: 'Manhattan SEZ Co., Ltd.', registeredDate: '2026-08-20', transportNo: 'TR-260821', truckBill: 'TB-8821', truckNo: '3C-9088', licensePlate: '3C-9088', containerNo: 'MSCU 482190-7', containerType: '40HC', sealNo: 'SL-9912', port: 'Cat Lai', etaFactory: '2026-08-21', referenceNo: 'REF-LCS-8821', supplier: 'NTL Transport', driver: 'Vannak', driverPhone: '+855 12 900 111', truckCompany: 'NTL Transport', transportCost: 1250, status: 'In Transit' },
    { id: id('sh', 2), jobNo: 'LCS-EX-260820', customer: 'Tai Seng Manufacturing', registeredDate: '2026-08-19', transportNo: 'TR-260820', truckBill: 'TB-8734', truckNo: '3A-5512', licensePlate: '3A-5512', containerNo: 'TGHU 771923-4', containerType: '20GP', sealNo: 'SL-7741', port: 'Cat Lai', etaFactory: '2026-08-22', referenceNo: 'REF-LCS-8734', supplier: 'Golden Logistics', driver: 'Sovann', driverPhone: '+855 16 200 333', truckCompany: 'Golden Logistics', transportCost: 980, status: 'Registered' },
    { id: id('sh', 3), jobNo: 'LCS-IM-260819', customer: 'Royal Group Manufacturing', registeredDate: '2026-08-17', transportNo: 'TR-260819', truckBill: 'TB-8690', truckNo: '3B-7721', licensePlate: '3B-7721', containerNo: 'OOLU 204187-1', containerType: '40GP', sealNo: 'SL-4410', port: 'Cai Mep', etaFactory: '2026-08-18', referenceNo: 'REF-LCS-8690', supplier: 'Vanxuan Transport', driver: 'Rithy', driverPhone: '+855 10 444 555', truckCompany: 'Vanxuan Transport', transportCost: 1100, status: 'Completed' },
  ]

  const customs: FreightRecord[] = [
    { id: id('cu', 1), jobNo: 'LCS-IM-260821', date: '2026-08-20', company: 'Manhattan SEZ Co., Ltd.', customer: 'Manhattan SEZ Co., Ltd.', zone: 'Manhattan SEZ', direction: 'Import', invoiceNo: 'INV-2608-118', containerNo: 'MSCU 482190-7', containerType: '40HC', customsNo: 'SAD-IM-008821', customsFeeNo: 'CF-8821', referenceNo: 'REF-LCS-8821', status: 'Cleared', declarationDate: '2026-08-20', submissionDate: '2026-08-20', clearanceDate: '2026-08-20', invoiceDoc: 'INV-2608-118', packingListDoc: 'PL-2608-118', blDoc: 'EGLV-8821907', patentDoc: 'PAT-24018', soDoc: 'SO-2608-118', clearanceFee: 120, sealFee: 25, inspectionFee: 0, overtime: 0, fine: 0, otherCharges: 0, notes: 'Cleared same day.', holdReason: '' },
    { id: id('cu', 2), jobNo: 'LCS-EX-260820', date: '2026-08-19', company: 'Tai Seng Manufacturing', customer: 'Tai Seng Manufacturing', zone: 'Bavet SEZ', direction: 'Export', invoiceNo: 'INV-2608-109', containerNo: 'TGHU 771923-4', containerType: '20GP', customsNo: 'SAD-EX-008734', customsFeeNo: 'CF-8734', referenceNo: 'REF-LCS-8734', status: 'Processing', declarationDate: '2026-08-19', submissionDate: '2026-08-19', clearanceDate: '', invoiceDoc: 'INV-2608-109', packingListDoc: 'PL-2608-109', blDoc: 'OOLU-7719234', patentDoc: 'PAT-24031', soDoc: 'SO-2608-109', clearanceFee: 95, sealFee: 25, inspectionFee: 40, overtime: 0, fine: 0, otherCharges: 0, notes: '', holdReason: 'Waiting extra customs sheet.' },
    { id: id('cu', 3), jobNo: 'LCS-IM-260819', date: '2026-08-18', company: 'Royal Group Manufacturing', customer: 'Royal Group Manufacturing', zone: 'Phnom Penh SEZ', direction: 'Import', invoiceNo: 'INV-2608-096', containerNo: 'OOLU 204187-1', containerType: '40GP', customsNo: 'SAD-IM-008690', customsFeeNo: 'CF-8690', referenceNo: 'REF-LCS-8690', status: 'Cleared', declarationDate: '2026-08-17', submissionDate: '2026-08-17', clearanceDate: '2026-08-18', invoiceDoc: 'INV-2608-096', packingListDoc: 'PL-2608-096', blDoc: 'MSCU-2041871', patentDoc: 'PAT-24052', soDoc: 'SO-2608-096', clearanceFee: 120, sealFee: 25, inspectionFee: 0, overtime: 30, fine: 0, otherCharges: 0, notes: '', holdReason: '' },
  ]

  const documents: FreightRecord[] = [
    { id: id('doc', 1), documentNo: 'DOC-2608-091', jobNo: 'LCS-IM-260821', customer: 'Manhattan SEZ Co., Ltd.', documentType: 'B/L', referenceNo: 'EGLV-8821907', file: 'BL-8821.pdf', uploadDate: '2026-08-20', uploadedBy: 'Sokha V.', status: 'Approved', remark: '' },
    { id: id('doc', 2), documentNo: 'DOC-2608-090', jobNo: 'LCS-EX-260820', customer: 'Tai Seng Manufacturing', documentType: 'Packing List', referenceNo: 'PL-2608-109', file: 'PL-109.pdf', uploadDate: '2026-08-19', uploadedBy: 'Dara C.', status: 'Uploaded', remark: '' },
    { id: id('doc', 3), documentNo: 'DOC-2608-089', jobNo: 'LCS-IM-260819', customer: 'Royal Group Manufacturing', documentType: 'Customs Declaration', referenceNo: 'SAD-IM-008690', file: 'SAD-8690.pdf', uploadDate: '2026-08-18', uploadedBy: 'Lina K.', status: 'Approved', remark: '' },
    { id: id('doc', 4), documentNo: 'DOC-2608-088', jobNo: 'LCS-EX-260817', customer: 'Dragon Well Garment', documentType: 'Invoice', referenceNo: 'INV-2608-155', file: 'INV-155.pdf', uploadDate: '2026-08-17', uploadedBy: 'Lina K.', status: 'Uploaded', remark: 'B/L still missing.' },
  ]

  const deliveries: FreightRecord[] = [
    { id: id('dl', 1), jobNo: 'LCS-IM-260821', customer: 'Manhattan SEZ Co., Ltd.', factory: 'Manhattan Factory', deliveryAddress: 'Manhattan Factory Gate 2, Bavet', containerNo: 'MSCU 482190-7', containerType: '40HC', truckNo: '3C-9088', driver: 'Vannak', etaFactory: '2026-08-21', arrivalTime: '', unloadingTime: '', completedTime: '', receiver: '', pod: '', remark: 'Arriving tomorrow afternoon.', status: 'Arriving' },
    { id: id('dl', 2), jobNo: 'LCS-IM-260819', customer: 'Royal Group Manufacturing', factory: 'Royal Factory', deliveryAddress: 'Royal Factory Dock 1, PPSEZ', containerNo: 'OOLU 204187-1', containerType: '40GP', truckNo: '3B-7721', driver: 'Rithy', etaFactory: '2026-08-18', arrivalTime: '2026-08-18 15:10', unloadingTime: '2026-08-18 15:40', completedTime: '2026-08-18 17:05', receiver: 'Kim Lina', pod: 'POD-8690.pdf', remark: 'Unloaded without issue.', status: 'POD Received' },
    { id: id('dl', 3), jobNo: 'LCS-IM-260818', customer: 'QiLu Cambodia Co., Ltd.', factory: 'QiLu Plant', deliveryAddress: 'QiLu Plant Yard, Manhattan SEZ', containerNo: 'CSLU 551882-1', containerType: '40HC', truckNo: '3C-2210', driver: 'Vannak', etaFactory: '2026-08-21', arrivalTime: '', unloadingTime: '', completedTime: '', receiver: '', pod: '', remark: 'Pending dispatch.', status: 'Scheduled' },
  ]

  const debitNotes: FreightRecord[] = [
    { id: id('dn', 1), debitNoteNo: 'DN-2608-041', date: '2026-08-20', customer: 'Manhattan SEZ Co., Ltd.', customerAddress: 'Manhattan SEZ, Bavet, Svay Rieng', jobNo: 'LCS-IM-260821', invoiceNo: 'INV-2608-118', blNo: 'EGLV-8821907', containerNo: 'MSCU 482190-7', quantity: 1, containerType: '40HC', direction: 'Import', charges: debitCharges({ 'Customs Clearance Fee': { cambodia: 120 }, 'Customs Seal': { cambodia: 25 }, 'Trucking Fee': { vietnam: 1250 }, 'Fuel Surcharge': { cash: 80 } }), cambodiaSubtotal: 145, vietnamSubtotal: 1250, cashSubtotal: 80, amount: 1475, vatRate: 10, vat: 147.5, total: 1622.5, status: 'Sent' },
    { id: id('dn', 2), debitNoteNo: 'DN-2608-040', date: '2026-08-19', customer: 'Tai Seng Manufacturing', customerAddress: 'Tai Seng SEZ, Bavet', jobNo: 'LCS-EX-260820', invoiceNo: 'INV-2608-109', blNo: 'OOLU-7719234', containerNo: 'TGHU 771923-4', quantity: 1, containerType: '20GP', direction: 'Export', charges: debitCharges({ 'Customs Clearance Fee': { cambodia: 95 }, 'Trucking Fee': { vietnam: 980 }, 'Local Charge': { cash: 40 } }), cambodiaSubtotal: 95, vietnamSubtotal: 980, cashSubtotal: 40, amount: 1115, vatRate: 10, vat: 111.5, total: 1226.5, status: 'Approved' },
    { id: id('dn', 3), debitNoteNo: 'DN-2608-039', date: '2026-08-18', customer: 'Royal Group Manufacturing', customerAddress: 'PPSEZ, Khan Prek Pnov', jobNo: 'LCS-IM-260819', invoiceNo: 'INV-2608-096', blNo: 'MSCU-2041871', containerNo: 'OOLU 204187-1', quantity: 1, containerType: '40GP', direction: 'Import', charges: debitCharges({ 'Customs Clearance Fee': { cambodia: 120 }, 'Overtime': { cambodia: 30 }, 'Trucking Fee': { vietnam: 1100 } }), cambodiaSubtotal: 150, vietnamSubtotal: 1100, cashSubtotal: 0, amount: 1250, vatRate: 10, vat: 125, total: 1375, status: 'Paid' },
  ]

  const customerPayments: FreightRecord[] = [
    { id: id('cp', 1), paymentNo: 'PAY-2608-028', date: '2026-08-20', customer: 'Manhattan SEZ Co., Ltd.', jobNo: 'LCS-IM-260821', invoiceNo: 'INV-2608-118', customsNo: 'SAD-IM-008821', direction: 'Import', containerNo: 'MSCU 482190-7', containerType: '40HC', sealNo: 'SL-9912', referenceNo: 'ABA-26082091', debitNoteNo: 'DN-2608-041', amountDue: 1622.5, received: 0, outstanding: 1622.5, paymentMethod: 'Bank Transfer', currency: 'USD', remark: 'Invoice sent.', status: 'Unpaid' },
    { id: id('cp', 2), paymentNo: 'PAY-2608-027', date: '2026-08-19', customer: 'Tai Seng Manufacturing', jobNo: 'LCS-EX-260820', invoiceNo: 'INV-2608-109', customsNo: 'SAD-EX-008734', direction: 'Export', containerNo: 'TGHU 771923-4', containerType: '20GP', sealNo: 'SL-7741', referenceNo: 'CASH-26081902', debitNoteNo: 'DN-2608-040', amountDue: 1226.5, received: 500, outstanding: 726.5, paymentMethod: 'Cash', currency: 'USD', remark: 'Partial cash received.', status: 'Partial' },
    { id: id('cp', 3), paymentNo: 'PAY-2608-026', date: '2026-08-18', customer: 'Royal Group Manufacturing', jobNo: 'LCS-IM-260819', invoiceNo: 'INV-2608-096', customsNo: 'SAD-IM-008690', direction: 'Import', containerNo: 'OOLU 204187-1', containerType: '40GP', sealNo: 'SL-4410', referenceNo: 'ACLEDA-26081877', debitNoteNo: 'DN-2608-039', amountDue: 1375, received: 1375, outstanding: 0, paymentMethod: 'Bank Transfer', currency: 'USD', remark: 'Paid in full.', status: 'Paid' },
  ]

  const supplierCosts: FreightRecord[] = [
    { id: id('sc', 1), jobNo: 'LCS-IM-260821', supplier: 'NTL Transport', chargeType: 'Trucking Fee', description: 'Cross-border trucking', quantity: 1, unitCost: 1250, amount: 1250, currency: 'USD', invoiceNo: 'SUP-NTL-3391', status: 'Unpaid', chargeSide: 'Supplier' },
    { id: id('sc', 2), jobNo: 'LCS-EX-260820', supplier: 'Golden Logistics', chargeType: 'Customs Clearance', description: 'Export declaration', quantity: 1, unitCost: 320, amount: 320, currency: 'USD', invoiceNo: 'SUP-GD-1287', status: 'Paid', chargeSide: 'Supplier' },
    { id: id('sc', 3), jobNo: 'LCS-IM-260819', supplier: 'Vanxuan Transport', chargeType: 'Vietnam Service', description: 'Port and border handling', quantity: 1, unitCost: 610, amount: 610, currency: 'USD', invoiceNo: 'SUP-VX-8852', status: 'Partial', chargeSide: 'Supplier' },
    { id: id('sc', 4), jobNo: 'LCS-IM-260821', supplier: 'TOP1 Service', chargeType: 'Vietnam Service', description: 'Moc Bai gate in/out', quantity: 1, unitCost: 85, amount: 85, currency: 'USD', invoiceNo: 'SUP-T1-4411', status: 'Unpaid', chargeSide: 'Supplier' },
  ]

  const jobCharges: FreightRecord[] = [
    { id: id('jc', 1), jobNo: 'LCS-IM-260821', chargeSide: 'Customer', supplier: '', chargeType: 'Trucking Fee', description: 'Selling trucking', quantity: 1, unitPrice: 1850, amount: 1850, currency: 'USD', tax: 185, invoiceNo: 'DN-2608-041', status: 'Unpaid' },
    { id: id('jc', 2), jobNo: 'LCS-IM-260821', chargeSide: 'Supplier', supplier: 'NTL Transport', chargeType: 'Trucking Fee', description: 'Buying trucking', quantity: 1, unitPrice: 1250, amount: 1250, currency: 'USD', tax: 0, invoiceNo: 'SUP-NTL-3391', status: 'Unpaid' },
    { id: id('jc', 3), jobNo: 'LCS-EX-260820', chargeSide: 'Customer', supplier: '', chargeType: 'Customs Clearance', description: 'Export clearance sold', quantity: 1, unitPrice: 420, amount: 420, currency: 'USD', tax: 42, invoiceNo: 'DN-2608-040', status: 'Partial' },
    { id: id('jc', 4), jobNo: 'LCS-EX-260820', chargeSide: 'Supplier', supplier: 'Golden Logistics', chargeType: 'Customs Clearance', description: 'Export clearance bought', quantity: 1, unitPrice: 320, amount: 320, currency: 'USD', tax: 0, invoiceNo: 'SUP-GD-1287', status: 'Paid' },
  ]

  const supplierPayments: FreightRecord[] = [
    { id: id('sp', 1), paymentNo: 'SP-2608-021', date: '2026-08-19', jobNo: 'LCS-EX-260820', supplier: 'Golden Logistics', invoiceNo: 'SUP-GD-1287', service: 'Customs', amount: 320, currency: 'USD', paymentMethod: 'Bank Transfer', referenceNo: 'ABA-SP-021', paidBy: 'Dara C.', status: 'Paid', remark: '' },
    { id: id('sp', 2), paymentNo: 'SP-2608-020', date: '2026-08-18', jobNo: 'LCS-IM-260819', supplier: 'Vanxuan Transport', invoiceNo: 'SUP-VX-8852', service: 'Vietnam Service', amount: 300, currency: 'USD', paymentMethod: 'Cash', referenceNo: 'CASH-SP-020', paidBy: 'Lina K.', status: 'Partial', remark: 'Balance next week.' },
    { id: id('sp', 3), paymentNo: 'SP-2608-019', date: '2026-08-16', jobNo: 'LCS-IM-260816', supplier: 'NTL Transport', invoiceNo: 'SUP-NTL-3301', service: 'Trucking', amount: 980, currency: 'USD', paymentMethod: 'Bank Transfer', referenceNo: 'ACLEDA-SP-019', paidBy: 'Sokha V.', status: 'Paid', remark: '' },
  ]

  const users: FreightRecord[] = [
    { id: id('us', 1), name: 'System Administrator', username: 'admin.lcs', email: 'admin@lcs.com.kh', phone: '+855 12 000 001', role: 'Administrator', department: 'Management', status: 'Active' },
    { id: id('us', 2), name: 'Sokha Vann', username: 'sokha.ops', email: 'sokha@lcs.com.kh', phone: '+855 12 000 002', role: 'Operations', department: 'Operations', status: 'Active' },
    { id: id('us', 3), name: 'Dara Chan', username: 'dara.finance', email: 'dara@lcs.com.kh', phone: '+855 12 000 003', role: 'Finance', department: 'Finance', status: 'Active' },
    { id: id('us', 4), name: 'Lina Kim', username: 'lina.customs', email: 'lina@lcs.com.kh', phone: '+855 12 000 004', role: 'Customs', department: 'Customs', status: 'Active' },
  ]

  const roles: FreightRecord[] = [
    { id: id('rl', 1), name: 'Administrator', description: 'Full system access', userCount: 1, permissionCount: 0, status: 'Active' },
    { id: id('rl', 2), name: 'Operations', description: 'Jobs, shipments, documents and deliveries', userCount: 4, permissionCount: 0, status: 'Active' },
    { id: id('rl', 3), name: 'Finance', description: 'Debit notes, payments, AR/AP and profitability', userCount: 2, permissionCount: 0, status: 'Active' },
    { id: id('rl', 4), name: 'Customs', description: 'Customs processing and related documents', userCount: 2, permissionCount: 0, status: 'Active' },
  ]

  const auditLogs: FreightRecord[] = [
    { id: id('log', 1), occurredAt: '2026-08-20 16:20', user: 'Sokha V.', action: 'Customs cleared', module: 'Customs', recordNo: 'LCS-IM-260818', result: 'SUCCESS', remark: '' },
    { id: id('log', 2), occurredAt: '2026-08-20 11:40', user: 'Dara C.', action: 'Debit note sent', module: 'Debit Notes', recordNo: 'DN-2608-041', result: 'SUCCESS', remark: '' },
    { id: id('log', 3), occurredAt: '2026-08-19 09:00', user: 'Dara C.', action: 'Updated service order', module: 'Service Orders', recordNo: 'LCS-EX-260820', result: 'SUCCESS', remark: 'Documents received' },
    { id: id('log', 5), occurredAt: '2026-08-20 08:00', user: 'Sokha V.', action: 'Created service order', module: 'Service Orders', recordNo: 'LCS-IM-260821', result: 'SUCCESS', remark: '' },
    { id: id('log', 6), occurredAt: '2026-08-20 10:12', user: 'Sokha V.', action: 'Updated service order', module: 'Service Orders', recordNo: 'LCS-IM-260821', result: 'SUCCESS', remark: 'Containers assigned' },
    { id: id('log', 7), occurredAt: '2026-08-20 14:40', user: 'Sokha V.', action: 'Completed component', module: 'Service Orders', recordNo: 'LCS-IM-260821', result: 'SUCCESS', remark: 'Trucking' },
    { id: id('log', 8), occurredAt: '2026-08-19 08:10', user: 'Dara C.', action: 'Created service order', module: 'Service Orders', recordNo: 'LCS-EX-260820', result: 'SUCCESS', remark: '' },
  ]

  return {
    companies,
    quotations,
    jobs,
    shipments,
    customs,
    documents,
    deliveries,
    debitNotes,
    customerPayments,
    jobCharges,
    supplierCosts,
    supplierPayments,
    suppliers,
    users,
    roles,
    auditLogs,
    zones: [
      { id: id('zn', 1), code: 'MH-SEZ', name: 'Manhattan SEZ', status: 'Active' },
      { id: id('zn', 2), code: 'BV-SEZ', name: 'Bavet SEZ', status: 'Active' },
      { id: id('zn', 3), code: 'PP-SEZ', name: 'Phnom Penh SEZ', status: 'Active' },
      { id: id('zn', 4), code: 'TS-SEZ', name: 'Tai Seng SEZ', status: 'Active' },
    ],
    locations: [
      { id: id('lc', 1), code: 'CTL', name: 'Cat Lai', country: 'Vietnam', category: 'Port', status: 'Active' },
      { id: id('lc', 2), code: 'CMP', name: 'Cai Mep', country: 'Vietnam', category: 'Port', status: 'Active' },
      { id: id('lc', 3), code: 'MCB', name: 'Moc Bai', country: 'Vietnam', category: 'Border', status: 'Active' },
      { id: id('lc', 4), code: 'BVT', name: 'Bavet', country: 'Cambodia', category: 'Border', status: 'Active' },
      { id: id('lc', 5), code: 'MHN', name: 'Manhattan', country: 'Cambodia', category: 'Factory', status: 'Active' },
    ],
    equipmentTypes: [
      { id: id('eq', 1), code: '20GP', name: '20GP', category: 'Container', status: 'Active' },
      { id: id('eq', 2), code: '40GP', name: '40GP', category: 'Container', status: 'Active' },
      { id: id('eq', 3), code: '40HC', name: '40HC', category: 'Container', status: 'Active' },
      { id: id('eq', 4), code: '45HC', name: '45HC / HQ', category: 'Container', status: 'Active' },
      { id: id('eq', 5), code: '1.5T', name: '1.5T', category: 'Truck', status: 'Active' },
      { id: id('eq', 6), code: '2T', name: '2T', category: 'Truck', status: 'Active' },
      { id: id('eq', 7), code: '3.5T', name: '3.5T', category: 'Truck', status: 'Active' },
      { id: id('eq', 8), code: '5T', name: '5T', category: 'Truck', status: 'Active' },
      { id: id('eq', 9), code: '8T', name: '8T', category: 'Truck', status: 'Active' },
    ],
    directions: [
      { id: id('dir', 1), code: 'IM', name: 'Import', status: 'Active' },
      { id: id('dir', 2), code: 'EX', name: 'Export', status: 'Active' },
    ],
    chargeTypes: [
      { id: id('ch', 1), code: 'CCL', name: 'Customs Clearance Fee', category: 'Customs', unit: 'Job', status: 'Active' },
      { id: id('ch', 2), code: 'TRK', name: 'Trucking Fee', category: 'Trucking', unit: 'Trip', status: 'Active' },
      { id: id('ch', 3), code: 'FSC', name: 'Fuel Surcharge', category: 'Trucking', unit: 'Trip', status: 'Active' },
      { id: id('ch', 4), code: 'VNS', name: 'Vietnam Service', category: 'Vietnam', unit: 'Job', status: 'Active' },
      { id: id('ch', 5), code: 'SEAL', name: 'Customs Seal', category: 'Customs', unit: 'Document', status: 'Active' },
    ],
    currencies: [
      { id: id('cur', 1), code: 'USD', name: 'US Dollar', exchangeRate: 1, status: 'Active' },
      { id: id('cur', 2), code: 'KHR', name: 'Khmer Riel', exchangeRate: 4100, status: 'Active' },
      { id: id('cur', 3), code: 'VND', name: 'Vietnamese Dong', exchangeRate: 24950, status: 'Active' },
    ],
  }
}

export function deriveReceivables(debitNotes: FreightRecord[], payments: FreightRecord[]): FreightRecord[] {
  return debitNotes.map((note, index) => {
    const related = payments.filter(p => p.debitNoteNo === note.debitNoteNo || p.jobNo === note.jobNo)
    const received = related.reduce((sum, p) => sum + Number(p.received || 0), 0)
    const amount = Number(note.total || note.amount || 0)
    const outstanding = money(amount - received)
    const invoiceDate = String(note.date || '')
    const due = invoiceDate ? new Date(`${invoiceDate}T00:00:00`) : new Date()
    due.setDate(due.getDate() + 14)
    const dueDate = due.toISOString().slice(0, 10)
    const days = Math.max(0, Math.round((Date.parse('2026-08-20') - Date.parse(dueDate)) / 86400000))
    let status = 'Unpaid'
    if (outstanding <= 0) status = 'Paid'
    else if (received > 0) status = 'Partial'
    else if (days > 0) status = 'Overdue'
    return {
      id: `ar-${index + 1}`,
      customer: note.customer,
      jobNo: note.jobNo,
      invoiceNo: note.debitNoteNo,
      invoiceDate,
      dueDate,
      amount,
      received,
      outstanding,
      daysOutstanding: Math.max(days, 0),
      status,
    }
  })
}

export function derivePayables(costs: FreightRecord[], payments: FreightRecord[]): FreightRecord[] {
  return costs.map((cost, index) => {
    const related = payments.filter(p => p.invoiceNo === cost.invoiceNo || (p.jobNo === cost.jobNo && p.supplier === cost.supplier))
    const paid = related.reduce((sum, p) => sum + Number(p.amount || 0), Number(cost.status === 'Paid' ? cost.amount : 0) && related.length ? 0 : (cost.status === 'Paid' ? Number(cost.amount) : cost.status === 'Partial' ? Number(cost.amount) * 0.4 : 0))
    const amount = Number(cost.amount || 0)
    const outstanding = money(Math.max(amount - paid, 0))
    let status = 'Unpaid'
    if (outstanding <= 0) status = 'Paid'
    else if (paid > 0) status = 'Partial'
    return {
      id: `ap-${index + 1}`,
      supplier: cost.supplier,
      jobNo: cost.jobNo,
      invoiceNo: cost.invoiceNo,
      invoiceDate: '2026-08-12',
      dueDate: '2026-08-26',
      amount,
      paid: money(paid),
      outstanding,
      status,
    }
  })
}

export function deriveProfitability(jobs: FreightRecord[], debitNotes: FreightRecord[], costs: FreightRecord[]): FreightRecord[] {
  return jobs.map((job, index) => {
    const notes = debitNotes.filter(n => n.jobNo === job.jobNo)
    const revenue = notes.reduce((sum, n) => sum + Number(n.total || n.amount || 0), 0)
    const jobCosts = costs.filter(c => c.jobNo === job.jobNo)
    const truckingCost = jobCosts.filter(c => String(c.chargeType).toLowerCase().includes('truck')).reduce((s, c) => s + Number(c.amount || 0), 0)
    const customsCost = jobCosts.filter(c => String(c.chargeType).toLowerCase().includes('custom')).reduce((s, c) => s + Number(c.amount || 0), 0)
    const vietnamCost = jobCosts.filter(c => String(c.chargeType).toLowerCase().includes('vietnam')).reduce((s, c) => s + Number(c.amount || 0), 0)
    const cambodiaCost = notes.reduce((s, n) => s + Number(n.cambodiaSubtotal || 0), 0)
    const otherCost = jobCosts.reduce((s, c) => s + Number(c.amount || 0), 0) - truckingCost - customsCost - vietnamCost
    const totalCost = jobCosts.reduce((s, c) => s + Number(c.amount || 0), 0) || (cambodiaCost + vietnamCost + truckingCost)
    const profit = money(revenue - totalCost)
    const margin = revenue ? money((profit / revenue) * 100) : 0
    return {
      id: `pr-${index + 1}`,
      jobNo: job.jobNo,
      customer: job.customer,
      direction: job.direction,
      containerNo: job.containerNo,
      revenue: money(revenue),
      cambodiaCost: money(cambodiaCost),
      vietnamCost: money(vietnamCost),
      truckingCost: money(truckingCost),
      customsCost: money(customsCost),
      otherCost: money(Math.max(otherCost, 0)),
      totalCost: money(totalCost),
      profit,
      margin,
    }
  })
}

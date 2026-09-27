import type { FreightRecord } from '~/types/freight/record'
import { DEFAULT_INVOICE_LOGO_URL } from '~/utils/freight/print-navigation'

/**
 * Shared print view model. Layout components read this typed model only —
 * they never reach into raw record keys, so nothing sensitive (customs
 * credentials, internal notes, unmasked bank data) can leak onto paper.
 */

export type PrintParty = {
  name: string
  legalName: string
  nameKh: string
  taxIdentifier: string
  address: string
  phone: string
  email: string
  contact: string
}

export type PrintIssuer = PrintParty & {
  legalNameKh: string
  addressKh: string
  displayName: string
  logoUrl: string
}

export type PrintDocumentMeta = {
  number: string
  documentType: string
  issueDate: string
  dueDate: string
  currency: string
  status: string
  remarks: string
  personInCharge: string
  exchangeRate: number
}

export type PrintShipment = {
  workNo: string
  houseNo: string
  masterNo: string
  blNo: string
  loadingPort: string
  dischargePort: string
  etd: string
  eta: string
  vessel: string
  voyage: string
  containerNo: string
  containerType: string
  packageQty: string
  packageUnit: string
  shipper: string
  consignee: string
  notifyParty: string
}

export type PrintLine = {
  no: number
  reference: string
  description: string
  descriptionKh: string
  quantity: number
  unit: string
  unitPrice: number
  currency: string
  debit: number
  credit: number
  amount: number
}

export type PrintTotals = {
  currency: string
  subtotal: number
  taxRate: number
  taxAmount: number
  grandTotal: number
  totalDebit: number
  totalCredit: number
  balance: number
  localCurrency: string
  exchangeRate: number
  grandTotalLocal: number
  outstanding: number
}

export type PrintSettlement = {
  accountName: string
  accountAddress: string
  bankName: string
  accountNumber: string
  swiftCode: string
}

export type PrintWatermark = 'DRAFT' | 'CANCELLED' | 'REVERSED' | null

export type PrintSignatures = {
  customerSignatureUrl: string
  customerStampUrl: string
  sellerSignatureUrl: string
  sellerStampUrl: string
}

export type PrintViewModel = {
  templateId: string
  issuer: PrintIssuer
  party: PrintParty
  document: PrintDocumentMeta
  shipment: PrintShipment
  lines: PrintLine[]
  totals: PrintTotals
  settlement: PrintSettlement
  signatures: PrintSignatures
  watermark: PrintWatermark
  amountInWords: string
}

export type PrintModelContext = {
  companies?: FreightRecord[]
  suppliers?: FreightRecord[]
  jobs?: FreightRecord[]
  financialAccounts?: FreightRecord[]
  logoUrl?: string
  localCurrency?: string
}

/* ------------------------------------------------------------------ */
/* Safe accessors                                                      */
/* ------------------------------------------------------------------ */

export function printStr(value: unknown): string {
  if (value === undefined || value === null) return ''
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : ''
  if (typeof value === 'string') return value.trim()
  return ''
}

export function printNum(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(printStr(value).replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}

/** Display fallback for optional print fields. */
export function printOrDash(value: string): string {
  return value || '-'
}

/* ------------------------------------------------------------------ */
/* Watermark                                                           */
/* ------------------------------------------------------------------ */

export function printWatermarkFor(status: unknown): PrintWatermark {
  const value = printStr(status).toUpperCase()
  if (!value) return null
  if (value.includes('CANCEL') || value === 'VOIDED') return 'CANCELLED'
  if (value.includes('REVERSED')) return 'REVERSED'
  if (value.includes('DRAFT')) return 'DRAFT'
  return null
}

/* ------------------------------------------------------------------ */
/* Amount in words (English, currency-aware, deterministic)            */
/* ------------------------------------------------------------------ */

const ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
const SCALES = ['', ' thousand', ' million', ' billion', ' trillion']

function threeDigitWords(n: number): string {
  const parts: string[] = []
  const hundreds = Math.floor(n / 100)
  const rest = n % 100
  if (hundreds) parts.push(`${ONES[hundreds]} hundred`)
  if (rest) {
    if (rest < 20) parts.push(ONES[rest] ?? String(rest))
    else {
      const ten = Math.floor(rest / 10)
      const one = rest % 10
      parts.push(one ? `${TENS[ten] ?? ''}-${ONES[one] ?? ''}` : TENS[ten] ?? '')
    }
  }
  return parts.join(' ')
}

/** Convert a whole number to English words (deterministic, no dependencies). */
export function numberToEnglishWords(value: number): string {
  if (!Number.isFinite(value)) return 'zero'
  const negative = value < 0
  let whole = Math.floor(Math.abs(value))
  if (whole === 0) return negative ? 'negative zero' : 'zero'
  const groups: string[] = []
  let scaleIndex = 0
  while (whole > 0) {
    const chunk = whole % 1000
    if (chunk) groups.unshift(`${threeDigitWords(chunk)}${SCALES[scaleIndex] || ''}`)
    whole = Math.floor(whole / 1000)
    scaleIndex += 1
    if (scaleIndex >= SCALES.length) break
  }
  return `${negative ? 'negative ' : ''}${groups.join(' ')}`
}

type CurrencyWordForms = { whole: string, sub?: string, singularWhole?: string }

const CURRENCY_WORDS: Record<string, CurrencyWordForms> = {
  USD: { whole: 'dollars', sub: 'cents', singularWhole: 'dollar', },
  KHR: { whole: 'riels' },
  VND: { whole: 'dong' },
  THB: { whole: 'baht', sub: 'satang' },
  EUR: { whole: 'euros', sub: 'cents', singularWhole: 'euro' },
  GBP: { whole: 'pounds sterling', sub: 'pence', singularWhole: 'pound sterling' },
  JPY: { whole: 'yen' },
  CNY: { whole: 'yuan' },
  SGD: { whole: 'singapore dollars', sub: 'cents', singularWhole: 'singapore dollar' },
  AUD: { whole: 'australian dollars', sub: 'cents', singularWhole: 'australian dollar' },
}

/**
 * Deterministic English amount-in-words with currency names.
 * Unknown currencies fall back to "1,234.50 XYZ" style so nothing is invented.
 */
export function amountInWords(amount: number, currency = 'USD'): string {
  if (!Number.isFinite(amount)) return '-'
  const code = (currency || 'USD').toUpperCase()
  const forms = CURRENCY_WORDS[code]
  if (!forms) return `${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${code}`
  const singularWhole = forms.singularWhole
  const negative = amount < 0
  const abs = Math.abs(amount)
  const whole = Math.floor(abs)
  const cents = Math.round((abs - whole) * 100)
  const wholeWord = `${numberToEnglishWords(whole)} ${whole === 1 && singularWhole ? singularWhole : forms.whole}`
  if (cents === 0) return `${negative ? 'minus ' : ''}${wholeWord} only`
  const words = forms.sub
    ? `${wholeWord} and ${numberToEnglishWords(cents)} ${cents === 1 ? forms.sub.replace(/s$/, '') : forms.sub}`
    : `${wholeWord} and ${String(cents).padStart(2, '0')}/100`
  return `${negative ? 'minus ' : ''}${words} only`
}

/** DCN-style amount in words: `USD NINE HUNDRED SEVENTY NINE AND CENTS SEVEN`. */
export function formatDebitNoteAmountInWords(amount: number, currency = 'USD'): string {
  if (!Number.isFinite(amount)) return '-'
  const code = (currency || 'USD').toUpperCase()
  const negative = amount < 0
  const abs = Math.abs(amount)
  const whole = Math.floor(abs)
  const cents = Math.round((abs - whole) * 100)
  const wholeWords = numberToEnglishWords(whole).toUpperCase().replace(/-/g, ' ')
  if (cents === 0) return `${code} ${negative ? 'MINUS ' : ''}${wholeWords} ONLY`
  const centsWords = numberToEnglishWords(cents).toUpperCase().replace(/-/g, ' ')
  return `${code} ${negative ? 'MINUS ' : ''}${wholeWords} AND CENTS ${centsWords}`
}

/* ------------------------------------------------------------------ */
/* Line + totals normalization                                         */
/* ------------------------------------------------------------------ */

type RawLine = Record<string, unknown>

export function feeLinesToPrintLines(feeLines: RawLine[], reference: string, currency: string): PrintLine[] {
  return feeLines.map((row, index) => {
    const quantity = printNum(row.quantity) || 1
    const unitPrice = printNum(row.unitAmount ?? row.unitPrice)
    const discount = printNum(row.discount)
    const taxAmount = printNum(row.taxAmount ?? row.tax)
    const grossAmount = printNum(row.amount)
    const net = Math.max(0, quantity * unitPrice - discount)
    const amount = grossAmount || net + taxAmount
    return {
      no: index + 1,
      reference,
      description: printStr(row.description) || printStr(row.feeType) || 'Service charge',
      descriptionKh: printStr(row.descriptionKh) || printStr(row.description_kh),
      quantity,
      unit: printStr(row.unit) || 'Service',
      unitPrice,
      currency,
      debit: amount,
      credit: 0,
      amount,
    }
  }).filter(line => line.amount > 0 || line.description)
}

function normalizeDocumentLines(record: FreightRecord, templateId?: string): PrintLine[] {
  const currency = printStr(record.currency) || 'USD'
  const lineReference = templateId === 'debit-note'
    ? printStr(record.blNo) || printStr(record.jobNo)
    : printStr(record.debitNoteNo) || printStr(record.invoiceNo) || printStr(record.jobNo)
  const raw = Array.isArray(record.lines) ? record.lines as RawLine[] : []
  const lines = raw.map((row, index) => {
    const quantity = printNum(row.quantity) || 1
    const unitPrice = printNum(row.unitAmount ?? row.unitPrice)
    const grossAmount = printNum(row.amount ?? row.lineTotal)
    const taxAmount = printNum(row.taxAmount)
    const discount = printNum(row.discount)
    const calculatedNet = unitPrice ? quantity * unitPrice - discount : grossAmount - taxAmount
    const amount = printNum(row.netAmount ?? row.subtotal) || calculatedNet || grossAmount
    const debit = printNum(row.debit_amount ?? row.debit)
    const credit = printNum(row.credit_amount ?? row.credit)
    return {
      no: index + 1,
      reference: lineReference,
      description: printStr(row.description),
      descriptionKh: printStr(row.descriptionKh) || printStr(row.description_kh),
      quantity,
      unit: printStr(row.unit) || '-',
      unitPrice,
      currency,
      debit: debit || amount || 0,
      credit,
      amount,
    }
  })
  if (lines.length) return lines

  const feeLines = Array.isArray(record.feeLines) ? record.feeLines as RawLine[] : []
  const feeLineRows = feeLinesToPrintLines(feeLines, lineReference, currency)
  if (feeLineRows.length) return feeLineRows

  // Debit-note charge tables: description + cambodia/vietnam/cash amounts.
  const charges = Array.isArray(record.charges) ? record.charges as RawLine[] : []
  const chargeLines = charges
    .map((row, index) => {
      const amount = printNum(row.cambodia) + printNum(row.vietnam) + printNum(row.cash)
      return {
        no: index + 1,
        reference: lineReference,
        description: printStr(row.description),
      descriptionKh: printStr(row.descriptionKh) || printStr(row.description_kh),
        quantity: amount ? 1 : 0,
        unit: amount ? (templateId === 'debit-note' ? 'CONT' : 'Service') : '-',
        unitPrice: amount,
        currency,
        debit: amount,
        credit: 0,
        amount,
      }
    })
    .filter(line => line.amount !== 0 || line.description)
  if (chargeLines.length) return chargeLines

  // Service charges / single-value documents.
  const amount = printNum(record.amount ?? record.total)
  if (amount) {
    return [{
      no: 1,
      reference: lineReference,
      description: printStr(record.description) || printStr(record.chargeType) || 'Service charge',
      descriptionKh: printStr(record.descriptionKh) || printStr(record.description_kh),
      quantity: printNum(record.quantity) || 1,
      unit: 'Service',
      unitPrice: printNum(record.unitPrice) || amount,
      currency,
      debit: amount,
      credit: 0,
      amount,
    }]
  }
  return []
}

export function sumPrintLines(lines: PrintLine[]) {
  const totalDebit = lines.reduce((sum, line) => sum + line.debit, 0)
  const totalCredit = lines.reduce((sum, line) => sum + line.credit, 0)
  const subtotal = lines.reduce((sum, line) => sum + line.amount, 0)
  return { totalDebit, totalCredit, subtotal }
}

/* ------------------------------------------------------------------ */
/* View-model builder                                                  */
/* ------------------------------------------------------------------ */

function resolveParty(name: string, context: PrintModelContext, record: FreightRecord): PrintParty {
  const key = name.trim().toLowerCase()
  const companies = context.companies || []
  const suppliers = context.suppliers || []
  const match = companies.find(row => [row.legalName, row.name, row.displayName].some(value => String(value || '').toLowerCase() === key))
    || suppliers.find(row => [row.legalName, row.name, row.displayName].some(value => String(value || '').toLowerCase() === key))
  const fallback: PrintParty = {
    name,
    legalName: printStr(record.customer) === name ? printStr(record.customer) : name,
    nameKh: '',
    taxIdentifier: '',
    address: printStr(record.customerAddress) || '',
    phone: '',
    email: '',
    contact: '',
  }
  if (!match) return fallback
  return {
    name,
    legalName: printStr(match.legalName) || name,
    nameKh: printStr(match.legalNameKh) || printStr(match.nameKh),
    taxIdentifier: printStr(match.taxIdentifier),
    address: printStr(match.address),
    phone: printStr(match.phone),
    email: printStr(match.email),
    contact: printStr(match.contactPerson),
  }
}

function resolveShipment(record: FreightRecord, jobs: FreightRecord[]): PrintShipment {
  const job = jobs.find(row => String(row.jobNo || '') === printStr(record.jobNo)) || null
  const pick = (a: unknown, b: unknown) => printStr(a) || printStr(b)
  const containerNo = pick(record.containerNo, job?.containerNo)
  const packageQty = printStr(record.quantity) || printStr(job?.quantity)
  const packageUnit = printStr(record.containerType) || printStr(job?.containerType)
  return {
    workNo: pick(record.jobNo, job?.jobNo),
    houseNo: pick(record.houseNo, job?.houseNo),
    masterNo: pick(record.masterNo, job?.masterNo),
    blNo: pick(record.blNo, job?.blNo),
    loadingPort: pick(record.loadingPort ?? record.pickup, job?.loadingPort ?? job?.pol),
    dischargePort: pick(record.dischargePort ?? record.delivery, job?.dischargePort ?? job?.pod),
    etd: pick(record.etd, job?.etd),
    eta: pick(record.eta, job?.eta),
    vessel: pick(record.vessel, job?.vessel),
    voyage: pick(record.voyage, job?.voyage),
    containerNo,
    containerType: printStr(record.containerType) || printStr(job?.containerType),
    packageQty,
    packageUnit,
    shipper: pick(record.shipper, job?.shipper),
    consignee: pick(record.consignee, job?.consignee),
    notifyParty: pick(record.notifyParty, job?.notifyParty),
  }
}

function resolveSettlement(record: FreightRecord, financialAccounts: FreightRecord[]): PrintSettlement {
  const key = printStr(record.financialAccount).toLowerCase()
  const match = key
    ? financialAccounts.find(row => String(row.accountName || '').toLowerCase() === key)
    : financialAccounts.find(row => String(row.accountType || '').toLowerCase() === 'bank')
  if (!match) return { accountName: '', accountAddress: '', bankName: '', accountNumber: '', swiftCode: '' }
  return {
    accountName: printStr(match.accountName),
    accountAddress: printStr(match.accountAddress) || printStr(match.address),
    bankName: printStr(match.bankName),
    // Only the masked, print-authorized number ever reaches paper.
    accountNumber: printStr(match.accountNumberMasked),
    swiftCode: printStr(match.swiftCode),
  }
}

function resolveSignatures(record: FreightRecord): PrintSignatures {
  return {
    customerSignatureUrl: printStr(record.customerSignatureUrl),
    customerStampUrl: printStr(record.customerStampUrl),
    sellerSignatureUrl: printStr(record.sellerSignatureUrl),
    sellerStampUrl: printStr(record.sellerStampUrl),
  }
}

/** Build the shared print view model for a scoped record. */
export function buildPrintViewModel(
  record: FreightRecord,
  templateId: string,
  context: PrintModelContext = {},
): PrintViewModel {
  const currency = printStr(record.currency) || 'USD'
  const exchangeRate = printNum(record.exchangeRate) || printNum(record.exchangeRateLocal)
  const lines = normalizeDocumentLines(record, templateId)
  const { subtotal, totalDebit, totalCredit } = sumPrintLines(lines)
  const taxRate = printNum(record.vatRate ?? record.taxRate)
  const taxAmount = printNum(record.vat ?? record.taxAmount)
  const grandTotal = printNum(record.total ?? record.grandTotal) || subtotal + taxAmount
  const localCurrency = printStr(context.localCurrency) || 'KHR'
  const outstanding = printNum(record.outstanding ?? record.amountDue)
  const party = resolveParty(printStr(record.customer) || printStr(record.supplier), context, record)

  return {
    templateId,
    issuer: {
      name: '',
      legalName: '',
      nameKh: '',
      legalNameKh: '',
      displayName: '',
      taxIdentifier: '',
      address: '',
      addressKh: '',
      phone: '',
      email: '',
      contact: '',
      logoUrl: printStr(context.logoUrl) || DEFAULT_INVOICE_LOGO_URL,
    },
    party,
    document: {
      number: templateId === 'tax-invoice'
        ? printStr(record.invoiceNo) || printStr(record.id)
        : printStr(record.debitNoteNo) || printStr(record.invoiceNo) || printStr(record.id),
      documentType: printStr(record.documentType),
      issueDate: printStr(record.date),
      dueDate: printStr(record.dueDate),
      currency,
      status: printStr(record.status),
      remarks: printStr(record.remark) || printStr(record.remarks),
      personInCharge: printStr(record.personInCharge),
      exchangeRate,
    },
    shipment: resolveShipment(record, context.jobs || []),
    lines,
    totals: {
      currency,
      subtotal,
      taxRate,
      taxAmount,
      grandTotal,
      totalDebit,
      totalCredit,
      balance: totalDebit - totalCredit,
      localCurrency,
      exchangeRate,
      grandTotalLocal: exchangeRate > 0 ? grandTotal * exchangeRate : 0,
      outstanding,
    },
    settlement: resolveSettlement(record, context.financialAccounts || []),
    signatures: resolveSignatures(record),
    watermark: printWatermarkFor(record.status),
    amountInWords: templateId === 'debit-note'
      ? formatDebitNoteAmountInWords(totalDebit - totalCredit, currency)
      : amountInWords(grandTotal, currency),
  }
}

/**
 * Service Order Finance Summary arithmetic.
 *
 * Values come from the same records the backend persists: linked Service
 * Charges (already discounted/taxed by the charge service) and financial
 * documents (already carrying their posted totals, paid amount and outstanding
 * balance). Nothing here recalculates a posted document; it only aggregates the
 * authoritative values and keeps currencies separate.
 *
 * Sums are done on scaled integers, not floats, so 0.1 + 0.2 is 0.3 and a
 * credit line subtracts exactly.
 */
import type { FreightRecord } from '~/types/record'
import { chargeDomainStatus, financeDomainStatus } from '~/utils/freight/states'
import {
  EXCLUDED_FINANCE_SUMMARY_STATUSES,
  EXPENSE_BEHAVIORS,
  EXPENSE_CREDIT_BEHAVIORS,
  INCOME_BEHAVIORS,
  INCOME_CREDIT_BEHAVIORS,
} from '~/utils/constants/document-types'

const SCALE = 10_000n

/** Parse a decimal value into 4-dp scaled integer; invalid values contribute 0. */
export function scaledDecimal(value: unknown): bigint {
  const raw = typeof value === 'number'
    ? (Number.isFinite(value) ? String(value) : '')
    : String(value ?? '').trim()
  if (!raw) return 0n
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(raw)
  if (!match) return 0n
  const sign = match[1] === '-' ? -1n : 1n
  const whole = BigInt(match[2] || '0') * SCALE
  const fraction = BigInt((match[3] || '').padEnd(4, '0').slice(0, 4) || '0')
  return sign * (whole + fraction)
}

/** Display/money formatter value from a scaled integer. */
export function scaledNumber(value: bigint): number {
  return Number(value) / Number(SCALE)
}

export type FinanceSummaryCharge = {
  id?: string
  clientRowId?: string
  status?: unknown
  currency?: unknown
  total?: unknown
  financialDocumentId?: unknown
}

export type FinanceSummaryInternalCharge = {
  currency?: unknown
  /** Internal cost side; the selling side is already in `charges`. */
  costTotal?: unknown
  supplierDocumentId?: unknown
}

export type FinanceSummaryEntry = {
  id?: string
  status?: unknown
  currency?: unknown
  /** Accounting behaviour: CUSTOMER_INVOICE, SUPPLIER_BILL, ... */
  behavior?: string
  /** Live draft amount; for a posted row the caller passes the authoritative total. */
  total?: unknown
  /** Posted invoice/bill balance left after allocations. */
  outstanding?: unknown
  paidAmount?: unknown
}

export type FinanceSummaryGroup = {
  currency: string
  totalCharges: number
  chargedAmount: number
  unchargedAmount: number
  totalExpenses: number
  netAmount: number
  outstandingBalance: number
  /** Amounts still in DRAFT (preview) rather than formally charged/posted. */
  draftCharges: number
  draftExpenses: number
  /** True when any contributing figure is a draft/unposted preview. */
  estimated: boolean
}

type Totals = {
  currency: string
  totalCharges: bigint
  chargedAmount: bigint
  totalExpenses: bigint
  draftCharges: bigint
  draftExpenses: bigint
  outstandingBalance: bigint
}

function emptyTotals(currency: string): Totals {
  return {
    currency,
    totalCharges: 0n,
    chargedAmount: 0n,
    totalExpenses: 0n,
    draftCharges: 0n,
    draftExpenses: 0n,
    outstandingBalance: 0n,
  }
}

function amountOf(value: unknown): bigint {
  return scaledDecimal(value)
}

function behaviorOf(document: FreightRecord | Record<string, unknown>): string {
  return String(
    (document as Record<string, unknown>).accountingBehavior
    || (document as Record<string, unknown>).documentType
    || '',
  ).toUpperCase()
}

/** Apply an unsaved charge total over the saved row with the same identity. */
function withPreview(
  charges: readonly FinanceSummaryCharge[],
  preview?: FinanceSummaryCharge | null,
): FinanceSummaryCharge[] {
  if (!preview) return [...charges]
  const previewId = String(preview.id || '').trim()
  const previewMarker = String(preview.clientRowId || '').trim()
  const matchIndex = charges.findIndex((charge) => {
    if (previewId && String(charge.id || '') === previewId) return true
    return Boolean(previewMarker) && String(charge.clientRowId || '') === previewMarker
  })
  if (matchIndex < 0) return [...charges, preview]
  return charges.map((charge, index) => (index === matchIndex ? { ...charge, ...preview } : charge))
}

export function buildFinanceSummary(input: {
  charges: readonly FinanceSummaryCharge[]
  entries: readonly FinanceSummaryEntry[]
  /** Internal cost preview; skipped once its supplier draft exists. */
  internalCharges?: readonly FinanceSummaryInternalCharge[]
  /** The selected charge's unsaved total, if any. */
  previewCharge?: FinanceSummaryCharge | null
  /** Always show this currency even when it has no rows yet. */
  primaryCurrency?: string
}): FinanceSummaryGroup[] {
  const groups = new Map<string, Totals>()
  const currencyOf = (value: unknown, fallback = '') => String(value ?? '').trim() || fallback

  function totals(currency: string): Totals {
    const key = currency || '—'
    const existing = groups.get(key)
    if (existing) return existing
    const created = emptyTotals(currency)
    groups.set(key, created)
    return created
  }

  const primary = currencyOf(input.primaryCurrency)
  if (primary) totals(primary)

  for (const charge of withPreview(input.charges, input.previewCharge)) {
    const status = chargeDomainStatus(charge.status)
    if (status !== 'DRAFT' && status !== 'ISSUED') continue
    const currency = currencyOf(charge.currency, primary)
    const bucket = totals(currency)
    const total = amountOf(charge.total)
    bucket.totalCharges += total
    // Only an issued charge is formally charged. A linked draft invoice is not
    // an invoiced amount yet.
    if (status === 'ISSUED') {
      bucket.chargedAmount += total
    }
    else {
      bucket.draftCharges += total
    }
  }

  // Internal cost is a preview only until a generated supplier bill exists;
  // once it does, the bill is the authoritative expense and this rows is skipped.
  for (const internal of input.internalCharges || []) {
    if (String(internal.supplierDocumentId || '').trim()) continue
    const cost = amountOf(internal.costTotal)
    if (cost === 0n) continue
    const currency = currencyOf(internal.currency, primary)
    const bucket = totals(currency)
    bucket.totalExpenses += cost
    bucket.draftExpenses += cost
  }

  for (const entry of input.entries) {
    const status = financeDomainStatus(entry.status)
    if (EXCLUDED_FINANCE_SUMMARY_STATUSES.has(status)) continue
    const behavior = String(entry.behavior || '').toUpperCase()
    const currency = currencyOf(entry.currency, primary)
    const bucket = totals(currency)
    const total = amountOf(entry.total)
    if (EXPENSE_BEHAVIORS.has(behavior) || EXPENSE_CREDIT_BEHAVIORS.has(behavior)) {
      const signed = EXPENSE_CREDIT_BEHAVIORS.has(behavior) ? -total : total
      bucket.totalExpenses += signed
      if (status !== 'POSTED') bucket.draftExpenses += signed
      continue
    }
    if (!INCOME_BEHAVIORS.has(behavior) && !INCOME_CREDIT_BEHAVIORS.has(behavior)) continue
    // Outstanding is an authoritative posted receivable balance. A draft
    // invoice is never outstanding money yet. A posted credit note reduces the
    // receivable (a negative balance is a valid customer credit).
    if (status === 'POSTED') {
      const paid = amountOf(entry.paidAmount)
      const outstanding = entry.outstanding !== undefined && entry.outstanding !== null
        ? amountOf(entry.outstanding)
        : total - paid
      bucket.outstandingBalance += INCOME_CREDIT_BEHAVIORS.has(behavior) ? -outstanding : outstanding
    }
  }

  return [...groups.values()].map((bucket) => {
    const uncharged = bucket.totalCharges - bucket.chargedAmount
    const net = bucket.totalCharges - bucket.totalExpenses
    return {
      currency: bucket.currency,
      totalCharges: scaledNumber(bucket.totalCharges),
      chargedAmount: scaledNumber(bucket.chargedAmount),
      // Never clamp: a credit/overcharge is a valid negative difference.
      unchargedAmount: scaledNumber(uncharged),
      totalExpenses: scaledNumber(bucket.totalExpenses),
      netAmount: scaledNumber(net),
      outstandingBalance: scaledNumber(bucket.outstandingBalance),
      draftCharges: scaledNumber(bucket.draftCharges),
      draftExpenses: scaledNumber(bucket.draftExpenses),
      estimated: bucket.draftCharges !== 0n || bucket.draftExpenses !== 0n,
    }
  })
}

/** Behaviour for a financial document, from its type master when available. */
export function financeDocumentBehavior(
  document: FreightRecord | Record<string, unknown>,
  documentTypes: readonly FreightRecord[] = [],
): string {
  const code = String((document as Record<string, unknown>).documentType || '').toUpperCase()
  const typeRecord = documentTypes.find(row => String(row.code || '').toUpperCase() === code)
  return String(typeRecord?.accountingBehavior || behaviorOf(document)).toUpperCase()
}

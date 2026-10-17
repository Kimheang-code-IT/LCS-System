/**
 * Currency conversion for the document form.
 *
 * The backend is authoritative: it resolves the rate, validates it, and stores
 * the converted amounts on the document. The form still has to show the same
 * figures while they are being typed, so the arithmetic lives here once, in the
 * same shape the ledger uses — `base = amount * rate`, rounded with the
 * currency's configured precision — and the rate is always shown in its readable
 * direction so a rate below 1 never renders as a fraction.
 */

import { formatNumber } from '~/utils/format/format-service'

/** Fallback when the currency master does not say (matches the backend default). */
export const DEFAULT_CURRENCY_PRECISION = 2

/** The most decimal places a currency may be configured with (matches the backend). */
export const MAX_CURRENCY_PRECISION = 6

/**
 * How a rate renders: up to the stored scale, but never padded to the currency's
 * two decimals — a rate is a ratio, not an amount, so "1 USD = 4,000 KHR" reads
 * better than "4,000.00".
 */
const RATE_FORMAT: Intl.NumberFormatOptions = {
  minimumFractionDigits: 0,
  maximumFractionDigits: MAX_CURRENCY_PRECISION,
}

/** Round a money amount half-up to a number of decimal places. */
export function roundMoney(value: number, precision: number = DEFAULT_CURRENCY_PRECISION): number {
  return Number(value.toFixed(currencyPrecision(precision)))
}

/**
 * A currency's configured decimal places, clamped to what may be stored.
 *
 * Zero is a legitimate configuration (the Riel and the Yen have no minor unit), so
 * only a missing value falls back to the default — treating 0 as "unset" would
 * round a whole-unit currency to two decimals and disagree with the backend.
 */
export function currencyPrecision(
  value: unknown,
  fallback: number = DEFAULT_CURRENCY_PRECISION,
): number {
  if (value === undefined || value === null || value === '') return fallback
  const places = Number(value)
  if (!Number.isFinite(places)) return fallback
  return Math.max(0, Math.min(Math.trunc(places), MAX_CURRENCY_PRECISION))
}

/** Case-insensitive currency comparison; false when either side is empty. */
export function sameCurrency(left: unknown, right: unknown): boolean {
  const first = String(left ?? '').trim().toUpperCase()
  const second = String(right ?? '').trim().toUpperCase()
  return Boolean(first) && first === second
}

/**
 * The rate direction a document displays ("1 USD = 4,000 KHR").
 *
 * A rate at or above 1 reads as "1 document = rate base". A rate below 1 — which
 * is what a document in a small unit against a large one stores, because the
 * ledger multiplies by it — is inverted for display, so the operator reads
 * "1 base = 1/rate document" instead of six zeros. Empty when there is nothing
 * meaningful to show (same currency, or a rate that is not usable).
 */
export function rateDirection(
  documentCurrency: unknown,
  baseCurrency: unknown,
  rate: unknown,
): string {
  const document = String(documentCurrency ?? '').trim().toUpperCase()
  const base = String(baseCurrency ?? '').trim().toUpperCase()
  const value = Number(rate)
  if (!document || !base || document === base) return ''
  if (!Number.isFinite(value) || value <= 0) return ''
  return value >= 1
    ? `1 ${document} = ${formatNumber(value, RATE_FORMAT)} ${base}`
    : `1 ${base} = ${formatNumber(1 / value, RATE_FORMAT)} ${document}`
}

/**
 * The converted amount of one document amount.
 *
 * An amount that cannot be converted (no usable rate) comes back as `null`, which
 * the form renders as empty rather than as a misleading zero.
 */
export function baseAmount(
  amount: unknown,
  rate: unknown,
  precision: number = DEFAULT_CURRENCY_PRECISION,
): number | null {
  const value = Number(amount)
  const applied = Number(rate)
  if (!Number.isFinite(value) || !Number.isFinite(applied) || applied <= 0) return null
  return roundMoney(value * applied, precision)
}

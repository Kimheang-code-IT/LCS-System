import type { AppConfigLocalization } from '~/types/settings'
import { shallowRef } from 'vue'

/** Defaults aligned with System Settings → Localization. */
export const DEFAULT_FORMAT_CONFIG: AppConfigLocalization = {
  defaultLanguage: 'en',
  availableLanguages: ['en', 'km'],
  timezone: 'Asia/Phnom_Penh',
  dateFormat: 'DD/MM/YYYY',
  timeFormat: 'HH:mm',
  firstDayOfWeek: 1,
  numberFormat: '#,##0.00',
  currency: 'USD',
  locale: 'en-US',
}

const NUMBER_FORMATS: Record<string, { locale: string, digits: number }> = {
  '#,##0.00': { locale: 'en-US', digits: 2 },
  '#.##0,00': { locale: 'de-DE', digits: 2 },
  '# ##0,00': { locale: 'fr-FR', digits: 2 },
}
const LEGACY_NUMBER_FORMATS: Record<string, string> = {
  '1,234.56': '#,##0.00',
  '1.234,56': '#.##0,00',
  '1 234,56': '# ##0,00',
}
const DATE_FORMATS = new Set(['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY', 'DD-MM-YYYY', 'D MMM YYYY'])
const TIME_FORMATS = new Set(['HH:mm', 'HH:mm:ss', 'h:mm A', 'h:mm:ss A'])
const LANGUAGES = new Set(['en', 'km'])
const CURRENCIES = new Set(['USD', 'KHR', 'THB', 'VND', 'SGD', 'EUR', 'GBP', 'JPY', 'CNY'])
const LANGUAGE_LOCALES: Record<string, string> = { en: 'en-US', km: 'km-KH' }

let activeConfig: AppConfigLocalization = {
  ...DEFAULT_FORMAT_CONFIG,
  availableLanguages: [...DEFAULT_FORMAT_CONFIG.availableLanguages],
}
export const formatConfigVersion = shallowRef(0)

function supportedTimezone(value: unknown): value is string {
  if (typeof value !== 'string' || !value) return false
  try {
    new Intl.DateTimeFormat('en', { timeZone: value }).format()
    return true
  }
  catch {
    return false
  }
}

export function normalizeFormatConfig(next: Partial<AppConfigLocalization> = {}): AppConfigLocalization {
  const language = LANGUAGES.has(String(next.defaultLanguage))
    ? next.defaultLanguage as AppConfigLocalization['defaultLanguage']
    : DEFAULT_FORMAT_CONFIG.defaultLanguage
  const languages = Array.isArray(next.availableLanguages)
    ? next.availableLanguages.filter((item): item is 'en' | 'km' => LANGUAGES.has(item))
    : []
  const legacyNumberFormat = LEGACY_NUMBER_FORMATS[String(next.numberFormat)] || next.numberFormat
  const locale = LANGUAGE_LOCALES[language]!
  return {
    defaultLanguage: language,
    availableLanguages: languages.length ? [...new Set(languages)] : [...DEFAULT_FORMAT_CONFIG.availableLanguages],
    timezone: supportedTimezone(next.timezone) ? next.timezone : DEFAULT_FORMAT_CONFIG.timezone,
    dateFormat: DATE_FORMATS.has(String(next.dateFormat)) ? String(next.dateFormat) : DEFAULT_FORMAT_CONFIG.dateFormat,
    timeFormat: TIME_FORMATS.has(String(next.timeFormat)) ? String(next.timeFormat) : DEFAULT_FORMAT_CONFIG.timeFormat,
    firstDayOfWeek: next.firstDayOfWeek === 0 || next.firstDayOfWeek === 6 ? next.firstDayOfWeek : 1,
    numberFormat: NUMBER_FORMATS[String(legacyNumberFormat)] ? String(legacyNumberFormat) : DEFAULT_FORMAT_CONFIG.numberFormat,
    currency: CURRENCIES.has(String(next.currency)) ? String(next.currency) : DEFAULT_FORMAT_CONFIG.currency,
    locale,
  }
}

export function configureFormats(next: Partial<AppConfigLocalization>) {
  const normalized = normalizeFormatConfig({ ...activeConfig, ...next })
  if (JSON.stringify(normalized) === JSON.stringify(activeConfig)) return
  activeConfig = normalized
  formatConfigVersion.value += 1
}

export function getFormatConfig(): Readonly<AppConfigLocalization> {
  return activeConfig
}

function numberLocale() {
  void formatConfigVersion.value
  return NUMBER_FORMATS[activeConfig.numberFormat]?.locale || activeConfig.locale
}

function numberPrecision() {
  return NUMBER_FORMATS[activeConfig.numberFormat]?.digits ?? 2
}

function validDate(value: unknown): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (value == null || value === '') return null
  const text = normalizeTimestampInput(String(value))
  const date = new Date(text)
  return Number.isNaN(date.getTime()) ? null : date
}

/** Normalize legacy UTC timestamps to explicit ISO instants before parsing. */
export function normalizeTimestampInput(text: string) {
  const trimmed = text.trim()
  const normalized = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(trimmed) ? trimmed.replace(' ', 'T') : trimmed
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(normalized)) return `${normalized}Z`
  return normalized
}

function dateOnlyParts(value: unknown): { year: string, month: string, day: string } | null {
  const text = normalizeTimestampInput(String(value || ''))
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|T)/)
  if (!match || text.includes('T')) return null
  return { year: match[1]!, month: match[2]!, day: match[3]! }
}

function configuredDateParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const read = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value || ''
  return { year: read('year'), month: read('month'), day: read('day') }
}

function formatPattern(
  parts: { year: string, month: string, day: string },
  pattern: string,
  locale: string,
) {
  if (pattern === 'DD/MM/YYYY') return `${parts.day}/${parts.month}/${parts.year}`
  if (pattern === 'MM/DD/YYYY') return `${parts.month}/${parts.day}/${parts.year}`
  if (pattern === 'DD-MM-YYYY') return `${parts.day}-${parts.month}-${parts.year}`
  if (pattern === 'D MMM YYYY') {
    const safe = new Date(Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), 12))
    return new Intl.DateTimeFormat(locale, {
      timeZone: 'UTC',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(safe)
  }
  return `${parts.year}-${parts.month}-${parts.day}`
}

export function formatDate(value: unknown, fallback = '—') {
  void formatConfigVersion.value
  const rawParts = dateOnlyParts(value)
  const date = rawParts ? null : validDate(value)
  if (!rawParts && !date) return fallback
  try {
    const parts = rawParts || configuredDateParts(date!, activeConfig.timezone)
    return formatPattern(parts, activeConfig.dateFormat, activeConfig.locale)
  }
  catch {
    return rawParts ? `${rawParts.year}-${rawParts.month}-${rawParts.day}` : String(value || fallback)
  }
}

export function formatTime(value: unknown, fallback = '—') {
  void formatConfigVersion.value
  const date = validDate(value)
  if (!date) return fallback
  const showSeconds = activeConfig.timeFormat.includes('ss')
  const hour12 = activeConfig.timeFormat.toLowerCase().includes('a')
  try {
    return new Intl.DateTimeFormat(activeConfig.locale, {
      timeZone: activeConfig.timezone,
      hour: hour12 ? 'numeric' : '2-digit',
      minute: '2-digit',
      ...(showSeconds ? { second: '2-digit' as const } : {}),
      ...(hour12 ? { hour12: true } : { hourCycle: 'h23' as const }),
    }).format(date)
  }
  catch {
    return String(value || fallback)
  }
}

export function formatDateTime(value: unknown, fallback = '—') {
  void formatConfigVersion.value
  const date = validDate(value)
  if (!date) return fallback
  // A date-only value (YYYY-MM-DD) has no time to show; don't invent midnight in
  // the configured timezone, which would shift the displayed date/time.
  if (dateOnlyParts(value)) return formatDate(value, fallback)
  return `${formatDate(value, fallback)} ${formatTime(value, '')}`.trim()
}

export function formatDatePart(
  value: unknown,
  options: Intl.DateTimeFormatOptions,
  fallback = '—',
) {
  void formatConfigVersion.value
  const date = validDate(value)
  if (!date) return fallback
  try {
    return new Intl.DateTimeFormat(activeConfig.locale, {
      ...options,
      timeZone: options.timeZone || activeConfig.timezone,
    }).format(date)
  }
  catch {
    return String(value || fallback)
  }
}

export function formatNumber(value: unknown, options: Intl.NumberFormatOptions = {}) {
  void formatConfigVersion.value
  if (value == null || value === '') return ''
  const number = Number(value)
  if (!Number.isFinite(number)) return String(value ?? '')
  try {
    const digits = numberPrecision()
    return new Intl.NumberFormat(numberLocale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      ...options,
    }).format(number)
  }
  catch {
    return String(number)
  }
}

export function formatCurrency(value: unknown, currency = activeConfig.currency) {
  if (value == null || value === '') return ''
  const number = Number(value)
  if (!Number.isFinite(number)) return String(value)
  const code = String(currency || activeConfig.currency).trim().toUpperCase() || activeConfig.currency
  const digits = numberPrecision()
  try {
    return new Intl.NumberFormat(numberLocale(), {
      style: 'currency',
      currency: code,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(number)
  }
  catch {
    return `${code} ${formatNumber(number)}`
  }
}

/** Money display: record currency when provided, otherwise System Settings default. */
export function formatMoney(value: unknown, currency?: string) {
  const code = String(currency || activeConfig.currency).trim() || activeConfig.currency
  return formatCurrency(value, code)
}

export function formatCompact(value: unknown) {
  void formatConfigVersion.value
  if (value == null || value === '') return ''
  const number = Number(value)
  if (!Number.isFinite(number)) return String(value ?? '')
  try {
    return new Intl.NumberFormat(numberLocale(), {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(number)
  }
  catch {
    if (Math.abs(number) >= 1000) {
      return `${(number / 1000).toFixed(number % 1000 === 0 ? 0 : 1)}k`
    }
    return String(number)
  }
}

export type RelativeTimeLabels = {
  justNow: string
  minuteAgo?: string
  minutesAgo: (n: number) => string
  hourAgo?: string
  hoursAgo: (n: number) => string
  dayAgo?: string
  daysAgo: (n: number) => string
}

/** ERPNext-style relative stamp; switches to absolute date after `absoluteAfterDays`. */
export function formatRelativeTime(
  value: unknown,
  labels: RelativeTimeLabels,
  options?: { absoluteAfterDays?: number, fallback?: string },
) {
  const fallback = options?.fallback ?? '—'
  const raw = String(value ?? '').trim()
  if (!raw) return fallback

  const parsed = validDate(raw)
  if (!parsed) return raw

  const seconds = Math.round((Date.now() - parsed.getTime()) / 1000)
  const abs = Math.abs(seconds)

  if (abs < 45) return labels.justNow

  if (abs < 3600) {
    const mins = Math.max(1, Math.round(abs / 60))
    if (mins === 1 && labels.minuteAgo) return labels.minuteAgo
    return labels.minutesAgo(mins)
  }

  if (abs < 86400) {
    const hours = Math.max(1, Math.round(abs / 3600))
    if (hours === 1 && labels.hourAgo) return labels.hourAgo
    return labels.hoursAgo(hours)
  }

  const days = Math.max(1, Math.round(abs / 86400))
  const absoluteAfter = options?.absoluteAfterDays ?? 7
  if (days >= absoluteAfter) return formatDate(parsed, fallback)

  if (days === 1 && labels.dayAgo) return labels.dayAgo
  return labels.daysAgo(days)
}

/** Format date parts for date-picker placeholders (calendar day, not timezone-shifted). */
export function formatDateParts(parts: { year: number, month: number, day: number }) {
  void formatConfigVersion.value
  const yyyy = String(parts.year)
  const mm = String(parts.month).padStart(2, '0')
  const dd = String(parts.day).padStart(2, '0')
  return formatPattern({ year: yyyy, month: mm, day: dd }, activeConfig.dateFormat, activeConfig.locale)
}

import { describe, expect, it, beforeEach } from 'vitest'
import { effect } from 'vue'
import {
  configureFormats,
  DEFAULT_FORMAT_CONFIG,
  formatCompact,
  formatDate,
  formatDateTime,
  formatMoney,
  formatNumber,
  formatRelativeTime,
  formatTime,
  getFormatConfig,
  normalizeFormatConfig,
} from '../app/utils/format/format-service'

describe('format-service', () => {
  beforeEach(() => {
    configureFormats(DEFAULT_FORMAT_CONFIG)
  })

  it('formats dates from settings dateFormat', () => {
    configureFormats({ dateFormat: 'DD/MM/YYYY' })
    expect(formatDate('2026-08-20')).toBe('20/08/2026')
    expect(formatDate('2026-08-20T15:30:00')).toMatch(/20\/08\/2026/)
  })

  it('formats numbers from settings numberFormat locale', () => {
    configureFormats({ numberFormat: '#.##0,00', locale: 'de-DE' })
    expect(formatNumber(1234.5)).toBe('1.234,50')
  })

  it('formats money with record currency and settings locale', () => {
    configureFormats({ currency: 'USD', locale: 'en-US', numberFormat: '1,234.56' })
    const formatted = formatMoney(1250, 'USD')
    expect(formatted).toMatch(/1,?250\.00/)
    expect(formatted).toMatch(/USD|\$/)
    expect(formatMoney(1250, 'CAD')).toMatch(/1,250\.00/)
  })

  it('formats compact numbers', () => {
    configureFormats({ locale: 'en-US', numberFormat: '#,##0.00' })
    expect(formatCompact(1500)).toMatch(/1\.5K|1,5K/i)
  })

  it('formats time using configured timezone and 24h pattern', () => {
    configureFormats({
      timezone: 'UTC',
      timeFormat: 'HH:mm',
      locale: 'en-US',
    })
    const label = formatTime('2026-08-20T14:30:00Z')
    expect(label).toBe('14:30')
  })

  it('joins date and time for datetime values', () => {
    configureFormats({
      dateFormat: 'YYYY-MM-DD',
      timeFormat: 'HH:mm',
      timezone: 'UTC',
      locale: 'en-US',
    })
    const value = formatDateTime('2026-08-20T14:30:00Z')
    expect(value).toContain('2026-08-20')
    expect(value).toContain('14:30')
  })

  it('relative time uses labels and falls back to absolute date', () => {
    const labels = {
      justNow: 'Just now',
      minutesAgo: (n: number) => `${n}m`,
      hoursAgo: (n: number) => `${n}h`,
      daysAgo: (n: number) => `${n}d`,
    }
    const recent = formatRelativeTime(new Date(Date.now() - 120_000).toISOString(), labels)
    expect(recent).toBe('2m')

    const old = formatRelativeTime('2020-01-15', labels, { absoluteAfterDays: 7 })
    expect(old).toBe('15/01/2020')
  })

  it('handles null, invalid, zero, negative, decimals, and large numbers safely', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate('not-a-date')).toBe('—')
    expect(formatNumber(null)).toBe('')
    expect(formatNumber(undefined)).toBe('')
    expect(formatNumber(0)).toBe('0.00')
    expect(formatNumber(-1234.5)).toBe('-1,234.50')
    expect(formatNumber(1234567890.126)).toBe('1,234,567,890.13')
  })

  it('converts the same instant to Cambodia time and switches 12h/24h display', () => {
    configureFormats({ timezone: 'Asia/Phnom_Penh', timeFormat: 'HH:mm', dateFormat: 'DD/MM/YYYY' })
    expect(formatDateTime('2026-10-01T01:00:00Z')).toBe('01/10/2026 08:00')
    configureFormats({ timeFormat: 'h:mm A' })
    expect(formatTime('2026-10-01T11:30:00Z')).toMatch(/6:30\s*PM/i)
  })

  it('uses IANA daylight-saving rules without changing the instant', () => {
    configureFormats({ timezone: 'America/New_York', timeFormat: 'HH:mm' })
    expect(formatTime('2026-01-15T12:00:00Z')).toBe('07:00')
    expect(formatTime('2026-07-15T12:00:00Z')).toBe('08:00')
  })

  it('falls back from malformed settings and normalizes legacy number formats', () => {
    const normalized = normalizeFormatConfig({
      timezone: 'Mars/Olympus_Mons',
      currency: 'BTC',
      dateFormat: 'YY/DD',
      timeFormat: 'clock',
      numberFormat: '1 234,56',
    })
    expect(normalized.timezone).toBe(DEFAULT_FORMAT_CONFIG.timezone)
    expect(normalized.currency).toBe(DEFAULT_FORMAT_CONFIG.currency)
    expect(normalized.dateFormat).toBe(DEFAULT_FORMAT_CONFIG.dateFormat)
    expect(normalized.timeFormat).toBe(DEFAULT_FORMAT_CONFIG.timeFormat)
    expect(normalized.numberFormat).toBe('# ##0,00')
  })

  it('reactively invalidates consumers when settings change', () => {
    let rendered = ''
    effect(() => {
      rendered = formatDate('2026-10-01')
    })
    expect(rendered).toBe('01/10/2026')
    configureFormats({ dateFormat: 'YYYY-MM-DD' })
    expect(rendered).toBe('2026-10-01')
    expect(getFormatConfig().dateFormat).toBe('YYYY-MM-DD')
  })
})

import { describe, expect, it } from 'vitest'
import {
  DEFAULT_INVOICE_LOGO_URL,
  buildPrintRoute,
  documentDetailPath,
  isAutoPrintRoute,
  safePrintReturnPath,
} from '../app/utils/freight/print-navigation'

describe('invoice print navigation', () => {
  it('keeps valid internal document routes', () => {
    expect(safePrintReturnPath('/service-charges/jc-001?tab=traceability', '/service-charges')).toBe('/service-charges/jc-001?tab=traceability')
    expect(safePrintReturnPath(['/finance/documents/dn-001'], '/finance/documents')).toBe('/finance/documents/dn-001')
  })

  it('rejects external and malformed return routes', () => {
    const fallback = '/finance/documents/dn-001'
    expect(safePrintReturnPath('https://example.com', fallback)).toBe(fallback)
    expect(safePrintReturnPath('//example.com/path', fallback)).toBe(fallback)
    expect(safePrintReturnPath('/service-charges\\jc-001', fallback)).toBe(fallback)
    expect(safePrintReturnPath('/service-charges/jc-001\nnext', fallback)).toBe(fallback)
  })

  it('builds encoded detail paths and exposes the LCS logo fallback', () => {
    expect(documentDetailPath('/service-charges', 'SC 001')).toBe('/service-charges/SC%20001')
    expect(DEFAULT_INVOICE_LOGO_URL).toBe('/lcs-invoice-logo.png')
  })

  it('builds auto-print routes and detects auto-print query', () => {
    expect(buildPrintRoute({
      collection: 'debitNotes',
      recordId: 'dn-001',
      template: 'tax-invoice',
      returnTo: '/finance/documents/dn-001',
      modulePath: '/finance/documents',
    })).toEqual({
      path: '/print/debitNotes/dn-001',
      query: {
        template: 'tax-invoice',
        returnTo: '/finance/documents/dn-001',
        autoPrint: '1',
      },
    })
    expect(buildPrintRoute({
      collection: 'jobCharges',
      recordId: 'jc-001',
      template: 'tax-invoice',
      lineIndex: 1,
      returnTo: '/service-charges/jc-001',
      modulePath: '/service-charges',
    })).toEqual({
      path: '/print/jobCharges/jc-001',
      query: {
        template: 'tax-invoice',
        returnTo: '/service-charges/jc-001',
        autoPrint: '1',
        line: '1',
      },
    })
    expect(isAutoPrintRoute({ autoPrint: '1' })).toBe(true)
    expect(isAutoPrintRoute({ autoPrint: 'true' })).toBe(true)
    expect(isAutoPrintRoute({})).toBe(false)
  })
})

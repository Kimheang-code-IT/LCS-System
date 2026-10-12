import { describe, expect, it, vi } from 'vitest'

import { ACTIVE_STATUS, CONTAINER_STATUSES, DOCUMENT_TYPES } from '../app/config/freight-options'
import { labeledStatusOptions, shortDay } from '../app/utils/freight/format'
import { defaultStatusForModule, emptyFreightRecord, statusColor } from '../app/composables/freight/useFreight'
import { lcsReferenceModules } from '../app/config/lcs-reference-modules'
import { freightModules } from '../app/config/freight-modules'

vi.mock('#components', () => ({
  UBadge: { name: 'UBadge' },
}))

describe('shortDay', () => {
  it('uses the configured default date format and falls back when empty', () => {
    expect(shortDay('2026-08-20T11:40:00')).toBe('20/08/2026')
    expect(shortDay('')).toBe('—')
    expect(shortDay('', '')).toBe('')
  })
})

describe('labeledStatusOptions', () => {
  it('uses catalog i18n when the key exists, otherwise a readable code', () => {
    const t = (key: string) => key === 'freight.reportCatalog.statuses.open' ? 'Open' : key
    const te = (key: string) => key === 'freight.reportCatalog.statuses.open'
    expect(labeledStatusOptions(['OPEN', 'IN_PROGRESS'], t, te)).toEqual([
      { label: 'Open', value: 'OPEN' },
      { label: 'IN PROGRESS', value: 'IN_PROGRESS' },
    ])
  })
})

describe('statusColor', () => {
  it('maps issued/completed to success and draft/pending to warning', () => {
    expect(statusColor('Issued')).toBe('success')
    expect(statusColor('COMPLETED')).toBe('success')
    expect(statusColor('Draft')).toBe('warning')
    expect(statusColor('PENDING')).toBe('warning')
  })
})

describe('new record status defaults', () => {
  it('starts a master-data reference record as Active, never Draft', () => {
    const businessParties = lcsReferenceModules.find(module => module.collection === 'businessParties')
    expect(businessParties).toBeTruthy()
    expect(emptyFreightRecord(businessParties!).status).toBe('Active')
  })

  it('starts a service order as Active', () => {
    const jobs = freightModules.find(module => module.collection === 'jobs')
    expect(jobs).toBeTruthy()
    expect(emptyFreightRecord(jobs!).status).toBe('Active')
  })

  it('keeps the first declared workflow status for document modules', () => {
    const quotations = freightModules.find(module => module.collection === 'quotations')
    expect(quotations).toBeTruthy()
    expect(defaultStatusForModule(quotations!)).toBe('Draft')
  })
})

describe('freight option lists', () => {
  it('keeps supporting-document on DOCUMENT_TYPES and container workflow statuses in config', () => {
    expect(DOCUMENT_TYPES).toContain('Supporting Document')
    expect([...CONTAINER_STATUSES]).toEqual(['Expected', 'Planned', 'Loaded', 'In Transit', 'Delivered', 'Returned'])
    expect([...ACTIVE_STATUS]).toEqual(['Active', 'Inactive'])
  })
})

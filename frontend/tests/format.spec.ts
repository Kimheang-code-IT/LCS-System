import { describe, expect, it, vi } from 'vitest'

vi.mock('#components', () => ({
  UBadge: { name: 'UBadge' },
}))

import { CONTAINER_STATUSES, DOCUMENT_TYPES, JOB_WORKFLOW_STATUS } from '../app/config/freight-options'
import { labeledStatusOptions, shortDay } from '../app/utils/freight/format'
import { statusColor } from '../app/composables/freight/useFreight'

describe('shortDay', () => {
  it('keeps YYYY-MM-DD and falls back when empty', () => {
    expect(shortDay('2026-08-20T11:40:00')).toBe('2026-08-20')
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

describe('freight option lists', () => {
  it('keeps supporting-document on DOCUMENT_TYPES and container workflow statuses in config', () => {
    expect(DOCUMENT_TYPES).toContain('Supporting Document')
    expect([...CONTAINER_STATUSES]).toEqual(['Expected', 'Planned', 'Loaded', 'In Transit', 'Delivered', 'Returned'])
    expect(JOB_WORKFLOW_STATUS).toContain('OPEN')
  })
})

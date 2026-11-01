import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'
import type { FreightModule } from '../app/config/freight-modules'
import { normalizeAuditLog, resolveAuditEntityPath } from '../app/utils/freight/audit-logs'

// `useFreight` renders badges through Nuxt's `#components`; the node test only
// needs its pure cell formatter.
vi.mock('#components', () => ({ UBadge: { name: 'UBadge' } }))

const { formatFreightCell } = await import('../app/composables/freight/useFreight')

const moduleStub = (partial: Partial<FreightModule>): FreightModule => ({
  path: '/service-orders', title: 'Service Orders', titleKm: '', singular: 'Service Order', singularKm: '',
  description: '', descriptionKm: '', icon: '', group: 'operations', permission: 'operations.service_orders.view',
  collection: 'jobs', titleField: 'jobNo', columns: [], fields: [], canCreate: true, kind: 'job',
  ...partial,
})

describe('audit log table logic', () => {
  it('normalizes legacy audit rows for the table', () => {
    expect(normalizeAuditLog({ id: 'log-1', action: 'Updated service order', module: 'Service Orders', recordNo: 'JOB-1', remark: 'Changed route' })).toMatchObject({
      eventType: 'UPDATED_SERVICE_ORDER', entityType: 'Service Orders', entity: 'JOB-1', result: 'SUCCESS', reason: 'Changed route',
    })
  })

  it('links an entity to an existing accessible record', () => {
    const path = resolveAuditEntityPath(
      { id: 'log-1', entityType: 'Service Order', entity: 'JOB-1' },
      [moduleStub({})],
      collection => collection === 'jobs' ? [{ id: 'job-1', jobNo: 'JOB-1' }] : [],
      () => true,
    )
    expect(path).toBe('/service-orders/job-1')
  })

  it('does not create broken or unauthorized links', () => {
    const module = moduleStub({})
    expect(resolveAuditEntityPath({ id: 'log-1', entity: 'MISSING' }, [module], () => [], () => true)).toBe('')
    expect(resolveAuditEntityPath({ id: 'log-2', entity: 'JOB-1' }, [module], () => [{ id: 'job-1', jobNo: 'JOB-1' }], () => false)).toBe('')
  })

  it('renders the record identifier as an identifier, never as an amount', () => {
    // Regression: the numeric cell formatter produced "46.00" for entityId.
    expect(formatFreightCell(46, 'entityId')).toBe('46')
    expect(formatFreightCell(1234, 'entityId')).toBe('1234')
    // Money is still formatted as money.
    expect(formatFreightCell(46, 'amount', 'USD')).not.toBe('46')
    expect(formatFreightCell(46, 'amount', 'USD')).toMatch(/46/)
    // Datetimes render as datetimes even without the At/Timestamp suffix
    // (regression: the users list printed the raw IS0-8601 string).
    expect(formatFreightCell('2026-10-31T03:43:09.617190+00:00', 'lastLogin')).not.toContain('T03')
  })

  it('keeps the shared status manager from probing a missing policy', () => {
    // The pure predicate is what loadPolicy() consults; this pins the call so a
    // future edit cannot silently re-enable the request for read-only history.
    const source = readFileSync(
      fileURLToPath(new URL('../app/composables/freight/useRecordStatus.ts', import.meta.url)),
      'utf8',
    )
    expect(source).toContain('supportsStatusPolicy(current)')
  })
})

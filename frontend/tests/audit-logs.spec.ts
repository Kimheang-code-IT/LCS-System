import { describe, expect, it } from 'vitest'
import type { FreightModule } from '../app/config/freight-modules'
import { normalizeAuditLog, resolveAuditEntityPath } from '../app/utils/freight/audit-logs'

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
})

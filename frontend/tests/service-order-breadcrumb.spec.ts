import { describe, expect, it } from 'vitest'
import { serviceOrderBreadcrumbs } from '../app/utils/freight/job-workspace'

const list = { label: 'Service Orders', to: '/service-orders' }

describe('service order breadcrumb', () => {
  it('shows the real document number returned by the API', () => {
    expect(serviceOrderBreadcrumbs('Service Orders', '/service-orders', {
      id: '42',
      jobNo: 'SO2026-000001',
    })).toEqual([list, { label: 'SO2026-000001' }])
  })

  it('falls back to the API alias, never to the database id', () => {
    expect(serviceOrderBreadcrumbs('Service Orders', '/service-orders', {
      id: '42',
      serviceOrderNo: 'SO2026-000002',
    })).toEqual([list, { label: 'SO2026-000002' }])
  })

  it('links the parent crumb to the Service Orders list', () => {
    const items = serviceOrderBreadcrumbs('Service Orders', '/service-orders', { jobNo: 'SO2026-000003' })
    expect(items[0]).toEqual(list)
  })

  it('updates when a different record is loaded', () => {
    const first = serviceOrderBreadcrumbs('Service Orders', '/service-orders', { jobNo: 'SO2026-000004' })
    const second = serviceOrderBreadcrumbs('Service Orders', '/service-orders', { jobNo: 'SO2026-000005' })
    expect(first[1]!.label).toBe('SO2026-000004')
    expect(second[1]!.label).toBe('SO2026-000005')
  })

  it('handles loading and missing records without a fake number', () => {
    expect(serviceOrderBreadcrumbs('Service Orders', '/service-orders', {}, { loading: true }))
      .toEqual([list, { label: '…' }])
    expect(serviceOrderBreadcrumbs('Service Orders', '/service-orders', {}, { notFound: true }))
      .toEqual([list])
    expect(serviceOrderBreadcrumbs('Service Orders', '/service-orders', { jobNo: '   ' }))
      .toEqual([list])
  })
})

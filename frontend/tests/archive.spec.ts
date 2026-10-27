import { describe, expect, it } from 'vitest'
import { confirmsArchiveHardDelete, hasArchivePermission } from '~/utils/archive/access'
import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'
import { permissionRowsFromFlatKeys, permissionRowsToFlatKeys } from '~/utils/role/permissions'

describe('archive permissions and actions', () => {
  it('requires explicit source permissions for archive actions', () => {
    expect(hasArchivePermission([], 'archive.restore')).toBe(false)
    expect(hasArchivePermission(['archive.view'], 'archive.restore')).toBe(false)
    expect(hasArchivePermission(['archive.restore'], 'archive.restore')).toBe(true)
    expect(hasArchivePermission(['ALL_PAGES'], 'archive.hard_delete')).toBe(true)
  })

  it('maps legacy archive actions onto the matrix row', () => {
    const rows = permissionRowsFromFlatKeys(['archive.view', 'archive.restore', 'archive.hard_delete'])
    const archive = rows.find(row => row.documentType === 'admin_archive')
    expect(archive?.actions).toEqual(['view', 'restore'])

    const codes = permissionRowsToFlatKeys(rows)
    expect(codes).toContain('admin.archive.view')
    expect(codes).toContain('admin.archive.restore')
    expect(codes).not.toContain('admin.archive.delete')
    expect(codes).not.toContain('admin.archive.hard_delete')
  })

  it('does not imply restore from view or export', () => {
    const rows = permissionRowsFromFlatKeys(['admin.archive.view', 'admin.archive.export'])
    const archive = rows.find(row => row.documentType === 'admin_archive')
    expect(archive?.actions).toEqual(['view', 'export'])
  })

  it('requires the exact destructive confirmation phrase', () => {
    expect(confirmsArchiveHardDelete('DELETE')).toBe(true)
    expect(confirmsArchiveHardDelete('delete')).toBe(false)
    expect(confirmsArchiveHardDelete('DELETE ')).toBe(false)
  })

  it('builds the archive detail, restore, and hard-delete endpoints', () => {
    expect(ApiV1Endpoints.ARCHIVE_RECORD('feeTypes', 12)).toBe('/api/v1/archive/feeTypes/12')
    expect(ApiV1Endpoints.ARCHIVE_RESTORE('feeTypes', 12)).toBe('/api/v1/archive/feeTypes/12/restore')
  })
})

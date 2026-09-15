import { describe, expect, it } from 'vitest'
import type { AuthUser } from '../app/types/auth-user'
import { compactAuthUser, sessionHasPermissionData } from '../app/utils/auth/session'

const adminUser: AuthUser = {
  id: 1,
  name: 'Demo Administrator',
  email: 'admin@example.test',
  role: 'SuperAdmin',
  pageAccess: ['ALL_PAGES'],
  organizationId: 1,
  organizationCode: 'LCS',
  organizationName: 'LCS Freight',
  permissionScope: 'ORGANIZATION',
  assignedBranchIds: [1, 2],
}

const standardUser: AuthUser = {
  id: 2,
  name: 'Operations Officer',
  email: 'ops@example.test',
  role: 'Operations',
  permissions: ['operations.service_orders.view'],
  organizationId: 1,
  organizationCode: 'LCS',
  organizationName: 'LCS Freight',
  branchId: 1,
  assignedBranchIds: [1],
  permissionScope: 'BRANCH',
}

describe('auth session cookie', () => {
  it('keeps compact auth cookies under the browser size limit', () => {
    for (const user of [adminUser, standardUser]) {
      const compact = compactAuthUser(user)
      const bytes = JSON.stringify(compact).length
      expect(bytes).toBeLessThan(2048)
      expect(compact.permissions).toBeUndefined()
    }
  })

  it('marks all-access users with ALL_PAGES only', () => {
    const compact = compactAuthUser(adminUser)
    expect(compact.pageAccess).toEqual(['ALL_PAGES'])
    expect(sessionHasPermissionData(compact)).toBe(true)
  })

  it('treats compact standard sessions as missing permission data until hydrated', () => {
    const compact = compactAuthUser(standardUser)
    expect(sessionHasPermissionData(compact)).toBe(false)
    expect(sessionHasPermissionData(standardUser)).toBe(true)
  })
})

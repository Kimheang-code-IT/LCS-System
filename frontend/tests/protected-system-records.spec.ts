import { describe, expect, it } from 'vitest'
import { isProtectedManagementRecord } from '../app/utils/auth/protected-system-records'

describe('protected system management records', () => {
  it('identifies the protected administrator by the backend flag', () => {
    expect(isProtectedManagementRecord('users', { isProtectedSystemAccount: true })).toBe(true)
    expect(isProtectedManagementRecord('users', { username: 'admin' })).toBe(false)
  })

  it('protects built-in roles without affecting ordinary records', () => {
    expect(isProtectedManagementRecord('roles', { isSystemRole: true })).toBe(true)
    expect(isProtectedManagementRecord('roles', { isSystemRole: false })).toBe(false)
    expect(isProtectedManagementRecord('businessParties', { isSystemRole: true })).toBe(false)
  })

  it('hides archive for canonical document types only', () => {
    expect(isProtectedManagementRecord('documentTypes', { code: 'CUSTOMER_INVOICE' })).toBe(true)
    expect(isProtectedManagementRecord('documentTypes', { code: 'MY_CUSTOM_TYPE' })).toBe(false)
    expect(isProtectedManagementRecord('documentTypes', {})).toBe(false)
  })
})

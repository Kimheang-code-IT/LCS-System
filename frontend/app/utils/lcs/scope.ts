import type { FreightRecord } from '~/types/freight/record'
import type { LcsSession } from '~/types/lcs/session'
import { domainError } from '~/utils/lcs/errors'

const GENERIC_DENIED = 'You do not have access to this record.'

export function recordOrganizationId(record: Record<string, unknown> | null | undefined) {
  return Number(record?.organizationId || 0)
}

export function recordBranchId(record: Record<string, unknown> | null | undefined) {
  return Number(record?.branchId || 0)
}

export function isRecordInOrganization(record: Record<string, unknown>, organizationId: number) {
  const orgId = recordOrganizationId(record)
  return !orgId || orgId === organizationId
}

export function isRecordInBranchScope(record: Record<string, unknown>, session: LcsSession) {
  if (!isRecordInOrganization(record, session.organizationId)) return false
  const branchId = recordBranchId(record)
  if (!branchId) return true
  if (session.permissionScope === 'ORGANIZATION' && session.branchId === 'all') {
    return session.assignedBranchIds.includes(branchId)
  }
  if (session.branchId === 'all') {
    return session.assignedBranchIds.includes(branchId)
  }
  return branchId === session.branchId && session.assignedBranchIds.includes(branchId)
}

export function isRecordVisible(record: Record<string, unknown>, session: LcsSession) {
  if (!isRecordInBranchScope(record, session)) return false
  if (session.permissionScope === 'OWN') {
    return Number(record.createdByUserId || record.ownerUserId || 0) === session.userId
      || String(record.assignedStaff || '') === session.userName
  }
  return true
}

export function filterScopedRecords<T extends Record<string, unknown>>(rows: T[], session: LcsSession) {
  return rows.filter(row => isRecordVisible(row, session))
}

export function assertRecordAccess(record: FreightRecord | Record<string, unknown> | null | undefined, session: LcsSession) {
  if (!record) {
    throw domainError('REFERENCE_NOT_FOUND', 'The requested record was not found.', { statusCode: 404 })
  }
  if (!isRecordInOrganization(record, session.organizationId)) {
    throw domainError('ACCESS_DENIED', GENERIC_DENIED, { statusCode: 403 })
  }
  if (!isRecordInBranchScope(record, session)) {
    throw domainError('BRANCH_SCOPE_DENIED', GENERIC_DENIED, { statusCode: 403 })
  }
  if (session.permissionScope === 'OWN' && !isRecordVisible(record, session)) {
    throw domainError('ACCESS_DENIED', GENERIC_DENIED, { statusCode: 403 })
  }
}

export function assertPermission(session: LcsSession, code: LcsSession['sourcePermissions'][number]) {
  if (session.sourcePermissions.includes(code)) return
  throw domainError('ACCESS_DENIED', GENERIC_DENIED, { statusCode: 403 })
}

export function stampTenant<T extends Record<string, unknown>>(
  record: T,
  session: LcsSession,
  fallbackBranchId?: number,
): T {
  const branchId = session.branchId === 'all'
    ? (fallbackBranchId || session.assignedBranchIds[0] || 0)
    : session.branchId
  return {
    ...record,
    organizationId: session.organizationId,
    branchId,
    createdByUserId: record.createdByUserId || session.userId,
  }
}

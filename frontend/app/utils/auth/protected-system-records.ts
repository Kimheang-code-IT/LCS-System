export function isProtectedManagementRecord(
  collection: string | null | undefined,
  record: Record<string, unknown>,
): boolean {
  if (collection === 'users') return record.isProtectedSystemAccount === true
  if (collection === 'roles') return record.isSystemRole === true
  return false
}

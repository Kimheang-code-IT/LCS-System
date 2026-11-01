import { DOCUMENT_TYPE_BEHAVIORS } from '~/utils/constants/document-types'

export function isProtectedManagementRecord(
  collection: string | null | undefined,
  record: Record<string, unknown>,
): boolean {
  if (collection === 'users') return record.isProtectedSystemAccount === true
  if (collection === 'roles') return record.isSystemRole === true
  // The canonical seeded document types cannot be archived (SYSTEM_DOCUMENT_TYPE);
  // the row menu must not offer an action the API always refuses.
  if (collection === 'documentTypes') {
    return DOCUMENT_TYPE_BEHAVIORS.includes(String(record.code || '').toUpperCase() as never)
  }
  return false
}

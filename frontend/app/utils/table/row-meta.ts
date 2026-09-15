/** Shared list-row stamp / comment / avatar helpers for compact ERP tables. */

export function tableRowStamp(row: Record<string, unknown>) {
  return String(row.updatedAt || row.createdAt || row.date || row.occurredAt || '')
}

export function tableRowCommentCount(row: Record<string, unknown>) {
  const comments = row.comments
  if (Array.isArray(comments)) return comments.length
  const count = Number(row.commentCount)
  return Number.isFinite(count) && count > 0 ? count : 0
}

export function tableRowInitials(row: Record<string, unknown>) {
  const name = String(row.assignedStaff || row.updatedBy || row.createdBy || row.user || row.contact || '')
  const parts = name.split(/[\s.]+/).filter(Boolean)
  const letters = parts.slice(0, 2).map(part => part[0]).join('')
  return (letters || 'S').toUpperCase()
}

export function tableRowActorName(row: Record<string, unknown>) {
  return String(row.assignedStaff || row.updatedBy || row.createdBy || row.user || row.contact || '')
}

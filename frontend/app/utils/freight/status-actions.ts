import type { RecordStatusPolicy, RecordStatusTransition } from '~/types/status'
import { STATUS_ACTION_META, type StatusActionMeta } from '~/config/status-actions'

export type { StatusActionColor, StatusActionMeta } from '~/config/status-actions'

/** Statuses are stored and compared case-insensitively; ACTIVE === Active. */
export function normalizeRecordStatus(value: unknown): string {
  return String(value ?? '').trim().toUpperCase()
}

/**
 * How each transition verb looks in the row "..." menu. The backend decides
 * *which* transitions exist; this only maps the verb to its label, icon and
 * tone, with the target status as the label for vocabulary moves
 * ("Mark as Cleared").
 */
export function statusActionMeta(action: string): StatusActionMeta {
  return STATUS_ACTION_META[action] || STATUS_ACTION_META.change!
}

/** The record's lifecycle value, including the quotation revision special case. */
export function statusValueOf(row: Record<string, unknown>): unknown {
  return row.revisionStatus ?? row.workflowStatus ?? row.status
}

/** Transitions the policy allows from the record's current status. */
export function statusTransitionsFor(
  policy: RecordStatusPolicy | null | undefined,
  current: unknown,
): RecordStatusTransition[] {
  if (!policy) return []
  return policy.transitions[normalizeRecordStatus(current)] || []
}

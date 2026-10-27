import type { RecordStatusPolicy, RecordStatusTransition } from '~/types/status'
import { STATUS_ACTION_META, type StatusActionMeta } from '~/config/status-actions'
import type { FreightModule } from '~/config/freight-modules'

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

/**
 * Whether a module can own a record status policy at all.
 *
 * Historical and derived collections (audit logs, the archive, reports, the AR/AP
 * views) are read-only and have no lifecycle, and a module that exposes no
 * `status` value has nothing to transition. Asking the API for their policy only
 * produces a 404, so the shared status manager must not ask. The backend stays
 * authoritative: a module that passes this check is still offered only the
 * transitions its policy actually returns.
 */
export function supportsStatusPolicy(
  module: Pick<FreightModule, 'readOnly' | 'columns' | 'fields'>,
): boolean {
  if (module.readOnly) return false
  return [...(module.columns ?? []), ...(module.fields ?? [])].some(field => field.key === 'status')
}

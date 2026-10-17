/**
 * Record status policy as served by the backend (`GET
 * /api/v1/{collection}/status-policy`).
 *
 * The backend owns which transitions exist and who may perform them; the
 * frontend only renders what it is given, which is why a status can never be
 * offered from a screen that would be refused on save.
 */
export type RecordStatusTransitionKind = 'status' | 'command'

export interface RecordStatusTransition {
  /** The status this transition moves the record to. */
  to: string
  /** Verb used for labels, icons and the audit trail (`activate`, `post`…). */
  action: string
  /** `status` runs through the shared status endpoint, `command` through the
   * collection's own workflow endpoint (posting, reversal, issuing, closing). */
  kind: RecordStatusTransitionKind
  /** The user must confirm before it runs. */
  confirm: boolean
  /** A reason must be entered (reversal). */
  reason: boolean
}

export interface RecordStatusPolicy {
  collection: string
  statuses: string[]
  /** Normalised current status -> legal transitions. */
  transitions: Record<string, RecordStatusTransition[]>
}

/**
 * Session-scoped draft persistence for a record form.
 *
 * A quotation's unsaved state lives in `DocumentView`'s local `model` ref — it
 * dies on navigation, on the Add-New round trip to Master Data, and on a
 * browser refresh. This composable keeps a versioned copy in sessionStorage
 * (keyed by user and record, so two tabs or two users cannot collide) and
 * restores it on the next mount unless the server copy moved past the draft's
 * base — the server, not the local cache, is the authority once it changed.
 * Nothing here claims data was "saved": until the API confirms persistence the
 * only status shown is "Unsaved changes".
 */
export type RecordDraft = {
  /** Draft format version — bump to invalidate all stored copies at once. */
  v: number
  savedAt: string
  recordId: string
  /** `updatedAt` of the server record the draft was written against ('' when new). */
  baseUpdatedAt: string
  model: Record<string, unknown>
}

const DRAFT_VERSION = 1

export function recordDraftKey(user: string, collection: string, recordId: string): string {
  return `lcs.draft.${collection}.${user}.${recordId || 'new'}`
}

export function readRecordDraft(key: string): RecordDraft | null {
  const raw = sessionStorage.getItem(key)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as RecordDraft
    if (parsed?.v !== DRAFT_VERSION || typeof parsed.model !== 'object' || parsed.model === null) return null
    return parsed
  }
  catch {
    return null
  }
}

export function writeRecordDraft(key: string, draft: Omit<RecordDraft, 'v' | 'savedAt'>): void {
  const payload: RecordDraft = { ...draft, v: DRAFT_VERSION, savedAt: new Date().toISOString() }
  sessionStorage.setItem(key, JSON.stringify(payload))
}

export function clearRecordDraft(key: string): void {
  sessionStorage.removeItem(key)
}

/**
 * True when the draft may be applied over the freshly loaded record: the draft
 * must describe the same record, and — for an existing one — the server row
 * must not have been updated since the draft was written.
 */
export function draftAppliesTo(draft: RecordDraft, recordId: string, updatedAt: unknown): boolean {
  if (draft.recordId !== recordId) return false
  if (!recordId) return true
  return String(updatedAt ?? '') === draft.baseUpdatedAt
}
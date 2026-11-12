/**
 * Versioned draft persistence for a record form.
 *
 * A form's unsaved state lives in a component `model` ref and dies on
 * navigation or refresh. This composable keeps a copy in sessionStorage (tab
 * lifetime) or localStorage (survives a browser reopen), keyed by collection,
 * user and record so records/users cannot collide. A draft is applied only
 * while the server copy still matches the draft's `baseUpdatedAt`; otherwise
 * the caller offers the operator a Restore/Discard choice. Nothing here claims
 * data was "saved".
 */
export type RecordDraft = {
  /** Draft format version. v1 drafts are upgraded on read, never discarded. */
  v: number
  savedAt: string
  recordId: string
  /** Module the draft belongs to; used to reject a copy pasted into another key. */
  collection?: string
  /** Authenticated user the draft belongs to (single-tenant app: no workspace id). */
  scope?: string
  /** `updatedAt` of the server record the draft was written against ('' when new). */
  baseUpdatedAt: string
  model: Record<string, unknown>
}

const DRAFT_VERSION = 2
/** Versions this build can still read. v1 has no collection/scope fields. */
const READABLE_VERSIONS = new Set([1, DRAFT_VERSION])

/** Where a draft lives: `session` dies with the browser tab, `local` survives a reopen. */
export type DraftStorage = 'session' | 'local'

function draftArea(kind: DraftStorage): Storage | null {
  // `globalThis` is the browser window in the app and the test stub in vitest;
  // during SSR neither storage exists and the helpers degrade to no-ops.
  const scope = globalThis as { localStorage?: Storage, sessionStorage?: Storage }
  return (kind === 'local' ? scope.localStorage : scope.sessionStorage) ?? null
}

export function recordDraftKey(user: string, collection: string, recordId: string): string {
  return `lcs.draft.${collection}.${user}.${recordId || 'new'}`
}

export function readRecordDraft(key: string, storage: DraftStorage = 'session'): RecordDraft | null {
  const area = draftArea(storage)
  if (!area) return null
  let raw: string | null
  try {
    raw = area.getItem(key)
  }
  catch {
    // Private mode / denied storage: a form still works, it just cannot restore.
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as RecordDraft
    if (!parsed || !READABLE_VERSIONS.has(Number(parsed.v))
      || typeof parsed.model !== 'object' || parsed.model === null) {
      // A version this build cannot read is dropped instead of breaking the form.
      try { area.removeItem(key) }
      catch { /* ignore */ }
      return null
    }
    return parsed
  }
  catch {
    // Corrupt storage is discarded instead of breaking the form mount.
    try { area.removeItem(key) }
    catch { /* ignore */ }
    return null
  }
}

export function writeRecordDraft(
  key: string,
  draft: Omit<RecordDraft, 'v' | 'savedAt'>,
  storage: DraftStorage = 'session',
): void {
  const area = draftArea(storage)
  if (!area) return
  const payload: RecordDraft = { ...draft, v: DRAFT_VERSION, savedAt: new Date().toISOString() }
  try {
    area.setItem(key, JSON.stringify(payload))
  }
  catch {
    // Quota exceeded / storage disabled: never let draft persistence break the
    // edit. The in-memory model remains authoritative for this session.
  }
}

export function clearRecordDraft(key: string, storage: DraftStorage = 'session'): void {
  try {
    draftArea(storage)?.removeItem(key)
  }
  catch { /* ignore */ }
}

/** Every stored draft key beginning with `prefix`, newest first. */
export function readRecordDraftsByPrefix(
  prefix: string,
  storage: DraftStorage = 'local',
): Array<{ key: string, draft: RecordDraft }> {
  const area = draftArea(storage)
  if (!area) return []
  const keys: string[] = []
  try {
    for (let index = 0; index < area.length; index += 1) {
      const key = area.key(index)
      if (key && key.startsWith(prefix)) keys.push(key)
    }
  }
  catch {
    return []
  }
  return keys
    .map(key => ({ key, draft: readRecordDraft(key, storage) }))
    .filter((entry): entry is { key: string, draft: RecordDraft } => entry.draft !== null)
    .sort((a, b) => String(b.draft.savedAt).localeCompare(String(a.draft.savedAt)))
}

/** Drop every draft belonging to one user (logout / shared workstation hygiene). */
export function clearRecordDraftsForUser(
  user: string,
  storage?: DraftStorage,
): void {
  const scope = String(user || '').trim()
  if (!scope) return
  const areas: DraftStorage[] = storage ? [storage] : ['local', 'session']
  for (const kind of areas) {
    const area = draftArea(kind)
    if (!area) continue
    const keys: string[] = []
    try {
      for (let index = 0; index < area.length; index += 1) {
        const key = area.key(index)
        if (key && key.startsWith('lcs.draft.') && key.includes(`.${scope}.`)) keys.push(key)
      }
    }
    catch {
      continue
    }
    for (const key of keys) clearRecordDraft(key, kind)
  }
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

/**
 * A draft written against an older server copy. The caller must not apply it
 * silently: the operator decides between the draft and the newer server row.
 */
export function draftConflictsWithServer(draft: RecordDraft, recordId: string, updatedAt: unknown): boolean {
  if (draft.recordId !== recordId || !recordId) return false
  return String(updatedAt ?? '') !== draft.baseUpdatedAt
}

/**
 * JSON-safe copy of a form model for storage: drops File/Blob values, functions
 * and client-only `_` keys. Authentication credentials and password inputs are
 * removed by key so a draft can never leak them into browser storage.
 */
const NEVER_PERSIST = /^(password|confirmPassword|currentPassword|accessToken|refreshToken|token)$/i

export function sanitizeDraftModel(value: unknown): Record<string, unknown> {
  const seen = new WeakSet<object>()
  function walk(input: unknown): unknown {
    if (input === null || typeof input !== 'object') return input
    if (input instanceof Date) return input.toISOString()
    if (typeof File !== 'undefined' && input instanceof File) return undefined
    if (typeof Blob !== 'undefined' && input instanceof Blob) return undefined
    if (seen.has(input as object)) return undefined
    seen.add(input as object)
    if (Array.isArray(input)) return input.map(walk).filter(item => item !== undefined)
    const output: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(input as Record<string, unknown>)) {
      if (key.startsWith('_') || NEVER_PERSIST.test(key) || typeof item === 'function') continue
      const next = walk(item)
      if (next !== undefined) output[key] = next
    }
    return output
  }
  const result = walk(value)
  return result && typeof result === 'object' && !Array.isArray(result)
    ? result as Record<string, unknown>
    : {}
}
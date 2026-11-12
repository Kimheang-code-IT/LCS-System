import { computed, getCurrentInstance, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  clearRecordDraft,
  draftAppliesTo,
  draftConflictsWithServer,
  readRecordDraft,
  recordDraftKey,
  sanitizeDraftModel,
  writeRecordDraft,
  type DraftStorage,
  type RecordDraft,
} from './useRecordDraft'

type DraftModel = Record<string, unknown>

export type UseRecordFormDraftOptions<M extends DraftModel> = {
  /** Collection/module the form edits; part of the storage key. */
  collection: () => string
  /** Authenticated user id (single-tenant app: no workspace dimension). */
  scope: () => string
  /** Server record id, or '' for a new record. May carry a parent prefix. */
  recordId: () => string
  /** `updatedAt` of the record the form was loaded from ('' when new). */
  baseUpdatedAt?: () => string
  /** The single authoritative form model. */
  model: () => M
  /** Merge a stored model back onto the live form. */
  apply: (stored: DraftModel) => void
  /** True while the form differs from its last loaded/saved server copy. */
  isDirty: () => boolean
  /** False for read-only/posted forms; no draft is read or written then. */
  canDraft?: () => boolean
  /** Extra sanitising on top of the shared File/secret/`_` stripping. */
  sanitize?: (model: DraftModel) => DraftModel
  storage?: DraftStorage
  /** Quiet period before a local write (ms). */
  delay?: number
  /** Register the page-level browser-unload warning. One owner per document. */
  warnOnUnload?: boolean
  /** True while a request is in flight: writes are skipped, never cleared. */
  suspend?: () => boolean
}

export type DraftRestoreResult = 'applied' | 'conflict' | 'none'

/**
 * One debounced, versioned local draft for one document form.
 *
 * The form model stays authoritative; this composable only mirrors it into
 * storage and puts it back on request. A draft written against a newer server
 * copy is never applied silently: it is exposed as `conflict` so the operator
 * can Restore or Discard it. Nothing here saves, submits or posts a document.
 */
export function useRecordFormDraft<M extends DraftModel>(options: UseRecordFormDraftOptions<M>) {
  const storage = options.storage ?? 'local'
  const delay = options.delay ?? 500
  const conflict = ref<RecordDraft | null>(null)
  const restored = ref(false)

  const key = computed(() => recordDraftKey(
    options.scope(),
    options.collection(),
    options.recordId(),
  ))

  /** Key that owns the edits currently in memory (may be the pre-save `new` slot). */
  let boundKey = ''
  let boundRecordId = ''
  let timer: ReturnType<typeof setTimeout> | null = null

  function canDraft() {
    return options.canDraft ? options.canDraft() : true
  }

  function sanitize(model: M): DraftModel {
    return options.sanitize ? options.sanitize(model) : sanitizeDraftModel(model)
  }

  function clearTimer() {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  /**
   * Persist the current model now; a clean model clears its slot instead.
   * No-op until `bind()` has pointed the draft at the loaded record, so a mount
   * never writes an empty model under the incoming route's key.
   */
  function flush(targetKey?: string) {
    clearTimer()
    const target = targetKey || boundKey
    if (!target) return
    // A save is in flight: keep the slot as it was. The save clears it on
    // success and leaves it intact on failure.
    if (options.suspend?.()) return
    // An undecided conflict must survive until the operator chooses.
    if (conflict.value) return
    if (!canDraft() || !options.isDirty()) {
      clearRecordDraft(target, storage)
      return
    }
    writeRecordDraft(target, {
      recordId: boundRecordId || options.recordId(),
      collection: options.collection(),
      scope: options.scope(),
      baseUpdatedAt: String(options.baseUpdatedAt?.() ?? ''),
      model: sanitize(options.model()),
    }, storage)
  }

  /** An edit happened: write after the quiet period. */
  function schedule() {
    clearTimer()
    if (conflict.value) return
    timer = setTimeout(() => flush(), delay)
  }

  /** Point the draft at the record now loaded (after a route/selection change). */
  function bind() {
    boundKey = key.value
    boundRecordId = options.recordId()
    conflict.value = null
    restored.value = false
  }

  /** Apply the stored draft for the bound record, if it is still compatible. */
  function restore(): DraftRestoreResult {
    conflict.value = null
    const target = boundKey || key.value
    if (!target || !canDraft()) return 'none'
    // Quotations used sessionStorage before the shared draft layer; read that
    // copy once so an open tab is not lost by the upgrade.
    let stored = readRecordDraft(target, storage)
    if (!stored && storage === 'local') stored = readRecordDraft(target, 'session')
    if (!stored) return 'none'
    // A draft copied under another collection's key is not this form's state.
    if (stored.collection && stored.collection !== options.collection()) {
      clearRecordDraft(target, storage)
      return 'none'
    }
    const recordId = options.recordId()
    const base = String(options.baseUpdatedAt?.() ?? '')
    if (draftAppliesTo(stored, recordId, base)) {
      options.apply(stored.model)
      restored.value = true
      return 'applied'
    }
    if (draftConflictsWithServer(stored, recordId, base)) {
      conflict.value = stored
      return 'conflict'
    }
    // Same slot, different record: the stored copy cannot belong here.
    clearRecordDraft(target, storage)
    return 'none'
  }

  function restoreConflict() {
    const stored = conflict.value
    if (!stored) return
    options.apply(stored.model)
    conflict.value = null
    restored.value = true
  }

  function discardConflict() {
    const stored = conflict.value
    if (stored) clearRecordDraft(boundKey || key.value, storage)
    conflict.value = null
    restored.value = false
  }

  /** A save committed: clear the record slot and any pre-save `new` slot. */
  function clear() {
    clearTimer()
    clearRecordDraft(key.value, storage)
    if (boundKey && boundKey !== key.value) clearRecordDraft(boundKey, storage)
    conflict.value = null
    restored.value = false
    boundKey = key.value
    boundRecordId = options.recordId()
  }

  if (getCurrentInstance()) {
    onBeforeUnmount(() => flush())
  }

  if (options.warnOnUnload && getCurrentInstance()) {
    function beforeUnload(event: BeforeUnloadEvent) {
      if (!options.isDirty()) return
      event.preventDefault()
      event.returnValue = ''
    }
    onMounted(() => window.addEventListener('beforeunload', beforeUnload))
    onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
  }

  return {
    key,
    conflict,
    restored,
    bind,
    restore,
    schedule,
    flush,
    clear,
    restoreConflict,
    discardConflict,
  }
}

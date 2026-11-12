import { computed, ref } from 'vue'

/**
 * Debounced, single-flight autosave state machine.
 *
 * Every edit calls `schedule()`; the save runs once the user stops typing
 * (`delay`, default 800 ms). Only one request is ever in flight: edits made
 * while it runs set `queued`, and a second save starts as soon as the first
 * finishes, so a slow response can never land after (and overwrite) a newer
 * one. `flush()` runs a pending save immediately (tab switch / manual save),
 * `retry()` reruns a failed one, and `markDirty()` is how the caller says
 * "there is still something the server does not have" after a partial save.
 *
 * The composable owns no network code: `save` returns true when the call
 * succeeded. The state shown to the user is derived from what actually
 * happened — never from optimism.
 */
export type AutosaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'error'

export interface UseAutosaveOptions {
  /** Quiet period after the last edit before saving (ms). */
  delay?: number
}

export function useAutosave(
  save: () => Promise<boolean>,
  options: UseAutosaveOptions = {},
) {
  const delay = options.delay ?? 800
  const state = ref<AutosaveState>('idle')
  /** Last failure message, kept until a retry succeeds. */
  const error = ref('')
  const inFlight = ref(false)

  let timer: ReturnType<typeof setTimeout> | null = null
  let queued = false
  let running: Promise<boolean> | null = null

  function clearTimer() {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  /** An edit happened: mark unsaved and (re)start the quiet period. */
  function schedule() {
    state.value = 'dirty'
    clearTimer()
    timer = setTimeout(() => { void flush() }, delay)
  }

  /** The caller found more local work after a successful partial save. */
  function markDirty() {
    if (state.value !== 'saving' && state.value !== 'error') state.value = 'dirty'
  }

  async function runLoop(): Promise<boolean> {
    do {
      queued = false
      state.value = 'saving'
      error.value = ''
      const ok = await save()
      if (!ok) {
        state.value = 'error'
        return false
      }
    } while (queued)
    state.value = 'saved'
    return true
  }

  /**
   * Run the pending save now. A call while a save is running queues exactly
   * one follow-up run and resolves with the same result, so callers awaiting
   * a flush never see a false "saved".
   */
  function flush(): Promise<boolean> {
    clearTimer()
    if (running) {
      queued = true
      return running
    }
    inFlight.value = true
    running = runLoop()
      .catch((failure) => {
        // The caller's save usually renders its own message; keep a fallback so
        // the header can always explain the failed state.
        error.value = failure instanceof Error ? failure.message : ''
        state.value = 'error'
        return false
      })
      .finally(() => {
        running = null
        inFlight.value = false
      })
    return running
  }

  /** Rerun after a failure without waiting for another edit. */
  function retry(): Promise<boolean> {
    return flush()
  }

  /** Forget the timer (component teardown); an in-flight call finishes. */
  function dispose() {
    clearTimer()
  }

  const status = computed(() => ({
    state: state.value,
    error: error.value,
    pending: timer !== null || inFlight.value,
  }))

  return { state, error, status, schedule, markDirty, flush, retry, dispose }
}

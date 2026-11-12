import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAutosave } from '../app/composables/common/useAutosave'

describe('useAutosave', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('waits for the quiet period, then saves and reports Saved', async () => {
    const save = vi.fn().mockResolvedValue(true)
    const autosave = useAutosave(save, { delay: 800 })

    autosave.schedule()
    expect(autosave.state.value).toBe('dirty')
    await vi.advanceTimersByTimeAsync(799)
    expect(save).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(save).toHaveBeenCalledTimes(1)
    expect(autosave.state.value).toBe('saved')
  })

  it('coalesces rapid edits into one request', async () => {
    const save = vi.fn().mockResolvedValue(true)
    const autosave = useAutosave(save, { delay: 800 })

    autosave.schedule()
    await vi.advanceTimersByTimeAsync(400)
    autosave.schedule()
    await vi.advanceTimersByTimeAsync(400)
    autosave.schedule()
    await vi.advanceTimersByTimeAsync(800)

    expect(save).toHaveBeenCalledTimes(1)
    expect(autosave.state.value).toBe('saved')
  })

  it('never runs two saves at once and runs one queued follow-up', async () => {
    const pending: Array<(ok: boolean) => void> = []
    const save = vi.fn(() => new Promise<boolean>((resolve) => { pending.push(resolve) }))
    const autosave = useAutosave(save, { delay: 800 })

    const first = autosave.flush()
    expect(save).toHaveBeenCalledTimes(1)
    // An edit during the in-flight request queues exactly one follow-up once
    // its own quiet period elapses.
    autosave.schedule()
    autosave.schedule()
    await vi.advanceTimersByTimeAsync(800)
    pending[0]!(true)
    await vi.advanceTimersByTimeAsync(0)
    expect(save).toHaveBeenCalledTimes(2)
    pending[1]!(true)
    expect(await first).toBe(true)

    // The timer scheduled during the flight is harmless: the caller's save
    // finds nothing pending, but it must never start concurrently.
    autosave.dispose()
  })

  it('keeps the error state and retries without losing the caller data', async () => {
    const save = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true)
    const autosave = useAutosave(save, { delay: 800 })

    expect(await autosave.flush()).toBe(false)
    expect(autosave.state.value).toBe('error')

    expect(await autosave.retry()).toBe(true)
    expect(autosave.state.value).toBe('saved')
    expect(save).toHaveBeenCalledTimes(2)
  })

  it('turns a thrown failure into the error state', async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(true)
    const autosave = useAutosave(save)

    expect(await autosave.flush()).toBe(false)
    expect(autosave.state.value).toBe('error')
    expect(autosave.error.value).toBe('offline')
  })

  it('stays dirty when the caller reports remaining local work', async () => {
    const save = vi.fn().mockResolvedValue(true)
    const autosave = useAutosave(save)

    expect(await autosave.flush()).toBe(true)
    autosave.markDirty()
    expect(autosave.state.value).toBe('dirty')
  })

  it('flush cancels the scheduled timer and saves immediately', async () => {
    const save = vi.fn().mockResolvedValue(true)
    const autosave = useAutosave(save, { delay: 800 })

    autosave.schedule()
    expect(await autosave.flush()).toBe(true)
    await vi.advanceTimersByTimeAsync(800)
    expect(save).toHaveBeenCalledTimes(1)
  })
})

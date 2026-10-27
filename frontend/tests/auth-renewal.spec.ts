import { afterEach, describe, expect, it, vi } from 'vitest'
import { canReplayBody, createRenewalCoordinator } from '../app/utils/auth/renewal'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function harness(request = vi.fn(async () => ({ expires_at: Date.now() / 1000 + 900 }))) {
  const apply = vi.fn()
  const expired = vi.fn()
  const unavailable = vi.fn()
  return { request, apply, expired, unavailable, coordinator: createRenewalCoordinator({ request, apply, expired, unavailable }) }
}

afterEach(() => { vi.useRealTimers() })

describe('session renewal', () => {
  it('shares one refresh among five callers and keeps the open draft unchanged', async () => {
    vi.useFakeTimers()
    const pending = deferred<{ expires_at: number }>()
    const h = harness(vi.fn(() => pending.promise))
    const draft = { serviceOrder: { customer: 'Unsaved customer', note: 'Keep this' } }
    const before = structuredClone(draft)
    const callers = Array.from({ length: 5 }, () => h.coordinator.refresh())
    expect(h.request).toHaveBeenCalledTimes(1)
    pending.resolve({ expires_at: Date.now() / 1000 + 900 })
    expect(await Promise.all(callers)).toEqual(Array(5).fill('renewed'))
    expect(h.apply).toHaveBeenCalledTimes(1)
    expect(h.expired).not.toHaveBeenCalled()
    expect(draft).toEqual(before)
    h.coordinator.invalidate()
  })

  it('renews 90 seconds before the server expiration timestamp', async () => {
    vi.useFakeTimers()
    const h = harness()
    h.coordinator.schedule(Date.now() / 1000 + 900)
    await vi.advanceTimersByTimeAsync(809000)
    expect(h.request).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1000)
    expect(h.request).toHaveBeenCalledTimes(1)
    h.coordinator.invalidate()
  })

  it('invalid sessions expire once and stop the timer', async () => {
    vi.useFakeTimers()
    const h = harness(vi.fn().mockRejectedValue({ statusCode: 401 }))
    expect(await h.coordinator.refresh()).toBe('expired')
    expect(h.expired).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(3600000)
    expect(h.request).toHaveBeenCalledTimes(1)
  })

  it('a one-minute token refreshes near expiry without a one-second loop', async () => {
    vi.useFakeTimers()
    const h = harness(vi.fn(async () => ({ expires_at: Date.now() / 1000 + 60 })))
    await h.coordinator.refresh()
    await vi.advanceTimersByTimeAsync(53000)
    expect(h.request).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1000)
    expect(h.request).toHaveBeenCalledTimes(2)
    h.coordinator.invalidate()
  })

  it('network failures retain state and retry only twice', async () => {
    vi.useFakeTimers()
    const h = harness(vi.fn().mockRejectedValue(new TypeError('offline')))
    expect(await h.coordinator.refresh()).toBe('unavailable')
    await vi.advanceTimersByTimeAsync(5000)
    await vi.advanceTimersByTimeAsync(30000)
    await vi.advanceTimersByTimeAsync(3600000)
    expect(h.request).toHaveBeenCalledTimes(3)
    expect(h.expired).not.toHaveBeenCalled()
    expect(h.apply).not.toHaveBeenCalled()
    h.coordinator.invalidate()
  })

  it('CSRF refusal is not retried or treated as revocation', async () => {
    vi.useFakeTimers()
    const h = harness(vi.fn().mockRejectedValue({ statusCode: 403 }))
    expect(await h.coordinator.refresh()).toBe('unavailable')
    await vi.advanceTimersByTimeAsync(3600000)
    expect(h.request).toHaveBeenCalledTimes(1)
    expect(h.expired).not.toHaveBeenCalled()
  })

  it('does not proactively rotate an unattended session', async () => {
    vi.useFakeTimers()
    const request = vi.fn(async () => ({ expires_at: Date.now() / 1000 + 900 }))
    const coordinator = createRenewalCoordinator({ request, apply: vi.fn(), expired: vi.fn(), unavailable: vi.fn(), isActive: () => false })
    coordinator.schedule(Date.now() / 1000 + 900)
    await vi.advanceTimersByTimeAsync(3600000)
    expect(request).not.toHaveBeenCalled()
    // A user-driven request or wake can still explicitly restore the session.
    expect(await coordinator.refresh()).toBe('renewed')
    coordinator.invalidate()
  })

  it('a delayed refresh cannot restore authentication after logout', async () => {
    const pending = deferred<{ expires_at: number }>()
    const h = harness(vi.fn(() => pending.promise))
    const result = h.coordinator.refresh()
    h.coordinator.invalidate()
    pending.resolve({ expires_at: Date.now() / 1000 + 900 })
    expect(await result).toBe('cancelled')
    expect(h.apply).not.toHaveBeenCalled()
    expect(await h.coordinator.refresh()).toBe('cancelled')
  })

  it('does not replay upload, binary or streamed bodies', () => {
    expect(canReplayBody({ customer: 1 })).toBe(true)
    expect(canReplayBody(JSON.stringify({ note: 'Draft' }))).toBe(true)
    expect(canReplayBody(new FormData())).toBe(false)
    expect(canReplayBody(new Blob(['upload']))).toBe(false)
    expect(canReplayBody(new ReadableStream())).toBe(false)
    expect(canReplayBody(new Uint8Array(3))).toBe(false)
  })
})

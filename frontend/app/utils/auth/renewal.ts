export type RenewalResult = 'renewed' | 'expired' | 'unavailable' | 'cancelled'

export type SessionResponse = {
  access_token?: string | null
  expires_at: number
  user?: import('~/types/api').AuthUser
}

export function renewalLeadMillis(remaining: number) {
  return Math.min(90_000, Math.max(1000, remaining / 10))
}

export function authErrorStatus(error: unknown): number {
  const e = error as { statusCode?: number, status?: number, response?: { status?: number } }
  return e?.response?.status || e?.statusCode || e?.status || 0
}

export function authErrorCode(error: unknown): string {
  return (error as { data?: { code?: string } })?.data?.code || ''
}

/** A rejected request is replayable only when its body can be reconstructed. */
export function canReplayBody(body: unknown): boolean {
  return body == null || typeof body === 'string' || typeof body === 'number'
    || typeof body === 'boolean' || Array.isArray(body)
    || (typeof body === 'object' && Object.getPrototypeOf(body) === Object.prototype)
}

/** One generation-guarded renewal for all consumers, with bounded network retry. */
export function createRenewalCoordinator(options: {
  request: () => Promise<SessionResponse>
  apply: (response: SessionResponse) => void
  expired: () => void
  unavailable: () => void
  now?: () => number
  isActive?: () => boolean
}) {
  let generation = 0
  let pending: Promise<RenewalResult> | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let retries = 0
  let stopped = false
  const now = options.now || Date.now
  const stopTimer = () => { clearTimeout(timer); timer = undefined }

  function schedule(expiresAt: number) {
    stopTimer()
    const remaining = expiresAt * 1000 - now()
    const lead = renewalLeadMillis(remaining)
    if (!stopped) timer = setTimeout(() => {
      if (options.isActive?.() !== false) void refresh()
    }, Math.max(1000, remaining - lead))
  }

  function refresh(): Promise<RenewalResult> {
    if (stopped) return Promise.resolve('cancelled')
    if (pending) return pending
    const version = generation
    const operation = (async (): Promise<RenewalResult> => {
      try {
        const response = await options.request()
        if (generation !== version) return 'cancelled'
        retries = 0
        options.apply(response)
        schedule(response.expires_at)
        return 'renewed'
      }
      catch (error) {
        if (generation !== version) return 'cancelled'
        if (authErrorStatus(error) === 401) {
          stopTimer()
          options.expired()
          return 'expired'
        }
        options.unavailable()
        // CSRF/permission failures are never retried as authentication expiry.
        if ((authErrorStatus(error) === 0 || authErrorStatus(error) >= 500) && retries < 2) {
          stopTimer()
          timer = setTimeout(() => { void refresh() }, [5000, 30000][retries++]!)
        }
        return 'unavailable'
      }
    })()
    pending = operation
    void operation.finally(() => { if (pending === operation) pending = null })
    return operation
  }

  function invalidate() {
    generation++
    stopped = true
    stopTimer()
    // Keep an in-flight request attached until it settles; logout can wait for
    // its cookie response before revoking the server session.
  }

  function resume() { generation++; stopped = false; retries = 0 }

  return { refresh, schedule, invalidate, resume, settle: () => pending || Promise.resolve('cancelled') }
}

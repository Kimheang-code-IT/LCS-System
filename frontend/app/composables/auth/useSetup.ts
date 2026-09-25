import { ApiV1Endpoints } from '~/utils/constants/api-v1-endpoints'

export type SetupInput = {
  email: string
  password: string
  name?: string
  username?: string
}

function payloadOf(response: unknown): Record<string, unknown> {
  if (response && typeof response === 'object' && 'data' in response) {
    const data = (response as { data?: unknown }).data
    if (data && typeof data === 'object') return data as Record<string, unknown>
  }
  return (response && typeof response === 'object' ? response : {}) as Record<string, unknown>
}

/**
 * First-run provisioning. `/api/v1/setup/status` is public; `initialize` is
 * accepted only while the database has no user account.
 *
 * Uses raw `$fetch` (not `useApi`) on purpose: the global route middleware calls
 * `refresh()` outside a component `setup()`, where `useApi()`'s `useI18n()`
 * would throw `MUST_BE_CALL_SETUP_TOP`.
 */
export function useSetup() {
  const config = useRuntimeConfig()
  const requiresSetup = useState<boolean | null>('setup-required', () => null)

  function baseURL(): string {
    const configured = String(config.public.apiBase || '')
    return configured || (import.meta.client ? window.location.origin : '')
  }

  function timeout(): number {
    return Number(config.public.apiTimeoutMs) || 30000
  }

  async function refresh(force = false): Promise<boolean> {
    if (!force && requiresSetup.value !== null) return requiresSetup.value
    try {
      const response = await $fetch<{ data?: { requiresSetup?: boolean } }>(ApiV1Endpoints.SETUP_STATUS, {
        baseURL: baseURL(),
        timeout: timeout(),
      })
      requiresSetup.value = Boolean(payloadOf(response).requiresSetup)
    }
    catch {
      requiresSetup.value = false
    }
    return requiresSetup.value
  }

  async function initialize(input: SetupInput): Promise<Record<string, unknown>> {
    const response = await $fetch<{ data?: Record<string, unknown> }>(ApiV1Endpoints.SETUP_INITIALIZE, {
      baseURL: baseURL(),
      method: 'POST',
      body: input,
      timeout: timeout(),
    })
    requiresSetup.value = false
    return payloadOf(response)
  }

  return { requiresSetup, refresh, initialize }
}

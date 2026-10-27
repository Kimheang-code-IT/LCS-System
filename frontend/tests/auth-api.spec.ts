import { computed } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useApi } from '../app/composables/useApi'

const auth = vi.hoisted(() => ({
  accessToken: 'old', sessionExpired: false, identityUnverified: false,
  activityHeaders: vi.fn(() => ({})), waitForIdentity: vi.fn(),
  renewAccess: vi.fn(), expire: vi.fn(), blockChangedAccount: vi.fn(),
}))
vi.mock('~/stores/auth', () => ({ useAuthStore: () => auth }))

type Options = { onResponseError: (context: { response: { status: number, _data?: { message?: string } } }) => void }
const failure = (status: number, code: string) => ({ name: 'FetchError', statusCode: status, data: { code } })

beforeEach(() => {
  vi.clearAllMocks()
  auth.accessToken = 'old'
  auth.sessionExpired = false
  auth.identityUnverified = false
  auth.renewAccess.mockResolvedValue('renewed')
  vi.stubGlobal('computed', computed)
  vi.stubGlobal('useToast', () => ({ add: vi.fn() }))
  vi.stubGlobal('useNuxtApp', () => ({ $i18n: { t: (key: string) => key } }))
  vi.stubGlobal('useRuntimeConfig', () => ({ public: { apiBase: 'http://test.local', csrfCookieName: 'XSRF-TOKEN', csrfHeaderName: 'X-CSRF-Token' } }))
  vi.stubGlobal('sameOriginApiUrl', () => true)
})
afterEach(() => vi.unstubAllGlobals())

describe('central authentication retry', () => {
  it.each(['/api/v1/auth/forgot-password', '/api/v1/auth/forgot-password/verify', '/api/v1/auth/forgot-password/reset'])('allows signed-out recovery through %s without identity renewal', async (path) => {
    const request = vi.fn().mockResolvedValue({ data: { sent: true } })
    vi.stubGlobal('$fetch', request)
    auth.sessionExpired = true
    auth.identityUnverified = true
    await expect(useApi().post(path, { token: 'recovery-token' })).resolves.toMatchObject({ data: { sent: true } })
    expect(request).toHaveBeenCalledTimes(1)
    expect(auth.renewAccess).not.toHaveBeenCalled()
  })
  it('blocks writes while the shared-cookie identity could not be verified', async () => {
    const request = vi.fn()
    vi.stubGlobal('$fetch', request)
    auth.identityUnverified = true
    await expect(useApi().post('/api/v1/service-orders', { note: 'draft' })).rejects.toMatchObject({ statusCode: 503 })
    expect(request).not.toHaveBeenCalled()
  })
  it('returns the original request result after one silent renewal and retry', async () => {
    const request = vi.fn().mockImplementationOnce(async (_url: string, options: Options) => {
      options.onResponseError({ response: { status: 401 } })
      throw failure(401, 'ACCESS_TOKEN_EXPIRED')
    }).mockResolvedValue({ data: { saved: true } })
    vi.stubGlobal('$fetch', request)
    expect(await useApi().post('/api/v1/service-orders', { note: 'unsaved' })).toEqual({ data: { saved: true } })
    expect(auth.renewAccess).toHaveBeenCalledTimes(1)
    expect(request).toHaveBeenCalledTimes(2)
    expect(auth.expire).not.toHaveBeenCalled()
  })

  it.each([[403, 'ACCESS_DENIED'], [401, 'AUTH_REQUIRED'], [422, 'VALIDATION_ERROR']])('does not renew for %i %s', async (status, code) => {
    vi.stubGlobal('$fetch', vi.fn(async (_url: string, options: Options) => {
      options.onResponseError({ response: { status } })
      throw failure(status, code)
    }))
    await expect(useApi().get('/api/v1/feeTypes')).rejects.toMatchObject({ statusCode: status })
    expect(auth.renewAccess).not.toHaveBeenCalled()
  })

  it('never loops if the retried request is still expired', async () => {
    const request = vi.fn(async (_url: string, options: Options) => {
      options.onResponseError({ response: { status: 401 } })
      throw failure(401, 'ACCESS_TOKEN_EXPIRED')
    })
    vi.stubGlobal('$fetch', request)
    await expect(useApi().get('/api/v1/feeTypes')).rejects.toMatchObject({ statusCode: 401 })
    expect(request).toHaveBeenCalledTimes(2)
    expect(auth.renewAccess).toHaveBeenCalledTimes(1)
  })

  it('does not replay an upload or clear the draft on temporary renewal failure', async () => {
    const request = vi.fn(async (_url: string, options: Options) => {
      options.onResponseError({ response: { status: 401 } })
      throw failure(401, 'ACCESS_TOKEN_EXPIRED')
    })
    vi.stubGlobal('$fetch', request)
    auth.renewAccess.mockResolvedValue('unavailable')
    await expect(useApi().post('/api/v1/attachments', new FormData())).rejects.toMatchObject({ statusCode: 401 })
    expect(request).toHaveBeenCalledTimes(1)
    expect(auth.expire).not.toHaveBeenCalled()
  })

  it('does not run refresh recursively for a rejected refresh endpoint', async () => {
    vi.stubGlobal('$fetch', vi.fn(async (_url: string, options: Options) => {
      options.onResponseError({ response: { status: 401 } })
      throw failure(401, 'SESSION_EXPIRED')
    }))
    await expect(useApi().post('/api/v1/auth/refresh', {})).rejects.toMatchObject({ statusCode: 401 })
    expect(auth.renewAccess).not.toHaveBeenCalled()
    expect(auth.expire).toHaveBeenCalledTimes(1)
  })
})

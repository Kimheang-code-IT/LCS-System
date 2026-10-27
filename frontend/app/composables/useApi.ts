import { useAuthStore } from '~/stores/auth'
import { ref } from 'vue'
import type { TableQueryParams } from '~/types/api'
import { compactQuery, stableQueryString } from '~/utils/api/query'
import { csrfRequestHeaders } from '~/utils/security/csrf'
import { authErrorCode, canReplayBody } from '~/utils/auth/renewal'
import { isNetworkFailure } from '~/utils/api/errors'

type ApiRequestOptions = {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
    headers?: Record<string, string>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    body?: Record<string, any> | BodyInit | null
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    query?: Record<string, any> | TableQueryParams
    suppressErrorToast?: boolean
    suppressAccessAlert?: boolean
    /** Statuses the caller handles itself; they never raise a toast. */
    expectedErrorStatuses?: number[]
    requestKey?: string
    cancelPrevious?: boolean
}

type ApiErrorPayload = {
    message?: string
}

type ApiFetchError = Error & {
    name: string
    status?: number
    statusCode?: number
    data?: ApiErrorPayload
    // ofetch wraps a cancelled fetch in a FetchError and keeps the original
    // AbortError (or TimeoutError) on the wrapped error's `cause`.
    cause?: { name?: string }
}

// Shared across every useApi() consumer so a later request can cancel an older
// request even when composables created separate useApi instances.
const requestControllers = new Map<string, AbortController>()

/**
 * Standard API Fetching Composable
 * ───────────────────────────────────────
 * Use this for all backend requests. It automatically:
 * 1. Attaches the auth token (if user is logged in)
 * 2. Handles global error notifications
 * 3. Supports standard REST methods
 */
export function useApi() {
    const toast = useToast()
    // Repositories are initialized during the client startup plugin as well as
    // from components. The Nuxt-provided global composer is valid in both
    // contexts; `useI18n()` requires an active component setup instance.
    const { $i18n } = useNuxtApp()
    const t = $i18n.t
    const config = useRuntimeConfig()
    const authStore = useAuthStore()
    const activeRequests = ref(0)
    const pending = computed(() => activeRequests.value > 0)
    const error = ref<string | null>(null)

    const configuredBase = String(config.public.apiBase || '')
    const baseURL = configuredBase || (import.meta.client ? window.location.origin : '')

    function isAuthEndpoint(url: string) {
        const path = new URL(url, baseURL || 'http://localhost').pathname
        return new Set([
            '/api/v1/auth/login', '/api/v1/auth/refresh', '/api/v1/auth/logout',
            '/api/v1/auth/forgot-password', '/api/v1/auth/forgot-password/verify',
            '/api/v1/auth/forgot-password/resend', '/api/v1/auth/forgot-password/reset',
        ]).has(path)
    }

    /**
     * Responses the owning form renders itself: the backend attaches
     * `field_errors`, and the form maps each entry onto its input plus the
     * error summary. Toasting here would duplicate the message and would also
     * raise a notification for something the user can act on in place.
     */
    function isInlineValidationStatus(status: number) {
        return status === 400 || status === 409 || status === 422
    }

    function getRequestKey(url: string, options: ApiRequestOptions): string {
        const queryKey = stableQueryString(compactQuery(options.query))
        return options.requestKey || `${options.method || 'GET'}:${url}${queryKey ? `?${queryKey}` : ''}`
    }

    function cancelRequest(key: string) {
        const controller = requestControllers.get(key)
        if (controller) {
            controller.abort()
            requestControllers.delete(key)
        }
    }

    const fetch = async <T>(url: string, options: ApiRequestOptions = {}, isRetry = false): Promise<T> => {
        if (!sameOriginApiUrl(url, String(baseURL))) {
            throw new Error('API requests must use the configured API origin')
        }
        if (!isAuthEndpoint(url)) await authStore.waitForIdentity()
        if (authStore.identityUnverified && !isAuthEndpoint(url)) {
            throw { statusCode: 503, data: { code: 'SESSION_IDENTITY_UNAVAILABLE', message: t('session.connection') } }
        }
        if (authStore.sessionExpired && !isAuthEndpoint(url)) {
            throw { statusCode: 401, data: { code: 'SESSION_EXPIRED', message: t('session.expired') } }
        }
        const requestKey = getRequestKey(url, options)
        const shouldCancelPrevious = options.cancelPrevious !== false

        if (shouldCancelPrevious) {
            cancelRequest(requestKey)
        }

        const controller = new AbortController()
        requestControllers.set(requestKey, controller)
        let handledAccessError = false
        let sawUnauthorized = false

        try {
            activeRequests.value += 1
            error.value = null
            const method = options.method || 'GET'
            return await $fetch<T>(url, {
                baseURL,
                ...options,
                method,
                query: compactQuery(options.query),
                signal: controller.signal,
                timeout: Number(config.public.apiTimeoutMs) || 30000,
                credentials: 'include',
                retry: 0,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    ...authStore.activityHeaders(),
                    ...(authStore.user?.id ? { 'X-Expected-User-Id': String(authStore.user.id) } : {}),
                    ...(authStore.accessToken ? { Authorization: `Bearer ${authStore.accessToken}` } : {}),
                    ...csrfRequestHeaders(
                        method,
                        String(config.public.csrfCookieName),
                        String(config.public.csrfHeaderName),
                    ),
                    ...options.headers,
                },
                onResponseError({ response }) {
                    if (response.status === 401) {
                        sawUnauthorized = true
                        return
                    }

                    if (response.status === 403) {
                        handledAccessError = true
                        return
                    }

                    const expected = options.expectedErrorStatuses?.includes(response.status)
                    if (!options.suppressErrorToast && !expected && !isInlineValidationStatus(response.status)) {
                        toast.add({
                            title: t('api.errorTitle', { status: response.status }),
                            description: response._data?.message || t('api.somethingWentWrong'),
                            color: 'error'
                        })
                    }
                }
            })
        }
        catch (err: unknown) {
            // Network, parsing, or cancellation errors
            const fetchError = err as ApiFetchError
            // A request cancelled by `cancelPrevious` / `cancelRequest` surfaces as
            // an ofetch FetchError whose cause is an AbortError. Treat it as silent
            // instead of reporting a bogus "could not reach the server" failure.
            if (fetchError.name === 'AbortError' || fetchError.cause?.name === 'AbortError') {
                return Promise.reject(err)
            }

            // Try a single token refresh before forcing the user to sign in again.
            if (sawUnauthorized && authErrorCode(err) === 'ACCESS_TOKEN_EXPIRED' && !isRetry && !isAuthEndpoint(url)) {
                const refreshed = await authStore.renewAccess()
                if (refreshed === 'renewed' && canReplayBody(options.body)) {
                    return await fetch<T>(url, options, true)
                }
            }

            if (authErrorCode(err) === 'SESSION_ACCOUNT_CHANGED') authStore.blockChangedAccount()

            if (sawUnauthorized) {
                if (['SESSION_EXPIRED', 'SESSION_REVOKED', 'SESSION_INVALID'].includes(authErrorCode(err))) authStore.expire()
                throw err
            }

            error.value = fetchError?.message || t('api.requestFailed')

            // ofetch names every HTTP failure a `FetchError` too, so only a
            // missing status (no response at all) is a real connection failure.
            // A 404 is a server answer the UI already reports; calling it
            // "could not reach the server" is misleading and duplicates a toast.
            if (isNetworkFailure(fetchError) && !handledAccessError && !options.suppressErrorToast) {
                toast.add({
                    title: t('api.connectionErrorTitle'),
                    description: t('api.connectionErrorDescription'),
                    color: 'error'
                })
            }

            throw err
        }
        finally {
            if (requestControllers.get(requestKey) === controller) {
                requestControllers.delete(requestKey)
            }
            activeRequests.value = Math.max(0, activeRequests.value - 1)
        }
    }

    return {
        pending,
        error,
        cancelRequest,
        get: <T>(url: string, opt?: ApiRequestOptions) => fetch<T>(url, { method: 'GET', ...opt }),
        post: <T>(url: string, body: ApiRequestOptions['body'], opt?: ApiRequestOptions) => fetch<T>(url, { method: 'POST', body, ...opt }),
        put: <T>(url: string, body: ApiRequestOptions['body'], opt?: ApiRequestOptions) => fetch<T>(url, { method: 'PUT', body, ...opt }),
        patch: <T>(url: string, body: ApiRequestOptions['body'], opt?: ApiRequestOptions) => fetch<T>(url, { method: 'PATCH', body, ...opt }),
        delete: <T>(url: string, opt?: ApiRequestOptions) => fetch<T>(url, { method: 'DELETE', ...opt }),
        request: fetch,
    }
}

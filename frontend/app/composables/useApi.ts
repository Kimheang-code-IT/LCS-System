import { useAuthStore } from '~/stores/auth'
import { ref } from 'vue'
import type { TableQueryParams } from '~/types/api'
import { compactQuery, stableQueryString } from '~/utils/api/query'
import { useAccessAlert } from '~/composables/common/useAccessAlert'
import { csrfRequestHeaders } from '~/utils/security/csrf'

type ApiRequestOptions = {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
    headers?: Record<string, string>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    body?: Record<string, any> | BodyInit | null
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    query?: Record<string, any> | TableQueryParams
    suppressErrorToast?: boolean
    suppressAccessAlert?: boolean
    requestKey?: string
    cancelPrevious?: boolean
}

type ApiErrorPayload = {
    message?: string
}

type ApiFetchError = Error & {
    name: string
    data?: ApiErrorPayload
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
    const { showPermissionDenied, showSessionExpired } = useAccessAlert()
    const { t } = useI18n()
    const route = useRoute()
    const config = useRuntimeConfig()
    const activeRequests = ref(0)
    const pending = computed(() => activeRequests.value > 0)
    const error = ref<string | null>(null)

    const configuredBase = String(config.public.apiBase || '')
    const baseURL = configuredBase || (import.meta.client ? window.location.origin : '')

    function getRequestKey(url: string, options: ApiRequestOptions): string {
        const queryKey = stableQueryString(compactQuery(options.query) as Record<string, unknown> | undefined)
        return options.requestKey || `${options.method || 'GET'}:${url}${queryKey ? `?${queryKey}` : ''}`
    }

    function cancelRequest(key: string) {
        const controller = requestControllers.get(key)
        if (controller) {
            controller.abort()
            requestControllers.delete(key)
        }
    }

    const fetch = async <T>(url: string, options: ApiRequestOptions = {}) => {
        if (!sameOriginApiUrl(url, String(baseURL))) {
            throw new Error('API requests must use the configured API origin')
        }
        // Retrieve real global app state via Pinia
        const authStore = useAuthStore()
        const requestKey = getRequestKey(url, options)
        const shouldCancelPrevious = options.cancelPrevious !== false

        if (shouldCancelPrevious) {
            cancelRequest(requestKey)
        }

        const controller = new AbortController()
        requestControllers.set(requestKey, controller)
        let handledAccessError = false

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
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
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
                        handledAccessError = true
                        authStore.clearSession()
                        if (!options.suppressAccessAlert) {
                            showSessionExpired()
                            void navigateTo('/auth/login')
                        }
                        return
                    }

                    if (response.status === 403) {
                        handledAccessError = true
                        if (!options.suppressAccessAlert) {
                            showPermissionDenied({
                                requestedPath: route.fullPath,
                                description: response._data?.message,
                            })
                        }
                        return
                    }

                    if (!options.suppressErrorToast) {
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
            // Network or parsing errors
            const fetchError = err as ApiFetchError
            if (fetchError.name === 'AbortError') {
                return Promise.reject(err)
            }

            error.value = fetchError?.message || t('api.requestFailed')

            if (fetchError.name === 'FetchError' && !handledAccessError && !options.suppressErrorToast) {
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
